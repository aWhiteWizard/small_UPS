# T-0004 知识库候选

## PowerShell 读取无 BOM UTF-8 文档时的默认编码假失败

KB-TYPE: system
KB-EVIDENCE: `Get-Content .agent/requirements.md -Raw` 读到 7235 字符且中文乱码（`'数控可调直流电源'` 的 `.Contains()` 为 False）；加 `-Encoding UTF8` 后读到 12050 字节原文，同一断言为 True。
KB-TAGS: powershell, utf8, encoding, validation

校验中文文档必须显式 `-Encoding UTF8`（或 `[IO.File]::ReadAllText(..., UTF8)`）；不要用默认 `Get-Content` 的 `.Contains()` 结果判定缺失，否则会把正常文档误判为 FAIL。同一根因还会让行数假缩水：`(Get-Content docs/architecture.md).Count`=47，而 `-Encoding UTF8` 与 `[IO.File]::ReadAllLines` 均为 67（文件 LF=67）；做 ≤120 行/文件规模校验时同样必须显式 UTF8。

## worktree 基点落后 origin/master 时先 ff-only 再开发

KB-TYPE: system
KB-EVIDENCE: `git branch -avv` 显示 task/T-0004 基点 f4cbc29、origin/master bdc0512（behind 2）；`git merge --ff-only origin/master` 后 HEAD=bdc0512，后续 push 可快进。
KB-TAGS: git, worktree, baseline, delivery

新 worktree 开工先比对 `git rev-parse HEAD` 与 `git ls-remote origin refs/heads/master`；落后则 ff-only 到远端 master，避免基于旧骨架开发、交付时非快进或把上游文件算进本单 diff。

## 主仓 checkout 落后且脏时，抢救产物要在工单 worktree 提交后 push master

KB-TYPE: system
KB-EVIDENCE: `git -C D:\workspace\small-ups status -sb` → `## master...origin/master [behind 9]`；`git worktree list` → T-0012 HEAD f4cbc29、origin/master 3d641eb；T-0005 分支 65549a2 未并入 master
KB-TAGS: git, worktree, delivery, salvage

主仓 `D:\workspace\small-ups` 可能长期停在旧 SHA 且有脏 task/project/tx 文件，不能直接在主仓 commit。做法：工单 worktree 内 `git merge --ff-only origin/master`，提交后 `git push origin HEAD:refs/heads/master`，用 worktree HEAD 与 `git ls-remote` 对 SHA。

## T-0005 需求第 2 部分与 T-0012 当前口径的差异（只登记，勿静默改）

KB-TYPE: content
KB-EVIDENCE: .agent/requirements-part2.md:247-251（每通道 5 点）、:145-168（无 PFC_FAULT；UNDERVOLTAGE=0x04）、:61（4.7k 仅调试板侧）、:32-33（A28/A29 已为 UART）
KB-CONFLICT: T-0012 验收要求 6 点电压 + 3 点电流、故障码含 PFC_FAULT；T-0005 验收与第 2 部分为每通道 5 点且无 PFC_FAULT。
KB-TAGS: requirements, calibration, fault-code, salvage

## worktree 内看板可能停在建单时，填充单映射以主仓看板为准

KB-TYPE: system
KB-EVIDENCE: worktree `.agent/board/tasks.json` 仅 3 单、末单 T-0003（29,572B）；`[IO.File]::ReadAllText("D:\workspace\small-ups\.agent\board\tasks.json", UTF8)` 为 100,414B、T-0001–T-0020。`Get-Content .agent/board/tasks.json -Raw | ConvertFrom-Json` 报 `传入的对象无效，应为“:”或“}”`；显式 UTF8 后同一 worktree 文件可解析，确认是旧数据而非损坏。
KB-TAGS: worktree, board, tasks, powershell, utf8

worktree 只带建单时的看板副本，可能缺后续单；确认「本文由哪些单填充」时读主仓最新看板，并显式 UTF8。不要把 worktree 看板当验收基准或据此判定文件损坏。


## 需求审计以主仓最新看板为准，worktree 的 tasks.json 可能停在 init

KB-TYPE: system
KB-EVIDENCE: 主仓 `.agent/board/tasks.json` 100414B，含 T-0004–T-0013；worktree 同文件 18398B，仅 T-0001–T-0003，`git log -- .agent/board/tasks.json` 只有 f4cbc29 init。
KB-TAGS: board, worktree, baseline

