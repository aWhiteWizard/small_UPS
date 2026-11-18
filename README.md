# 小型PSU电源（small_UPS）

> 仓库名沿用历史命名 `small_UPS`；现行定版为**数控可调直流电源（PSU）**，不是 UPS（不间断电源）。

## 1. 项目定位

- 数控可调直流电源：设定 0–48V、最大 5A，保证指标 0.5–48V；经 I2C 设定电压/电流，具备过压、过流、短路、过温等保护（具体指标以需求冻结工单为准）。
- 由两块板组成：**电源本体**（金手指模块，含 AC/DC 与输出级、后面板故障灯）+ **电源调试板**（2×4 位数码管只显示实测 V/I、按键、PT100）。
- 交付范围：**硬件 + 固件 + PC 配置/标定工具（软件，必需服务工具，不进整机 BOM）**；不提供上位机产品功能/仪器程控（SCPI/云/无线等）。
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
├── .gitignore           # 硬件工程 / 构建产物 / IDE 配置 / 影运行期记录忽略规则
├── firmware/            # 固件源码（入库）
│   └── README.md        # 固件目录说明
├── docs/                # 设计摘要页（正文已归并至 .agent/docs，不再承载正文）
│   ├── architecture.md  # → .agent/docs/architecture.md §1–§5
│   ├── module-design.md # → .agent/docs/modules.md §1–§2
│   ├── interface.md     # → .agent/docs/architecture.md §6–§9
│   └── test-plan.md     # → .agent/docs/architecture.md §10
├── Hardware/            # 立创EDA 工程与导出（内容仅本地，不入库）
│   └── README.md        # 目录说明（入库，保住 clone 后的目录）
└── .agent/              # 流程看板（入库）与运行期记录（不入库）
    ├── docs/            # 唯一事实源：requirements.md / architecture.md / modules.md
    ├── requirements.md  # 已迁移，仅历史（见 .agent/docs/requirements.md）
    └── requirements-draft.md  # 历史草稿，仅追溯
```

- `firmware/`：STM32 源码、链接脚本、启动文件、构建脚本、单元测试；构建产物不入库。
- `Hardware/`：立创EDA 工程、自定义库、BOM、原理图/PCB 导出、Gerber、装配图；**只在本地维护（`README.md` 除外，入库占位）**。
- `docs/`：四份**设计摘要页**，只引用 `.agent/docs` 对应章节，不再承载正文；不得在 `docs/` 新增设计内容。硬件审阅导出件（PDF/BOM/图片）作为证据放 `.agent/evidence/` 或工单指定位置，不塞进 `docs/`。
- `.agent/docs/`：**唯一事实源**——`requirements.md`（需求）、`architecture.md`（架构/接口/时序/升级/测试）、`modules.md`（功能模块设计）。审查/验收只认这三份。
- `.agent/requirements.md`：已迁移，仅作历史追溯；`requirements-draft.md`、`mech-draft.md` 同样仅历史，不作为审查/执行依据。
- 约定：新代码进 `firmware/`，新硬件资料进 `Hardware/`，需求只进 `.agent/docs/requirements.md`，架构/接口只进 `.agent/docs/architecture.md`，模块设计只进 `.agent/docs/modules.md`。

## 4. 硬件图纸为什么不进 git

1. 立创EDA 工程是二进制/大体积文件，diff 不可读、无法有效评审，冲突几乎不可合并。
2. 工程自动保存频繁，容易把临时文件、备份、缓存带进历史，仓库迅速膨胀。
3. 硬件版本以立创EDA 工程历史 + 本地备份为准；进 git 的应当是**导出审阅件**（PDF/图片/BOM），按需作为证据入库。
4. 固件按冻结的针脚表/寄存器表开发，接口文档入库即可，无需依赖工程源文件。

因此 `Hardware/` 的内容（`README.md` 除外）由 `.gitignore` 的 `/Hardware/*` 排除，`README.md` 由 `!/Hardware/README.md` 放行入库；请勿使用 `git add -f Hardware/...` 绕过。保留该 README 是为了让 clone 后 `Hardware/` 目录仍然存在（git 不跟踪空目录），工程文件依旧只在本地维护。

## 5. 被忽略路径清单

| 类别 | `.gitignore` 规则 | 覆盖路径示例 |
|---|---|---|
| 硬件工程（README 除外） | `/Hardware/*`、`!/Hardware/README.md` | `Hardware/small_ups.epro`、`Hardware/exports/v1/psu.pdf`（`Hardware/README.md` 入库） |
| 构建目录 | `build/`、`cmake-build-*/`、`.pio/` | `firmware/build/`、`firmware/cmake-build-debug/` |
| 构建产物 | `*.o`、`*.elf`、`*.bin`、`*.hex`、`*.map`、`*.lst`、`*.d`、`*.su` | `firmware/build/main.o`、`firmware/build/app.elf` |
| 立创EDA 备份/临时 | `*.bak`、`*.bak.*`、`*_bak`、`*.backup`、`*.autosave`、`*.tmp`、`*.temp`、`*~`、`*.lck`、`.~lock.*`、`*.swp`、`*.swo`、`backup/`、`history/` | `Hardware/backup/...`、`project.epro.bak`、`.~lock.x.epro#` |
| IDE 配置 | `.vscode/`、`.idea/`、`.vs/`、`.settings/`、`.metadata/`、`.clangd/` | `.vscode/settings.json`、`.idea/workspace.xml` |
| 系统杂项 | `Thumbs.db`、`Desktop.ini`、`.DS_Store` | 资源管理器/访达缓存 |
| 影运行期记录 | `.agent/tx/`、`.agent/worklogs/`、`.agent/evidence/` | 调用流水、单 worklog、单证据（均不入库） |

