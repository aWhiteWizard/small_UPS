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
