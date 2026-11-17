// Code colouring for replies (UI1-08, D-093): a small in-house tokenizer, no
// dependency. It knows comments, strings, numbers, keywords, literals and calls for
// the languages models write most; anything else stays plain. Pure and linear, so a
// reply that is still streaming can be coloured on every token.
//
// shortcut: a lexer per language family, not a grammar: a regex literal or a nested
// template string can colour wrongly. Swap in a vetted library if that matters.

export type TokenKind = "" | "kw" | "str" | "com" | "num" | "fn" | "lit";

export interface Token {
  k: TokenKind;
  v: string;
}

interface Family {
  /** Display name for the code block's header. */
  label: string;
  keywords: Set<string>;
  literals: Set<string>;
  line: string[];
  block: [string, string] | null;
  /** Characters that open a string. */
  quotes: string;
  /** `#` starts a comment only at a line start or after a space (shells). */
  hashNeedsSpace?: boolean;
  /** `$name` is a variable (shells). */
  dollarVars?: boolean;
  /** JSON: a string before `:` is a key. */
  keys?: boolean;
  /** HTML and XML: the tag names. */
  tags?: boolean;
  /** Python and friends: `"""` / `'''` strings span lines. */
  triple?: boolean;
}

const words = (s: string) => new Set(s.split(/\s+/).filter(Boolean));

const C_LITERALS = words("true false null undefined NaN Infinity nullptr nil this self super");

const JS: Family = {
  label: "JavaScript",
  keywords: words(
    "async await break case catch class const continue debugger default delete do else enum export extends finally for from function if implements import in instanceof interface let new of package private protected public readonly return static switch throw try type typeof var void while with yield as declare keyof namespace satisfies abstract",
  ),
  literals: C_LITERALS,
  line: ["//"],
  block: ["/*", "*/"],
  quotes: "\"'`",
};

const PYTHON: Family = {
  label: "Python",
  keywords: words(
    "and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield match case print",
  ),
  literals: words("True False None self cls"),
  line: ["#"],
  block: null,
  quotes: "\"'",
  triple: true,
};

const SHELL: Family = {
  label: "Bash",
  keywords: words("if then else elif fi for while until do done case esac in function return local export source alias echo cd exit set unset readonly shift sudo"),
  literals: words("true false"),
  line: ["#"],
  block: null,
  quotes: "\"'",
  hashNeedsSpace: true,
  dollarVars: true,
};

const POWERSHELL: Family = {
  label: "PowerShell",
  keywords: words(
    "begin break catch class continue data do dynamicparam else elseif end exit filter finally for foreach from function if in param process return switch throw trap try until using var while",
  ),
  literals: words("$true $false $null"),
  line: ["#"],
  block: ["<#", "#>"],
  quotes: "\"'",
  hashNeedsSpace: true,
  dollarVars: true,
};

const C_LIKE = (label: string, extra: string): Family => ({
  label,
  keywords: words(
    "auto break case catch char class const continue default do double else enum extern float for goto if inline int long namespace new private protected public register return short signed sizeof static struct switch template throw try typedef union unsigned using virtual void volatile while bool string var let fn mut impl trait pub use mod match loop where crate move ref dyn func package import go defer chan select range type interface map final abstract extends implements interface throws instanceof boolean byte override async await yield foreach in out is as readonly sealed " +
      extra,
  ),
  literals: C_LITERALS,
  line: ["//"],
  block: ["/*", "*/"],
  quotes: "\"'`",
});

const JSON_FAMILY: Family = {
  label: "JSON",
  keywords: new Set(),
  literals: words("true false null"),
  line: [],
  block: null,
  quotes: '"',
  keys: true,
};

const SQL: Family = {
  label: "SQL",
  keywords: words(
    "select from where and or not insert into values update set delete create table index view drop alter add column primary key foreign references join left right inner outer full on group by order having limit offset as distinct union all case when then else end is in like between exists returning with default unique constraint begin commit rollback",
  ),
  literals: words("null true false"),
  line: ["--"],
  block: ["/*", "*/"],
  quotes: "'\"",
};

