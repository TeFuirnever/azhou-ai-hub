# Safe prose compression

Compress only natural-language files: Markdown, text, reStructuredText, Typst, TeX, or a verified extensionless prose file. Refuse code, configuration, environment files, lockfiles, HTML, SQL, shell scripts, backup files, files above 500 KB, and paths whose names indicate credentials, keys, secrets, or tokens.

## Workflow

1. Run preflight:

   ```bash
   python3 "$SKILL_DIR/scripts/compression_guard.py" preflight /absolute/path/to/file --json
   ```

2. Read the source. Create a candidate in a temporary path without changing the source. Compress prose only.
3. Preserve YAML frontmatter, headings, fenced code, inline code, URLs, link targets, paths, commands, technical identifiers, dates, versions, numbers, list hierarchy, and table structure.
4. Validate:

   ```bash
   python3 "$SKILL_DIR/scripts/compression_guard.py" validate /absolute/path/to/file /absolute/path/to/candidate --json
   ```

5. Fix only reported mismatches. Retry at most twice. Never recompress an already valid section merely to repair one mismatch.
6. Apply only after validation passes:

   ```bash
   python3 "$SKILL_DIR/scripts/compression_guard.py" apply /absolute/path/to/file /absolute/path/to/candidate --json
   ```

The guard mechanically compares its recognized command forms, camel-case or uppercase identifiers, dates, versions, and numbers. It does not recognize every lowercase library or product name. The active agent must still perform semantic readback and preserve unrecognized names exactly.

The apply command takes a per-source non-blocking lock, writes a verified out-of-tree backup and receipt, proves same-directory hard-link support before moving the source, then creates a handoff checkpoint. It verifies that displaced file against the preflight hash and installs the prepared candidate with a no-overwrite link. If another writer changes the checkpoint or recreates the source path, the candidate is not installed; current external work is restored or retained. A process holding the old file descriptor can still write the displaced inode after installation, so the guard keeps every handoff path in the receipt instead of unlinking it. Restore and finalize block if that evidence changed. A detected conflict keeps the verified backup and marks the receipt `conflict`. On POSIX, the state directory is mode `0700` and backup, receipt, and lock files are mode `0600`.

UTF-8 reads preserve the source's LF or CRLF bytes. The backup and restore path is byte-exact for supported newline forms; a candidate that changes protected structure through newline normalization does not bypass validation.

## Restore

Restore only when the current source hash still matches the receipt's compressed hash:

```bash
python3 "$SKILL_DIR/scripts/compression_guard.py" restore /absolute/path/to/file --json
```

If the current file changed after compression, stop. Do not force restoration over newer work. A `conflict` receipt can be reconciled by running restore again only when the current hash still equals the recorded original or compressed hash; any third hash remains a manual hold.

Successful restore retains the verified backup, all recorded handoffs, and a `restored` receipt. Close every editor or process that may still hold the old file, then explicitly finalize:

```bash
python3 "$SKILL_DIR/scripts/compression_guard.py" finalize /absolute/path/to/file --json
```

Finalize requires the current source and backup to match the original hash and every handoff to match its recorded checkpoint hash. It removes the verified backup and handoffs, then retains an idempotent `finalized` receipt until the next apply retires it. A `finalizing` receipt resumes partial cleanup safely. Finalize is required before another apply; a changed handoff or incomplete state remains a manual hold.

Finalize deletes recovery evidence. A general compress or restore request does not authorize it: report the exact backup, receipt, and handoff paths, then require explicit user confirmation for `finalize`.

## Data boundary

Do not launch another model CLI or SDK from the guard. The active agent performs transformation through its authorized context; deterministic scripts inspect local files only. Do not send file content over network tools unless the user explicitly authorizes that separate data transfer.

Warnings are not success. Return the backup path, original and compressed SHA-256 values, validation result, and any hold in the final receipt.
