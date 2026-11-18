"""启动 PSU 标定工具完整界面（T-0027）：在 ``tools`` 目录执行 ``py -3 -m calib``。"""
import tkinter as tk

from .app import CalibApp


def main() -> None:
    root = tk.Tk()
    root.title("PSU 标定工具 · T-0027（设备信息 / 五点表 / 状态日志）")
    root.geometry("1320x880")
    root.minsize(1120, 760)
    app = CalibApp(root)
    app.pack(fill="both", expand=True)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


if __name__ == "__main__":
    main()
