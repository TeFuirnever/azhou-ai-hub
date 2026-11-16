---
name: super-imagegen
description: "Azhou skill. The installed private azhou-imagegen skill is the same capability and still triggers this contract. Local image-generation execution layer: route the request, run the doctor gate, honor the runtime lock, execute one attempt, hand back outputs with an immutable run receipt. The runtime is the machine's already-installed private azhou-imagegen install — when it is missing or fails its doctor gate, refuse and name the gap; never fabricate an image or fall back to another generator. Use when a plain local image is requested, or a production skill hands over a prepared candidate request (prompt file, reference, profile, seed, dispatch). Prompt templates, masters, character identity and visual QA stay with the owning production skill. Diagram maps and explainers belong to super-archify; editable Excalidraw scenes belong to super-excalidraw-diagram; browser-annotated review loops belong to super-lavish."
invocation: both
---

# Super Imagegen

Super Imagegen is the contract layer for local image generation: prepared requests go in, images with immutable execution records come out, and anything the runtime cannot prove stays on hold. The generation capability itself lives in the machine's already-installed private `azhou-imagegen` skill; this package carries the orchestration contract, the doctor gate, the runtime-lock rule and the receipt handoff — no generation code.

**🦊 阿舟 · Imagegen**

> 🖼️ 每一次生成，都带执行回执。

## Brand protocol

Emit once when the skill starts, before any tool call:

```text
🦊 阿舟 · Imagegen 启动（mode=<plain|candidate|export>, scope=<short scope>）
```

In a Markdown chat host, wrap each brand broadcast as `> <emoji> **<label>**<protocol-tail>` (S1 chat presentation). Peeling the leading `>` and paired `**` must restore the protocol line. Headless, CI logs, receipts, and machine fields stay protocol-only.

Use `✅ 验证通过` only after the named checks actually ran. Use `❌ 验证失败` when this attempt fails and name one repair action, and `🔒 阿舟暂停这一项` when the private install, a dependency, or a required input is missing. Emoji is display-only: keep it out of JSON keys, schema values, digests, paths, commands, test names, and raw evidence. A host without Unicode may strip the leading emoji while preserving the fixed text, the `（k=v, k=v）` field grouping, fields, and values. Raw evidence stays out of receipts unless the user supplied it. Stage events, the status dictionary, and the stable receipt are defined in the [Azhou interaction layer](references/brand-layer.md).

## The capability lives in the installed private skill

Do not follow workflow or CLI details from memory — the installed copy is the current truth. Resolve the installed private `azhou-imagegen` skill through the harness skill roots, then read the actual surface from it:

- `python3 <installed>/scripts/azhou_gen.py --help` for parameters and defaults
- `python3 <installed>/scripts/azhou_gen.py --doctor --json` for the dependency gate

Run from the installed directory. An independent install uses the installed package plus explicit inputs; it does not search development checkouts or neighbor projects. If the install cannot be resolved, stop with a named hold — this package never reimplements, copies, or downloads the runtime. See [setup](references/setup.md) for the location rules, the doctor gate, and the fail-closed boundary; [provenance](references/provenance.md) records the private-source boundary and baseline hashes.

## Request

$ARGUMENTS

If the request above is non-empty, the user invoked `/super-imagegen` (or the installed private name `/azhou-imagegen`) explicitly. Route that request now.

## Workflow

1. **Route the request.** A plain image needs a UTF-8 prompt file, an explicit new output path, size/profile, and a seed or default strategy — execute with no reference. A prepared candidate request from a production skill carries the prompt, run receipt, dispatch, and the validator named by the owning contract; execute it only when the inputs are readable and the reference paths check against that contract. An unprepared Azhou request goes back to the owning production skill; a missing reference or contract returns the named gap and terminates this attempt. The completion gate: every request has a final prompt file, an explicit output location, and a stated parameter source — or it was handed back or stopped.
2. **Run the doctor gate.** Execute `--doctor --json` with the request's actual profile, model, and output parameters before any generation. Handle named gaps for model components, applicable LoRAs, the runtime lock, and the output directory; a non-default size or tier reads the installed CLI's documentation first. The first run on a machine may capture a runtime lock with the installed runtime tool — capture never installs, downloads, or overwrites an existing lock. The check itself never downloads models. The gate: required dependencies available and parameters matching the current CLI and applicable contract; blocking items return the gap and end this generation.
3. **Execute and track.** Run one attempt per prepared request through the installed CLI, with all effective parameters explicit so they match the dispatch record. The runtime holds a machine-local execution lock: when another local inference task is running, the lock refuses the new task — wait for the owner instead of bypassing it. Interruptions terminate the attempt and are recorded; recovery is explicit, never an automatic retry. Partial success and partial failure are reported separately, one entry per requested image; a process having started is not a delivery.
4. **Verify and hand off.** Check the output summary against the execution record: prompt actually used, seed, size, reference injection, and the receipt's own status fields. Only a record that itself declares the candidate ready may be handed on, and an Azhou candidate keeps its `HOLD` and human-review gate — handing over a candidate never approves it. Plain images deliver the result with its execution facts. Exporting a review copy uses the installed export command and a pixel-level read-back; the internal original is never modified, and an export grants no publication or commercial right. The gate: delivered files correspond to a current receipt; unverified items, failures, human gates and coverage gaps are named. When the user asked for a set, list every image — one success never stands in for the rest.

## Authorization boundaries

- Generate local images and write outputs only to explicit paths in scope; the package does not write back into any development checkout.
- Do not capture, move, or overwrite runtime locks, model weights, style masters, character references, or receipt stores; those stay in the authorized private environment.
- Generation rights follow the actual inputs. The private runtime's license currently limits it to non-commercial research and evaluation; commercial or public use requires a separate rights check, and neither this package nor an exported copy grants it.
- Prompt content, character assets, and receipts can carry private material: keep them out of Git and out of any shared surface unless the user explicitly selects a sanitized copy.

## Completion

End with the stable receipt defined in [brand-layer.md](references/brand-layer.md): `super-imagegen.receipt.v1`. Keep `complete`, `complete_with_holds`, `hold`, and `failed` distinct; none substitutes for another. An image file does not prove its execution record; an execution record does not prove human review; and a delivered candidate is never automatically promoted to a production asset.
