const xml = (value) => String(value ?? "").replace(/[<>&"']/g, (char) => ({
  "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&apos;",
})[char]);

export function renderFeed({ title, link, self, description, entries, articleUrl, sourceTitle }) {
  const rows = [...entries].sort((a, b) => b.first_published.localeCompare(a.first_published) ||
    a.id.localeCompare(b.id));
  const items = rows.map((item) => [
    "    <item>",
    `      <title>${xml(item.title)}</title>`,
    `      <link>${xml(articleUrl(item))}</link>`,
    `      <guid isPermaLink="false">urn:azhou:source-library:${item.id}</guid>`,
    `      <pubDate>${new Date(item.first_published).toUTCString()}</pubDate>`,
    `      <category>${xml(sourceTitle(item))}</category>`,
    `      <description>${xml(item.note)}</description>`,
    "    </item>",
  ].join("\n"));
  return [
    '<?xml version="1.0" encoding="utf-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    "  <channel>",
    `    <title>${xml(title)}</title>`,
    `    <link>${xml(link)}</link>`,
    `    <description>${xml(description)}</description>`,
    `    <atom:link href="${xml(self)}" rel="self" type="application/rss+xml"/>`,
    ...items,
    "  </channel>",
    "</rss>",
    "",
  ].join("\n");
}
