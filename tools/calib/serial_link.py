"""pyserial 串口层（T-0025）：枚举、连接/断开、超时、重连、收发原文日志。"""
from __future__ import annotations
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
try:  # 未装 pyserial 时仍可导入本模块做离线检查
    import serial
    from serial.tools import list_ports as _comports
except ImportError:
    serial = _comports = None

class LinkError(Exception):
    """串口层异常基类；message 可直接展示给用户。"""

class NoDeviceError(LinkError):
    """无设备：没有可用串口，或目标端口不存在/已拔出。"""

class PortBusyError(LinkError):
    """端口被占用：其他程序持有该串口，或当前用户无权访问。"""

class UnpluggedError(LinkError):
    """拔线：读写过程中设备消失或端口失效。"""

class ReadTimeout(LinkError):
    """超时：命令已发出，但在超时时间内没有收到完整回包。"""

@dataclass(frozen=True)
class PortInfo:
    device: str
    description: str = ""

    def label(self) -> str:
        return f"{self.device} — {self.description}" if self.description else self.device

@dataclass(frozen=True)
class ConnectionState:
    connected: bool
    port: str = ""
    text: str = "未连接"
    error: str = ""

def list_ports() -> list[PortInfo]:
    """枚举当前可用串口；无 pyserial 时给出安装提示，而不是返回空列表。"""
    if _comports is None:
        raise LinkError("未安装 pyserial：请执行 py -3 -m pip install pyserial")
    return [PortInfo(p.device, p.description or "") for p in _comports.comports()]

def _stamp() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def _classify_open_error(port: str, exc: Exception) -> LinkError:
    msg = str(exc) or exc.__class__.__name__
    low = msg.lower()
    if any(k in low for k in ("access is denied", "permissionerror", "拒绝访问", "被占用", "busy")):
        return PortBusyError(f"串口 {port} 被占用：请关闭占用该串口的程序后重试（{msg}）")
    if any(k in low for k in ("filenotfounderror", "not found", "找不到", "不存在", "could not open port")):
        return NoDeviceError(f"串口 {port} 不存在或已拔出（无设备）：{msg}")
    return LinkError(f"串口 {port} 打开失败：{msg}")

class SerialLink:
    """串口连接 + 行协议收发；线程安全，状态经 ``on_status`` 回调给界面。"""

    def __init__(self, port: str = "", baud: int = 115200, timeout: float = 1.0,
                 log=None, on_status=None, serial_factory=None, reconnect_attempts: int = 3):
        self.port, self.baud, self.timeout = port, baud, timeout
        self.reconnect_attempts = reconnect_attempts
        self._log = log or (lambda _line: None)
        self._on_status = on_status
        self._factory = serial_factory
        self._ser = None
        self._lock = threading.RLock()
        self.state = ConnectionState(False, port, "未连接")

    def _emit(self, direction: str, text: str) -> None:
        self._log(f"[{_stamp()}] {direction} {text}")

    def _set_state(self, connected: bool, text: str, error: str = "") -> ConnectionState:
        self.state = ConnectionState(connected, self.port, text, error)
        if self._on_status:
            self._on_status(self.state)
        return self.state

    def _open(self):
        if self._factory is not None:
            return self._factory(self.port, self.baud, self.timeout)
        if serial is None:
            raise LinkError("未安装 pyserial：请执行 py -3 -m pip install pyserial")
        return serial.Serial(self.port, self.baud, timeout=self.timeout, write_timeout=self.timeout)

    def connect(self, port: str | None = None) -> ConnectionState:
        with self._lock:
            if port:
                self.port = port
            if self._ser is not None:
                self.disconnect("重复连接前关闭")
            if not self.port:
                raise NoDeviceError("未选择串口：请点“刷新”后选择一个端口")
            if self._factory is None and not list_ports():
                raise NoDeviceError("未检测到可用串口（无设备）：请检查 USB 线、设备供电与驱动")
            try:
                self._ser = self._open()
            except LinkError as exc:
                self._set_state(False, str(exc), str(exc))
                raise
            except Exception as exc:
                err = _classify_open_error(self.port, exc)
                self._set_state(False, str(err), str(err))
                raise err from exc
            self._emit("---", f"已连接 {self.port} @ {self.baud} 8N1")
            return self._set_state(True, f"已连接 {self.port} @ {self.baud} 8N1")

    def disconnect(self, reason: str = "用户断开") -> ConnectionState:
        with self._lock:
            ser, self._ser = self._ser, None
            if ser is not None:
                try:
                    ser.close()
                except Exception as exc:  # 关闭失败也要留痕，不能静默
                    self._emit("!", f"关闭串口异常：{exc}")
            self._emit("---", f"已断开 {self.port}（{reason}）")
            return self._set_state(False, f"未连接（{reason}）")

    def reconnect(self, attempts: int | None = None, delay: float = 0.8) -> ConnectionState:
        """断开后重连；默认 3 次。重连成功不自动重发上一条命令，避免重复执行。"""
        attempts = self.reconnect_attempts if attempts is None else attempts
        if self._ser is not None:
            self.disconnect("重连前关闭")
        last: LinkError | None = None
        for i in range(1, attempts + 1):
            self._emit("---", f"重连 {i}/{attempts}：{self.port or '(未选串口)'}")
            try:
                return self.connect()
            except LinkError as exc:
                last = exc
                if i < attempts:
                    time.sleep(delay)
        raise LinkError(f"重连失败（已尝试 {attempts} 次）：{last}")

    def _drop(self, reason: str) -> None:
        self._emit("!", reason)
        ser, self._ser = self._ser, None
        if ser is not None:
            try:
                ser.close()
            except Exception as exc:  # 句柄关闭异常留痕
                self._emit("!", f"关闭异常句柄失败：{exc}")
        self._set_state(False, f"已断开 {self.port}（拔线）：{reason}", reason)

    def send(self, line: str, timeout: float | None = None) -> str:
        """发送一行并读取一条回包；返回去掉行尾的原文。"""
        with self._lock:
            if self._ser is None:
                raise LinkError("串口未连接：请先连接设备")
            command = line.rstrip("\r\n")
            self._emit("TX>", command)
            try:
                self._ser.write((command + "\r\n").encode("ascii"))
                self._ser.flush()
            except Exception as exc:
                self._drop(f"发送失败：{exc}")
                raise UnpluggedError(f"串口 {self.port} 已断开（拔线）：发送“{command}”失败；{exc}") from exc
            effective = self.timeout if timeout is None else timeout
            try:
                self._ser.timeout = effective
                raw = self._ser.readline()
            except Exception as exc:
                self._drop(f"读取失败：{exc}")
                raise UnpluggedError(f"串口 {self.port} 已断开（拔线）：读取回包失败；{exc}") from exc
            if not raw:
                self._emit("RX<", "(超时，无回包)")
                raise ReadTimeout(f"等待设备响应超时（{effective:.1f}s）：命令“{command}”已发出，未收到回包")
            text = raw.decode("utf-8", "backslashreplace").rstrip("\r\n")
            self._emit("RX<", text)
            if not raw.endswith(b"\n"):
                raise ReadTimeout(f"等待设备响应超时（{effective:.1f}s）：只收到不完整回包“{text}”")
            return text
