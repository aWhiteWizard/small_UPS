#!/usr/bin/env python3
"""PSU PC calibration tool (T-0008).

Tkinter GUI + pyserial. Text protocol aligned with the T-0008 work order:
  CAL BEGIN <ch> / SET <ch> <idx> <value> / MEAS <ch> <idx> <value>
  COMMIT <ch> / READ <ch> / ABORT <ch>
Device replies OK / ERR <code> <msg>.  READ may return payload
OK <state> <active> <version> <crc>; INFO may return OK INFO <proto> <fw> [sn].
"""
import argparse
import csv
import os
import re
import sys
import tempfile
import time
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

APP_TITLE = "PSU PC 标定工具 · T-0008"
BAUD = 115200
POINTS = {
    "V": [("0.5 V", 500), ("3.3 V", 3300), ("5 V", 5000),
          ("12 V", 12000), ("24 V", 24000), ("48 V", 48000)],
    "I": [("1 A", 1000), ("2.5 A", 2500), ("5 A", 5000)],
}
UNIT = {"V": "mV", "I": "mA"}


class LinkError(Exception):
    pass


class ProtocolError(Exception):
    pass


class DeviceError(Exception):
    def __init__(self, code, msg):
        super().__init__("ERR %s %s" % (code, msg))
        self.code, self.msg = code, msg