工单 acceptance 的基准可能只存在于主仓工作区的未提交看板；worktree 内跟踪的 tasks.json 可能是初始版本。审计/实现前先比较两处文件大小与 `git log -- <board>`，以主仓看板为准，且不要复制或提交主仓看板到本单。

## 计数审计要区分“寄存器 LSB/内部编码”与“对外设定步进”

KB-TYPE: method
KB-EVIDENCE: `.agent/requirements-part2.md:203-204`（LSB 1mV/1mA 为内部编码，对外步进 0.01V/0.01A）；`.agent/requirements.md:95`（界面步进 0.01V/0.01A）。
KB-TAGS: requirements, calibration, step

同一份验收里可能同时要求“LSB ≤1mV”和“步进 0.01V/0.01A”。不要把两者判成冲突：寄存器 LSB 是编码精度，对外步进是界面/命令粒度。文档要分别写明，否则下游会把 1mV 当成 UI 步进或反过来把 0.01V 写进寄存器 LSB。

## 校准 EEPROM 的“次数/温度”若由设备写入，主机 CRC 不能覆盖这两个字段

KB-TYPE: method
KB-EVIDENCE: `.agent/requirements-part2.md:263,271,280`；T-0005 第 4 条只要求 COMMIT 写 EEPROM 含 CRC/版本/次数/温度，未规定主机如何获知次数/温度。
KB-TAGS: calibration, crc, eeprom

把次数/温度放进 CRC 覆盖范围会导致主机无法预先计算 CAL_CHECKSUM（次数由设备 +1，温度由设备采样）。要么增加可读回/可写寄存器，要么让 CRC 只覆盖主机已知的点表字段，把次数/温度作为元数据；未定前必须标“待 owner 确认”，不要自行编造编码。

## 取消并联均流要全链路清理，不只改 SHARE/SYNC 针

KB-TYPE: content
KB-EVIDENCE: `.agent/requirements-part2.md:113-114,142-144,167-168,207`；`.agent/requirements.md:84,130`；T-0006 第 1 条。
KB-TAGS: requirements, parallel, consistency

取消多 PSU 均流时，容易只改针脚“SHARE/SYNC 预留”，遗漏 PARALLEL_MODE/CURRENT_SHARE_EN 寄存器、OUTPUT_STATUS 的 MASTER/SLAVE/SHARE_ACTIVE 位、IMBALANCE/PARALLEL_FAULT 故障码、3.6 语义和覆盖表。审计要按“针脚→寄存器→状态位→故障码→功能条目→覆盖表”全链路扫一遍，保留编号但标“保留/不产生”比删行更利于兼容。

## 主机侧 EN 延时与本体使能判定只有端点重合时，取上限并留事务裕量

KB-TYPE: method
KB-EVIDENCE: `.agent/requirements.md:704`（T-0009 主机侧验收 10–20ms，实现取 20ms）；`docs/interface.md:76`（T-0006 本体 S1_CHECK 要求 EN 高 ≥20ms）
KB-TAGS: enable, timing, interface, d-side, review

跨板时序不能两端各写“在范围内”：T-0009 主机侧 10–20ms 与 T-0006 本体侧 EN 高 ≥20ms 的交集只有 20ms 一个端点。主机必须固定 20ms，且从 EN 上升到写 OUTPUT_ENABLE 之间还要有 I2C 事务时间（>0）才真正超过 20ms；只等到 10–15ms 会被本体判 EN 未稳定。若实现无法保证，应回写本体去抖下限或主机上限，不能靠“应该能过”。

## 需求并单后必须同步改写 docs 与 KB 的旧路径/章节引用

KB-TYPE: method
KB-EVIDENCE: `.agent/requirements.md:7`（合并说明）、`:525-560`（附录 D 映射与删除原因）；`docs/architecture.md:5,53-67`（R1/R2 已改为 requirements.md §2/§3）；`Test-Path .agent/requirements-part2.md` → `False`
KB-TAGS: docs, requirements, merge, references, single-source

把 requirements 第 1/2 部分并成单文件时，除了搬正文，必须同步做三件事：①在合并文件开头与附录写“来源映射 + 删除原因 + git 历史可追溯”；②把 docs/README 里所有 `R1`/`R2`/`requirements-part2.md` 引用改成新章节号（只改引用，不动骨架标题）；③知识库中指向被删文件的旧证据行要标注为历史，新的证据行改用合并后的文件:行。只删文件不改引用，会让下游把“引用缺口”误判成需求缺失。

