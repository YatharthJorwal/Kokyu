// Renders a reply's Markdown (K1-04, FR-C-8) from the tree in ../markdown.ts.
// Only React elements, never innerHTML, so model output cannot inject markup.
// Code blocks get a Copy button.

import { useMemo, type ReactNode } from "react";

import { parseMarkdown, type Block, type Inline } from "../markdown";
import { CopyButton } from "./CopyButton";

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
        // A new window: the chat itself must never navigate away.
        return (
          <a key={i} href={n.href} target="_blank" rel="noopener noreferrer">
            {inline(n.c)}
          </a>
        );
      case "br":
        return <br key={i} />;
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
      return (
        <div key={i} className="code-block">
          <div className="code-head">
            <span>{b.lang || "code"}</span>
            {b.open ? null : <CopyButton text={b.v} label="Copy code" />}
          </div>
          <pre>
            <code>{b.v}</code>
          </pre>
        </div>
      );
    case "list": {
      const items = b.items.map((it, n) => <li key={n}>{inline(it)}</li>);
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

export function Markdown({ text }: { text: string }) {
  const blocks = useMemo(() => parseMarkdown(text), [text]);
  return <div className="md">{blocks.map(block)}</div>;
}