验证命令：

```bash
# Hardware/ 内除 README 外的文件不应出现在 status 中
git status --porcelain=v1 --untracked-files=all

# 工程文件被 /Hardware/* 忽略：exit 0，输出命中规则
git check-ignore -v --no-index Hardware/<任意工程文件>

# 已跟踪文件默认不参与 check-ignore（exit 1、无输出）；加 --no-index 才能看到负向规则
git check-ignore -v --no-index Hardware/README.md   # 输出 !/Hardware/README.md（负向规则，即不忽略）
git check-ignore -q --no-index Hardware/README.md; echo $?   # 1 = 未忽略

# README 已在库中（clone 后目录存在）
git ls-files --error-unmatch Hardware/README.md
```

## 6. 当前状态

- T-0001：完成仓库初始化（目录骨架、忽略规则、本文档）。
- T-0002：完成 STM32 工具链/HAL/CMake/OpenOCD/串口环境与最小点灯工程编译验证（占位 STM32G071KB，见 `firmware/README.md`）。
- T-0015：完成 `docs/` 四份设计骨架（仅标题/表头/待填占位）。
- T-0016：完成需求第 1/2 部分合并为 `.agent/requirements.md` v0.3（五章 + 完成度表 + 填写规则），删除 `requirements-part2.md`，建立本文档地图。
- T-0006/T-0007：完成系统级时序（§2.4）与系统级安全/指标/热/成本/待确认/参考对照（§2.5–§2.12）；`test-plan` §1/§2/§3/§5/§6 与 `architecture` §1.1 已填。
- T-0009：完成调试板①（§4.1 D-01～D-10、§4.2 按键/显示/状态机/主机侧使能/PT100/USB-C 升级拓扑）；`docs/interface.md` §3 时序与 §4.4 已填。
- T-0010：完成调试板②接口与结构（§4.4 承插腔/64 针插座/USB-C/RS485/香蕉头/5 键+电源键/Ø5-Ø8 定位/顶丝/磁吸）；`docs/interface.md` §1.2 面板坐标表与 §5.3 I2C/ALERT/EN 电气、`architecture` §1.2/§3/§4、`module-design` §2.1 已填。
- T-0011：完成本体①电气规格与拓扑（§3.5：输入 EMI/有源 PFC/LLC+SR/同步 buck、55V 母线与 80/100V 耐压计算、布局/散热/风道/后板/SWD、效率 88/90% 与待机 <1.5W）；`architecture` §2/§3/§4、`module-design` §1.1–§1.5、`test-plan` §3.1/§6.2 已填。
- T-0017：完成安全与使用边界变更单（v0.8）：新增 P-15 机械急停（§3.1.1）；二级 OTP 定为仅关断输出并锁存、不切 220V；§1.5 补输出负极浮地/禁串联/禁电池储能/多台共地；§2.9/§3.5.9 收口强制风冷；`test-plan` §4 安全测试已填。
- T-0018：完成能力补齐需求（v0.9 附录 G）：保护阈值可设性、故障可追溯、异常安全态/看门狗、8 组参数预设、能力留口（升级/远端采样补偿/校准会话）；4 项冲突/口径待 owner 确认（G.6）。
- T-0019：完成输出能力包络与环境降额变更单（v1.0 附录 H）：0.5–48V×0–5A 全段 5A/240W 角点、0–0.5V 同 5A 上限不保证、0–40℃ 连续满载/超 40℃ 降额或关断判据、不需独立 OPP、7 项自洽核对。
- T-0020：完成对标补缺（v1.1 附录 I）：插拔寿命/接触可靠性判据、状态可见性能力、范围外 O-02 修订与 O-06～O-10、PC 标定工具/USB-C 服务口径、T-0007 交叉引用与冲突清单；未改既有环境/安规/成本/精度数值。
- T-0031：完成显示/职责/PC 工具变更单（v1.2 附录 J）：显示回红色双行 4 位共 8 位数码管且只显示实测 V/I（4 位+小数点规则、关断/故障归零）；调试板只设 V/I/开关输出，取消板上温度页/阈值；PT100 阈值经 USB-C 由 PC 工具写入并本地保存、D 本地判断；本体后面板故障灯（P-16）；PC 工具由可选变必需（温度阈值/故障码历史页面）；强制关断改上+下长按 2s；T-0030 OLED 作废。
- T-0014：`Hardware/README.md` 入库占位；`.gitignore` 改为 `/Hardware/*` + `!/Hardware/README.md`，并新增 `.agent/tx/`、`.agent/worklogs/`、`.agent/evidence/` 运行期记录忽略（历史已跟踪文件未删除）。
- T-0032：正文归并（v2.0）——需求/架构/模块设计统一到 `.agent/docs/requirements.md`、`architecture.md`、`modules.md`；`docs/` 四份降为摘要页，`.agent/requirements.md` 仅历史；迁移对照见 R 附录 K，校验与规模见 R 附录 L。
- 后续：按第 8 节规则只改 `.agent/docs` 三份，不再新建需求/设计散文档。

