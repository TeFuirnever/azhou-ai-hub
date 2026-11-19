# Readability measurement V3: conditional raster evidence

Status: proposed evaluator contract, not product acceptance.

## Prior failures and scope
V1 strict-zero and V2 hard-max-one failures remain failed. The original temporal raster cause remains unknown. V2's 600 frames lack per-frame paint-context and retained-owner fields and cannot be relabeled V3. Collect new evidence; do not rewrite production to satisfy this measurement.

## Prospective registration
Freeze HEAD/index/all input hashes, evaluator hashes, Chrome/Node/platform and protocol JSON before collection. Four conditions: 997×613/DPR1.5/zoom0.9 and 811×577/DPR2/zoom1.1, each with #123b57 and #d8c49a. T=0,15,57,85,100. Five isolated Chrome sessions per phase; six unfiltered full-viewport PNGs per T. New process/profile every session. Preserve raw hashes outside Git.

Train in ascending T. Holdout uses new sessions alternating [57,0,100,15,85] and [85,15,100,0,57]. Freeze the write-once training envelope digest before any holdout. Never feed holdout back.

## Strict frame validity
Before and after every frame record retained controller identity/current slot equality, owner token, applied/themeApplied=true, themePending=false, connected main, document token/epoch and rectangle. A status read can dispose a stale owner: recheck identity and applied state afterward. Invalid ownership blocks collection; no silent reapply between frames.

Record computed root/body/sidebar/header background color/image/size/position/attachment/repeat, opacity, filter/backdrop-filter, transform, blend modes, zoom, viewport/DPR. Bind the actual applied SVG/scene digest using the independent XML whitelist and CSS mapping oracle. Missing fields or context drift invalidate the run. Same-T observations remain equal before/after and across frames. Across T only the final authorized workspace rect opacity may differ. All other SVG attributes/stops/geometry/CSS/scene must match. Canonicalize only the exact observed scene and mask URLs, never arbitrary URL or opacity fields.

## Conditional metrics
ROIs: topProbe (280,24,12,12), sidebarProbe (24,180,12,12), header (280,12,192,24), sidebar (24,128,96,192); fixed 24 CSS-pixel tiles; boundary (round(main.x+5),round(main.y-2),12,12), same-T only. Integer device-pixel crops come from complete raw PNGs, independently decoded as RGB with Pillow.

For all 15 same-session/same-T frame pairs compute max channel delta, changed fraction, per-channel positive/negative fractions, mean absolute delta and absolute signed mean. Freeze observed upper envelopes per registered condition/ROI/paint context with no margins. Max is calibrated like the other metrics, not forced to one; independently confirmed two-level training differences remain visible, not clipped.

Holdout compares same-T pairs plus ten cross-T first-frame pairs outside workspace; boundary is excluded only cross-T because it straddles the authorized changing region. Structure/geometry/context mismatch is hard failure. Pixel metrics above the frozen envelope are inconclusive and block acceptance. No sample exclusion, resampling, averaging, majority voting or retrospective expansion. Finite conditional bounds are not universal: changed Chrome/GPU/host/context needs fresh registration. Synthetic Chrome does not replace real Codex/DSH acceptance.

## Fault controls
Mutate actual SVG: rect y ±1 CSS pixel, global-wash replacement, exterior alpha +1/255 and +0.01. Save before/after full PNGs, require independent structure rejection and successful own-mask restoration. Record pixel-envelope detection separately for every fault/ROI; structural-only detection is not screenshot sensitivity. Stale-owner mutation, missing rejection or failed restoration is hard failure.

## Reproducibility and gate composition
Repository commands expose register → train collection → analyze/freeze → new holdout collection → analyze with explicit protocol/output/envelope hashes. No private precomputed envelope dependency. Ordinary fullChrome reports functional/structural regression separately from calibrated measurement. Collection success is never acceptance; final gate needs both lanes. Missing/inconclusive measurement blocks completion. Raw screenshots, machine receipts and TMP paths stay outside Git.

## Commands (repository root)
Use an evidence directory outside every worktree. Verify installed Chrome and Node identities before registration. Python requires Pillow.

```sh
python3 -B packages/agent-skin/tools/test-theme-readability-measurement.py --register "$EVIDENCE/registration" --browser-version "Chrome/<verified-version>" --node-version "v<verified-version>"
for i in 0 1 2 3 4; do
  python3 -B packages/agent-skin/tools/test-startup-payload-browser.py --only 'theme readability is pixel bounded through viewport changes and legacy handover' --theme-protocol "$EVIDENCE/registration/train-$i.json" --out "$EVIDENCE/train-$i" || break
done
python3 -B packages/agent-skin/tools/test-theme-readability-measurement.py --protocol "$EVIDENCE/registration/protocol.json" --runs "$EVIDENCE"/train-{0,1,2,3,4} --output "$EVIDENCE/training-envelope.json"
```