## PC 标定工具协议存在“工单明列命令”与 T-0006 文档命令名的漂移

KB-TYPE: method
KB-EVIDENCE: `tools/calib_tool.py:5-6`（CAL BEGIN/SET/MEAS/COMMIT/READ/ABORT）；`.agent/requirements.md:602`（T-0006 §3.4.5 的 CAL POINT/CAL STATUS）；`docs/interface.md:320`（命令映射）；`.agent/evidence/T-0008-p0-acceptance.txt:21`
KB-TAGS: calibration, protocol, t-0008, firmware

写上位机工具前先对齐“工单明列命令”与需求/设计文档的命令表。T-0008 工单要求 SET/MEAS/READ，而 T-0006 串口文档 §3.4.5 写 CAL POINT/CAL STATUS；两者不是同一套文本命令。按工单实现并在 README/报告中登记偏差，不要静默选一套。设备信息 INFO、READ 的 CRC 回包字段也未定，需在工具端做兼容并明确“缺字段=未校验”。

## Windows 高 DPI 下 tkinter 窗口截图被裁剪

KB-TYPE: bug
KB-EVIDENCE: 未设 DPI awareness 时 `CopyFromScreen(1180×790)` 只截到左侧/上半，右侧按钮与日志丢失；在创建 Tk 前执行 `windll.shcore.SetProcessDpiAwareness(1)` 后同尺寸截图完整（T-0008-p0-ui.png 1180×840）
KB-TAGS: windows, tkinter, dpi, screenshot, evidence

给 tkinter 窗口做 P0 截图时，先在进程启动处声明 DPI awareness，再用 `winfo_rootx/y/width/height` + `CopyFromScreen` 截客户区；否则 Windows 会把逻辑尺寸放大，截图像素对不上，右侧控件被裁掉。


## 需求长文追加变更用附录，不重排章节号

KB-TYPE: method
KB-EVIDENCE: `.agent/requirements.md:1104`（附录 G T-0018）；`:41`（完成度表仅 +2 行）；正文原有章节号未改。
KB-TAGS: requirements, appendix, change-ticket, numbering

需求正文超过 1000 行、章节号被 `docs/` 多份设计文档引用时，变更单优先在文末追加附录（T-0017 附录 F、T-0018 附录 G），不要插入新的 §3.6/§2.13。这样避免重排后续章节号、同步索引/完成度表/设计引用，也保留变更单正文可追溯；新增需求仍要进完成度表、附录 C 与附录 E.2。

## 故障历史/预设持久化与 P-06/§3.3.7 的存储范围张力

KB-TYPE: content
KB-EVIDENCE: `.agent/requirements.md:384`（P-06 只保存 V/I，可含阈值）、`:541`（§3.3.7 不保存故障历史）、`:1243-1245`（G.6 冲突表）。
KB-TAGS: requirements, storage, fault-history, preset

P-06 与 §3.3.7 对“本体存储只放什么”的口径不完全一致：P-06 允许“可含过流/过压阈值”，§3.3.7 只列 V/I 且明确不保存故障历史。新增故障历史/预设/阈值持久化需求前，先裁决“设定区 vs 独立区/介质”和“8 组预设是否仍属 V/I 设定”，否则实现单会各自解释。T-0018 默认：故障历史待 owner、用户阈值不持久化、预设仅 V/I。

## 安全边界变更必须三处同步：需求项 / 故障码 / T-0006 保护清单

KB-TYPE: method
KB-EVIDENCE: `.agent/requirements.md:385`（P-09）、`.agent/requirements.md:482`（0x05）、`docs/interface.md:205`（T-0006 保护清单 0x05）
KB-TAGS: requirements, safety, otp, consistency

只改需求 P-09 会让 `docs/interface.md` 的 T-0006 保护表仍停在旧动作（如 OTP 只写“断输出”），设计/固件按旧表实现后与需求冲突。裁决安全项时按“需求项 → 故障码语义 → T-0006 保护清单 → 测试计划”全链路同步；本单把 OTP 二级统一为“仅关断输出并锁存、不切 220V、保辅助/风扇”，三处文字均含该口径。