## 7. 文档地图

> 唯一索引。完成度表（章节 × 状态 × 负责单号）在 `.agent/docs/requirements.md` 开头；状态只用 **已定稿 / 待填写 / 待确认** 三档。审查/验收只认前三行三份正文。

| 文档 | 用途 | 负责单号 | 当前状态 |
|---|---|---|---|
| `.agent/docs/requirements.md` | 需求唯一事实源：§1–§5 + 附录 A–L；含完成度表、填写规则、迁移对照与校验 | T-0004/T-0005 定稿；T-0016 合并；T-0006/T-0007 系统级；T-0009 调试板①；T-0010 调试板②；T-0011 本体①；T-0017 安全与使用边界；T-0018 能力补齐；T-0019 输出包络；T-0020 对标补缺；T-0031 显示/职责/PC 工具；T-0032 归并 | 已定稿（v2.0） |
| `.agent/docs/architecture.md` | 架构/接口/时序/升级/测试唯一事实源：§1–§11 | T-0032 归并；原 T-0006/T-0007/T-0009/T-0010/T-0011/T-0017/T-0031 | 已定稿（v2.0） |
| `.agent/docs/modules.md` | 功能模块设计唯一事实源：§1 本体 8 模块、§2 调试板 6 模块、§3 映射、§4 来源 | T-0032 归并；原 T-0011/T-0006/T-0009/T-0010/T-0031 | 已定稿（v2.0） |
| `docs/architecture.md` | 摘要页 → `.agent/docs/architecture.md` §1–§5 | T-0032 | 引用页（无正文） |
| `docs/module-design.md` | 摘要页 → `.agent/docs/modules.md` §1–§2 | T-0032 | 引用页（无正文） |
| `docs/interface.md` | 摘要页 → `.agent/docs/architecture.md` §6–§9 | T-0032 | 引用页（无正文） |
| `docs/test-plan.md` | 摘要页 → `.agent/docs/architecture.md` §10 | T-0032 | 引用页（无正文） |
| `.agent/requirements.md` | 已迁移，仅历史追溯 | T-0032 标注 | 历史（不作审查依据） |
| `.agent/requirements-draft.md` / `.agent/mech-draft.md` | 历史草稿，仅追溯 | T-0032 标注 | 历史（不作审查依据） |

- `requirements-part2.md` 已于 T-0016 删除，内容并入需求第 2/3/5 章；逐节映射与删除原因见 `.agent/docs/requirements.md` 附录 D，历史全文可查 git 历史。
- 文档状态变化时，同步更新本表与 `.agent/docs/requirements.md` 完成度表；两处不得互相矛盾。
- 三份之外不认新建需求/设计文档；`docs/` 四份与历史文件只作引用/追溯。

## 8. 文档填写规则（后续所有工单必须遵守）

1. **报告必写落点**：每张后续工单的 done 报告必须写明「写入文件:章节」与章节范围，路径只能是 `.agent/docs/requirements.md`、`.agent/docs/architecture.md`、`.agent/docs/modules.md` 三份之一（示例：`.agent/docs/requirements.md:3.3.3`、`.agent/docs/architecture.md:7.2`）。禁止新建独立需求/设计文档；未写落点或写到三份之外视为交付不完整。
2. **需求改动**：只改 `.agent/docs/requirements.md` 对应章节，并在附录 C「变更记录」追加一行（日期/单号/改了什么）；不得另起文件，不得把需求正文复制到 `docs/` 或任何第四份文档。
3. **设计展开**：设计细节只写 `.agent/docs/architecture.md` 或 `.agent/docs/modules.md` 的对应小节；`docs/` 四份是摘要引用页，不再承载正文。需求与设计不得互相复制——需求只写“要什么”，设计只写“怎么做”。
4. **未成文不预造**：未完成章节写「待填（来源：T-00xx）」；待 owner 拍板的写「待确认（owner）」，不猜默认值。
5. **状态同步**：文档状态/负责单号变化时，同步更新第 7 节文档地图与 `.agent/docs/requirements.md` 完成度表；只改状态，不改历史变更记录。
