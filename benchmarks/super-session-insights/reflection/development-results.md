# Reflection evaluation: synthetic development results

Status: exploratory development evidence, recorded 2026-11-19. These comparisons do not establish a workflow benefit, a validated behavior benchmark, or approval to promote either candidate. No validation or holdout cases were run. The two private candidate revisions were not installed or merged. The [evaluation plan](evaluation-plan.md) remains the proposal for an independent evaluation.

## Materials and limits

[Development cases D01–D04](development-cases/) are the development portion of a frozen 12-case synthetic set; four validation and four holdout groups were also prepared. [NEW-01–NEW-04](development-cases/) are an additional independent set of synthetic development scenarios. Inputs and scoring keys here are copies of the frozen development bytes. The original NEW keys say “draft” in their titles: that was already present at freeze time, not an indication that they were edited after the results were seen. Their subjects, people, records and paths are fictional. These public, already-used cases cannot serve as a blind holdout. Validation and holdout inputs and keys are not included here.

For the later development comparisons, both treatments requested `gpt-6-astra` through Codex CLI 0.169.0 with the same input and budget, one generation per arm and case. The immutable backend version and actual monetary cost were unknown. Each case had three separate AI reviewer sessions; they are not independent human reviewers. Reviewer prompts supplied anonymized answers, but scoring keys were accessible on the same host and the enforced tool boundary was not verified. Blindness therefore remains unverified. Human semantic review was pending. The comparisons assessed chat answers; the file-based reflection, citation review and rendering workflow remained on hold, so its end-to-end behavior was not evaluated.

## Earlier ten exploratory pairs

Each pair used one synthetic case, one generation per arm and one AI reviewer. The reflection arm used excerpts from the reflection contract; it did not execute the complete file workflow. Conditions changed across the pairs: cases 1–7 did not give the ordinary-summary arm the same source-citation instruction, while cases 8–10 matched that instruction. Do not aggregate the results as a win rate.

| Case | Scenario | AI judgment | Important qualification |
| --- | --- | --- | --- |
| 1 | One-off exception and assistant repetition | Reflection preferred | The ordinary answer's preference record may have referred to the original handoff; an initial startup-warning classification was corrected. |
| 2 | Bounded preference and urgent exception | Tie | Both retained the scope and exception. |
| 3 | Already-verified export handoff | Tie | Neither added an action. |
| 4 | Unknown delivery status | Tie | Both retained a read-only check. |
| 5 | Report preview versus quarter completion | Tie | Neither added an action. |
| 6 | Dependent retellings | Reflection preferred | The ordinary answer treated a historical weekly-report correction as a current action. |
| 7 | Useful practice and urgent exception | Reflection preferred | The arms received different citation instructions. |
| 8 | Matched citation instruction and a table | Reflection preferred | The penalty for a conditional future suggestion was disputed. |
| 9 | Unknown client approval | Tie | Citation instructions matched. |
| 10 | Independence of retries within one batch | Tie | Both retained a necessary check. |

The first four pairs requested a read-only environment; pairs 5–10 ran in the current environment without filesystem isolation. The complete host tool boundary, immutable backend revision and actual cost were not established. One reviewer per pair and known scoring ambiguity limit the conclusions.

## Four original development cases

The first D01–D04 run compared an ordinary summary with a reflection treatment. Three AI reviewers tied D01, preferred the ordinary summary on D02 and D03, and two of three preferred reflection on D04. D02's reflection next step was generic; D03 did not state as clearly that timing applied to that day's inspection. D04 avoided an extra action, though reviewers differed on the severity of the ordinary answer's extra action. One reviewer mixed another case into an explanation and later corrected the record without changing the score. Tool access and blinding were not verified.

The first candidate, B1, added guidance about task constraints, time scope, historical requests and avoiding unnecessary action to a frozen package based on commit `89daa1f30c3f423151328d7e3ca69dcdf89b710f` (skill tree `15a2acdab0074710becfa83cd855e84af7f902a9`). Its preregistered review round was **uncertain**: all 12 reviewer prompts omitted the required answer tags. A separately frozen post-hoc recovery reused the original answers without new generation; it suggested B1 was more specific on D02, but both arms remained at 1/2 for action value. The recovery cannot turn the original review into a pass.

The B2 candidate changed one sentence relative to B1 to ask for a specific action and applicable constraints when a next step is needed. In a new D01–D04 comparison, D02 action value remained 1/2 for both arms; D03 retained its time qualifier and D04 remained no-action in both. B2 did not meet the predeclared development improvement threshold. These repeatedly used cases cannot establish general performance.

## Additional next-action controls

These cases compared private B1 and B2, not either candidate against the current main branch. Each treatment generated one answer per case. Three independent new AI sessions reviewed each case; their judgments and key limitations are:

| Case | Frozen scenario | Observation |
| --- | --- | --- |
| NEW-01 | A requested local comparison with an unresolved record identity | Two reviewers preferred B2 overall and one tied. B2 named the comparison more precisely, but omitted an explicit condition to keep the row blocked if identity remained unknown; median action value fell from 2/2 to 1/2. |
| NEW-02 | A requested adjustment to one page | Both suggested changing the specified page and also regenerating and locally rechecking a PDF. The frozen burden key had no reliable anchor for that combination; all three marked the comparison uncertain. The actions were not executed. |
| NEW-03 | A completed task with no action needed | All tied; both answered that no further action was needed. |
| NEW-04 | A historical request without current execution authorization | All tied; both summarized the old request without adding a current action. |

No reviewer marked a critical failure defined by the frozen keys in this batch. An uncertain score is not a safety pass. The cases do not establish a consistent benefit for B2, and the earlier D02 threshold was not met.

## Failures, evidence and next use

The original B1 review assembly failure and its post-hoc recovery are retained separately. In the B2 round, a manifest's HOLD status rule was initially too strict and a review-structure script first used the wrong directory; corrections were recorded without overwriting the originals. In the NEW round, authoring and preflight checks failed before model calls, a reviewer assembly check counted instruction examples as answer tags, and an auditor expanded the frozen checksum list; the original list was restored byte-for-byte, so the record must not claim it was never touched. Startup warnings, raw events, outputs, failures, corrections and detailed reviewer records remain in the local Git-external evidence store. They are not included in this repository.

Future evaluation should use newly selected, authorized real tasks where possible, preserve privacy and distinguish a suggestion from user adoption and any later observed outcome. Record whether an action was requested, whether the proposed step respected time and authorization, whether it added unnecessary work, and any user correction. A user adoption alone is not proof of a workflow improvement. If a candidate is reconsidered, bind it to the actual current base, freeze fresh evaluation conditions and preserve all attempts; promotion and exact-diff human approval follow the project standard. Do not treat these development cases as validation or holdout evidence.
