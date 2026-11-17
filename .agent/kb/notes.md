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
