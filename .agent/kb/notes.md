# T-0004 知识库候选

## PowerShell 读取无 BOM UTF-8 文档时的默认编码假失败

KB-TYPE: system
KB-EVIDENCE: `Get-Content .agent/requirements.md -Raw` 读到 7235 字符且中文乱码（`'数控可调直流电源'` 的 `.Contains()` 为 False）；加 `-Encoding UTF8` 后读到 12050 字节原文，同一断言为 True。
KB-TAGS: powershell, utf8, encoding, validation

校验中文文档必须显式 `-Encoding UTF8`（或 `[IO.File]::ReadAllText(..., UTF8)`）；不要用默认 `Get-Content` 的 `.Contains()` 结果判定缺失，否则会把正常文档误判为 FAIL。

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
