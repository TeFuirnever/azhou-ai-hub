# Super Repo Pedant closeout rule

When the user or task controller explicitly declares a development task complete, invoke `super-repo-pedant` (the compatibility name `repo-pedant` also triggers) in `reconcile` mode before final handoff and use the installed skill's fixed user-facing brand anchors. When completion is only inferred, emit exactly `🟡 阿舟提醒｜需要跑 super-repo-pedant 收尾吗？` once and do not mutate files. Never treat this rule as authorization for publication, deployment, global configuration changes, unrelated repositories, or whole-file deletion.