const CSS: Family = {
  label: "CSS",
  keywords: words("important media supports keyframes import from to"),
  literals: new Set(),
  line: [],
  block: ["/*", "*/"],
  quotes: "\"'",
};

const MARKUP: Family = {
  label: "HTML",
  keywords: new Set(),
  literals: new Set(),
  line: [],
  block: ["<!--", "-->"],
  quotes: "\"'",
  tags: true,
};

const CONFIG: Family = {
  label: "YAML",
  keywords: new Set(),
  literals: words("true false null yes no on off"),
  line: ["#"],
  block: null,
  quotes: "\"'",
  hashNeedsSpace: true,
};

const LUA: Family = {
  label: "Lua",
  keywords: words("and break do else elseif end for function goto if in local not or repeat return then until while"),
  literals: words("true false nil self"),
  line: ["--"],
  block: ["--[[", "]]"],
  quotes: "\"'",
};

const FAMILIES: Record<string, Family> = {
  js: JS,
  javascript: JS,
  jsx: { ...JS, label: "JSX" },
  mjs: JS,
  cjs: JS,
  ts: { ...JS, label: "TypeScript" },
  typescript: { ...JS, label: "TypeScript" },
  tsx: { ...JS, label: "TSX" },
  py: PYTHON,
  python: PYTHON,
  python3: PYTHON,
  sh: SHELL,
  bash: SHELL,
  shell: SHELL,
  zsh: { ...SHELL, label: "Zsh" },
  console: { ...SHELL, label: "Terminal" },
  ps1: POWERSHELL,
  powershell: POWERSHELL,
  pwsh: POWERSHELL,
  c: C_LIKE("C", ""),
  h: C_LIKE("C", ""),
  cpp: C_LIKE("C++", ""),
  "c++": C_LIKE("C++", ""),
  cs: C_LIKE("C#", ""),
  csharp: C_LIKE("C#", ""),
  java: C_LIKE("Java", ""),
  kotlin: C_LIKE("Kotlin", "fun val when object companion data"),
  kt: C_LIKE("Kotlin", "fun val when object companion data"),
  go: C_LIKE("Go", ""),
  rust: C_LIKE("Rust", "self Self unsafe const static enum struct"),
  rs: C_LIKE("Rust", "self Self unsafe const static enum struct"),
  swift: C_LIKE("Swift", "func let var guard init deinit extension protocol"),
  php: C_LIKE("PHP", "echo function"),
  json: JSON_FAMILY,
  jsonc: { ...JSON_FAMILY, line: ["//"], block: ["/*", "*/"] },
  sql: SQL,
  css: CSS,
  scss: { ...CSS, label: "SCSS", line: ["//"] },
  html: MARKUP,
  xml: { ...MARKUP, label: "XML" },
  svg: { ...MARKUP, label: "SVG" },
  vue: { ...MARKUP, label: "Vue" },
  yaml: CONFIG,
  yml: CONFIG,
  toml: { ...CONFIG, label: "TOML" },
  ini: { ...CONFIG, label: "INI", line: [";", "#"] },
  dockerfile: { ...SHELL, label: "Dockerfile", keywords: words("FROM RUN CMD COPY ADD ENV ARG WORKDIR EXPOSE ENTRYPOINT USER VOLUME LABEL") },
  lua: LUA,
};

/** The code block header's name for a fence's language ("py" → "Python"). */
export function languageLabel(lang: string): string {
  const family = FAMILIES[lang.toLowerCase()];
  if (family) return family.label;
  return lang ? lang : "Code";
}

// Past this, the block stays plain: colouring is a nicety, never a stall.
const MAX_CHARS = 60_000;