## 急停“切市电”与“状态可读”的张力

KB-TYPE: hardware
KB-EVIDENCE: `.agent/requirements.md:393-399`（P-15/§3.1.1）
KB-TAGS: estop, safety, status, power-loss

急停机械切断 220VAC 后整机可能失电，若要求“状态可被 MCU/I2C 读取”会自相矛盾。需求必须写明：状态读取形式由设计定，允许整机失电时仅以无源触点/机械指示对外呈现；寄存器只作补充，且不得被 CLEAR/软件复位/重新上电伪造。否则设计无法同时满足“切市电”和“状态可读”。

## 旧口径只存在于历史草稿时，收口要引用旧行号并在草稿加历史标注

KB-TYPE: method
KB-EVIDENCE: `.agent/requirements.md:326`（§2.9 收口）、`.agent/requirements.md:1089-1093`（附录 F.4）、`.agent/requirements-draft.md:6`（历史标注）、`:30,32,54`（原始旧句）
KB-TAGS: requirements, deprecation, traceability, review

本单要废止“自然散热/二级切整机 220V”，但 `requirements.md` 正文已无这些词，旧句只在 `requirements-draft.md`。只改正文会让 reviewer grep 到草稿旧句而误判未收口。做法：正文写“旧表述作废”并引用草稿行号，草稿顶部加历史标注（保留原文），附录 F.4 列 old→new；三处都不删原文，只标作废。

## 工单 baseSha 落后于真实开工基线会把继承变更算进本单规模

KB-TYPE: system
KB-EVIDENCE: 看板 baseSha=29470ae 按 `git diff` 计 10 文件/1311 行（>1200 硬上限拒付）；真实开工基线为 ff-only 后的 cb3d9df；`git diff --shortstat cb3d9df..b678a7a -- . ':!.agent/evidence' ':!.agent/kb'` → `8 files changed, 601 insertions(+), 429 deletions(-)` = 1030 行（<1200）。
KB-TAGS: baseSha, diff, size, worktree, delivery

worktree 的 baseSha 必须是本单真实开工点（`git merge --ff-only origin/master` 后的 HEAD），并与审查上界配套计算 diff；从上游继承的 T-0013/T-0015 变更、以及本单之后叠加的 T-0006/T-0021 提交都不应计入本单规模。引擎按旧 baseSha 判超限时，先核对 ff 记录与 `git merge-base`，用真实区间留痕后再交付，不要为凑规模拆单或把上游文件重做成自己的 diff。

## 60mm 面宽上 0.56" 双行数码管与屏侧上/下键不可兼得

KB-TYPE: hardware
KB-EVIDENCE: .agent/requirements.md:826-827（屏 ≤50×26、0.40"；0.56" 高约 38mm 与屏侧键冲突）；docs/interface.md:67（屏 48×25，Up/Down 在 x=52.5–58.5）
KB-LAYER: 3_hardware
KB-TAGS: panel, display, layout, 60mm, 0.56in

60mm 宽面板若屏占约 50mm，左右仅剩约 5mm，放不下 6mm 轻触键。0.56" 双行 4 位模块典型高约 38mm、宽约 50.8mm，屏侧上/下键无空间；T-0010 选 0.40" 48×25 模块并把 Up/Down 竖排在屏右侧，才满足“屏侧上/下”。若 owner 要求 0.56"，必须改为屏下 5 键或加宽面板，不能只改字高。

## 定位销进入承插腔时，整机总深不能叠加销长

KB-TYPE: hardware
KB-EVIDENCE: .agent/requirements.md:293（§2.7 总深 180+35=215，销 15–18 在腔内不叠加）；.agent/requirements.md:794（承插腔容纳销 15–18）
KB-LAYER: 3_hardware
KB-TAGS: mechanical, depth, locating-pin, cavity

调试板贴本体前面时，定位销前伸 15–18mm 进入调试板 35mm 承插腔，不应再把销长加到整机总深。T-0007 旧口径写成 180+35+15–18=230–233，T-0010 修正为壳体 215mm、含香蕉头正面凸出 ≤233mm；做深度链时先算腔内容纳（销+插座+PCB+显示+间隙），不要重复计销长。

## NTC 5D-15/10D-11 的 15/11 是直径，不是冷态阻值

