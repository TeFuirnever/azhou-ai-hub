export function validateCheckSelection(selectedChecks, availableChecks) {
  const available = availableChecks instanceof Set ? availableChecks : new Set(availableChecks);
  const missingChecks = [...new Set(selectedChecks)].filter(name => !available.has(name));
  return { valid: missingChecks.length === 0, missingChecks };
}
