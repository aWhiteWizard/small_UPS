"""T-0027 离线自测 + 运行截图驱动（不接真机，不生成产品文件）。

用法:
  py -3 -B .agent/evidence/T-0027-p1-selftest.py          # 断言自测
  py -3 -B .agent/evidence/T-0027-p1-selftest.py --demo   # 打开已填满的界面供截图
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, "tools")

from calib.app import CalibApp
from calib.serial_link import PortInfo
from calib.session import CHANNELS, cal_crc


class FakeSerial:
    """最小 PSU 设备：INFO/CAL/SET/MEAS/COMMIT/READ/ABORT，可注入一条 ERR。"""

    def __init__(self, port, baud, timeout):
        self.port, self.baud, self.timeout = port, baud, timeout
        self.ch, self.sets, self.meas = None, {}, {}
        self.commits, self.version, self.last = 0, 0, None
        self.replies: list[bytes] = []
        self.err_on = None  # 例如 "ERR_ON_MEAS"

    def write(self, data: bytes) -> None:
        line = data.decode("ascii").strip()
        self.replies.append((self._handle(line) + "\n").encode("ascii"))

    def flush(self) -> None:
        pass

    def readline(self) -> bytes:
        return self.replies.pop(0) if self.replies else b""

    def close(self) -> None:
        pass

    def _handle(self, line: str) -> str:
        p = line.split()
        if not p:
            return "ERR 7 empty"
        head = p[0].upper()
        if head == "INFO":
            return "OK INFO 1.0 0.9.0 PSU-DEMO-0001"
        if head == "CAL" and len(p) == 3 and p[1].upper() == "BEGIN":
            self.ch = p[2].upper()
            return "OK"
        if head == "CAL" and len(p) == 3 and p[1].upper() == "ABORT":
            self.ch = None
            return "OK"
        if head == "SET" and len(p) == 4:
            self.sets[int(p[2])] = int(p[3])
            return "OK"
        if head == "MEAS" and len(p) == 4:
            if self.err_on == "ERR_ON_MEAS":
                return "ERR 5 point rejected"
            self.meas[int(p[2])] = int(p[3])
            return "OK"
        if head == "COMMIT" and len(p) == 2:
            self.commits += 1
            self.version += 1
            pts = [(self.sets[i], self.meas[i]) for i in range(len(self.meas))]
            self.last = (self.ch, self.version, cal_crc(self.ch, self.version, pts))
            return "OK"
        if head == "READ" and len(p) == 2:
            ch, ver, crc = self.last
            return f"OK 2 1 {ver} {crc:04X}"
        if head == "ABORT" and len(p) == 2:
            self.ch = None
            return "OK"
        return "ERR 7 unknown"


def make_app(fake_box):
    root = tk.Tk()
    root.withdraw()
    app = CalibApp(root, serial_factory=lambda p, b, t: fake_box.setdefault(
        "dev", FakeSerial(p, b, t)))
    app.pack(fill="both", expand=True)
    app.serial._ports = [PortInfo("DEMO", "mock")]
    app.serial.port_box["values"] = ["DEMO — mock"]
    app.serial.port_var.set("DEMO — mock")
    app.serial.toggle()
    root.update()
    return root, app, fake_box["dev"]


def full_session(app, ch, delta):
    app.ch_var.set(ch)
    app._channel_changed()
    app.begin()
    for i, setpoint in enumerate(CHANNELS[ch]["points"]):
        app.point()
        app.rows[i]["meas_var"].set(str(setpoint - delta))
        app.meas()
    app.commit()
    app.read()
    return app


def test_table_and_error():
    fake = {}
    root, app, dev = make_app(fake)
    try:
        assert app.serial.info_var.get().endswith("PSU-DEMO-0001")
        assert len(app.rows) == 6, len(app.rows)  # V: >=5 个点可见可编辑
        assert str(app.rows[0]["set_entry"]["state"]) == "normal"
        app.rows[0]["meas_var"].set("497")
        app.update_idletasks()
        assert app.rows[0]["err_var"].get() == "-3"
        assert app.rows[0]["pct_var"].get() == "-0.60%"
        app.rows[0]["set_var"].set("510")
        app.update_idletasks()
        assert app.rows[0]["err_var"].get() == "-13"
        app.ch_var.set("I")
        app._channel_changed()
        assert len(app.rows) == 3
        print("PASS 1/5 设备信息、V6/I3 点表、设定/实测可编辑与误差实时计算")
    finally:
        root.destroy()


def test_full_flow():
    fake = {}
    root, app, dev = make_app(fake)
    try:
        full_session(app, "V", 3)
        assert dev.commits == 1
        assert "PASS" in app.status_var.get()
        assert "PASS" in app.result_var.get()
        assert "TX> INFO" in app.serial.log_text.get("1.0", "end")
        assert "RX< OK INFO 1.0 0.9.0 PSU-DEMO-0001" in app.serial.log_text.get("1.0", "end")
        assert "CAL BEGIN V" in app.serial.log_text.get("1.0", "end")
        print("PASS 2/5 完整 V6 流程 BEGIN→SET/MEAS→COMMIT→READ，CRC PASS，收发原文入日志")
    finally:
        root.destroy()


def test_abort_on_error():
    fake = {}
    root, app, dev = make_app(fake)
    dev.err_on = "ERR_ON_MEAS"
    try:
        app.begin()
        app.point()
        app.rows[0]["meas_var"].set("497")
        app.meas()
        assert dev.commits == 0
        assert app.session is None
        assert app.status_lbl.cget("style") == "Fail.TLabel"
        log = app.serial.log_text.get("1.0", "end")
        assert "ABORT V" in log and "ERR 5" in log
        print("PASS 3/5 设备 ERR 自动 ABORT、失败状态红色、COMMIT=0（未写 EEPROM）")
    finally:
        root.destroy()


def test_channel_switch_and_abort():
    fake = {}
    root, app, dev = make_app(fake)
    try:
        app.begin()
        app.point()
        app.ch_var.set("I")
        app._channel_changed()
        assert app.ch_var.get() == "V"
        assert app.status_lbl.cget("style") == "Fail.TLabel"
        app.abort()
        assert app.session is None
        assert app.ch_var.get() == "V"
        assert "已中止" in app.step_var.get()
        print("PASS 4/5 会话中拒绝切换通道、CAL ABORT 收口（未 COMMIT）")
    finally:
        root.destroy()


def test_current_channel_flow():
    fake = {}
    root, app, dev = make_app(fake)
    try:
        full_session(app, "I", 1)
        assert dev.commits == 1
        assert "PASS" in app.status_var.get()
        assert "TX> COMMIT I" in app.serial.log_text.get("1.0", "end")
        print("PASS 5/5 I3 流程 BEGIN→SET/MEAS→COMMIT→READ，CRC PASS")
    finally:
        root.destroy()


def demo():
    fake = {}
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root.title("PSU 标定工具 · T-0027")
    root.geometry("1320x880+100+60")
    app = CalibApp(root, serial_factory=lambda p, b, t: fake.setdefault(
        "dev", FakeSerial(p, b, t)))
    app.pack(fill="both", expand=True)
    app.serial._ports = [PortInfo("COM9", "USB-SERIAL CH340 (DEMO)")]
    app.serial.port_box["values"] = ["COM9 — USB-SERIAL CH340 (DEMO)"]
    app.serial.port_var.set("COM9 — USB-SERIAL CH340 (DEMO)")
    app.serial.toggle()
    full_session(app, "V", 2)
    app.update_idletasks()
    root.update()
    root.lift()
    root.attributes("-topmost", True)
    root.after(300, lambda: (root.lift(), root.focus_force()))
    bounds = Path(".agent/evidence/T-0027-p1-window.txt")
    bounds.write_text(f"{root.winfo_rootx()},{root.winfo_rooty()},"
                      f"{root.winfo_width()},{root.winfo_height()}", encoding="ascii")
    root.after(20000, root.destroy)
    print("DEMO_READY", bounds)
    root.mainloop()


def main() -> int:
    if "--demo" in sys.argv:
        demo()
        return 0
    for test in (test_table_and_error, test_full_flow, test_abort_on_error,
                 test_channel_switch_and_abort, test_current_channel_flow):
        test()
    print("RESULT: PASS (5/5)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
