// Plays the kernel's `speak` clips one after another (K1-02). The chat window
// has no avatar until the Stage view (K2), so there is no lip-sync here: just
// the audio, in order, and a Stop that silences it at once (FR-C-2). A clip
// with no audio (voice backend down) is skipped: the text is already in the
// thread (FR-V-7).

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
  private queue: SpeakClip[] = [];
  private current: HTMLAudioElement | null = null;
  private currentUrl: string | null = null;

  enqueue(clip: SpeakClip): void {
    if (!clip.audio_b64) return;
    this.queue.push(clip);
    if (!this.current) this.playNext();
  }

  stop(): void {
    this.queue = [];
    this.release();
  }

  private release(): void {
    if (this.current) {
      this.current.pause();
      this.current.src = "";
    }
    if (this.currentUrl) URL.revokeObjectURL(this.currentUrl);
    this.current = null;
    this.currentUrl = null;
  }

  private playNext(): void {
    this.release();
    const clip = this.queue.shift();
    if (!clip) return;
    const url = toBlobUrl(clip);
    const audio = new Audio(url);
    this.current = audio;
    this.currentUrl = url;
    const next = () => {
      if (this.current === audio) this.playNext();
    };
    audio.addEventListener("ended", next);
    audio.addEventListener("error", next);
    audio.play().catch((err) => {
      console.warn("[kokyu] could not play a voice clip", err);
      next();
    });
  }
}
