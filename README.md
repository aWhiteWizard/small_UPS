# 小型PSU电源（small_UPS）

> 仓库名沿用历史命名 `small_UPS`；现行定版为**数控可调直流电源（PSU）**，不是 UPS（不间断电源）。

## 1. 项目定位

- 数控可调直流电源：设定 0–48V、最大 5A，保证指标 0.5–48V；经 I2C 设定电压/电流，具备过压、过流、短路、过温等保护（具体指标以需求冻结工单为准）。
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
├── README.md            # 项目定位、目录约定、文档地图、填写规则
├── .gitignore           # 硬件工程 / 构建产物 / IDE 配置忽略规则
├── firmware/            # 固件源码（入库）
│   └── README.md        # 固件目录说明
├── docs/                # 设计摘要页（正文已归并至 .agent/docs，不再承载正文）
│   ├── architecture.md  # → .agent/docs/architecture.md §1–§5
│   ├── module-design.md # → .agent/docs/modules.md §1–§2
│   ├── interface.md     # → .agent/docs/architecture.md §6–§9
│   └── test-plan.md     # → .agent/docs/architecture.md §10
├── Hardware/            # 立创EDA 工程与导出（仅本地，整目录不入库）
│   └── README.md        # 目录说明（随目录一起被忽略）
└── .agent/              # 流程看板、工作日志与证据（执行器维护）
    ├── docs/            # 唯一事实源：requirements.md / architecture.md / modules.md
    ├── requirements.md  # 已迁移，仅历史（见 .agent/docs/requirements.md）
    └── requirements-draft.md  # 历史草稿，仅追溯
```

- `firmware/`：STM32 源码、链接脚本、启动文件、构建脚本、单元测试；构建产物不入库。
- `Hardware/`：立创EDA 工程、自定义库、BOM、原理图/PCB 导出、Gerber、装配图；**只在本地维护**。
- `docs/`：四份设计**摘要页**，只引用 `.agent/docs` 对应章节，不再承载正文；不得在 `docs/` 新增设计内容。硬件审阅导出件（PDF/BOM/图片）作为证据放 `.agent/evidence/` 或工单指定位置，不塞进 `docs/`。
- `.agent/docs/`：**唯一事实源**——`requirements.md`（需求）、`architecture.md`（架构/接口/时序/升级/测试）、`modules.md`（功能模块设计）。审查/验收只认这三份。
- `.agent/requirements.md`：已迁移，仅作历史追溯；`requirements-draft.md`、`mech-draft.md` 同样仅历史，不作为审查/执行依据。
- 约定：新代码进 `firmware/`，新硬件资料进 `Hardware/`，需求只进 `.agent/docs/requirements.md`，架构/接口只进 `.agent/docs/architecture.md`，模块设计只进 `.agent/docs/modules.md`。

## 4. 硬件图纸为什么不进 git

1. 立创EDA 工程是二进制/大体积文件，diff 不可读、无法有效评审，冲突几乎不可合并。
2. 工程自动保存频繁，容易把临时文件、备份、缓存带进历史，仓库迅速膨胀。
3. 硬件版本以立创EDA 工程历史 + 本地备份为准；进 git 的应当是**导出审阅件**（PDF/图片/BOM），按需作为证据入库。
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
- T-0002：计划落地 STM32 工具链、HAL/LL、构建系统与烧写调试链路。
- T-0015：完成 `docs/` 四份设计骨架（仅标题/表头/待填占位）。
- T-0016：完成需求第 1/2 部分合并为 `.agent/requirements.md` v0.3（五章 + 完成度表 + 填写规则），删除 `requirements-part2.md`，建立本文档地图。
- T-0034：正文归并（v2.0）——需求正文整体迁入 `.agent/docs/requirements.md`；`docs/` 四份降为摘要页；`.agent/requirements.md` 标注仅历史；迁移对照与校验见需求附录 F。
- 后续：按第 8 节规则只改 `.agent/docs` 三份，不再新建需求/设计散文档。

## 7. 文档地图

> 唯一索引。完成度表（章节 × 状态 × 负责单号）在 `.agent/docs/requirements.md` 开头；状态只用 **已定稿 / 待填写 / 待确认** 三档。审查/验收只认前三行三份正文。

| 文档 | 用途 | 负责单号 | 当前状态 |
|---|---|---|---|
| `.agent/docs/requirements.md` | 需求唯一事实源：§1–§5 + 附录 A–F；含完成度表、填写规则、迁移对照与校验 | T-0004/T-0005 定稿；T-0016 合并；T-0034 归并 | 已定稿（v2.0） |
| `.agent/docs/architecture.md` | 架构/接口/时序/升级/测试唯一事实源：§1–§12 | T-0034 归并；原 T-0015 骨架 | 骨架（正文待 T-0006/T-0007/T-0009/T-0010/T-0011 填充） |
| `.agent/docs/modules.md` | 功能模块设计唯一事实源：§1 本体 8 模块、§2 调试板 6 模块、§3–§6 | T-0034 归并；原 T-0015 骨架 | 骨架（待 T-0011/T-0006/T-0009/T-0010 填充） |
| `docs/architecture.md` | 摘要页 → `.agent/docs/architecture.md` §1–§5 | T-0034 | 引用页（无正文） |
| `docs/module-design.md` | 摘要页 → `.agent/docs/modules.md` §1–§2 | T-0034 | 引用页（无正文） |
| `docs/interface.md` | 摘要页 → `.agent/docs/architecture.md` §6–§9 | T-0034 | 引用页（无正文） |
| `docs/test-plan.md` | 摘要页 → `.agent/docs/architecture.md` §10 | T-0034 | 引用页（无正文） |
| `.agent/requirements.md` | 已迁移，仅历史追溯 | T-0034 标注 | 历史（不作审查依据） |
| `.agent/requirements-draft.md` / `.agent/mech-draft.md` | 历史草稿，仅追溯 | 历史 | 历史（不作审查依据） |

- `requirements-part2.md` 已于 T-0016 删除，内容并入 `.agent/docs/requirements.md` 第 2/3/5 章；逐节映射与删除原因见该文件附录 D，历史全文可查 git 历史。
- 文档状态变化时，同步更新本表与 `.agent/docs/requirements.md` 完成度表；两处不得互相矛盾。

## 8. 文档填写规则（后续所有工单必须遵守）

1. **报告必写落点**：每张后续工单的 done 报告必须写明「写入文件:章节」与章节范围（示例：`.agent/docs/requirements.md:3.3.3`、`.agent/docs/architecture.md:7.2`、`.agent/docs/modules.md:1.6`）。禁止新建独立需求/设计文档。
2. **需求改动**：只改 `.agent/docs/requirements.md` 对应章节，并在附录 C「变更记录」追加一行（日期/单号/改了什么）；不得另起文件，不得把需求复制到 `docs/`。
3. **设计展开**：设计细节只写 `.agent/docs/architecture.md`（架构/接口/时序/升级/测试）或 `.agent/docs/modules.md`（功能模块设计）的对应章节；`docs/` 四份自 T-0034 起只是引用页，不再承载正文。需求与设计不得互相复制——需求只写“要什么”，设计只写“怎么做”。
4. **未成文不预造**：未完成章节写「待填（来源：T-00xx）」；待 owner 拍板的写「待确认（owner）」，不猜默认值。
5. **状态同步**：文档状态/负责单号变化时，同步更新第 7 节文档地图与 `.agent/docs/requirements.md` 完成度表；只改状态，不改历史变更记录。
