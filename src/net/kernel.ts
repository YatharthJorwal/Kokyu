// The chat window's connection to KASANE (K1-02): one WebSocket, reconnecting
// with backoff, that speaks protocol v1 both ways (D-062). No state lives here;
// the store does that.

import { clientFrame, parseFrame, type ClientData, type ClientType, type Frame } from "./protocol";

export const KERNEL_WS_URL = "ws://127.0.0.1:8780/ws";
/** The same engine over HTTP: files such as her portrait (D-091). */
export const KERNEL_HTTP_URL = "http://127.0.0.1:8780";

export type ConnectionStatus = "connecting" | "online" | "offline";

export interface KernelHandlers {
  onFrame: (frame: Frame) => void;
  onStatus: (status: ConnectionStatus) => void;
  /** A message this window could not understand (wrong protocol version, unknown type). */
  onProblem: (reason: string) => void;
}

/** 250 ms, 500, 1000, then 2000 ms between attempts. */
export function backoffMs(attempt: number): number {
  return Math.min(250 * 2 ** attempt, 2000);
}

/** Routes one raw message to the right handler. Exported for tests. */
export function dispatchRaw(raw: string, handlers: KernelHandlers): void {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    handlers.onProblem("Kōkyū's engine sent a message this window could not read.");
    return;
  }
  const result = parseFrame(parsed);
  if (result.kind === "frame") handlers.onFrame(result.frame);
  else handlers.onProblem(result.reason);
}

export class KernelSocket {
  private socket: WebSocket | null = null;
  private attempts = 0;
  private timer: number | undefined;
  private closed = false;

  constructor(
    private readonly handlers: KernelHandlers,
    private readonly url: string = KERNEL_WS_URL,
  ) {}

  connect(): void {
    this.closed = false;
    this.handlers.onStatus("connecting");
    const socket = new WebSocket(`${this.url}?surface=main`);
    this.socket = socket;
    socket.addEventListener("open", () => {
      this.attempts = 0;
      this.handlers.onStatus("online");
      this.send("hello", { client: "main", protocol: 1 });
    });
    socket.addEventListener("message", (event) => dispatchRaw(String(event.data), this.handlers));
    socket.addEventListener("close", () => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.handlers.onStatus("offline");
      if (!this.closed) this.timer = window.setTimeout(() => this.connect(), backoffMs(this.attempts++));
    });
  }

  /** Try again now instead of after the backoff (the banner's Reconnect). */
  reconnectNow(): void {
    if (this.socket) return; // open, or an attempt is under way
    window.clearTimeout(this.timer);
    this.attempts = 0;
    this.connect();
  }

  close(): void {
    this.closed = true;
    window.clearTimeout(this.timer);
    this.socket?.close();
  }

  /** A v1 frame. Returns false when the socket is not open (nothing is queued). */
  send<T extends ClientType>(type: T, data: ClientData[T], thread: string | null = null): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify(clientFrame(type, data, thread)));
    return true;
  }
}
