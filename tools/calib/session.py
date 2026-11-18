"""校准会话流程（T-0026）：BEGIN/SET/MEAS/COMMIT/READ/ABORT + 安全中止。

设备回执 ``OK`` / ``ERR <code> <msg>``；V 命令单位 mV，I 命令单位 mA（表按
§3.4.1 以 0.1mA 编码，CRC 回读时 ×10）。BEGIN 由设备把 V 限流降到 0.5A、
I 限流到目标点+1A；超时/ERR/非法输入立即 ABORT，未 COMMIT 不写 EEPROM。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum

from .serial_link import LinkError

class CalStatus(IntEnum):
    """CAL_STATUS（需求 §3.3.1，寄存器 0x2C）。"""

    IDLE, BUSY, OK, CRC, VERSION, POINT, UNCALIBRATED, CONDITION = range(8)

IDLE, BUSY, OK, CRC, VERSION, POINT, UNCALIBRATED, CONDITION = tuple(CalStatus)
STATUS_TEXT = {0: "idle 空闲", 1: "busy 校准中", 2: "ok 成功", 3: "CRC 错",
               4: "版本错", 5: "点错", 6: "未校准", 7: "条件不满足"}
CHANNELS = {  # 命令单位与表编码（scale）分离：V 1:1，I mA→0.1mA
    "V": {"name": "电压", "unit": "mV", "max": 48000, "scale": 1,
          "points": (500, 3300, 5000, 12000, 24000, 48000)},
    "I": {"name": "电流", "unit": "mA", "max": 5000, "scale": 10,
          "points": (1000, 2500, 5000)},
}


class CalError(Exception):
    """code 取 CAL_STATUS；raw 非空表示设备 ERR 的原文。"""

    def __init__(self, code: CalStatus, message: str, raw: str = ""):
        self.code, self.message, self.raw = CalStatus(code), message, raw
        super().__init__(f"ERR {int(self.code)} {message}")


class CalibrationAborted(Exception):
    """已安全中止；status 为触发时的 CAL_STATUS（通信故障为 None）。"""

    def __init__(self, message: str, status: CalStatus | None = None,
                 abort_sent: bool = False, abort_error: str = ""):
        self.status, self.abort_sent, self.abort_error = status, abort_sent, abort_error
        super().__init__(message)

@dataclass(frozen=True)
class ReadResult:
    state: int
    active: int
    version: int | None
    crc: int | None
    expected: int | None
    verified: bool
    note: str = ""

    def summary(self) -> str:
        crc = f"{self.crc:04X}" if self.crc is not None else "未回传"
        exp = f"{self.expected:04X}" if self.expected is not None else "—"
        note = f"（{self.note}）" if self.note else ""
        return (f"state={self.state} active={self.active} version={self.version} "
                f"CRC={crc} 期望={exp} 校验={'PASS' if self.verified else 'FAIL'}{note}")


def crc16_ccitt(data: bytes) -> int:
    """CRC16-CCITT-FALSE：poly=0x1021，init=0xFFFF，不反射，xorout=0。"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def cal_crc(channel: str, version: int, points: list[tuple[int, int]]) -> int:
    """§3.4.3：'CAL6'+ch+version+N×(set,meas)，小端；入参为命令单位。"""
    cfg = CHANNELS[channel.upper()]
    raw = b"CAL6" + bytes([0 if channel.upper() == "V" else 1]) + int(version).to_bytes(2, "little")
    for setpoint, measured in points:
        raw += int(setpoint * cfg["scale"]).to_bytes(2, "little")
        raw += int(measured * cfg["scale"]).to_bytes(2, "little")
    return crc16_ccitt(raw)

def parse_reply(raw: str) -> tuple[str, list]:
    """解析 OK/ERR；ERR 码越界按协议错处理，避免未知码被当合法回执。"""
    parts = (raw or "").strip().split()
    if not parts:
        raise CalError(CONDITION, "设备回包为空")
    if parts[0].upper() == "OK":
        return "OK", parts[1:]
    if parts[0].upper() == "ERR":
        if len(parts) < 2 or not parts[1].isdigit():
            raise CalError(CONDITION, f"ERR 回执缺少数字错误码：{raw!r}")
        code = int(parts[1])
        if code not in STATUS_TEXT:
            raise CalError(CONDITION, f"ERR 码 {code} 不在 CAL_STATUS 0–7 内：{raw!r}")
        return "ERR", [code, " ".join(parts[2:]) or "设备未给错误信息"]
    raise CalError(CONDITION, f"无法识别的回执 {raw!r}（预期 OK 或 ERR <code> <msg>）")


