export const MAX_ITEMS = 50;

export class IngestError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

interface ItemIn {
  title?: unknown;
  url?: unknown;
  publishedAt?: unknown;
  author?: unknown;
  raw?: { _aihot?: { backfill?: boolean; baseline?: boolean } } & Record<string, unknown>;
}

export function readBatch(body: { sourceId?: unknown; items?: unknown }) {
  const sourceId = typeof body.sourceId === "string" ? body.sourceId.trim() : "";
  const items = Array.isArray(body.items) ? (body.items as ItemIn[]) : [];
  if (!sourceId || !items.length) throw new IngestError(400, "sourceId and items[] required");
  if (items.length > MAX_ITEMS) throw new IngestError(413, `items[] exceeds max ${MAX_ITEMS} per request`);
  return { sourceId, items };
}

export function readItemFields(items: ItemIn[]) {
  const candidates = [];
  for (const it of items) {
    if (!it || typeof it !== "object") continue;
    const title = typeof it.title === "string" ? it.title.trim() : "";
    const rawUrl = typeof it.url === "string" ? it.url.trim() : "";
    if (!title || !rawUrl) continue;
    candidates.push({
      title, url: rawUrl, publishedAt: typeof it.publishedAt === "string" ? it.publishedAt : null,
    });
  }
  return candidates;
}
