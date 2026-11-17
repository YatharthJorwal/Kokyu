// A small Markdown parser for replies (K1-04, FR-C-8). It returns a tree that
// ui/Markdown.tsx turns into React elements, so model output never reaches the
// page as HTML: nothing to sanitize, nothing to inject (D-013 "sanitizing renderer").
// It also copes with a reply that is still streaming (an unclosed code fence).
//
// Roleplay threads (K1c-08, FR-MODE-7) parse with `{ roleplay: true }`: a `*…*`
// span is an action (shown italic and softer), and an out-of-character aside,
// `(OOC …)` or `((…))`, is its own node (shown small and muted). Chat parsing is
// unchanged, so "install it (with pip)" stays plain text there.
//
// shortcut: no tables, nested lists, images or reference links; add them (or a
// vetted library) if replies need them.

export type Inline =
  | { t: "text"; v: string }
  | { t: "code"; v: string }
  | { t: "strong"; c: Inline[] }
  | { t: "em"; c: Inline[] }
  | { t: "link"; href: string; c: Inline[] }
  | { t: "br" }
  /** Roleplay only: `*…*`, an action or narration. */
  | { t: "action"; c: Inline[] }
  /** Roleplay only: an out-of-character aside, parentheses included. */
  | { t: "ooc"; c: Inline[] };

export interface ParseOptions {
  /** Parse for a roleplay thread (FR-MODE-7). */
  roleplay?: boolean;
}

export type Block =
  | { t: "p"; c: Inline[] }
  | { t: "h"; level: 1 | 2 | 3; c: Inline[] }
  | { t: "code"; lang: string; v: string; open: boolean }
  | { t: "list"; ordered: boolean; start: number; items: Inline[][] }
  | { t: "quote"; c: Block[] }
  | { t: "hr" };

