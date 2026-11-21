#!/usr/bin/env bash
# Run from the clean checkout, after successful same-job preflight and displacement controls.
set -euo pipefail
: "${P07_EVIDENCE:?absolute same-job evidence root with registration}"
: "${P07_CHROME:?absolute executable used for browser identity and preflight}"
[[ "$P07_EVIDENCE" = /* && "$P07_CHROME" = /* && -x "$P07_CHROME" ]]
root="$(git rev-parse --show-toplevel)"
cd "$root"
case "$P07_EVIDENCE/" in "$root/"*) echo 'Evidence must be outside the checkout' >&2; exit 1;; esac
e="$P07_EVIDENCE"
protocol="$e/registration/protocol.json"
envelope="$e/training-envelope.json"
[[ -f "$protocol" && -f "$e/preflight/measurement-preflight.json" && -f "$e/displacement/collection-manifest.json" ]]
mkdir "$e/formal-logs"
stage=initial
trap 'rc=$?; printf "stage=%s exit=%s\n" "$stage" "$rc" | tee "$e/formal-logs/exit.txt"; exit "$rc"' EXIT
run() { stage="$1"; shift; "$@" 2>&1 | tee "$e/formal-logs/$stage.log"; }
status_is() {
    python3 -B - "$1" "$2" "$protocol" <<'PY'
import hashlib, json, pathlib, sys
file, expected, protocol = sys.argv[1:]
result = json.loads(pathlib.Path(file).read_bytes())
if result.get("status") != expected or result.get("protocolSHA256") != hashlib.sha256(pathlib.Path(protocol).read_bytes()).hexdigest():
    sys.exit(f"expected {expected} for the current protocol; got {result.get('status')!r}")
PY
}
wrapper=packages/agent-skin/tools/test-startup-payload-browser.py
evaluator=packages/agent-skin/tools/test-theme-readability-measurement.py
check='theme readability is pixel bounded through viewport changes and legacy handover'
train=()
for i in 0 1 2 3 4; do
    out="$e/train-$i"
    run "train-$i" python3 -B "$wrapper" --chrome "$P07_CHROME" --only "$check" \
        --theme-protocol "$e/registration/train-$i.json" --out "$out"
    train+=("$out")
done
run training-analysis python3 -B "$evaluator" --protocol "$protocol" --runs "${train[@]}" --output "$envelope"
run training-verify status_is "$envelope" training-frozen
envelope_sha() { shasum -a 256 "$envelope" | cut -d ' ' -f1; }
frozen_sha="$(envelope_sha)"
printf '%s\n' "$frozen_sha" | tee "$e/formal-logs/training-envelope.sha256"
check_envelope() {
    [[ "$(envelope_sha)" = "$frozen_sha" ]] || { echo 'Frozen training envelope changed' >&2; return 1; }
}
# The evaluator writes the current digest and freeze timestamp into holdout configs.
run holdout-registration python3 -B "$evaluator" --register-holdout "$e/holdout-registration" \
    --protocol "$protocol" --envelope "$envelope"
holdout=()
for i in 0 1 2 3 4; do
    out="$e/holdout-$i"
    run "holdout-$i" python3 -B "$wrapper" --chrome "$P07_CHROME" --only "$check" \
        --theme-protocol "$e/holdout-registration/holdout-$i.json" --out "$out"
    holdout+=("$out")
done
run envelope-verify check_envelope
result="$e/holdout-analysis.json"
run holdout-analysis python3 -B "$evaluator" --protocol "$protocol" --runs "${holdout[@]}" \
    --envelope "$envelope" --output "$result"
run envelope-final-verify check_envelope
run holdout-verify status_is "$result" holdout-passed
