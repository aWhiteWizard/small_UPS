"""设备信息读取（T-0025）：协议版本、固件版本、序列号（若有）。"""
from __future__ import annotations

from dataclasses import dataclass


class DeviceInfoError(Exception):
    """设备信息不可用；message 可直接展示。"""


@dataclass(frozen=True)
class DeviceInfo:
    protocol: str | None = None
    firmware: str | None = None
    serial_number: str | None = None
    raw: str = ""

    def display(self) -> str:
        return (f"协议版本：{self.protocol or '未提供'} ｜ 固件版本：{self.firmware or '未提供'}"
                f" ｜ 序列号：{self.serial_number or '未提供'}")


def parse_info(reply: str) -> DeviceInfo:
    """解析 ``OK INFO <协议> <固件> [序列号]``；缺字段/ERR/格式不符抛出明确文案。"""
    parts = reply.strip().split()
    if not parts:
        raise DeviceInfoError("设备信息读取失败：设备返回空回包")
    if parts[0].upper() == "ERR":
        raise DeviceInfoError(
            f"设备信息读取失败：设备不支持 INFO 或当前不可读（ERR {' '.join(parts[1:]) or '未给出错误码'}）")
    if parts[0].upper() == "OK":
        parts = parts[1:]
    if not parts or parts[0].upper() != "INFO":
        raise DeviceInfoError(
            f"设备信息读取失败：无法识别回包 {reply.strip()!r}（预期 OK INFO <协议> <固件> [序列号]）")
    fields = parts[1:]
    return DeviceInfo(*(fields[i] if i < len(fields) else None for i in range(3)), reply.strip())


def query_device_info(link) -> DeviceInfo:
    """发送 INFO 并解析；串口超时/断线异常原样抛出，由界面按错误类型显示文案。"""
    return parse_info(link.send("INFO"))
