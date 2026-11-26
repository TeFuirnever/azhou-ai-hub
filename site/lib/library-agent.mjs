import { answer } from "../vendor/aihot/agent-answer.mts";

const libraryPaths = {
  en: "/library/",
  zh: "/zh/library/",
};

const textEntities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", "［": "&#65339;", "］": "&#65341;" };

function markdownText(value) {
  return value.replace(/\s+/gu, " ").trim()
    .replace(/[&<>［］]/gu, (character) => textEntities[character])
    .replace(/[\\\x60*_[\]{}#!|~]/gu, "\\$&");
}

function originalUrl(value) {
  const url = new URL(value);
  if (url.protocol !== "https:" || url.username || url.password) {
    throw new Error("The Source Library requires an HTTPS original URL");
  }
  return url.href;
}

function markdownLink(label, url) {
  return "[" + markdownText(label) + "](<" + url + ">)";
}

function articleLines(items, locale) {
  const zh = locale === "zh";
  return items.flatMap((item, index) => {
    const note = item.notes[locale];
    const reference = [
      markdownText(item.source_names.join(" / ")),
      zh ? (item.scope === "full" ? "站内全文" : "原文链接") : (item.scope === "full" ? "Full archive" : "Link to original"),
    ];
    if (item.published_at) {
      reference.push((zh ? "原文发布于 " : "Originally published ") + markdownText(item.published_at));
    }
    return [
      (index + 1) + ". " + markdownLink(item.title, item.article_urls[locale]),
      "   " + reference.join(" · "),
      "   " + markdownLink(zh ? "原始出处" : "Original source", item.original_url),
      ...(note ? ["   " + (zh ? "阿舟导读：" : "Azhou’s reading note: ") + markdownText(note)] : []),
      "",
    ];
  });
}

export function libraryAgentFiles(library, siteUrl) {
  if (library.preview) return {};

  const sourceNames = new Map(library.channels.map(({ id, name }) => [id, name]));
  const selected = library.entries.map((entry) => ({
    id: entry.id,
    title: entry.title,
    source_ids: entry.sources,
    source_names: entry.sources.map((id) => sourceNames.get(id)),
    scope: entry.scope,
    kind: entry.kind,
    published_at: entry.published || null,
    first_published_at: entry.first_published,
    original_url: originalUrl(entry.url),
    article_urls: {
      en: siteUrl + libraryPaths.en + "articles/" + entry.id + "/",
      zh: siteUrl + libraryPaths.zh + "articles/" + entry.id + "/",
    },
    notes: { zh: entry.note, en: entry.noteEn || entry.note },
    ...(entry.scope === "full" ? { license: entry.license } : {}),
  }));
  const catalog = siteUrl + "/library/catalog.json";
  const rss = siteUrl + "/library/rss.xml";
  const en = siteUrl + libraryPaths.en;
  const zh = siteUrl + libraryPaths.zh;

  return {
    "llms.txt": [
      "# Azhou Source Library · 阿舟来源库",
      "",
      "> Editor-reviewed selections from official AI sources. 阿舟来源库的官方信源选文。",
      "",
      "- " + markdownLink("中文 Markdown", zh + "agent.md"),
      "- " + markdownLink("English Markdown", en + "agent.md"),
      "- " + markdownLink("JSON catalog", catalog),
      "- " + markdownLink("RSS", rss),
      "",
    ].join("\n"),
    "library/agent.md": answer([
      "# Azhou Source Library",
      "",
      "Browse " + markdownLink("the Source Library", en) + ", read the " + markdownLink("JSON catalog", catalog) +
        ", or subscribe to " + markdownLink("RSS", rss) + ".",
    ], selected.length ? articleLines(selected, "en") : null, [
      "Cite the article’s original publisher and URL.",
      "For full text, follow the published archive link when available. Link-only entries provide an editorial note and an original URL.",
    ], "en"),
    "zh/library/agent.md": answer([
      "# 阿舟来源库",
      "",
      markdownLink("打开来源库", zh) + " · " + markdownLink("JSON 目录", catalog) + " · " + markdownLink("RSS 订阅", rss),
    ], selected.length ? articleLines(selected, "zh") : null, [
      "引用时注明原发布者和原文链接。",
      "标为站内全文的条目可打开阿舟归档。链接条目提供导读和原文链接。",
    ], "zh"),
    "library/catalog.json": JSON.stringify({ schema_version: 1, articles: selected }, null, 2) + "\n",
  };
}
