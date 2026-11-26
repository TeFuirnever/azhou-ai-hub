export function getPath(obj: unknown, path: string): unknown {
  if (!path) return obj;
  let cur: unknown = obj;
  for (const seg of path.split(".")) {
    if (cur === null || cur === undefined) return undefined;
    if (Array.isArray(cur) && /^\d+$/.test(seg)) cur = cur[Number(seg)];
    else if (typeof cur === "object") cur = (cur as Record<string, unknown>)[seg];
    else return undefined;
  }
  return cur;
}

function firstString(obj: unknown, paths: string[] | undefined): string | null {
  for (const p of paths ?? []) {
    const v = getPath(obj, p);
    if (typeof v === "string" && v.trim()) return v.trim();
    if (typeof v === "number") return String(v);
  }
  return null;
}

/** "{path}" → encoded value, "{raw:path}" → raw value. Returns null when a referenced value is missing. */
export function renderTemplate(template: string, item: unknown): string | null {
  let missing = false;
  const out = template.replace(/\{(raw:)?([^}]+)\}/g, (_m, raw: string | undefined, path: string) => {
    const v = getPath(item, path);
    if (v === undefined || v === null || v === "") {
      missing = true;
      return "";
    }
    return raw ? String(v) : encodeURIComponent(String(v)).replace(/%2F/g, "/");
  });
  return missing ? null : out;
}

export { firstString };