KB-TYPE: hardware
KB-EVIDENCE: .agent/requirements.md:609（“NTC 冷态 5Ω/10Ω（5D-15/10D-11）”）
KB-LAYER: 3_hardware
KB-TAGS: input, ntc, inrush, bom

`5D-15` 表示 25℃ 冷态 5Ω、本体直径约 15mm；`10D-11` 表示 10Ω、约 11mm。不要把型号里的 15/11 当成阻值写成 11–15Ω。选型时按冷态阻值算浪涌、按稳态电流/热态残余阻值算损耗；本机 240W/220V 稳态约 1.4A，二者均可，最终按浪涌实测选。

## 55V 母线的最低器件档是 80V，60/63V 不能用

KB-TYPE: hardware
KB-EVIDENCE: .agent/requirements.md:602-603（53.18V 最小静态母线、55/80=68.75%、55/60=91.7%）
KB-LAYER: 3_hardware
KB-TAGS: bus, derating, buck, capacitor, 55v

55V±1V 母线下 buck/SR/输出电容不能按 60V 或 63V 选：55/60=91.7%，没有浪涌/振铃裕量；最低 80V（68.75%），优先 100V（55%）。母线下限计算要同时加 48/0.95、通路 50mV、纹波调节 0.5V、母线纹波 0.1V、5A 阶跃 2V，得 53.18V，再用 54V 下限校验仅 0.8V 裕量；不要只用 48/0.95=50.5V 就判 55V 够。

## 输出能力包络要写成矩形+角点，不是恒功率双曲线

KB-TYPE: content
KB-EVIDENCE: `.agent/requirements.md:1268-1283`（H.2 包络）、`:1316-1324`（H.3 降额）、`:1328-1340`（H.4 OPP）、`:1346-1352`（H.5 自洽）
KB-TAGS: requirements, output-envelope, derating, opp, consistency

48V×5A=240W 不是无条件承诺：需求要写成 0.5–48V×0–5A 矩形 + 240W 角点，明确“全段 5A”只对保证区成立、0–0.5V 同 5A 上限但不保证连续 5A/指标、保护容差（5.25A/50V）与远端采样针端 242.5W 不算连续能力。环境降额不要引用不存在的曲线：0–40℃ 按 40℃/240W/30min/≤70℃/≤55℃ 判，超 40℃ 只写“降额到热限或 OTP 95℃ 关断”的可判定边界；无独立 OPP 的结论必须带前提（5A 限流/48V/8A OCP/50V OVP）和重评触发，否则后续改限流会静默失效。

## P0 SHA 文件无法包含自身最终提交哈希：内容提交 C1 + 记录提交 C2

KB-TYPE: system
KB-EVIDENCE: `.agent/evidence/T-0018-p0-sha.txt:5-12`（COMMIT=C1、NOTE 随 C2 落库）；`.agent/worklogs/T-0007.md:32-36`（C6 内容/C7 仅记录）；T-0019 同法
KB-TAGS: git, sha, evidence, self-reference, delivery

P0 sha 文件要写 COMMIT/LOCAL_HEAD/REMOTE_HEAD/ls-remote 原文，但文件内无法写入“包含该文件的最终提交”哈希（自指）。做法：C1 提交内容并 push，C2 写 sha 文件记录 C1 并 push；sha 文件注明 C2 为记录提交、最终 LOCAL=REMOTE=C2 在报告里给。reviewer 核对 C2 只改 evidence/worklog，且 sha 中的 C1 是 C2 的父提交即可；不要为了把 C2 写进文件再无限追加记录提交。

## 连接器“500 次”是机械寿命，不等于热插拔/带电插拔寿命

KB-TYPE: hardware
KB-EVIDENCE: `.agent/requirements.md:1404-1411`（T-0020 I.1：热插拔循环定义、≥500 次、接触电阻/插拔力/保持力判据）；`docs/interface.md:47`（插座 ≥500 次）
KB-LAYER: 3_hardware
KB-TAGS: connector, card-edge, mating-cycles, hot-swap, durability

插座/连接器规格书的“500 Cycles”通常指机械插拔寿命，未区分是否带电/待机。需求若写“热插拔 500 次”，必须定义热插拔状态（输出 OFF、继电器断开、12V/I2C 带电待机）并说明不得用不带电次数替代；同时给接触电阻增量、插拔力/保持力判据。否则供应商按机械寿命交付，系统级热替换次数无法验收。

