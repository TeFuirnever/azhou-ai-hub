# super-prose-standard benchmark

Wiring-integrity suite for the recall batteries, registered in the repository verify gate. It runs the probe over the calibration corpus under `tests/fixtures/super-prose-standard/` and requires:

- every leakage fixture produces at least one probe hit (a zero-hit probe proves nothing until it matches a known positive);
- the keep corpus produces exactly the documented false-positive families — version identifiers, external standard sections, runtime old/new lifecycle — so any probe change that alters the over-match envelope fails here.

Fixtures prove probe wiring only; they are never benchmark evidence about model behavior.