class CalSession:
    """一次一个通道的校准会话；每条设备回执经 ``log`` 落原文。"""

    def __init__(self, link, log=None):
        self.link, self._log = link, (log or (lambda _line: None))
        self._reset()

    def _reset(self) -> None:
        self.channel: str | None = None
        self.stage = "idle"           # idle/armed/setting/ready/done
        self.sets: dict[int, int] = {}
        self.meas: dict[int, int] = {}
        self.committed, self.last_read, self.limit_a = False, None, None

    @property
    def active(self) -> bool:
        return self.channel is not None and not self.committed

    @property
    def cfg(self) -> dict | None:
        return CHANNELS.get(self.channel) if self.channel else None

    def _send(self, line: str) -> list:
        try:
            raw = self.link.send(line)
        except LinkError as exc:
            self._log(f"! {line} 通信失败：{exc}")
            raise
        self._log(f"回执 {line} → {raw}")
        kind, fields = parse_reply(raw)
        if kind == "ERR":
            code, msg = fields
            self._log(f"! 设备 ERR {code}（{STATUS_TEXT[code]}）：{msg}")
            raise CalError(code, msg, raw)
        return fields

    def _safe_abort(self, reason: str, status: CalStatus | None = None):
        """异常唯一出口：尽力 ABORT，丢弃 RAM；未 COMMIT 不写 EEPROM。"""
        ch, was_committed, sent, err = self.channel, self.committed, False, ""
        if ch and not was_committed:
            try:
                raw = self.link.send(f"ABORT {ch}")
                sent = True
                self._log(f"安全中止 ABORT {ch} → {raw}")
                kind, fields = parse_reply(raw)
                if kind == "ERR":
                    err = f"ERR {fields[0]} {fields[1]}"
            except Exception as exc:      # ABORT 自身失败也必须留痕并收口
                err = str(exc)
                self._log(f"! 自动 ABORT 发送失败：{exc}")
        self._reset()
        if was_committed:
            text = f"{reason}；COMMIT 已执行，EEPROM 已写，未再发 ABORT"
        else:
            text = f"{reason}；{'已发送 ABORT' if sent else 'ABORT 未发出'}，未 COMMIT，EEPROM 未写"
        if err:
            text += f"（ABORT 异常：{err}）"
        self._log("安全中止：" + text)
        raise CalibrationAborted(text, status, sent, err)

    def _ensure(self, ch: str) -> str:
        ch = (ch or "").strip().upper()
        if not self.channel:
            raise CalError(IDLE, "未在校准会话中：请先 CAL BEGIN <V|I>")
        if ch != self.channel:
            raise CalError(BUSY, f"当前会话为 {self.channel}，不允许切换为 {ch or '(空)'}")
        return ch

    def _index(self, idx) -> int:
        text = str(idx).strip()
        if isinstance(idx, bool) or not re.fullmatch(r"\d+", text):
            raise CalError(POINT, f"点号必须是非负整数：{idx!r}")
        num = int(text)
        if num >= len(self.cfg["points"]):
            raise CalError(POINT, f"点号 {num} 越界（0–{len(self.cfg['points']) - 1}）")
        return num

    def _value(self, value) -> int:
        text = str(value).strip()
        if isinstance(value, bool) or not re.fullmatch(r"\d+", text):
            raise CalError(POINT, f"数值必须是整数（{self.cfg['unit']}）：{value!r}")
        num = int(text)
        if num > self.cfg["max"]:
            raise CalError(POINT, f"数值 {num} 越界（0–{self.cfg['max']} {self.cfg['unit']}）")
        return num

    def _monotonic(self, idx: int, value: int, table: dict[int, int], label: str) -> None:
        if idx > 0 and idx - 1 in table and value <= table[idx - 1]:
            raise CalError(POINT, f"{label}必须严格递增：第 {idx} 点 {value} ≤ 第 {idx - 1} 点 {table[idx - 1]}")
        if idx + 1 in table and value >= table[idx + 1]:
            raise CalError(POINT, f"{label}必须严格递增：第 {idx} 点 {value} ≥ 第 {idx + 1} 点 {table[idx + 1]}")

    def guard(self, line: str) -> None:
        """会话中拒绝普通设定/使能命令（busy），不打断会话；READ/ABORT 始终放行。"""
        p = (line or "").strip().split()
        if not self.active or not p:
            return
        head = p[0].upper()
        allowed = head in ("SET", "MEAS", "COMMIT", "READ", "ABORT") or (
            head == "CAL" and len(p) > 1 and p[1].upper() in ("BEGIN", "ABORT", "STATUS"))
        if not allowed:
            self._log(f"拒绝普通命令 {line!r}：校准会话中 busy，会话不被打断")
            raise CalError(BUSY, f"校准会话进行中，命令 {line!r} 被拒绝（busy）")

    def execute(self, line: str):
        """GUI/CLI 唯一入口：分发校准命令，非校准命令不得绕过 guard。"""
        parts = (line or "").strip().split()
        if not parts:
            raise CalError(POINT, "空命令")
        self.guard(line)
        head = parts[0].upper()
        if head == "CAL" and len(parts) >= 2 and parts[1].upper() == "BEGIN":
            return self.begin(parts[2] if len(parts) > 2 else "")
        if head == "CAL" and len(parts) >= 2 and parts[1].upper() == "ABORT":
            return self.abort(parts[2] if len(parts) > 2 else None)
        if head in ("SET", "MEAS"):
            if len(parts) != 4:
                raise CalError(POINT, f"{head} 需要 4 段：{head} <ch> <idx> <value>")
            return (self.set_point if head == "SET" else self.meas_point)(parts[1], parts[2], parts[3])
        if head == "COMMIT" and len(parts) == 2:
            return self.commit(parts[1])
        if head == "READ" and len(parts) == 2:
            return self.read(parts[1])
        if head == "CAL" and len(parts) == 2 and parts[1].upper() == "STATUS":
            return self.read()
        if head == "CAL" and len(parts) == 3 and parts[1].upper() in ("STATUS", "READ"):
            return self.read(parts[2])
        raise CalError(CONDITION, f"非校准命令 {line!r}：本工具不发送普通设定/使能命令")

    def begin(self, ch: str) -> dict:
        ch = (ch or "").strip().upper()
        if self.active:
            raise CalError(BUSY, f"已有 {self.channel} 校准会话，先 COMMIT/ABORT")
        if ch not in CHANNELS:
            raise CalError(POINT, f"通道必须是 V 或 I：{ch or '(空)'}")
        self._reset()
        self.channel, self.stage = ch, "armed"
        self.limit_a = 0.5 if ch == "V" else None
        try:
            self._send(f"CAL BEGIN {ch}")
        except (CalError, LinkError) as exc:
            self._safe_abort(f"CAL BEGIN {ch} 失败：{exc}", getattr(exc, "code", None))
        limit = "0.5 A（设备校准态自动生效）" if ch == "V" else "目标点+1 A（设备校准态自动生效）"
        self._log(f"CAL BEGIN {ch} OK；限流 {limit}；会话中普通设定/使能命令将被 busy 拒绝")
        return {"channel": ch, "stage": self.stage, "limit_a": self.limit_a}

    def set_point(self, ch: str, idx, value) -> int:
        ch = self._ensure(ch)
        try:
            idx, value = self._index(idx), self._value(value)
            if idx in self.meas:
                raise CalError(POINT, f"第 {idx} 点已记录 MEAS，不能重设")
            if idx != len(self.meas):
                raise CalError(POINT, f"请按顺序下发：当前应下发第 {len(self.meas)} 点")
            self._monotonic(idx, value, self.sets, "设定值")
        except CalError as exc:
            self._safe_abort(f"SET 输入非法：{exc}", exc.code)
        try:
            self._send(f"SET {ch} {idx} {value}")
        except (CalError, LinkError) as exc:
            self._safe_abort(f"SET {ch} {idx} {value} 失败：{exc}", getattr(exc, "code", None))
        self.sets[idx], self.stage = value, "setting"
        if ch == "I":
            self.limit_a = value / 1000.0 + 1.0
            self._log(f"第 {idx} 点设定 {value} mA；设备限流目标点+1 A = {self.limit_a:.1f} A")
        return value

    def meas_point(self, ch: str, idx, value) -> int:
        ch = self._ensure(ch)
        try:
            idx, value = self._index(idx), self._value(value)
            if idx not in self.sets:
                raise CalError(POINT, f"第 {idx} 点尚未 SET，不能 MEAS")
            if idx in self.meas:
                raise CalError(POINT, f"第 {idx} 点已记录 MEAS，不能重复")
            if idx != len(self.meas):
                raise CalError(POINT, f"请按顺序下发：当前应记录第 {len(self.meas)} 点")
            self._monotonic(idx, value, self.meas, "实测值")
        except CalError as exc:
            self._safe_abort(f"MEAS 输入非法：{exc}", exc.code)
        try:
            self._send(f"MEAS {ch} {idx} {value}")
        except (CalError, LinkError) as exc:
            self._safe_abort(f"MEAS {ch} {idx} {value} 失败：{exc}", getattr(exc, "code", None))
        self.meas[idx] = value
        self.stage = "ready" if len(self.meas) == len(self.cfg["points"]) else "setting"
        self._log(f"第 {idx} 点记录完成（{len(self.meas)}/{len(self.cfg['points'])}）"
                  + ("；全部完成，COMMIT 前 EEPROM 未写" if self.stage == "ready" else ""))
        return value

    def commit(self, ch: str) -> ReadResult:
        ch = self._ensure(ch)
        if len(self.meas) != len(self.cfg["points"]):
            raise CalError(POINT, f"还有 {len(self.cfg['points']) - len(self.meas)} 点未 MEAS，不能 COMMIT")
        for i in range(1, len(self.meas)):
            if self.sets[i - 1] >= self.sets[i] or self.meas[i - 1] >= self.meas[i]:
                self._safe_abort("点表未严格递增，COMMIT 前拦截", POINT)
        try:
            self._send(f"COMMIT {ch}")
        except (CalError, LinkError) as exc:
            self._safe_abort(f"COMMIT {ch} 失败：{exc}", getattr(exc, "code", None))
        self.committed, self.stage, self.limit_a = True, "done", None
        self._log(f"COMMIT {ch} OK；设备已写 EEPROM（仅 COMMIT 写），开始回读校验")
        result = self.read(ch)
        if not result.verified:
            self._log(f"! COMMIT 后回读校验未通过：{result.summary()}")
        return result

    def read(self, ch: str | None = None) -> ReadResult:
        ch = self._ensure(ch or self.channel or "")
        try:
            fields = self._send(f"READ {ch}")
            if len(fields) < 3:
                raise CalError(CONDITION, f"READ 回执字段不足（需 state active version [crc]）：{fields!r}")
            state, active, version = int(fields[0]), int(fields[1]), int(fields[2])
            crc = int(fields[3], 16) if len(fields) > 3 else None
        except (CalError, LinkError, ValueError) as exc:
            self._safe_abort(f"READ {ch} 失败：{exc}", getattr(exc, "code", None))
        complete = len(self.meas) == len(self.cfg["points"])
        expected = (cal_crc(ch, version, [(self.sets[i], self.meas[i])
                                          for i in range(len(self.cfg["points"]))])
                    if complete else None)
        note = ("设备未回传 CRC，回读校验未完成" if crc is None else
                "会话尚未完成，仅回读状态" if not complete else
                "CAL_STATUS 非 ok 或 CAL_ACTIVE≠1" if state != OK or active != 1 else "")
        verified = bool(complete and crc is not None and expected == crc and state == OK and active == 1)
        result = ReadResult(state, active, version, crc, expected, verified, note)
        self.last_read = result
        self._log(f"READ {ch}：{result.summary()}")
        return result

    def abort(self, ch: str | None = None) -> None:
        ch = (ch or self.channel or "").strip().upper()
        if self.committed:
            self._log("会话已 COMMIT 完成，无需 ABORT")
            self._reset()
            return
        if ch not in CHANNELS:
            self._reset()
            self._log("无进行中的校准会话，未发送 ABORT")
            return
        ok = False
        try:
            raw = self.link.send(f"ABORT {ch}")
            self._log(f"ABORT {ch} → {raw}")
            kind, fields = parse_reply(raw)
            ok = kind != "ERR"
            if kind == "ERR":
                self._log(f"! ABORT 回执 ERR {fields[0]}（{STATUS_TEXT[fields[0]]}）：{fields[1]}")
        except Exception as exc:
            self._log(f"! ABORT {ch} 发送失败/已断开：{exc}")
        self._reset()
        self._log(f"ABORT {ch} {'完成' if ok else '未确认'}；未 COMMIT，EEPROM 未写")
