"""完整标定界面（T-0027）：串口/设备信息 + 通道 + 点表 + 会话按钮 + 状态日志。

组合 T-0025 ``SerialPanel`` 与 T-0026 ``CalSession``；仅依赖 tkinter 与 pyserial。
点表按需求 §3.4.1：V 6 点、I 3 点（工单“五点”按“至少五个可编辑点”落地，V 6 行可编辑）。
仅 COMMIT 写 EEPROM；异常由会话层自动 ABORT。
"""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk

from .session import CHANNELS, CalError, CalSession, CalibrationAborted
from .serial_link import LinkError
from .ui import SerialPanel

class CalibApp(ttk.Frame):
    """标定工具主界面；可注入 ``serial_factory`` 做离线演示/自测。"""
    def __init__(self, master, serial_factory=None):
        super().__init__(master)
        self.session: CalSession | None = None
        self.rows: list[dict] = []
        self._build(serial_factory)
        self._channel_changed()
        self._refresh_buttons()

    def _build(self, serial_factory) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 13, "bold"))
        style.configure("Big.TLabel", font=("Microsoft YaHei UI", 10, "bold"))
        for name, color in (("Ok", "#0b7a0b"), ("Fail", "#b00020"), ("Warn", "#a15c00"),
                            ("Info", "#0b4f8a"), ("Hint", "#555555")):
            style.configure(name + ".TLabel", foreground=color)

        head = ttk.Frame(self, padding=(10, 8, 10, 0))
        head.pack(fill="x")
        ttk.Label(head, text="PSU 标定工具", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="  仅服务/标定：不设定 V/I、不开关输出",
                  style="Hint.TLabel").pack(side="left", padx=8)
        self.status_var = tk.StringVar(value="等待连接设备")
        self.status_lbl = ttk.Label(head, textvariable=self.status_var, style="Warn.TLabel")
        self.status_lbl.pack(side="right")

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=6)
        self.serial = SerialPanel(body, serial_factory=serial_factory, on_state=self._link_state)
        body.add(self.serial, weight=2)
        self._build_cal(body)

        foot = ttk.Frame(self, padding=(10, 2, 10, 8))
        foot.pack(fill="x")
        self.step_var = tk.StringVar(value="步骤：未开始")
        ttk.Label(foot, textvariable=self.step_var, style="Info.TLabel").pack(side="left")
        self.limit_var = tk.StringVar(value="限流：—")
        ttk.Label(foot, textvariable=self.limit_var, style="Hint.TLabel").pack(side="right")

    def _build_cal(self, parent) -> None:
        cal = ttk.Frame(parent)
        parent.add(cal, weight=3)
        chan = ttk.LabelFrame(cal, text="通道选择", padding=6)
        chan.pack(fill="x")
        ttk.Label(chan, text="通道：", style="Big.TLabel").pack(side="left")
        self.ch_var = tk.StringVar(value="V")
        self.ch_radios = [ttk.Radiobutton(chan, text=f"{CHANNELS[ch]['name']} {ch}", value=ch,
                                          variable=self.ch_var, command=self._channel_changed)
                          for ch in ("V", "I")]
        for rb in self.ch_radios:
            rb.pack(side="left", padx=6)

        tablef = ttk.LabelFrame(cal, text="校准点表（序号 / 设定 / 实测 / 误差实时）", padding=6)
        tablef.pack(fill="both", expand=True, pady=6)
        self.table = ttk.Frame(tablef)
        self.table.pack(fill="both", expand=True)

        ops = ttk.LabelFrame(cal, text="校准操作", padding=6)
        ops.pack(fill="x")
        specs = (("CAL BEGIN", self.begin), ("逐点下发", self.point),
                 ("记录实测 MEAS", self.meas), ("CAL COMMIT", self.commit),
                 ("CAL READ 回读校验", self.read), ("CAL ABORT 中止", self.abort))
        self.btn_begin, self.btn_point, self.btn_meas, self.btn_commit, self.btn_read, self.btn_abort = (
            ttk.Button(ops, text=text, command=cmd) for text, cmd in specs)
        for i, btn in enumerate((self.btn_begin, self.btn_point, self.btn_meas, self.btn_commit,
                                 self.btn_read, self.btn_abort)):
            btn.grid(row=i // 3, column=i % 3, sticky="ew", padx=2, pady=3)
        for col in range(3):
            ops.columnconfigure(col, weight=1)
        self.result_var = tk.StringVar(value="回读 CRC：—")
        ttk.Label(cal, textvariable=self.result_var, style="Hint.TLabel").pack(
            fill="x", pady=(6, 0))

    def _rebuild_table(self) -> None:
        for child in self.table.winfo_children():
            child.destroy()
        self.rows = []
        cfg = CHANNELS[self.ch_var.get()]
        headers = ["序号", f"设定 ({cfg['unit']})", f"实测 ({cfg['unit']})",
                   f"误差 ({cfg['unit']})", "误差 (%)"]
        for col, text in enumerate(headers):
            ttk.Label(self.table, text=text, style="Big.TLabel").grid(
                row=0, column=col, padx=5, pady=3, sticky="w")
        for idx, setpoint in enumerate(cfg["points"]):
            row = {"set_var": tk.StringVar(value=str(setpoint)), "meas_var": tk.StringVar(),
                   "err_var": tk.StringVar(value="—"), "pct_var": tk.StringVar(value="—")}
            ttk.Label(self.table, text=str(idx)).grid(row=idx + 1, column=0, padx=5, pady=2)
            row["set_entry"] = ttk.Entry(self.table, textvariable=row["set_var"], width=11)
            row["set_entry"].grid(row=idx + 1, column=1, padx=5, pady=2, sticky="ew")
            row["meas_entry"] = ttk.Entry(self.table, textvariable=row["meas_var"], width=11)
            row["meas_entry"].grid(row=idx + 1, column=2, padx=5, pady=2, sticky="ew")
            row["err_lbl"] = ttk.Label(self.table, textvariable=row["err_var"], width=10)
            row["err_lbl"].grid(row=idx + 1, column=3, padx=5, pady=2, sticky="w")
            ttk.Label(self.table, textvariable=row["pct_var"], width=10).grid(
                row=idx + 1, column=4, padx=5, pady=2, sticky="w")
            for var in (row["set_var"], row["meas_var"]):
                var.trace_add("write", lambda *_a, i=idx: self._update_error(i))
            self.rows.append(row)
        for col in (1, 2):
            self.table.columnconfigure(col, weight=1)
        ttk.Label(self.table, text="设定值与实测值均可编辑；误差在输入时实时计算。",
                  style="Hint.TLabel").grid(row=len(cfg["points"]) + 1, column=0,
                                            columnspan=5, sticky="w", pady=(4, 0))

    def log(self, text: str) -> None:
        self.serial.append(f"[{datetime.now():%H:%M:%S}] {text}")

    def _set_status(self, text: str, level: str = "info") -> None:
        styles = {"ok": "Ok.TLabel", "fail": "Fail.TLabel",
                  "warn": "Warn.TLabel", "info": "Info.TLabel"}
        self.status_var.set(text)
        self.status_lbl.configure(style=styles[level])
        self._refresh_buttons()

    def _fail(self, text: str) -> None:
        self._set_status(text, "fail")
        self.log("! " + text)

    def _handle(self, exc: Exception) -> None:
        if isinstance(exc, CalibrationAborted):
            self._aborted(exc)
        else:
            self._fail(str(exc))

    def _update_error(self, idx: int) -> None:
        row = self.rows[idx]
        try:
            setpoint = int(row["set_var"].get().strip())
            measured = int(row["meas_var"].get().strip())
        except ValueError:
            row["err_var"].set("—")
            row["pct_var"].set("—")
            row["err_lbl"].configure(foreground="#555555")
            return
        diff = measured - setpoint
        pct = diff / setpoint * 100 if setpoint else 0.0
        row["err_var"].set(f"{diff:+d}")
        row["pct_var"].set(f"{pct:+.2f}%")
        row["err_lbl"].configure(foreground="#b00020" if abs(pct) > 5 else "#0b4f8a")

    def _link_state(self, state) -> None:
        if state.connected:
            self._set_status(f"已连接 {state.port}；请选择通道并 CAL BEGIN", "ok")
            return
        if self.session is not None and self.session.channel is not None:
            self._fail(f"串口已断开：{state.text}；校准会话无法继续（未 COMMIT 不写 EEPROM）")
            self.session = None
            self._reset_rows()
            self.step_var.set("步骤：串口断开，会话已收口")
            self.limit_var.set("限流：—")
        else:
            self._set_status(f"未连接：{state.text}", "warn")

    def _need_session(self) -> CalSession | None:
        if self.session is None or self.session.channel is None:
            self._fail("无校准会话：请先连接设备并点 CAL BEGIN")
            return None
        return self.session

    def _aborted(self, exc: CalibrationAborted) -> None:
        self.session = None
        self._fail(f"已安全中止：{exc}")
        self._reset_rows()
        self.result_var.set("回读 CRC：—")
        self.step_var.set("步骤：未开始（已中止，未 COMMIT 时 EEPROM 未写）")
        self.limit_var.set("限流：—")

    def _reset_rows(self) -> None:
        for row in self.rows:
            row["meas_var"].set("")
            row["err_var"].set("—")
            row["pct_var"].set("—")
            row["err_lbl"].configure(foreground="#555555")
            row["set_entry"].configure(state="normal")
            row["meas_entry"].configure(state="normal")

    def _refresh_buttons(self) -> None:
        link = self.serial.link
        connected = bool(link is not None and link.state.connected)
        locked = self.session is not None and self.session.channel is not None
        complete = bool(locked and self.session.cfg and
                        len(self.session.meas) == len(self.session.cfg["points"]))
        st = lambda on: "normal" if on else "disabled"
        self.btn_begin.configure(state=st(connected and not locked))
        self.btn_point.configure(state=st(connected and locked and not complete))
        self.btn_meas.configure(state=st(connected and locked and not complete and
                                         len(self.session.sets) > len(self.session.meas)))
        self.btn_commit.configure(state=st(connected and complete and not self.session.committed))
        self.btn_read.configure(state=st(connected and locked))
        self.btn_abort.configure(state=st(connected and locked))
        for rb in self.ch_radios:
            rb.configure(state=st(not locked))

    def _channel_changed(self) -> None:
        if self.session is not None and self.session.channel is not None:
            self.ch_var.set(self.session.channel)
            self._fail("校准会话进行中，不能切换通道；请先 CAL COMMIT 或 CAL ABORT")
            return
        self._rebuild_table()
        cfg = CHANNELS[self.ch_var.get()]
        self.step_var.set(f"步骤：{cfg['name']}通道 {len(cfg['points'])} 点（{cfg['unit']}），"
                          "等待 CAL BEGIN")
        self._set_status(f"已切换 {cfg['name']}通道；{len(cfg['points'])} 个校准点待标定", "info")
        self.log(f"切换通道：{self.ch_var.get()}（{len(cfg['points'])} 点，单位 {cfg['unit']}）")

    def begin(self) -> None:
        if self.session is not None and self.session.channel is not None:
            self._fail("已有校准会话；请先 CAL COMMIT 并 ABORT 收口，再开新会话")
            return
        link = self.serial.link
        if link is None or not link.state.connected:
            self._fail("未连接设备：请先选择串口并点“连接”")
            return
        ch, cfg = self.ch_var.get(), CHANNELS[self.ch_var.get()]
        session = CalSession(link, self.log)
        try:
            session.begin(ch)
        except (CalibrationAborted, CalError, LinkError) as exc:
            self._handle(exc)
            return
        self.session = session
        self._reset_rows()
        self.result_var.set("回读 CRC：—")
        self.step_var.set(f"步骤 1/{len(cfg['points'])}：下发第 1 点 SET（{cfg['unit']}）")
        self.limit_var.set("限流：0.5 A（V 校准态，设备内部生效）" if ch == "V"
                           else "限流：目标点+1 A（I 校准态，设备内部生效）")
        self._set_status(f"CAL BEGIN {ch} OK：{len(cfg['points'])} 点会话已建立", "ok")

    def point(self) -> None:
        if (session := self._need_session()) is None:
            return
        idx, cfg = len(session.meas), session.cfg
        if idx >= len(cfg["points"]):
            self._set_status("全部点已记录，请点 CAL COMMIT（COMMIT 前不写 EEPROM）", "warn")
            return
        row, text = self.rows[idx], self.rows[idx]["set_var"].get().strip()
        try:
            value = int(text)
        except ValueError:
            self._fail(f"第 {idx} 点设定值必须是整数（{cfg['unit']}）：{text!r}")
            return
        try:
            session.set_point(session.channel, idx, value)
        except (CalibrationAborted, CalError, LinkError) as exc:
            self._handle(exc)
            return
        row["set_entry"].configure(state="disabled")
        row["meas_entry"].focus_set()
        self.step_var.set(f"步骤 {idx + 1}/{len(cfg['points'])}：已下发 SET {value} "
                          f"{cfg['unit']}，请输入万用表实测值")
        self._set_status(f"第 {idx + 1}/{len(cfg['points'])} 点 SET 完成，等待实测", "warn")

    def meas(self) -> None:
        if (session := self._need_session()) is None:
            return
        idx, cfg = len(session.meas), session.cfg
        if idx >= len(cfg["points"]):
            self._set_status("全部点已完成，请点 CAL COMMIT", "warn")
            return
        if idx not in session.sets:
            self._fail(f"第 {idx + 1} 点尚未 SET：请先点“逐点下发”")
            return
        row = self.rows[idx]
        text = row["meas_var"].get().strip()
        if not text:
            self._fail(f"请输入第 {idx + 1} 点实测值（{cfg['unit']}）")
            return
        try:
            session.meas_point(session.channel, idx, text)
        except (CalibrationAborted, CalError, LinkError) as exc:
            self._handle(exc)
            return
        row["set_entry"].configure(state="disabled")
        row["meas_entry"].configure(state="disabled")
        self._update_error(idx)
        if len(session.meas) == len(cfg["points"]):
            self.step_var.set(f"全部 {len(cfg['points'])} 点已记录；COMMIT 前 EEPROM 未写")
            self._set_status("全部校准点已记录，请点 CAL COMMIT", "ok")
        else:
            self.step_var.set(f"步骤 {idx + 2}/{len(cfg['points'])}：下发下一点 SET")
            self._set_status(f"第 {idx + 1} 点已记录；请继续逐点下发", "ok")

    def commit(self) -> None:
        if (session := self._need_session()) is None:
            return
        cfg = session.cfg
        if len(session.meas) != len(cfg["points"]):
            self._fail(f"还有 {len(cfg['points']) - len(session.meas)} 点未记录，不能 COMMIT")
            return
        try:
            result = session.commit(session.channel)
        except (CalibrationAborted, CalError, LinkError) as exc:
            self._handle(exc)
            return
        self.result_var.set("回读 CRC：" + result.summary())
        if result.verified:
            self._set_status("CAL COMMIT 成功；CAL READ 回读 CRC 校验 PASS", "ok")
        else:
            self._fail("COMMIT 已写 EEPROM，但回读校验 FAIL：" + result.summary())
        self.step_var.set("步骤：已 COMMIT（仅此次写 EEPROM）；可继续 CAL READ 回读复核")

    def read(self) -> None:
        if (session := self._need_session()) is None:
            return
        try:
            result = session.read(session.channel)
        except (CalibrationAborted, CalError, LinkError) as exc:
            self._handle(exc)
            return
        self.result_var.set("回读 CRC：" + result.summary())
        if result.verified:
            self._set_status("CAL READ 回读 CRC 校验 PASS", "ok")
        elif result.crc is None:
            self._fail("CAL READ 未完成校验：设备未回传 CRC")
        else:
            self._fail("CAL READ 回读校验 FAIL：" + result.summary())

    def abort(self) -> None:
        session = self.session
        ch = session.channel if session else self.ch_var.get()
        if session is not None:
            session.abort(ch)
        else:
            self.log("无进行中的校准会话，未发送 ABORT")
        self.session = None
        self._reset_rows()
        self.result_var.set("回读 CRC：—")
        self.limit_var.set("限流：—")
        self.step_var.set("步骤：已中止（未 COMMIT，EEPROM 未写）")
        self._set_status("CAL ABORT 已发送；未 COMMIT，EEPROM 未写", "warn")

    def close(self) -> None:
        if self.session is not None and self.session.channel is not None:
            try:
                self.session.abort(self.session.channel)
            except Exception:
                pass
        self.serial.destroy()
        self.winfo_toplevel().destroy()