const WORD_START = /[A-Za-z_$@]/;
const WORD = /[\w$@]/;

export function highlight(code: string, lang: string): Token[] {
  const f = FAMILIES[lang.toLowerCase()];
  if (!f || code.length > MAX_CHARS) return [{ k: "", v: code }];
  const out: Token[] = [];
  const push = (k: TokenKind, v: string) => {
    const last = out[out.length - 1];
    if (last && last.k === k) last.v += v;
    else out.push({ k, v });
  };
  const n = code.length;
  let i = 0;
  while (i < n) {
    const ch = code[i];
    const prev = i > 0 ? code[i - 1] : "\n";
    // comments
    if (f.block && code.startsWith(f.block[0], i)) {
      const end = code.indexOf(f.block[1], i + f.block[0].length);
      const stop = end < 0 ? n : end + f.block[1].length;
      push("com", code.slice(i, stop));
      i = stop;
      continue;
    }
    const lineComment = f.line.find((m) => code.startsWith(m, i));
    if (lineComment && !(f.hashNeedsSpace && lineComment === "#" && !/\s/.test(prev))) {
      const end = code.indexOf("\n", i);
      const stop = end < 0 ? n : end;
      push("com", code.slice(i, stop));
      i = stop;
      continue;
    }
    // strings
    if (f.quotes.includes(ch)) {
      const triple = f.triple && code.startsWith(ch.repeat(3), i);
      const close = triple ? ch.repeat(3) : ch;
      let j = i + close.length;
      while (j < n) {
        if (code[j] === "\\") {
          j += 2;
          continue;
        }
        if (code.startsWith(close, j)) {
          j += close.length;
          break;
        }
        // Only template strings and triple quotes cross a line.
        if (code[j] === "\n" && !triple && ch !== "`") break;
        j += 1;
      }
      const v = code.slice(i, Math.min(j, n));
      let k: TokenKind = "str";
      if (f.keys && /^\s*:/.test(code.slice(j, j + 8))) k = "fn";
      push(k, v);
      i += v.length;
      continue;
    }
    // markup tags: <name and </name
    if (f.tags && ch === "<" && /[/!?\w]/.test(code[i + 1] ?? "")) {
      const m = /^<\/?[\w:.-]+/.exec(code.slice(i, i + 64));
      if (m) {
        push("", m[0].startsWith("</") ? "</" : "<");
        push("kw", m[0].replace(/^<\/?/, ""));
        i += m[0].length;
        continue;
      }
    }
    // shell variables
    if (f.dollarVars && ch === "$" && /[\w{(?]/.test(code[i + 1] ?? "")) {
      const m = /^\$(\{[^}\n]*\}|\w+|\?)/.exec(code.slice(i, i + 128));
      if (m) {
        push(f.literals.has(m[0].toLowerCase()) ? "lit" : "fn", m[0]);
        i += m[0].length;
        continue;
      }
    }
    // numbers
    if (/\d/.test(ch) && !WORD.test(prev)) {
      const m = /^(0x[\da-f_]+|\d[\d_]*(\.\d+)?(e[+-]?\d+)?)/i.exec(code.slice(i, i + 64));
      if (m) {
        push("num", m[0]);
        i += m[0].length;
        continue;
      }
    }
    // words: keywords, literals, calls
    if (WORD_START.test(ch) && !WORD.test(prev)) {
      let j = i + 1;
      while (j < n && /[\w$]/.test(code[j])) j += 1;
      const w = code.slice(i, j);
      const lower = w.toLowerCase();
      let k: TokenKind = "";
      if (f.keywords.has(w) || (f === SQL && f.keywords.has(lower))) k = "kw";
      else if (f.literals.has(w)) k = "lit";
      else if (/^\s*\(/.test(code.slice(j, j + 8))) k = "fn";
      push(k, w);
      i = j;
      continue;
    }
    push("", ch);
    i += 1;
  }
  return out;
}