def crc16_ccitt(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def cal_crc(ch, version, points):
    """T-0006 §3.4.3: 'CAL6' + ch + version + N*(set,meas), all little endian."""
    raw = b"CAL6" + bytes([0 if ch == "V" else 1]) + int(version).to_bytes(2, "little")
    for setpoint, measured in points:
        raw += int(setpoint).to_bytes(2, "little") + int(measured).to_bytes(2, "little")
    return crc16_ccitt(raw)


def parse_line(text):
    parts = text.strip().split()
    if not parts:
        raise ProtocolError("空响应")
    head = parts[0].upper()
    if head == "OK":
        return "OK", parts[1:]
    if head == "ERR":
        code = int(parts[1]) if len(parts) > 1 and parts[1].lstrip("-").isdigit() else 0
        return "ERR", [code, " ".join(parts[2:]) or "device error"]
    if head in ("INFO", "STATUS"):
        return head, parts[1:]
    raise ProtocolError("无法识别的响应: " + text.strip())


def parse_value(text, ch):
    text = text.strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        raise ValueError("请输入非负数字（整数或小数）")
    value = float(text)
    full = 48000 if ch == "V" else 5000
    limit = int(full * 1.1)
    if value > limit:
        raise ValueError("超出量程+10%% 容差（0–%d %s）" % (limit, UNIT[ch]))
    return int(round(value))


class SerialLink:
    def __init__(self, port, log, timeout=2.0):
        self.port, self.log, self.timeout, self.ser = port, log, timeout, None

    @staticmethod
    def ports():
        try:
            from serial.tools import list_ports
            return [p.device for p in list_ports.comports()]
        except Exception:
            return []

    def open(self):
        import serial
        self.ser = serial.Serial(self.port, BAUD, timeout=self.timeout)
        time.sleep(0.05)

    def close(self):
        if self.ser:
            try:
                self.ser.close()
            finally:
                self.ser = None

    def command(self, line, timeout=None):
        if not self.ser:
            raise LinkError("串口未连接")
        self.log("TX> " + line)
        self.ser.timeout = timeout or self.timeout
        try:
            self.ser.write((line + "\r\n").encode("ascii"))
            self.ser.flush()
            raw = self.ser.readline()
        except Exception as exc:
            raise LinkError("串口读写失败: %s" % exc)
        if not raw:
            try:
                self.ser.reset_input_buffer()
            except Exception:
                pass
            raise LinkError("等待响应超时（%ss）: %s" % (self.ser.timeout, line))
        reply = raw.decode("ascii", "replace").strip()
        self.log("RX< " + reply)
        return reply


class MockLink:
    """Offline demo/self-test device; same command surface as SerialLink."""
    def __init__(self, log):
        self.log, self.connected = log, False
        self.ch, self.sets, self.meas = None, {}, {}
        self.version, self.active, self.crc, self.last = 0, False, None, None

    @staticmethod
    def ports():
        return ["DEMO (mock)"]

    def open(self):
        self.connected = True

    def close(self):
        self.connected = False

    def command(self, line, timeout=None):
        if not self.connected:
            raise LinkError("Mock 未连接")
        self.log("TX> " + line)
        reply = self._handle(line.strip())
        self.log("RX< " + reply)
        return reply

    def _handle(self, line):
        p = line.split()
        if not p:
            return "ERR 1 empty command"
        cmd = p[0].upper()
        if cmd == "INFO":
            return "OK INFO 1.0 0.9.0 PSU-DEMO-0001"
        if cmd == "CAL" and len(p) == 3 and p[1].upper() == "BEGIN" and p[2].upper() in POINTS:
            if self.ch:
                return "ERR 2 busy"
            self.ch, self.sets, self.meas = p[2].upper(), {}, {}
            return "OK"
        if cmd in ("SET", "MEAS") and len(p) == 4:
            try:
                ch, idx, value = p[1].upper(), int(p[2]), int(p[3])
            except ValueError:
                return "ERR 1 bad argument"
            if ch != self.ch or idx < 0 or idx >= len(POINTS[ch]):
                return "ERR 5 point"
            if cmd == "MEAS" and idx not in self.sets:
                return "ERR 5 point"
            (self.sets if cmd == "SET" else self.meas)[idx] = value
            return "OK"
        if cmd == "COMMIT" and len(p) == 2 and p[1].upper() == self.ch:
            if len(self.meas) != len(POINTS[self.ch]):
                return "ERR 5 point"
            pts = [(self.sets[i], self.meas[i]) for i in range(len(POINTS[self.ch]))]
            self.version += 1
            self.crc = cal_crc(self.ch, self.version, pts)
            self.last, self.active = (self.ch, self.version, self.crc), True
            self.ch = None
            return "OK"
        if cmd == "READ" and len(p) == 2:
            if self.last and p[1].upper() == self.last[0]:
                return "OK 2 1 %d %04X" % (self.last[1], self.last[2])
            return "OK 1 0 0 0000"
        if cmd == "ABORT" and len(p) == 2:
            self.ch, self.sets, self.meas = None, {}, {}
            return "OK"
        return "ERR 9 unknown command"


class App(tk.Tk):
    def __init__(self, demo=False):
        super().__init__()
        self.demo, self.link, self.connected = demo, None, False
        self.session, self.rows, self.ch_radios = None, [], []
        self.title(APP_TITLE)
        self.geometry("1180x840")
        self.minsize(980, 720)
        self.log_text = None
        self._build_ui()
        self.after(150, self._bootstrap)

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 14, "bold"))
        style.configure("Ok.TLabel", foreground="#0b7a0b")
        style.configure("Bad.TLabel", foreground="#b00020")
        style.configure("Hint.TLabel", foreground="#555555")

        header = ttk.Frame(self, padding=(10, 8, 10, 0))
        header.pack(fill="x")
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").pack(side="left")
        self.status_var = tk.StringVar(value="未连接")
        self.status_lbl = ttk.Label(header, textvariable=self.status_var, style="Bad.TLabel")
        self.status_lbl.pack(side="right")

        cf = ttk.LabelFrame(self, text="串口与设备", padding=8)
        cf.pack(fill="x", padx=10, pady=6)
        row = ttk.Frame(cf)
        row.pack(fill="x")
        ttk.Label(row, text="串口:").pack(side="left")
        self.port_var = tk.StringVar()
        self.port_cb = ttk.Combobox(row, textvariable=self.port_var, width=24, state="readonly")
        self.port_cb.pack(side="left", padx=4)
        self.refresh_btn = ttk.Button(row, text="刷新", command=self.refresh_ports)
        self.refresh_btn.pack(side="left", padx=2)
        self.conn_btn = ttk.Button(row, text="连接", command=self.toggle_connect)
        self.conn_btn.pack(side="left", padx=2)
        ttk.Label(row, text="  波特率: %d 8N1" % BAUD, style="Hint.TLabel").pack(side="left")
        self.limit_var = tk.StringVar(value="限流: —")
        ttk.Label(row, textvariable=self.limit_var).pack(side="right")

        info = ttk.Frame(cf)
        info.pack(fill="x", pady=(6, 0))
        self.info_vars = {"proto": tk.StringVar(value="—"), "fw": tk.StringVar(value="—"),
                          "sn": tk.StringVar(value="—")}
        ttk.Label(info, text="设备信息:").pack(side="left")
        for key, caption in (("proto", "协议版本"), ("fw", "固件版本"), ("sn", "序列号")):
            ttk.Label(info, text="  %s:" % caption).pack(side="left")
            ttk.Label(info, textvariable=self.info_vars[key], width=14).pack(side="left")

        paned = ttk.Panedwindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        upper = ttk.Frame(paned)
        paned.add(upper, weight=3)
        left = ttk.LabelFrame(upper, text="校准点（通道 / 序号 / 设定 / 实测 / 误差）", padding=6)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.LabelFrame(upper, text="校准操作", padding=6)
        right.pack(side="right", fill="y", padx=(6, 0))

        channel_row = ttk.Frame(left)
        channel_row.pack(fill="x", pady=(0, 4))
        ttk.Label(channel_row, text="通道:").pack(side="left")
        self.ch_var = tk.StringVar(value="V")
        for ch, text in (("V", "电压 V"), ("I", "电流 I")):
            rb = ttk.Radiobutton(channel_row, text=text, value=ch, variable=self.ch_var,
                                 command=self.on_channel)
            rb.pack(side="left", padx=4)
            self.ch_radios.append(rb)
        self.point_btn = ttk.Button(channel_row, text="逐点下发", command=self.point,
                                    state="disabled")
        self.point_btn.pack(side="right")
        self.table = ttk.Frame(left)
        self.table.pack(fill="both", expand=True)
        self.rebuild_table()

        buttons = [("begin", "CAL BEGIN", self.begin), ("commit", "CAL COMMIT", self.commit),
                   ("read", "CAL READ 回读校验", self.read), ("abort", "CAL ABORT 中止", self.abort)]
        self.btns = {}
        btn_frame = ttk.Frame(right)
        btn_frame.pack(fill="x")
        for num, (name, text, cmd) in enumerate(buttons):
            btn = ttk.Button(btn_frame, text=text, command=cmd, state="disabled")
            btn.grid(row=num // 2, column=num % 2, sticky="ew", padx=1, pady=2)
            self.btns[name] = btn
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        ttk.Separator(right).pack(fill="x", pady=6)
        meta = ttk.Frame(right)
        meta.pack(fill="x")
        ttk.Label(meta, text="环境温度 (°C):").grid(row=0, column=0, sticky="w")
        self.temp_var = tk.StringVar(value="25")
        ttk.Entry(meta, textvariable=self.temp_var, width=12).grid(row=0, column=1, pady=2)
        ttk.Label(meta, text="万用表型号:").grid(row=1, column=0, sticky="w")
        self.dmm_var = tk.StringVar(value="")
        ttk.Entry(meta, textvariable=self.dmm_var, width=16).grid(row=1, column=1, pady=2)
        self.crc_var = tk.StringVar(value="CRC: —")
        ttk.Label(right, textvariable=self.crc_var, wraplength=220, style="Hint.TLabel").pack(
            fill="x", pady=(8, 2))
        ttk.Label(right, text="提示: BEGIN 后设备自动限流；只有 COMMIT 写 EEPROM。",
                  wraplength=220, style="Hint.TLabel").pack(fill="x", pady=4)

        logf = ttk.LabelFrame(paned, text="状态与日志（收发原文）", padding=6)
        paned.add(logf, weight=2)
        logbar = ttk.Frame(logf)
        logbar.pack(fill="x")
        self.export_btn = ttk.Button(logbar, text="导出 CSV", command=self.export_csv,
                                     state="disabled")
        self.export_btn.pack(side="right", padx=2)
        ttk.Button(logbar, text="清空日志", command=self.clear_log).pack(side="right", padx=2)
        self.log_text = ScrolledText(logf, height=8, state="disabled", wrap="word",
                                     font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

    def log(self, text):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", "%s %s\n" % (stamp, text))
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _status(self, text, bad=False):
        self.status_var.set(text)
        self.status_lbl.config(style="Bad.TLabel" if bad else "Ok.TLabel")

    def refresh_ports(self):
        ports = ["DEMO (mock)"] if self.demo else SerialLink.ports()
        self.port_cb["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])
        if not ports:
            self.port_var.set("")
            self.log("未发现串口；请检查 USB-UART 驱动/连接后点“刷新”")
        self.conn_btn.config(state="normal" if ports or self.connected else "disabled")

    def _bootstrap(self):
        self.refresh_ports()
        if self.demo:
            self.port_var.set("DEMO (mock)")
            self.connect()

    def toggle_connect(self):
        if self.connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("未选择串口", "请先选择串口，或点“刷新”重新扫描。")
            return
        try:
            link = MockLink(self.log) if port.startswith("DEMO") else SerialLink(port, self.log)
            link.open()
        except Exception as exc:
            self.log("连接失败 %s: %s" % (port, exc))
            self._status("连接失败", bad=True)
            messagebox.showerror("串口连接失败", "%s\n\n%s" % (port, exc))
            return
        self.link, self.connected = link, True
        self.conn_btn.config(text="断开")
        self.port_cb.config(state="disabled")
        self.refresh_btn.config(state="disabled")
        self.btns["begin"].config(state="normal")
        self._status("已连接 %s" % port)
        self.log("已连接 %s（%d 8N1）" % (port, BAUD))
        self.query_info()

    def disconnect(self):
        if self.session and self.session.get("stage") != "done":
            self.abort(silent=True)
        if self.link:
            try:
                self.link.close()
            except Exception as exc:
                self.log("关闭串口异常: %s" % exc)
        self.link, self.connected = None, False
        self.conn_btn.config(text="连接")
        self.port_cb.config(state="readonly")
        self.refresh_btn.config(state="normal")
        for name in self.btns:
            self.btns[name].config(state="disabled")
        self._status("未连接", bad=True)
        self.limit_var.set("限流: —")
        self.log("已断开串口")

    def query_info(self):
        try:
            kind, fields = self._parse(self.link.command("INFO", timeout=1.5))
        except Exception as exc:
            self.log("INFO 未响应（设备信息显示 N/A，不阻断校准）: %s" % exc)
            for var in self.info_vars.values():
                var.set("N/A")
            return
        if kind == "ERR":
            self.log("INFO 被设备拒绝（%s %s），设备信息显示 N/A" % (fields[0], fields[1]))
            for var in self.info_vars.values():
                var.set("N/A")
            return
        if kind == "OK" and fields and fields[0].upper() == "INFO":
            fields = fields[1:]
        if len(fields) < 2:
            self.log("INFO 响应缺少版本字段，设备信息显示 N/A")
            for var in self.info_vars.values():
                var.set("N/A")
            return
        self.info_vars["proto"].set(fields[0])
        self.info_vars["fw"].set(fields[1])
        self.info_vars["sn"].set(fields[2] if len(fields) > 2 else "—")
        self.log("设备信息: 协议=%s 固件=%s SN=%s" % (fields[0], fields[1],
                                                     fields[2] if len(fields) > 2 else "—"))

    def _parse(self, raw):
        try:
            kind, fields = parse_line(raw)
        except ProtocolError as exc:
            raise LinkError(str(exc))
        if kind == "ERR":
            raise DeviceError(fields[0], fields[1])
        return kind, fields

    def _cmd(self, line):
        if not self.link:
            raise LinkError("串口未连接")
        return self._parse(self.link.command(line))

    def _fail_safe(self, message, ch=None):
        ch = ch or (self.session or {}).get("ch") or self.ch_var.get()
        self.log("安全中止: " + message)
        if self.link:
            try:
                raw = self.link.command("ABORT " + ch)
                kind, fields = parse_line(raw)
                if kind == "ERR":
                    self.log("自动 ABORT 返回 ERR %s %s" % (fields[0], fields[1]))
                else:
                    self.log("已自动发送 ABORT %s；未 COMMIT，未写 EEPROM" % ch)
            except Exception as exc:
                self.log("自动 ABORT 失败: %s" % exc)
        self.session = None
        self._set_active(False)
        self._status("错误已安全中止", bad=True)
        messagebox.showerror("校准已中止", message + "\n\n已尝试 ABORT；未 COMMIT，不会写 EEPROM。")

    def _link_error(self, exc):
        self._fail_safe("串口断开/超时: %s" % exc)
        self.disconnect()

    def _device_error(self, exc, ch=None):
        self.log("设备返回 ERR %s %s" % (exc.code, exc.msg))
        self._fail_safe("设备返回 ERR %s：%s" % (exc.code, exc.msg), ch)

    def _set_active(self, active):
        state = "disabled" if active else "normal"
        self.port_cb.config(state="disabled" if active else "readonly")
        self.refresh_btn.config(state="disabled" if active else "normal")
        for rb in self.ch_radios:
            rb.config(state=state)
        self.btns["begin"].config(state="disabled" if active else "normal")
        self.btns["abort"].config(state="normal" if active else "disabled")
        self.btns["read"].config(state="normal" if active else "disabled")
        self.btns["commit"].config(state="disabled")
        if not active:
            self.point_btn.config(state="disabled", text="逐点下发")
            self.limit_var.set("限流: —")

    def rebuild_table(self):
        for child in self.table.winfo_children():
            child.destroy()
        self.rows = []
        ch = self.ch_var.get()
        headers = ["序号", "设定 (%s)" % UNIT[ch], "实测 (%s)" % UNIT[ch],
                   "误差 (%s)" % UNIT[ch], "误差 (%)", "状态"]
        for col, text in enumerate(headers):
            ttk.Label(self.table, text=text, font=("Microsoft YaHei UI", 9, "bold")).grid(
                row=0, column=col, padx=4, pady=3, sticky="w")
        for idx, (caption, setpoint) in enumerate(POINTS[ch]):
            var = tk.StringVar()
            errv = tk.StringVar(value="—")
            errp = tk.StringVar(value="—")
            status = tk.StringVar(value="待下发")
            ttk.Label(self.table, text=str(idx)).grid(row=idx + 1, column=0, padx=4, pady=2)
            ttk.Label(self.table, text="%d（%s）" % (setpoint, caption)).grid(
                row=idx + 1, column=1, padx=4, pady=2, sticky="w")
            entry = ttk.Entry(self.table, textvariable=var, width=12)
            entry.grid(row=idx + 1, column=2, padx=4, pady=2)
            entry.bind("<KeyRelease>", lambda _e, i=idx: self.update_error(i))
            ttk.Label(self.table, textvariable=errv, width=14).grid(
                row=idx + 1, column=3, padx=4, pady=2, sticky="w")
            ttk.Label(self.table, textvariable=errp, width=12).grid(
                row=idx + 1, column=4, padx=4, pady=2, sticky="w")
            ttk.Label(self.table, textvariable=status).grid(
                row=idx + 1, column=5, padx=4, pady=2, sticky="w")
            self.rows.append({"var": var, "errv": errv, "errp": errp,
                              "status": status, "entry": entry})
        self.table.columnconfigure(1, weight=1)
        self.table.columnconfigure(5, weight=1)

    def on_channel(self):
        if self.session and self.session.get("stage") != "done":
            self.ch_var.set(self.session["ch"])
            return
        self.rebuild_table()

    def update_error(self, idx):
        try:
            measured = parse_value(self.rows[idx]["var"].get(), self.ch_var.get())
        except ValueError:
            self.rows[idx]["errv"].set("—")
            self.rows[idx]["errp"].set("—")
            return
        setpoint = POINTS[self.ch_var.get()][idx][1]
        diff = measured - setpoint
        self.rows[idx]["errv"].set("%+d" % diff)
        self.rows[idx]["errp"].set("%+.2f%%" % (diff / setpoint * 100))

    def begin(self):
        ch = self.ch_var.get()
        try:
            self._cmd("CAL BEGIN " + ch)
        except DeviceError as exc:
            self._device_error(exc, ch)
            return
        except LinkError as exc:
            self._link_error(exc)
            return
        self.session = {"ch": ch, "idx": 0, "stage": "set", "points": {},
                        "committed": False, "read": None}
        self.rebuild_table()
        self._set_active(True)
        self.point_btn.config(state="normal", text="下发第 1 点 SET")
        self.export_btn.config(state="normal")
        self.limit_var.set("限流: 0.5 A（设备内部）" if ch == "V" else "限流: 目标+1 A（设备内部）")
        self.log("CAL BEGIN %s OK；限流由设备校准态自动降为 %s" % (
            ch, "0.5 A" if ch == "V" else "目标点 +1 A"))
        self._status("校准中: %s 0/%d" % (ch, len(POINTS[ch])))
        self.rows[0]["status"].set("请下发 SET")

    def point(self):
        if not self.session:
            return
        ch, idx, stage = self.session["ch"], self.session["idx"], self.session["stage"]
        setpoint = POINTS[ch][idx][1]
        if stage == "set":
            try:
                self._cmd("SET %s %d %d" % (ch, idx, setpoint))
            except DeviceError as exc:
                self._device_error(exc, ch)
                return
            except LinkError as exc:
                self._link_error(exc)
                return
            self.session["stage"] = "meas"
            self.rows[idx]["status"].set("等待实测")
            self.point_btn.config(text="记录第 %d 点 MEAS" % (idx + 1))
            self._status("%s 第 %d/%d 点已设定，请输入实测值" % (
                ch, idx + 1, len(POINTS[ch])))
            self.rows[idx]["entry"].focus_set()
            return
        try:
            measured = parse_value(self.rows[idx]["var"].get(), ch)
        except ValueError as exc:
            self.log("输入非法（第 %d 点）: %s；未发送 MEAS，自动 ABORT，不写 EEPROM" % (idx + 1, exc))
            self._fail_safe("实测值非法（第 %d 点）：%s" % (idx + 1, exc), ch)
            return
        try:
            self._cmd("MEAS %s %d %d" % (ch, idx, measured))
        except DeviceError as exc:
            self._device_error(exc, ch)
            return
        except LinkError as exc:
            self._link_error(exc)
            return
        self.session["points"][idx] = measured
        self.rows[idx]["status"].set("已记录")
        self.rows[idx]["entry"].config(state="disabled")
        self.update_error(idx)
        self.log("第 %d 点: SET=%d MEAS=%d 误差=%+d %s" % (
            idx, setpoint, measured, measured - setpoint, UNIT[ch]))
        if idx + 1 >= len(POINTS[ch]):
            self.session["stage"] = "ready"
            self.point_btn.config(state="disabled", text="全部点已完成")
            self.btns["commit"].config(state="normal")
            self._status("全部点已记录，请 CAL COMMIT")
            self.log("全部 %d 点完成；COMMIT 前 EEPROM 未写" % len(POINTS[ch]))
        else:
            self.session["idx"], self.session["stage"] = idx + 1, "set"
            self.point_btn.config(text="下发第 %d 点 SET" % (idx + 2))
            self._status("本点完成，请下发下一点")

    def commit(self):
        if not self.session or self.session["stage"] != "ready":
            messagebox.showwarning("未就绪", "请先完成全部校准点。")
            return
        ch = self.session["ch"]
        try:
            self._cmd("COMMIT " + ch)
        except DeviceError as exc:
            self._device_error(exc, ch)
            return
        except LinkError as exc:
            self._link_error(exc)
            return
        self.session["committed"] = True
        self.btns["commit"].config(state="disabled")
        self.log("COMMIT %s OK；设备端已写 EEPROM，开始自动回读校验" % ch)
        self._status("COMMIT OK，回读 CRC 校验中…")
        self.read(auto=True)

    def read(self, auto=False):
        ch = self.session["ch"] if self.session else self.ch_var.get()
        try:
            kind, fields = self._cmd("READ " + ch)
        except DeviceError as exc:
            self._device_error(exc, ch)
            return
        except LinkError as exc:
            self._link_error(exc)
            return
        if not fields:
            self.crc_var.set("设备未回传状态/CRC")
            self._status("READ OK，但响应缺少 CRC", bad=True)
            self.log("READ %s OK，但响应无状态/版本/CRC 字段，无法完成回读校验" % ch)
            if self.session and self.session.get("committed"):
                self.session["read"] = {"crc": None, "verified": False}
                self._finish()
            return
        try:
            state, active, version = int(fields[0]), int(fields[1]), int(fields[2])
            crc_text = fields[3] if len(fields) > 3 else None
        except (ValueError, IndexError):
            self.crc_var.set("READ 字段解析失败: %s" % " ".join(fields))
            self._status("READ 响应格式错误", bad=True)
            self.log("READ 响应格式错误: %s" % " ".join(fields))
            if self.session and self.session.get("committed"):
                self.session["read"] = {"crc": None, "verified": False}
                self._finish()
            return
        if not self.session or self.session.get("stage") != "ready" and not self.session.get(
                "committed"):
            self.log("READ: state=%d active=%d version=%d" % (state, active, version))
            self._status("设备返回 state=%d（未完成/未提交）" % state, bad=True)
            return
        points = [(POINTS[ch][i][1], self.session["points"][i]) for i in range(len(POINTS[ch]))]
        expected = cal_crc(ch, version, points)
        try:
            actual = int(crc_text, 16) if crc_text else None
        except ValueError:
            actual = None
        verified = actual == expected
        self.session["read"] = {"state": state, "active": active, "version": version,
                                "crc": crc_text, "verified": verified}
        if crc_text and verified:
            maxerr = max(abs(self.session["points"][i] - POINTS[ch][i][1])
                         for i in range(len(POINTS[ch])))
            avg = sum(abs(self.session["points"][i] - POINTS[ch][i][1])
                      for i in range(len(POINTS[ch]))) / len(POINTS[ch])
            self.crc_var.set("CRC 设备=%04X 期望=%04X → PASS" % (actual, expected))
            self._status("CRC PASS 最大误差 %d %s" % (maxerr, UNIT[ch]))
            self.log("READ %s: state=%d active=%d version=%d CRC=%04X 校验 PASS；"
                     "误差汇总 最大=%d %s 平均=%.2f %s" % (
                         ch, state, active, version, actual, maxerr, UNIT[ch], avg, UNIT[ch]))
        elif crc_text:
            self.crc_var.set("CRC 设备=%s 期望=%04X → FAIL" % (crc_text, expected))
            self._status("READ CRC 校验 FAIL", bad=True)
            self.log("READ CRC 校验 FAIL: 设备=%s 期望=%04X" % (crc_text, expected))
            messagebox.showerror("CRC 校验失败", "回读 CRC 与本机按标定点计算的期望值不一致。\n"
                                 "设备=%s 期望=%04X\n请勿放行，检查固件 CRC 覆盖范围/点表。"
                                 % (crc_text, expected))
        else:
            self.crc_var.set("设备未回传 CRC")
            self._status("READ OK，但缺 CRC", bad=True)
            self.log("READ 响应缺少 CRC 字段，回读校验未完成")
        if self.session.get("committed"):
            self._finish()

    def _finish(self):
        if self.session:
            self.session["stage"] = "done"
        self._set_active(False)
        if self.connected:
            self.btns["read"].config(state="normal")

    def abort(self, silent=False):
        ch = (self.session or {}).get("ch") or self.ch_var.get()
        if self.link:
            try:
                self._cmd("ABORT " + ch)
                self.log("ABORT %s OK；校准态中止，未 COMMIT，未写 EEPROM" % ch)
            except Exception as exc:
                self.log("ABORT 失败/已断开: %s" % exc)
        self.session = None
        self._set_active(False)
        self._status("已中止（未写 EEPROM）", bad=True)
        if not silent:
            messagebox.showinfo("已中止", "已发送 CAL ABORT；未执行 COMMIT，EEPROM 未被本次写入。")

    def export_csv(self):
        ch = self.ch_var.get()
        pairs = []
        for idx in range(len(POINTS[ch])):
            text = self.rows[idx]["var"].get().strip() if self.rows else ""
            if not text:
                continue
            try:
                pairs.append((idx, POINTS[ch][idx][1], parse_value(text, ch)))
            except ValueError:
                continue
        if not pairs:
            messagebox.showwarning("无数据", "还没有可导出的实测值。")
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sn = self.info_vars["sn"].get() or "unknown"
        path = filedialog.asksaveasfilename(
            title="导出校准 CSV", defaultextension=".csv",
            initialfile="calib_%s_%s.csv" % (sn, stamp),
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        if not path:
            self.log("已取消 CSV 导出")
            return
        read = (self.session or {}).get("read") or {}
        if read.get("verified"):
            result = "PASS"
        elif read.get("crc"):
            result = "FAIL"
        else:
            result = "UNVERIFIED" if read else "NOT_COMMITTED"
        expected = ""
        if read and self.session and len(self.session["points"]) == len(POINTS[ch]):
            expected = "%04X" % cal_crc(ch, read.get("version", 0), [
                (POINTS[ch][i][1], self.session["points"][i])
                for i in range(len(POINTS[ch]))])
        header = ["时间", "环境温度(°C)", "万用表型号", "协议版本", "固件版本", "序列号",
                  "通道", "序号", "设定值", "单位", "实测值", "误差", "误差(%)",
                  "校准状态", "CRC设备", "CRC期望", "结果"]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow(header)
                for idx, setpoint, measured in pairs:
                    diff = measured - setpoint
                    actual = read.get("crc") if read else ""
                    writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                     self.temp_var.get(), self.dmm_var.get(),
                                     self.info_vars["proto"].get(), self.info_vars["fw"].get(),
                                     sn, ch, idx, setpoint, UNIT[ch], measured, diff,
                                     "%.2f" % (diff / setpoint * 100), result, actual, expected, result])
        except Exception as exc:
            self.log("CSV 导出失败: %s" % exc)
            messagebox.showerror("导出失败", str(exc))
            return
        self.log("CSV 已导出: %s（%d 点，结果=%s）" % (path, len(pairs), result))
        self._status("CSV 已导出")

    def on_close(self):
        if self.session and self.session.get("stage") != "done":
            self.abort(silent=True)
        if self.link:
            try:
                self.link.close()
            except Exception:
                pass
        self.destroy()


def run_selftest():
    logs = []
    link = MockLink(logs.append)
    link.open()

    def cmd(line):
        kind, fields = parse_line(link.command(line))
        if kind == "ERR":
            raise DeviceError(fields[0], fields[1])
        return kind, fields

    kind, fields = cmd("INFO")
    assert kind == "OK" and fields[:3] == ["INFO", "1.0", "0.9.0"], fields
    print("PASS INFO: " + " ".join(fields))
    for ch in ("V", "I"):
        cmd("CAL BEGIN " + ch)
        for idx, (_, setpoint) in enumerate(POINTS[ch]):
            cmd("SET %s %d %d" % (ch, idx, setpoint))
            measured = setpoint - 3 if ch == "V" else setpoint - 2
            cmd("MEAS %s %d %d" % (ch, idx, measured))
        cmd("COMMIT " + ch)
        kind, fields = cmd("READ " + ch)
        state, active, version, crc = fields[0], fields[1], int(fields[2]), int(fields[3], 16)
        points = [(POINTS[ch][i][1], POINTS[ch][i][1] - (3 if ch == "V" else 2))
                  for i in range(len(POINTS[ch]))]
        assert state == "2" and active == "1" and crc == cal_crc(ch, version, points)
        print("PASS %s: points=%d state=%s active=%s version=%d CRC=%04X" % (
            ch, len(POINTS[ch]), state, active, version, crc))
    try:
        cmd("NOPE")
        raise AssertionError("ERR not raised")
    except DeviceError as exc:
        print("PASS ERR handling: ERR %s %s" % (exc.code, exc.msg))
    for bad in ("abc", "-1", "999999"):
        try:
            parse_value(bad, "V")
            raise AssertionError("invalid value accepted: " + bad)
        except ValueError:
            print("PASS invalid input: %r rejected" % bad)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "calib.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(["时间", "环境温度(°C)", "万用表型号", "固件版本", "设定值", "实测值"])
            writer.writerow(["2026-11-18 12:00:00", "25", "DMM-DEMO", "0.9.0", 500, 497])
        with open(path, encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
        assert len(rows) == 2 and rows[1][3] == "0.9.0" and rows[1][5] == "497"
        print("PASS CSV: %d rows" % len(rows))
    print("RESULT: PASS (%d commands logged)" % len([x for x in logs if x.startswith("TX>")]))


def main():
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--demo", action="store_true", help="use built-in mock device")
    parser.add_argument("--selftest", action="store_true", help="run offline protocol/CSV self-test")
    args = parser.parse_args()
    if args.selftest:
        try:
            run_selftest()
            return 0
        except Exception as exc:
            print("RESULT: FAIL %s" % exc)
            return 1
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = App(demo=args.demo)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
