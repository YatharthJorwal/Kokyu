// A small Markdown parser for replies (K1-04, FR-C-8). It returns a tree that
// ui/Markdown.tsx turns into React elements, so model output never reaches the
// page as HTML: nothing to sanitize, nothing to inject (D-013 "sanitizing renderer").
// It also copes with a reply that is still streaming (an unclosed code fence).
//
// shortcut: no tables, nested lists, images or reference links; add them (or a
// vetted library) if replies need them.

export type Inline =
  | { t: "text"; v: string }
  | { t: "code"; v: string }
  | { t: "strong"; c: Inline[] }
  | { t: "em"; c: Inline[] }
  | { t: "link"; href: string; c: Inline[] }
  | { t: "br" };

export type Block =
  | { t: "p"; c: Inline[] }
  | { t: "h"; level: 1 | 2 | 3; c: Inline[] }
  | { t: "code"; lang: string; v: string; open: boolean }
  | { t: "list"; ordered: boolean; start: number; items: Inline[][] }
  | { t: "quote"; c: Block[] }
  | { t: "hr" };

const FENCE = /^ {0,3}(`{3,}|~{3,})\s*([\w+#.-]*)\s*$/;
const HEADING = /^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$/;
const BULLET = /^ {0,3}[-*+]\s+(.*)$/;
const ORDERED = /^ {0,3}(\d{1,9})[.)]\s+(.*)$/;
const RULE = /^ {0,3}([-*_])(\s*\1){2,}\s*$/;
const QUOTE = /^ {0,3}>\s?(.*)$/;

export function parseMarkdown(text: string): Block[] {
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  const out: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === "") {
      i += 1;
      continue;
    }
    const fence = FENCE.exec(line);
    if (fence) {
      const marker = fence[1];
      const body: string[] = [];
      i += 1;
      let open = true;
      while (i < lines.length) {
        if (lines[i].trim().startsWith(marker[0].repeat(marker.length)) && lines[i].trim().replace(/[`~]/g, "") === "") {
          open = false;
          i += 1;
          break;
        }
        body.push(lines[i]);
        i += 1;
      }
      out.push({ t: "code", lang: fence[2], v: body.join("\n"), open });
      continue;
    }
    const heading = HEADING.exec(line);
    if (heading) {
      out.push({ t: "h", level: Math.min(3, heading[1].length) as 1 | 2 | 3, c: parseInline(heading[2]) });
      i += 1;
      continue;
    }
    if (RULE.test(line)) {
      out.push({ t: "hr" });
      i += 1;
      continue;
    }
    if (QUOTE.test(line)) {
      const body: string[] = [];
      while (i < lines.length && QUOTE.test(lines[i])) {
        body.push((QUOTE.exec(lines[i]) as RegExpExecArray)[1]);
        i += 1;
      }
      out.push({ t: "quote", c: parseMarkdown(body.join("\n")) });
      continue;
    }
    const bullet = BULLET.exec(line);
    const ordered = ORDERED.exec(line);
    if (bullet || ordered) {
      const isOrdered = !bullet;
      const pattern = isOrdered ? ORDERED : BULLET;
      const items: string[] = [];
      while (i < lines.length) {
        const m = pattern.exec(lines[i]);
        if (m) {
          items.push(isOrdered ? m[2] : m[1]);
        } else if (lines[i].trim() !== "" && /^\s+/.test(lines[i]) && items.length > 0) {
          items[items.length - 1] += `\n${lines[i].trim()}`; // an indented continuation line
        } else {
          break;
        }
        i += 1;
      }
      out.push({
        t: "list",
        ordered: isOrdered,
        start: ordered ? Number(ordered[1]) : 1,
        items: items.map(parseInline),
      });
      continue;
    }
    // A paragraph runs until a blank line or the start of another block.
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !(para.length > 0 && (FENCE.test(lines[i]) || HEADING.test(lines[i]) || QUOTE.test(lines[i]) || BULLET.test(lines[i]) || ORDERED.test(lines[i])))
    ) {
      para.push(lines[i]);
      i += 1;
    }
    out.push({ t: "p", c: parseInline(para.join("\n")) });
  }
  return out;
}

/** Only web and mail links are kept; anything else (javascript:, file:, data:) stays text. */
export function safeHref(href: string): string | null {
  const h = href.trim();
  return /^(https?:\/\/|mailto:)/i.test(h) ? h : null;
}

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  let buf = "";
  const flush = () => {
    if (buf) out.push({ t: "text", v: buf });
    buf = "";
  };
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    const rest = text.slice(i);
    if (ch === "\\" && i + 1 < text.length && /[\\`*_[\]()#+\-.!>~]/.test(text[i + 1])) {
      buf += text[i + 1];
      i += 2;
      continue;
    }
    if (ch === "\n") {
      flush();
      out.push({ t: "br" });
      i += 1;
      continue;
    }
    if (ch === "`") {
      const ticks = /^`+/.exec(rest)?.[0] ?? "`";
      const end = text.indexOf(ticks, i + ticks.length);
      if (end > i) {
        flush();
        out.push({ t: "code", v: text.slice(i + ticks.length, end).trim() || text.slice(i + ticks.length, end) });
        i = end + ticks.length;
        continue;
      }
    }
    if ((ch === "*" || ch === "_") && rest.startsWith(ch + ch)) {
      const end = text.indexOf(ch + ch, i + 2);
      if (end > i + 2) {
        flush();
        out.push({ t: "strong", c: parseInline(text.slice(i + 2, end)) });
        i = end + 2;
        continue;
      }
    }
    if (ch === "*" || (ch === "_" && (i === 0 || !/\w/.test(text[i - 1])))) {
      const end = findEmphasisEnd(text, i + 1, ch);
      if (end > i + 1) {
        flush();
        out.push({ t: "em", c: parseInline(text.slice(i + 1, end)) });
        i = end + 1;
        continue;
      }
    }
    if (ch === "[") {
      const m = /^\[([^\]\n]+)\]\(([^)\s]+)\)/.exec(rest);
      const href = m ? safeHref(m[2]) : null;
      if (m && href) {
        flush();
        out.push({ t: "link", href, c: parseInline(m[1]) });
        i += m[0].length;
        continue;
      }
    }
    if ((ch === "h" || ch === "H") && (i === 0 || /[\s(]/.test(text[i - 1]))) {
      const m = /^https?:\/\/[^\s<>()]+[^\s<>().,;:!?'"]/i.exec(rest);
      if (m) {
        flush();
        out.push({ t: "link", href: m[0], c: [{ t: "text", v: m[0] }] });
        i += m[0].length;
        continue;
      }
    }
    buf += ch;
    i += 1;
  }
  flush();
  return out;
}

function findEmphasisEnd(text: string, from: number, ch: string): number {
  // A closing marker not followed by a word character (for "_") and not doubled.
  for (let j = from; j < text.length; j += 1) {
    if (text[j] === "\n") return -1;
    if (text[j] === ch && text[j + 1] !== ch && text[j - 1] !== " " && !(ch === "_" && /\w/.test(text[j + 1] ?? ""))) {
      return j > from ? j : -1;
    }
  }
  return -1;
}
