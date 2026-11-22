// Quick-action menu's Upload Image/File item. Scoped deliberately narrow
// this round: images (any image/* MIME type) go through the same vision
// pipeline capture_screen/capture_camera already use, and plain text/code
// files get their content read directly -- no vision step needed for
// those. PDFs, Word docs, and video (the "mp4" half of the original
// "image/file/mp4" ask) are explicitly NOT handled here; each needs its
// own real parsing/frame-extraction work this round didn't attempt. See
// docs/DECISIONS.md for the full scoping reasoning.

/** Every upload is checked here before it is read (D-106): chat files, her
 * picture and the pet sheet. The kernel checks again (KASANE/uploads.py). */

/** The only pictures accepted, by MIME type: what every webview decodes and the
 * kernel's allowlist opens. No SVG (scripts), HEIC, TIFF, BMP or ICO. */
export const PICTURE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"] as const;
/** For an <input type="file" accept>. */
export const PICTURE_ACCEPT = PICTURE_TYPES.join(",");
export const MAX_PICTURE_BYTES = 20 * 1024 * 1024;
/** Same as KASANE/uploads.py MAX_PIXELS: about 6300 x 6300. */
export const MAX_PICTURE_PIXELS = 40_000_000;
/** A text or code file is read whole before it is cut to MAX_TEXT_CHARS. */
export const MAX_TEXT_BYTES = 2 * 1024 * 1024;

const mb = (bytes: number) => `${bytes / 1024 / 1024} MB`;

/** A refusal meant for the user, as thrown by resizeImageToBase64Jpeg. */
export class UploadProblem extends Error {}

/** Why this file cannot be used as a picture, or null when it can. */
export function pictureProblem(file: File): string | null {
  if (!(PICTURE_TYPES as readonly string[]).includes(file.type)) return "Pictures must be PNG, JPEG, WebP or GIF.";
  if (file.size > MAX_PICTURE_BYTES) return `That picture is too big (over ${mb(MAX_PICTURE_BYTES)}).`;
  if (file.size === 0) return "That file is empty.";
  return null;
}

/** Longest side an uploaded image gets resized to before encoding, via
 * canvas (see resizeImageToBase64Jpeg below) -- matches what a vision
 * model actually needs; sending a full 4000px phone photo would just be
 * wasted bandwidth and processing time for no extra understanding. */
const MAX_IMAGE_DIMENSION = 1024;

/** Text files get truncated to this many characters (not tokens -- a
 * rough but simple proxy) before being sent, so one large file can't
 * blow out the model's context window on its own. Truncation is called
 * out explicitly in what gets sent (see readTextFile below) rather than
 * silently cutting content off. */
const MAX_TEXT_CHARS = 6000;

/** Extensions treated as text even when the browser reports a generic or
 * empty MIME type for them (common for code files) -- checked in
 * addition to, not instead of, a `text/*` MIME type. Not exhaustive;
 * covers the languages/formats likely to actually come up here. */
const TEXT_EXTENSIONS = new Set([
  "txt",
  "md",
  "markdown",
  "csv",
  "log",
  "json",
  "yaml",
  "yml",
  "toml",
  "ini",
  "xml",
  "html",
  "css",
  "js",
  "ts",
  "jsx",
  "tsx",
  "py",
  "rs",
  "go",
  "java",
  "c",
  "cpp",
  "h",
  "hpp",
  "cs",
  "rb",
  "php",
  "sh",
  "sql",
]);

export type ClassifiedFile = { kind: "image" | "text" } | { kind: "unsupported"; reason: string };

/** Decides how (or whether) a picked file can be handled at all --
 * before any reading/resizing work happens, so an unsupported pick (a
 * PDF, a video, a spreadsheet) fails fast with a clear reason instead of
 * partway through trying to read it as text and producing garbage. */
export function classifyFile(file: File): ClassifiedFile {
  if (file.type.startsWith("image/")) {
    const reason = pictureProblem(file);
    return reason ? { kind: "unsupported", reason } : { kind: "image" };
  }
  // By extension only: a browser calls many binaries text/* or nothing at all.
  const dot = file.name.lastIndexOf(".");
  const ext = dot > 0 ? file.name.slice(dot + 1).toLowerCase() : "";
  if (TEXT_EXTENSIONS.has(ext)) {
    if (file.size > MAX_TEXT_BYTES) return { kind: "unsupported", reason: `That file is too big (over ${mb(MAX_TEXT_BYTES)}).` };
    return { kind: "text" };
  }
  return {
    kind: "unsupported",
    reason: "Only pictures (PNG, JPEG, WebP, GIF) and text or code files can be shared.",
  };
}

/** Draws the image onto an off-screen canvas (downscaled if needed) and
 * returns bare base64 JPEG -- no `data:` prefix, same convention
 * camera.ts's captureFrame() and every other image payload in this
 * project already use. Plain 2D canvas, same reasoning as camera.ts's
 * own choice: this is one still image with no filters or live rendering
 * involved, so WebGL wouldn't add anything here either. */
export async function resizeImageToBase64Jpeg(
  file: File,
  type: "image/jpeg" | "image/png" = "image/jpeg",
  maxSide: number = MAX_IMAGE_DIMENSION,
): Promise<string> {
  const problem = pictureProblem(file);
  if (problem) throw new UploadProblem(problem);
  const objectUrl = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = () => reject(new UploadProblem("That file is not a picture Kōkyū can read. Use a PNG, JPEG, WebP or GIF."));
      el.src = objectUrl;
    });
    if (img.naturalWidth * img.naturalHeight > MAX_PICTURE_PIXELS) {
      throw new UploadProblem("That picture is too large. Use one under about 6000 x 6000 pixels.");
    }

    const scale = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight));
    const width = Math.max(1, Math.round(img.naturalWidth * scale));
    const height = Math.max(1, Math.round(img.naturalHeight * scale));

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas 2D context unavailable.");
    ctx.drawImage(img, 0, 0, width, height);

    // PNG keeps transparency (a chosen portrait, D-091); JPEG is smaller for everything else.
    const dataUrl = canvas.toDataURL(type, 0.85);
    const commaIndex = dataUrl.indexOf(",");
    if (commaIndex === -1) throw new Error("Failed to encode image.");
    return dataUrl.slice(commaIndex + 1);
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

/** Reads a text/code file's content directly, truncated to
 * MAX_TEXT_CHARS with an explicit marker if it was cut -- the model
 * should know content is incomplete rather than silently reason about a
 * partial file as if it were the whole thing. */
export async function readTextFile(file: File): Promise<string> {
  const text = await file.text();
  if (text.includes("\u0000")) throw new UploadProblem("That is not a text file.");   // a binary with a text name
  if (text.length <= MAX_TEXT_CHARS) return text;
  return `${text.slice(0, MAX_TEXT_CHARS)}\n\n[... truncated, file continues beyond this point ...]`;
}
