// The microphone for dictation (D-097): MediaRecorder's WebM/Opus, which the engine's
// speech-to-text (faster-whisper through PyAV) reads as it is. Echo cancellation and
// noise suppression on. The audio goes to the engine on this PC and is not kept.

export class MicRecorder {
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];

  /** Asks for the mic and starts recording. Throws what getUserMedia throws (see micProblem). */
  async start(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
    });
    const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"].find((m) => MediaRecorder.isTypeSupported(m));
    this.recorder = new MediaRecorder(this.stream, mime ? { mimeType: mime } : undefined);
    this.chunks = [];
    this.recorder.addEventListener("dataavailable", (e) => {
      if (e.data.size > 0) this.chunks.push(e.data);
    });
    this.recorder.start();
  }

  /** Stops and hands back the recording; null when nothing was recorded. */
  stop(): Promise<Blob | null> {
    const rec = this.recorder;
    if (!rec || rec.state === "inactive") {
      this.release();
      return Promise.resolve(null);
    }
    return new Promise((resolve) => {
      rec.addEventListener(
        "stop",
        () => {
          const blob = new Blob(this.chunks, { type: rec.mimeType || "audio/webm" });
          this.chunks = [];
          this.release();
          resolve(blob.size > 0 ? blob : null);
        },
        { once: true },
      );
      rec.stop();
    });
  }

  /** Stops and drops the recording (the window closed). */
  cancel(): void {
    if (this.recorder && this.recorder.state !== "inactive") this.recorder.stop();
    this.chunks = [];
    this.release();
  }

  private release(): void {
    this.stream?.getTracks().forEach((t) => t.stop()); // the mic light goes off
    this.stream = null;
    this.recorder = null;
  }
}

/** The recording as base64, for the dictate frame. */
export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] ?? "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}
