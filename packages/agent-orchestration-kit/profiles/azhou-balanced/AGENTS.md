<!-- ASTRA-LUNA-ORCHESTRATOR:BEGIN -->
# Global Sol/Luna orchestration with optional Astra

For complex coding tasks or explicit delegation requests, use the installed `astra-orchestrator` skill (discover it by name).
Default to Sol/high for the root and the independent `reviewer`; use Luna/max for `explorer`, `worker`, `tester`, and `researcher`. The configured role settings take precedence over generic subagent-model preferences.
Use the `astra-specialist`, instructed to stay read-only, only for an explicit Astra request, an evidenced Sol reasoning blocker, or a concrete high-risk architecture/security decision. Explain the reason, provide a bounded question, and use at most one Astra specialist at a time; follow the skill's escalation rules.
Role instructions do not create a separate permission sandbox; Codex subagents inherit the parent session permissions.
Keep small tasks in the root. Delegate for distinct value, assign non-overlapping file ownership, keep handoffs concise, wait for required agents, and report actual verification evidence. Preserve Standard speed unless the user requests otherwise.
Explicit user instructions and more specific project instructions take precedence. Respect project or session model overrides; never switch the active root model merely to match a default profile.
<!-- ASTRA-LUNA-ORCHESTRATOR:END -->
