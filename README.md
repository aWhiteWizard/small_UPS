# 小型PSU电源（small_UPS）

> 仓库名沿用历史命名 `small_UPS`；现行定版为**数控可调直流电源（PSU）**，不是 UPS（不间断电源）。

## 1. 项目定位

- 数控可调直流电源：目标输出 0–48V、最大 5A，经 I2C 设定电压/电流，具备过压、过流、短路、过温等保护（具体指标以需求冻结工单为准）。
- 由两块板组成：**电源本体**（金手指模块，含 AC/DC 与输出级）+ **电源调试板**（显示、按键、PT100）。
- 交付范围：**硬件 + 固件，不含上位机软件**。
- 当前处于项目编制/需求确认阶段，具体参数、针脚表与寄存器表以冻结版需求文档为准。

## 2. 技术栈

| 层 | 选型 / 计划 |
|---|---|
| 硬件设计 | 立创EDA 专业版，工程维护于本地 `Hardware/`（不进 git） |
| 功率拓扑 | AC/DC + 同步 Buck（以需求冻结为准） |
| 控制 | STM32（具体型号以需求冻结为准），C + HAL/LL |
| 构建 | CMake 或 Makefile + `arm-none-eabi-gcc`（T-0002 固化版本） |
| 通信 | I2C，地址 0x30–0x3F 由拨码设定 |
| 调试/测试 | SWD（ST-Link/OpenOCD）、主机侧单元测试 |

## 3. 目录约定

```text
small_UPS/
├── README.md            # 项目定位、目录约定、忽略规则
├── .gitignore           # 硬件工程 / 构建产物 / IDE 配置忽略规则
├── firmware/            # 固件源码（入库）
│   └── README.md        # 固件目录说明
├── Hardware/            # 立创EDA 工程与导出（仅本地，整目录不入库）
│   └── README.md        # 目录说明（随目录一起被忽略）
└── .agent/              # 流程看板、工作日志与证据（执行器维护）
```

- `firmware/`：STM32 源码、链接脚本、启动文件、构建脚本、单元测试；构建产物不入库。
- `Hardware/`：立创EDA 工程、自定义库、BOM、原理图/PCB 导出、Gerber、装配图；**只在本地维护**。
- 硬件审阅导出件（PDF/BOM/图片）：需要入库时再按需创建 `docs/`；本单不建空目录。
- 约定：新代码进 `firmware/`，新硬件资料进 `Hardware/`；需要评审的导出件按需另建 `docs/`。

## 4. 硬件图纸为什么不进 git

1. 立创EDA 工程是二进制/大体积文件，diff 不可读、无法有效评审，冲突几乎不可合并。
2. 工程自动保存频繁，容易把临时文件、备份、缓存带进历史，仓库迅速膨胀。
3. 硬件版本以立创EDA 工程历史 + 本地备份为准；进 git 的应当是**导出审阅件**（PDF/图片/BOM），按需放 `docs/`。
4. 固件按冻结的针脚表/寄存器表开发，接口文档入库即可，无需依赖工程源文件。

因此 `Hardware/` **整个目录**被 `.gitignore` 排除；请勿使用 `git add -f Hardware/...` 绕过。目录内的 `Hardware/README.md` 仅本机存在，作用与本节一致。

## 5. 被忽略路径清单

| 类别 | `.gitignore` 规则 | 覆盖路径示例 |
|---|---|---|
| 硬件工程 | `/Hardware/` | `Hardware/small_ups.epro`、`Hardware/exports/v1/psu.pdf` |
| 构建目录 | `build/`、`cmake-build-*/`、`.pio/` | `firmware/build/`、`firmware/cmake-build-debug/` |
| 构建产物 | `*.o`、`*.elf`、`*.bin`、`*.hex`、`*.map`、`*.lst`、`*.d`、`*.su` | `firmware/build/main.o`、`firmware/build/app.elf` |
| 立创EDA 备份/临时 | `*.bak`、`*.bak.*`、`*_bak`、`*.backup`、`*.autosave`、`*.tmp`、`*.temp`、`*~`、`*.lck`、`.~lock.*`、`*.swp`、`*.swo`、`backup/`、`history/` | `Hardware/backup/...`、`project.epro.bak`、`.~lock.x.epro#` |
| IDE 配置 | `.vscode/`、`.idea/`、`.vs/`、`.settings/`、`.metadata/`、`.clangd/` | `.vscode/settings.json`、`.idea/workspace.xml` |
| 系统杂项 | `Thumbs.db`、`Desktop.ini`、`.DS_Store` | 资源管理器/访达缓存 |

验证命令：

```bash
git status --porcelain=v1 --untracked-files=all   # Hardware/ 内文件不应出现
git check-ignore -v Hardware/<任意文件>            # 应命中 /Hardware/ 规则
```

## 6. 当前状态

- T-0001：完成仓库初始化（目录骨架、忽略规则、本文档）。
- T-0002：落地 STM32 工具链、HAL/LL、构建系统与烧写调试链路。
- 后续：需求冻结后按需创建 `docs/`，补针脚表、寄存器表与测试记录。
