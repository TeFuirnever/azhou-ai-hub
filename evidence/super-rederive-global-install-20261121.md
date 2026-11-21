# Rederive user-scope installation

On 2026-11-21, the maintainer authorized installation of `super-rederive` into the shared user Skill root. The Codex bundled installer fetched the public repository using Git sparse checkout. All nine files matched Hub commit `a7d851fa861d366b7fee21171d1d56eacfccfd6f` by SHA-256 before the copy was placed in the user root; an existing destination would have stopped the operation. The private receipt retains the full file manifest and local path.

Codex CLI `0.169.1`, queried through Foundation Doctor and the app server from a project outside the Hub checkout, returned one enabled user-scope `super-rederive` entry with a complete catalog. This establishes installation and discovery on that host, not a complete lesson, persistence test, or invocation on another host. The earlier isolated opening remains [separate evidence](super-rederive-codex-20261121.md).

The project-scoped sparse installer command in both READMEs was also run in a temporary directory; its nine files matched the user-scope copy. On the same host, the `npx skills add` repository download timed out or disconnected, including a retry with an extended timeout. The sparse result does not establish that the `npx` route succeeds on this connection.
