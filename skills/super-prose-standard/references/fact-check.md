# Fact-check procedure: run it or delete it

Documentation states how the product behaves today, and the only admissible evidence for an operation claim is having run it. This procedure is mandatory for every new document and every new paragraph that claims an operation, command, default, error, or platform difference.

1. **Run every claimed operation against the current checkout.** Execute each CLI command, config snippet, and script example exactly as the document will show it; write down only what you observed, including the exact output, warnings, and failure modes. If a claim depends on a key or a network you do not have, say so and name the verification owner instead of asserting the behavior.
2. **Delete what you could not reproduce.** Never carry a command, field, default value, or behavior from memory, analogy, or a neighboring document. When a claim fails to reproduce, fix the claim — not the test.
3. **Classify before writing install guidance.** Read the facts, not the folder name: a tool's manifest declares what it is; an install command that does not apply to that shape is a failed fact-check.
4. **Check older docs against current main.** Before revising a pre-existing page, compare the section against current main; a stale statement there is still wrong — correct it against the code, not against the old prose.
5. **Record the run.** State the command and the observed result in the page's owning evidence surface or the closeout receipt; a claim without a run behind it is a hedge (taxonomy class 7), not documentation.