## “设定值与实测值同屏”在 8 位 2×4 屏上只能按被测量成对落实

KB-TYPE: content
KB-EVIDENCE: `.agent/requirements.md:1437`（I.2 S-02：同一被测量成对同屏，V/I 可分页）；`:1496`（I.5 #1：现布局仅实测 V/I，无设定/CV/CC/功率）
KB-LAYER: 1_application
KB-TAGS: requirements, display, visibility, ui, conflict

8 位 2×4 数码管（每页 2 行×4 位）无法同时显示 V 设定/实测 + I 设定/实测 + 模式 + 功率。把“同屏”写成“V/I 四个数值全同屏”会直接要求换屏/改结构；按“同一被测量的设定/实测成对同屏，V/I 可分页”写，既满足可判定又不越权改 T-0009 布局。若 owner 要四项全同屏，必须走 T-0009/T-0010 变更单。

## O-02“无上位机”必须给服务/标定工具留例外，否则与 USB-C 自相矛盾

KB-TYPE: content
KB-EVIDENCE: `.agent/requirements.md:90`（O-02 修订：T-0008/USB-C 服务例外）；`:1461-1479`（I.4 定义/裁决/验收）；`:891`（§4.2.6 USB-C 数据/升级）
KB-LAYER: 1_application
KB-TAGS: requirements, host-software, usb-c, calibration, scope

绝对化的“无上位机/无 PC 软件”会与调试板 USB-C 升级口、T-0008 标定工具冲突。正确口径是区分“上位机产品功能”（随整机交付、正常使用必需、提供 V/I/开关控制）与“服务/标定工具”（不随整机、不进 BOM、只做校准/读状态/升级）。O-02 必须写明例外，否则下游会以“范围外”为由删掉 USB-C 或把 T-0008 当产品功能。

## Windows PowerShell 5.1 无法解析无 BOM 的 UTF-8 中文脚本，且 native stderr 会触发 Stop

KB-TYPE: bug
KB-EVIDENCE: `powershell -File firmware/tools/bootstrap.ps1` → `At ...bootstrap.ps1:105 char:40 ... Unrecognized token in source text` / `The string is missing the terminator`；脚本改为 ASCII-only 后 exit 0。另 `openocd.exe --version` 把版本写到 stderr，在 `$ErrorActionPreference='Stop'` 下报 `NativeCommandError` 且脚本 exit 1。
KB-LAYER: 2_system
KB-TAGS: powershell, utf8, bom, stderr, bootstrap

Windows PowerShell 5.1 按 ANSI 读取无 BOM 的 UTF-8 `.ps1`，中文注释/字符串会被拆成非法 token；要么给脚本加 UTF-8 BOM，要么脚本保持 ASCII-only。调用会写 stderr 的原生工具（OpenOCD、部分 git）时，即使 `2>&1` 也可能抛 `NativeCommandError`，应在该调用周围临时 `$ErrorActionPreference='Continue'`，或 `Start-Process -RedirectStandardError` 捕获，不能让它中断幂等引导脚本。

## STM32 自定义链接脚本的三类新版 ld 警告：RWX / LMA adjusted / nosys

KB-TYPE: method
KB-EVIDENCE: `firmware/linker/STM32G071KBUx_FLASH.ld:14-19`（PHDRS text/data）与 `:126-135`（._user_heap_stack NOLOAD）；`powershell -File firmware/build.ps1 -Clean` 输出 `warning: psu_minimal has a LOAD segment with RWX permissions`、`section ._user_heap_stack lma 0x8000608 adjusted to 0x8000628`、`_close is not implemented and will always fail`
KB-LAYER: 1_application
KB-TAGS: stm32, linker-script, ld, cmake, newlib, nosys

新 binutils 对无 PHDRS 的脚本会报 RWX LOAD 段：给 FLASH 段 `:text`、RAM 段 `:data` 并声明 `PHDRS { text PT_LOAD FLAGS(5); data PT_LOAD FLAGS(6); }` 可消除。把 NOBITS 的 `._user_heap_stack` 也挂到 `:data` 会得到 “LMA adjusted” 警告，应写 `._user_heap_stack (NOLOAD)` 且不指定 phdr。`-specs=nosys.specs` 下 `_close/_lseek/_read/_write is not implemented` 是预期警告，不是链接失败判据；验收看 `Linking C executable`、Memory region 与产物大小。