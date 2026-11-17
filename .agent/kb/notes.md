## worktree 从旧基线创建时先对齐 origin/master

KB-TYPE: method
KB-EVIDENCE: .agent/evidence/T-0003-p0-g0.txt:14-15 + `git merge --ff-only origin/master` → "Updating f4cbc29..bdc0512"
KB-LAYER: 1_application
KB-TAGS: worktree,git,base
worktree 若从旧基线创建，开工先 `git merge --ff-only origin/master`；否则交付 diff 会把已合并的 T-0001 目录当成删除，且 push 后产品仓回退。
