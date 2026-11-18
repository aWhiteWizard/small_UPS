"""独立启动 T-0025「串口与设备」页：在 ``tools`` 目录执行 ``py -3 -m calib``。"""
import tkinter as tk

from .ui import SerialPanel


def main() -> None:
    root = tk.Tk()
    root.title("PSU 标定工具 · 串口与设备（T-0025）")
    root.geometry("900x580")
    SerialPanel(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
