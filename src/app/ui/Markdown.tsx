// Renders a reply's Markdown (K1-04, FR-C-8) from the tree in ../markdown.ts.
// Only React elements, never innerHTML, so model output cannot inject markup.
// Code blocks get a header with the language and Copy, and their code coloured
// (UI1-08, D-093); tables scroll sideways when wide. In a roleplay thread (FR-MODE-7)
// actions are italic and softer and out-of-character asides small and muted (app.css).

import { invoke, isTauri } from "@tauri-apps/api/core";
import { useMemo, type MouseEvent, type ReactNode } from "react";

import { highlight, languageLabel } from "../highlight";
import { parseMarkdown, type Block, type Inline } from "../markdown";
import { CopyButton } from "./CopyButton";

/** In the desktop app a link opens in the user's browser (the shell's open_link). */
export function openLink(e: MouseEvent, href: string): void {
  if (!isTauri()) return;
  e.preventDefault();
  void invoke<boolean>("open_link", { url: href }).catch(() => undefined);
}

function Code({ lang, v, open }: { lang: string; v: string; open: boolean }) {
  const tokens = useMemo(() => highlight(v, lang), [v, lang]);
  return (
    <div className="code-block">
      <div className="code-head">
        <span className="code-lang">{languageLabel(lang)}</span>
        {open ? null : <CopyButton text={v} label="Copy code" icon showLabel />}
      </div>
      <pre>
        <code>{tokens.map((t, n) => (t.k ? <span key={n} className={`tok-${t.k}`}>{t.v}</span> : t.v))}</code>
      </pre>
    </div>
  );
}

function inline(nodes: Inline[]): ReactNode[] {
  return nodes.map((n, i) => {
    switch (n.t) {
      case "text":
        return n.v;
      case "code":
        return <code key={i}>{n.v}</code>;
      case "strong":
        return <strong key={i}>{inline(n.c)}</strong>;
      case "em":
        return <em key={i}>{inline(n.c)}</em>;
      case "link":
        // The user's browser in the desktop app (a webview popup would be an app-looking
        // window on a remote page); a new tab in a plain browser. The chat never navigates away.
        return (
          <a key={i} href={n.href} target="_blank" rel="noopener noreferrer" onClick={(e) => openLink(e, n.href)}>
            {inline(n.c)}
          </a>
        );
      case "br":
        return <br key={i} />;
      case "action":
        return (
          <em key={i} className="rp-action">
            {inline(n.c)}
          </em>
        );
      case "tag":
        // D-097: her emotion tag, kept in the text and shown like an action
        return (
          <em key={i} className="emotion-tag">
            {n.v}
          </em>
        );
      case "ooc":
        return (
          <span key={i} className="rp-ooc">
            {inline(n.c)}
          </span>
        );
    }
  });
}

function block(b: Block, i: number): ReactNode {
  switch (b.t) {
    case "p":
      return <p key={i}>{inline(b.c)}</p>;
    case "h": {
      const H = (["h3", "h4", "h5"] as const)[b.level - 1];
      return <H key={i}>{inline(b.c)}</H>;
    }
    case "code":
      return <Code key={i} lang={b.lang} v={b.v} open={b.open} />;
    case "table":
      return (
        <div key={i} className="table-wrap">
          <table>
            <thead>
              <tr>
                {b.head.map((c, n) => (
                  <th key={n} style={b.align[n] ? { textAlign: b.align[n] ?? undefined } : undefined}>
                    {inline(c)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {b.rows.map((row, r) => (
                <tr key={r}>
                  {row.map((c, n) => (
                    <td key={n} style={b.align[n] ? { textAlign: b.align[n] ?? undefined } : undefined}>
                      {inline(c)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case "list": {
      const items = b.items.map((it, n) => (
        <li key={n}>
          {inline(it.c)}
          {it.blocks.map(block)}
        </li>
      ));
      return b.ordered ? (
        <ol key={i} start={b.start}>
          {items}
        </ol>
      ) : (
        <ul key={i}>{items}</ul>
      );
    }
    case "quote":
      return <blockquote key={i}>{b.c.map(block)}</blockquote>;
    case "hr":
      return <hr key={i} />;
  }
}

export function Markdown({ text, roleplay = false }: { text: string; roleplay?: boolean }) {
  const blocks = useMemo(() => parseMarkdown(text, { roleplay }), [text, roleplay]);
  return <div className="md">{blocks.map(block)}</div>;
}
