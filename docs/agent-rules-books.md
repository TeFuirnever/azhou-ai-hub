# Agent Rules Books

Choose a skill for the engineering decision you want help with.

- `a-philosophy-of-software-design` helps you simplify module boundaries and APIs.
- `clean-architecture` helps you keep business rules independent of frameworks, databases and UI.
- `clean-code` helps you improve names, functions and code readability.
- `code-complete` helps you review control flow, defensive code and tests.
- `designing-data-intensive-applications` helps you reason about consistency, replication and reliability.
- `domain-driven-design` helps you model a complex domain and define bounded contexts.
- `domain-driven-design-distilled` helps you map subdomains and their relationships.
- `implementing-domain-driven-design` helps you implement aggregates, domain events and repositories.
- `patterns-of-enterprise-application-architecture` helps you choose service layers, transaction scripts and data mappers.
- `refactoring` helps you improve existing code while preserving observable behavior.
- `refactoring-guru` helps you identify code smells and choose a refactoring technique.
- `release-it` helps you review timeouts, retries, circuit breakers and failure recovery.
- `the-pragmatic-programmer` helps you shorten feedback loops and decide what to automate.
- `working-effectively-with-legacy-code` helps you change hard-to-test code using seams and characterization tests.

### Use the rules in Azhou AI Hub

Hub keeps its maintained edition under `.agents/skills/`. Contributors use it directly from the checkout. In a Codex session opened there, try `$refactoring Review this change and suggest the smallest refactor that preserves behavior.` Ask Azhou can also recommend a book skill when it can verify the skill is enabled in this workspace.

### Install the rules in another project

With Node.js and npm, run this from your project directory to install the Hub edition for Codex. Replace `refactoring` with any skill name above. Select the current project if the installer asks for a scope.

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill refactoring --agent codex
~~~

Open a new session in that project and confirm the skill appears before invoking it. The installer uses Hub's default branch. To match a particular Hub checkout exactly, append `@<commit>` to the repository name. See [installation and updates](https://github.com/TeFuirnever/azhou-ai-hub/blob/main/docs/installation.md#install-agent-rules-books).
