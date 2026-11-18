# Approved entry points and their argument shapes. Adding a script under
# skills/ does not grant it automatic approval. Unknown forms stay silent.
BEGIN {
  CONTRACT["skills/show-me-your-work/scripts/log.sh"] = "log"
  CONTRACT["skills/setup-pstack/scripts/check-sheet.sh"] = "optional-path"
}

function script_contract(script, runner, T, first, n,    kind, count, i) {
  if (!(script in CONTRACT)) return 0
  kind = CONTRACT[script]
  if (runner != "") {
    if (kind == "log") { if (runner != "bash") return 0 }
    else if (runner != "sh" && runner != "bash") return 0
  }
  count = n - first + 1
  if (kind == "log") return count == 6 && safe_path(T[first])
  if (kind == "optional-path" && count > 1) return 0
  for (i = first; i <= n; i++) if (!safe_path(T[i])) return 0
  return 1
}
