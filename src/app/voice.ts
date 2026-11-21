// Plays the kernel's `speak` clips one after another (K1-02), in order, with a
// Stop that silences them at once (FR-C-2). Each clip goes through the engine's
// lip-sync player, so the Stage's mouth follows whatever is playing (D-104). A
// clip with no audio (voice backend down) is skipped: the text is already in
// the thread (FR-V-7).

import { speakWithLipsync, type SpeakHandle } from "../engine/lipsync";

export interface SpeakClip {
  text: string;
  audio_b64: string;
  mime: string;
}

function toBlobUrl(clip: SpeakClip): string {
  const bytes = atob(clip.audio_b64);
  const buffer = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i += 1) buffer[i] = bytes.charCodeAt(i);
  return URL.createObjectURL(new Blob([buffer], { type: clip.mime || "audio/wav" }));
}

export class VoicePlayer {
  /** Called whenever the last queued clip has finished or playback was stopped. */
  onIdle: (() => void) | null = null;
  private queue: SpeakClip[] = [];
  private current: SpeakHandle | null = null;
  private currentUrl: string | null = null;

  enqueue(clip: SpeakClip): void {
    if (!clip.audio_b64) return;
    this.queue.push(clip);
    if (!this.current) this.playNext();
  }

  stop(): void {
    this.queue = [];
    this.release();
    this.onIdle?.();
  }

  /** Nothing playing and nothing queued. */
  get idle(): boolean {
    return this.current === null && this.queue.length === 0;
  }

  private release(): void {
    this.current?.stop();
    if (this.currentUrl) URL.revokeObjectURL(this.currentUrl);
    this.current = null;
    this.currentUrl = null;
  }

  private playNext(): void {
    this.release();
    const clip = this.queue.shift();
    if (!clip) {
      this.onIdle?.();
      return;
    }
    const url = toBlobUrl(clip);
    this.currentUrl = url;
    const handle = speakWithLipsync(url);
    this.current = handle;
    handle.onFinish(() => {
      if (this.current === handle) this.playNext();
    });
  }
}