Stop unless the output is `training-frozen`; record its SHA256 before collecting holdout. Create holdout configs only now: `python3 -B packages/agent-skin/tools/test-theme-readability-measurement.py --register-holdout "$EVIDENCE/holdout-registration" --protocol "$EVIDENCE/registration/protocol.json" --envelope "$EVIDENCE/training-envelope.json"`. This binds the frozen envelope SHA256 and timestamp. Then run the identical collector with `holdout-registration/holdout-$i.json` and new `holdout-$i` output directories. Analyze with the same root protocol, all five holdout directories, `--envelope "$EVIDENCE/training-envelope.json"` and a new output. Exit 2 is inconclusive, not success. Never overwrite output or reuse a training browser. The functional full-payload/Native/preview suite remains independently required.

Collection checks HEAD, index, input inventory, bytes and modes before and after sampling; any drift blocks acceptance and remains in the report. A write-once collection manifest covers report, matrix, per-condition context JSON and every PNG. Analysis rechecks all artifacts and input identity, and excludes training browser PIDs/start times from holdout. Fault controls require specific oracle rejection, retained owner and actual injected paint before/after screenshots, plus exact restoration; generic exceptions are failures, never successful detection.

Measurement collection atomically claims a previously nonexistent output directory before protocol checks or browser startup. Existing output, even empty, is rejected without touching its contents. Preflight/finalization writes require the claimed directory identity. The payload wrapper does not precreate the collector output; do not reuse a former run directory.

Formal measurement uses the payload wrapper above, not the direct source-fixture Node runner. It builds isolated synthetic assets and the actual install.js, runs Native checks, and binds the cloned evaluator/source inventory (bytes and modes) to the registered original Git tree. Synthetic private fixtures have separate hashes; they are not approved Azhou artwork. The generated payload hash and execution-binding hash are recorded before and after collection. A generated measurement without the explicit wrapper binding is rejected.

Before expensive collection, run the same wrapper with `--measurement-preflight --theme-protocol "$EVIDENCE/registration/train-0.json" --out "$EVIDENCE/preflight"`. This still builds the actual payload and verifies original/clone/payload identities, but reports `preflight-only` and never starts Chrome or collects frames. It is not functional, visual or measurement acceptance. Use a fresh output directory for collection. Direct Node source-fixture results cannot substitute for this formal generated-payload lane.

The formal collector uses the generated install.js controller and public settings controls/save for every transparency change. It does not replace the owner with the source renderer. Each frame binds retained generated-controller and wallpaper-owner identities. The document token in this lane identifies the collector's actual Document object (explicitly labeled collector identity), not a claimed private adapter token; workspace epoch is read from the actual wallpaper status. Source-fixture runs remain diagnostics and analysis rejects their samples.

Analysis requires matching execution checkpoints and freezes stable content identity (copied source hashes, synthetic fixture hashes and exact generated payload hash) across all training sessions and holdout. Random temporary binding paths/hashes are checked within each run but are not mistaken for stable runtime content. Missing execution identity or differing content blocks analysis.

### Measurement-only scene signal and displacement controls
Only `--theme-protocol` builds replace the isolated clone's synthetic scene with a deterministic 2000×1000 opaque 19×17-source-pixel checkerboard, alternating RGB (255,96,48)/(32,96,255). The ordinary build fixture and production artwork are unchanged. The exact new fixture and payload bytes remain execution-identity inputs. Old R6 sparse-scene failures remain failed; do not reuse those frames.

Before training, run the formal wrapper with the registered protocol and `--only 'generated measurement scene detects actual image displacement in four conditions'` into a fresh directory. This is a control run, not training. All four registered conditions use the fixed 12×12 CSS-pixel ROI at (activeMain.x+35, activeMain.y+35), T=100. A test-owned CSS rule is created before settings application; during injection only its second body background layer's X or Y position changes by ±1 CSS pixel. The first mask layer, scene bytes, DOM, viewport and geometry remain unchanged. Full before/after PNGs feed the same fixed ROI. Exact structural mismatch, pixel detection (max RGB difference >1), retained controller/owner and exact structural restoration are reported separately. All four directions must be detected. The old crop-shift comparator remains a sampling-offset diagnostic, not an actual image-shift fault.

These controls also run inside each formal collection and are included in its sealed evidence manifest. Unregistered full-suite source-renderer sampling remains explicitly diagnostic; only registered collection uses generated-payload/public-settings evidence and is eligible for V3 analysis.

When combined with `--native-window-ordering`, measurement leaves the collector's output uncreated until its atomic claim and stores Native window-ordering evidence in the adjacent `<out>-native-window-ordering` directory. Both paths must be fresh. Ordinary browser runs retain the upstream nested Native evidence directory and strict full browser-report validation. Measurement preflight has a separate sealed preflight receipt; it is never represented as a successful browser report.
