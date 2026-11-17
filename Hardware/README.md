# Hardware/：立创EDA 工程与导出

本目录存放本项目的**立创EDA 工程与导出文件**：

- 立创EDA 工程源文件（如 `*.epro`、工程 JSON、自定义器件库）；
- 原理图 / PCB 的 PDF、Gerber、BOM、装配图等导出文件。

## 版本库约定

- **工程文件与导出文件不进 git**：根目录 `.gitignore` 用 `/Hardware/*` 排除本目录内容，避免二进制/大体积工程和本地自动保存状态污染仓库历史。
- **本 README 入库**：`.gitignore` 用 `!/Hardware/README.md` 单独放行本文件。git 不跟踪空目录，保留本文件可让 `clone` 后 `Hardware/` 仍然存在，供立创EDA 工程落地。
- 如需再放行其他说明性文本，请先在 `.gitignore` 增加 `!` 规则并在本 README 说明原因；工程/导出件请勿用 `git add -f` 强行入库。

## 相关

- 硬件设计口径与图纸说明见根 `README.md` 第 4、5 节。
- 固件源码在 `firmware/`，不在本目录。
