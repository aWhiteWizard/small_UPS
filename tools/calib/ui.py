"""连接与设备页（T-0025）：枚举/刷新/连接/断开/重连、设备信息、收发原文日志。"""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .device import DeviceInfoError, query_device_info
from .serial_link import LinkError, SerialLink, list_ports


class SerialPanel(ttk.Frame):
    """可独立运行、也可被 T-0027 完整界面嵌入的串口连接面板。"""

    def __init__(self, master, serial_factory=None):
        super().__init__(master, padding=8)
        self._ports: list = []
        self._factory = serial_factory
        self.link: SerialLink | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        style = ttk.Style(self)
        style.configure("LinkOk.TLabel", foreground="#0b7a0b")
        style.configure("LinkBad.TLabel", foreground="#b00020")
        style.configure("LinkWarn.TLabel", foreground="#a15c00")
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="串口:").pack(side="left")
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(bar, textvariable=self.port_var, width=32, state="readonly")
        self.port_box.pack(side="left", padx=4)
        self.refresh_btn = ttk.Button(bar, text="刷新", command=self.refresh)
        self.refresh_btn.pack(side="left", padx=2)
        self.connect_btn = ttk.Button(bar, text="连接", command=self.toggle)
        self.connect_btn.pack(side="left", padx=2)
        self.reconnect_btn = ttk.Button(bar, text="重连", command=self.reconnect, state="disabled")
        self.reconnect_btn.pack(side="left", padx=2)
        self.state_var = tk.StringVar(value="● 未连接")
        self.state_lbl = ttk.Label(self, textvariable=self.state_var, style="LinkBad.TLabel")
        self.state_lbl.pack(anchor="w", pady=(6, 0))
        info = ttk.LabelFrame(self, text="设备信息（INFO）", padding=6)
        info.pack(fill="x", pady=6)
        self.info_var = tk.StringVar(value="协议版本：— ｜ 固件版本：— ｜ 序列号：—")
        ttk.Label(info, textvariable=self.info_var).pack(anchor="w")
        logf = ttk.LabelFrame(self, text="收发原文日志（含时间戳）", padding=4)
        logf.pack(fill="both", expand=True)
        self.log_text = ScrolledText(logf, height=14, state="disabled", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

    def _append(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_status(self, text: str, style: str) -> None:
        self.state_var.set("● " + text)
        self.state_lbl.configure(style=style)

    def _on_state(self, state) -> None:
        self._set_status(state.text, "LinkOk.TLabel" if state.connected else "LinkBad.TLabel")
        self.connect_btn.configure(text="断开" if state.connected else "连接")
        self.refresh_btn.configure(state="disabled" if state.connected else "normal")
        self.port_box.configure(state="disabled" if state.connected else "readonly")
        self.reconnect_btn.configure(state="disabled" if state.connected else "normal")

    def _report(self, message: str) -> None:
        self._set_status(message, "LinkBad.TLabel")
        self._append(f"[{datetime.now():%H:%M:%S}] ! {message}")
        messagebox.showerror("串口错误", message, parent=self)

    def refresh(self) -> None:
        if self.link is not None and self.link.state.connected:
            return
        try:
            self._ports = list_ports()
        except LinkError as exc:
            self._ports = []
            self.port_box["values"] = []
            self._set_status(f"串口枚举失败：{exc}", "LinkBad.TLabel")
            self._append(f"! 串口枚举失败：{exc}")
            return
        self.port_box["values"] = [p.label() for p in self._ports]
        if self._ports:
            self.port_box.current(0)
            self._set_status(f"发现 {len(self._ports)} 个串口，未连接", "LinkWarn.TLabel")
            self._append(f"--- 枚举到 {len(self._ports)} 个串口：{', '.join(p.device for p in self._ports)} ---")
        else:
            self._set_status("无可用串口（无设备）：请检查 USB 连接、设备供电与驱动", "LinkBad.TLabel")
            self.info_var.set("协议版本：— ｜ 固件版本：— ｜ 序列号：—")
            self._append("--- 枚举到 0 个串口（无设备）---")
        self.reconnect_btn.configure(state="disabled")

    def _read_info(self) -> None:
        try:
            info = query_device_info(self.link)
        except (DeviceInfoError, LinkError) as exc:
            self.info_var.set("设备信息读取失败：" + str(exc))
            self._set_status(f"设备信息读取失败：{exc}", "LinkWarn.TLabel")
            self._append(f"! 设备信息读取失败：{exc}")
            return
        self.info_var.set(info.display())
        self._append(f"--- 设备信息：{info.display()} ---")

    def _connect(self) -> None:
        text = self.port_var.get()
        port = next((p.device for p in self._ports if text in (p.device, p.label())), text)
        if not self._ports and not self._factory:
            self._report("无可用串口（无设备）：请检查 USB 连接、设备供电与驱动后点“刷新”")
            return
        self.link = SerialLink(port=port, log=self._append, on_status=self._on_state,
                               serial_factory=self._factory)
        try:
            self.link.connect()
        except LinkError as exc:
            self._report(str(exc))
            return
        self._read_info()

    def toggle(self) -> None:
        if self.link is not None and self.link.state.connected:
            self.link.disconnect("用户断开")
            self.info_var.set("协议版本：— ｜ 固件版本：— ｜ 序列号：—")
        else:
            self._connect()

    def reconnect(self) -> None:
        if self.link is None:
            self._connect()
            return
        try:
            self.link.reconnect()
        except LinkError as exc:
            self._report(str(exc))
            return
        self._read_info()

    def destroy(self) -> None:
        if self.link is not None:
            self.link.disconnect("面板关闭")
        super().destroy()