// Any indent, so a fence inside a list item still opens a block; the language is
// the info string's first word (```python title="a.py").
const FENCE = /^\s*(`{3,}|~{3,})\s*([^\s`]*)[^`]*$/;
const HEADING = /^ {0,3}(#{1,6})\s+(.*)$/;
const BULLET = /^ {0,3}[-*+]\s+(.*)$/;
const ORDERED = /^ {0,3}(\d{1,9})[.)]\s+(.*)$/;
const RULE = /^ {0,3}([-*_])(\s*\1){2,}\s*$/;
const QUOTE = /^ {0,3}>\s?(.*)$/;
// Deeper nesting stays plain text, so a hostile reply cannot overflow the stack.
const MAX_DEPTH = 16;
// An aside longer than this stays text: keeps a hostile "((((…" from costing n² work.
const OOC_MAX = 2000;
// "(OOC", "(ooc:", "( OOC -" … : the word OOC right after the parenthesis.
const OOC_START = /^\(\s*ooc\b/i;

/** A heading's text without its closing #s ("C#" keeps its #). A loop, not a regex: no backtracking. */
function headingText(s: string): string {
  const t = s.trimEnd();
  let j = t.length;
  while (j > 0 && t[j - 1] === "#") j -= 1;
  return j === t.length || (j > 0 && !/\s/.test(t[j - 1])) ? t : t.slice(0, j).trim();
}

export function parseMarkdown(text: string, options: ParseOptions = {}, depth = 0): Block[] {
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
      out.push({ t: "h", level: Math.min(3, heading[1].length) as 1 | 2 | 3, c: parseInline(headingText(heading[2]), options) });
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
      const inner = body.join("\n");
      out.push({
        t: "quote",
        c: depth < MAX_DEPTH ? parseMarkdown(inner, options, depth + 1) : [{ t: "p", c: [{ t: "text", v: inner }] }],
      });
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
        } else if (lines[i].trim() !== "" && /^\s+/.test(lines[i]) && items.length > 0 && !FENCE.test(lines[i])) {
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
        items: items.map((it) => parseInline(it, options)),
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
    out.push({ t: "p", c: parseInline(para.join("\n"), options) });
  }
  return out;
}

/** Only web and mail links are kept; anything else (javascript:, file:, data:) stays text. */
export function safeHref(href: string): string | null {
  const h = href.trim();
  return /^(https?:\/\/|mailto:)/i.test(h) ? h : null;
}

export function parseInline(text: string, options: ParseOptions = {}, depth = 0): Inline[] {
  if (depth > MAX_DEPTH) return [{ t: "text", v: text }];
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
    if (options.roleplay && ch === "(" && (rest.startsWith("((") || OOC_START.test(rest))) {
      const end = asideEnd(text, i, rest.startsWith("(("));
      if (end > i) {
        flush();
        // Inside the aside, ordinary Markdown (an aside has no actions or asides of its own).
        out.push({ t: "ooc", c: parseInline(text.slice(i, end + 1), {}, depth + 1) });
        i = end + 1;
        continue;
      }
    }
    if ((ch === "*" || ch === "_") && rest.startsWith(ch + ch)) {
      const end = text.indexOf(ch + ch, i + 2);
      if (end > i + 2) {
        flush();
        out.push({ t: "strong", c: parseInline(text.slice(i + 2, end), options, depth + 1) });
        i = end + 2;
        continue;
      }
    }
    if (ch === "*" || (ch === "_" && (i === 0 || !/\w/.test(text[i - 1])))) {
      const end = findEmphasisEnd(text, i + 1, ch);
      if (end > i + 1) {
        flush();
        const c = parseInline(text.slice(i + 1, end), options, depth + 1);
        // In a roleplay, *…* is an action; _…_ stays ordinary emphasis.
        out.push(options.roleplay && ch === "*" ? { t: "action", c } : { t: "em", c });
        i = end + 1;
        continue;
      }
    }
    if (ch === "[") {
      // One level of balanced parentheses in the address (Wikipedia's Foo_(bar)).
      const m = /^\[([^\]\n]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)/.exec(rest);
      const href = m ? safeHref(m[2]) : null;
      if (m && href) {
        flush();
        out.push({ t: "link", href, c: parseInline(m[1], options, depth + 1) });
        i += m[0].length;
        continue;
      }
    }
    if ((ch === "h" || ch === "H") && (i === 0 || /[\s(]/.test(text[i - 1]))) {
      let url = /^https?:\/\/(?:[^\s<>()]|\([^\s<>()]*\))+/i.exec(rest)?.[0] ?? "";
      while (/[.,;:!?'"]$/.test(url)) url = url.slice(0, -1); // sentence punctuation is not the address
      if (/^https?:\/\/./i.test(url)) {
        flush();
        out.push({ t: "link", href: url, c: [{ t: "text", v: url }] });
        i += url.length;
        continue;
      }
    }
    buf += ch;
    i += 1;
  }
  flush();
  return out;
}

/** Where an aside opened at `from` closes: its balancing parenthesis, on the same line
 * and within OOC_MAX; a `((` aside must close with `))`. -1 when it does not close
 * (yet: a reply still streaming shows it as text until it does). */
function asideEnd(text: string, from: number, double: boolean): number {
  let depth = 0;
  const stop = Math.min(text.length, from + OOC_MAX);
  for (let j = from; j < stop; j += 1) {
    const c = text[j];
    if (c === "\n") return -1;
    if (c === "\\") {
      j += 1; // an escaped parenthesis does not count
      continue;
    }
    if (c === "(") depth += 1;
    else if (c === ")") {
      depth -= 1;
      if (depth === 0) return !double || text[j - 1] === ")" ? j : -1;
    }
  }
  return -1;
}

function findEmphasisEnd(text: string, from: number, ch: string): number {
  // A closing marker not followed by a word character (for "_") and not doubled.
  for (let j = from; j < text.length; j += 1) {
    if (text[j] === "\n") return -1;
    if (text[j] === ch && text[j + 1] === ch) {
      j += 1; // a doubled marker (bold inside, FR-MODE-7) is one unit, never a closer
      continue;
    }
    if (text[j] === ch && text[j + 1] !== ch && text[j - 1] !== " " && !(ch === "_" && /\w/.test(text[j + 1] ?? ""))) {
      return j > from ? j : -1;
    }
  }
  return -1;
}
