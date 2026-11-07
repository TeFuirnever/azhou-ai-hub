# pstack-azhouzhou namespace distribution repair — 2026-11-05

## Boundaries

Isolated Treehouse branch codex/pstack-namespace-sweep-20261105 was created
from codex/pstack-integration-20261104 at eb49500bb62e325f528755b421cd096d4f2bbafc.
No edit to pristine pinned pstack/ or components/, installed native caches,
the primary checkout and its 20 dirty files, local main, origin/main,
or any other leased writer.

## Root cause and repair

Patch 0018 changed the native distribution manifest to pstack-azhouzhou
but not upstream-origin user documentation, causing outdated instructions
for Claude commands (/pstack:poteto-mode) and named agents
(pstack:poteto-agent) against the new installed namespace.

The downstream quilt patch 0020-hub-claude-namespace-guides.patch modifies
the generated copy of the upstream README, poteto-help Skill, setup guide
and Claude Code adapter. The pristine upstream files remain untouched.

Hub-owned adapter docs were updated separately: Codex now refers to a native
Skill invocation instead of a Claude-only slash alias; ZCode refers to
discovered skills and the commands-only plugin; Copilot and Muse namespaces
now match the Hub plugin identity. The Hook runtime and model policy parser
were not edited.

## Verification and remaining scope

The standard generator applies all 20 patches to produce four trees with 68
skills per tree, 41 Codex prompts and 41 ZCode commands. Distribution tests
assert the current namespace and reject known obsolete command and agent
IDs on selected routes across the trees.

This is a docs/distribution fix, not real host invocation proof. Claude,
Copilot and Muse named agents, Codex native Skill rendering, ZCode GUI
commands and Hook trust require independent real-host receipts. Repository
paths, upstream URLs and the retired Pi contract are not automatically
converted into runtime identity names.

Production plugin update, release review and main merge remain open.


## Independent review and red-green correction

A read-only independent Codex review returned exit 0 and identified one P2
in the first draft: an overly broad replacement had turned a Muse link
from setup-pstack/SKILL.md into setup-pstack-azhouzhou/SKILL.md.
The first whole-repository verification failed the repository-policy gate
with that exact broken local link. The failure is preserved in the ignored
namespace-sweep verify.log.

The Hub-owned Muse guide now refers to the setup-pstack Skill's Other
runtimes table as plain text rather than using a source-layout-dependent
relative link, and the native approval example uses the new plugin identity.
The generator was rerun, six distribution tests passed, and the targeted
repository policy subsequently passed all 4,522 public files. This
follow-up fixes the reviewer-reported P2; the reviewer did not review
the post-fix diff again. Full repository verification is recorded
separately and is not claimed here until its actual exit is known.
