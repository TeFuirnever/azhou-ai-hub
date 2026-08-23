# Security policy

## Supported versions

Until the first stable release, the latest GitHub release and current <code>main</code> receive security fixes. After 1.0, the latest minor line receives fixes; older lines are supported only when a release note says so.

## Report privately

Do not open a public issue for a suspected vulnerability, leaked secret, unsafe deletion path, privacy exposure or supply-chain compromise.

Use [GitHub private vulnerability reporting](https://github.com/TeFuirnever/azhou-ai-hub/security/advisories/new). Include:

- affected commit/tag and skill;
- impact and realistic attack or data-loss path;
- minimal reproduction;
- required harness/tools/permissions;
- suggested mitigation if known;
- whether the report contains sensitive data.

Remove real credentials, private conversations and unrelated user data. If GitHub private reporting is unavailable, open a public issue containing no vulnerability detail and ask a maintainer for a private channel.

## Response targets

- acknowledgement within 3 business days;
- initial severity/scope assessment within 7 business days;
- status update at least every 14 days while remediation remains open.

Targets are communication goals, not a guaranteed fix deadline. Coordinated disclosure timing is agreed with the reporter after impact and remediation are understood.

## Scope

In scope:

- repository code and official GitHub releases;
- installable packages under <code>skills/</code>;
- history/evolution paths that could expose private data or mutate a live skill;
- hooks, setup scripts and converters that cross permission boundaries;
- GitHub Actions and vendored dependencies.

Out of scope:

- unofficial mirrors, modified forks or third-party package-manager behavior;
- model output quality without a security/privacy consequence;
- denial-of-service that only consumes the reporter's own local resources;
- social engineering unrelated to this project.

## Security invariants

- Hooks and history observers cannot silently edit a live skill.
- Raw agent history, tokens, private paths and unpublished assets stay outside Git.
- Destructive, global, cross-repository, publish and deploy actions require explicit authority.
- GitHub Actions use least privilege and immutable action SHAs.
- New vendored material requires source, version, license and retained notices.

Fixes receive a regression when safe to publish. Release notes describe impact and upgrade action without exposing users before a coordinated fix is available.
