# PRODUCT: Kōkyū

Product direction: who it is for, what ships when, how it will be sold, and what is still open. Requirements live in `SPEC.md`, the build in `ARCHITECTURE.md`, the one-page overview in `SCOPE.md`.

- **Version:** v1.0, 2026-11-17 (docs reset, D-076).
- **Status words:** **Decided** = the user said so. **Direction** = the user's intent, details open. **Open** = not decided.

## 1. Vision

Kōkyū is a **roleplay character app for Windows**, first and foremost (D-079). A non-technical person goes from download to a first conversation with their own AI character (persona, voice, look) without a terminal, while enthusiasts plug in local models, their own API keys and custom voices. We sell the **software and the setup experience**; the user brings the intelligence (local or API) and pays for it. The differentiators: (1) a first run that installs and repairs the plumbing, (2) companion creation inside the app, (3) one model picker and one companion switcher that stay independent (a companion is only a voice and a persona), (4) roleplay done properly (scenario cards, story memory), and (5) embodiment: a VRM stage first, desktop pets and a 3D apartment after.

## 2. Principles

1. Desktop software, not a hosted service. We sell no model access and no API credits. (Decided)
2. User-controlled: their model, key, voice, character. BYOK and BYOM. (Decided, D-033)
3. Local-first; nothing leaves the machine except what the user chose to send. (Decided)
4. No terminal for ordinary install and use; advanced settings exist for advanced users. (Decided)
5. First conversation fast; optional features never block it. (Decided)
6. No mandatory subscription. (Decided)
7. Do not promise "no restrictions"; promise freedom of configuration and ownership. (Decided)
8. Only working controls in the product; nothing disabled "for later". (Decided, D-082)

## 3. How a user reaches a first conversation

Estimates marked **est.** come from the development PC, not from measurements on buyers' machines.

| Path | User needs | Time to first conversation | Ongoing cost |
|---|---|---|---|
| **A. API key** | Any Windows PC with WebGL; an API key | Minutes; the key itself is the wall | Provider charges |
| **B. Local model** | NVIDIA GPU, about 8 GB VRAM or more (est.); a multi-GB model download | Download-bound | None beyond hardware |
| **C. + her own voice (GPT-SoVITS)** | NVIDIA GPU; a multi-GB component, set up automatically at first run (D-080) | Download-bound | None |
| **D. + hosted voice (e.g. ElevenLabs)** | Provider key and voice ID | Minutes | Provider charges (D-036, provisional) |

Reality checks:

- **Most buyers do not own a 12 GB NVIDIA card.** Local LLM plus local voice plus a 3D stage is an enthusiast setup. Path A must work well, and the first run says honestly what the PC can run (a hardware check that never blocks).
- **Getting an API key is a barrier** for non-technical buyers. The first run needs hand-holding screens (what a key is, where to get one, what it costs, a "test key" button), and the app makes clear that charges come from the provider.
- **Voice:** the first run sets up GPT-SoVITS and the speech-to-text model by itself, with progress and no tinkering (D-080). GPT-SoVITS still needs an NVIDIA GPU and a multi-GB download. What a buyer without one hears is **open**: D-036's small built-in voice has no chosen model, and the premades' voices exist only as GPT-SoVITS reference clips (§9).
- **Speech-to-text is easy:** faster-whisper on CPU, its model downloaded by the app.
- **Spending caps do not block BYOK endpoints:** a model with no catalog price runs under the cap, labelled "price unknown, not counted against the cap" (D-083).

## 4. Release boundaries

Per D-085 (provisional; the user confirms it next session).

| Release | Contents | Phases |
|---|---|---|
| **1.0** | Installer and first run with automatic voice setup; chat with Local and API models; Chat and Roleplay modes; model picker with short names; companion switcher; VRM stage; per-companion voice; in-app creator (Write it for me); Luna and Yuri as premades; shared memory | K0, K1, K1c (done); UI-1, K1b, K2, K3, W, K6, K7 |
| **1.1** | Desktop pets; the 3D apartment, built from Luna's apartment (D-078) | K4, K5 |
| **Not planned** | Agent mode (file read/write); VR is deferred long term (D-079) | none |

## 5. Distribution (current state)

| Topic | State |
|---|---|
| Installer | **Decided:** one per-user NSIS `.exe` from Tauri's bundler; no admin rights; no portable zip, `setup.ps1` or MSIX (D-081) |
| Licence | **Decided:** proprietary, all rights reserved; the repository is private (D-040) |
| Model | **Direction:** paid, one-time purchase, no subscription (D-033) |
| Payments, pricing, licence keys, website | **Deferred** until the product is developed (D-043) |
| Code signing, updater | **Deferred** (D-043); planned for K7 |
| Diagnostics | **Direction:** "Export diagnostics" zips redacted logs for support; no telemetry by default |

## 6. Hardware reality

| Component | Runs on | Note |
|---|---|---|
| VRM stage | Most GPUs, integrated included (WebGL) | Not built yet (K2); an auto-quality setting is a K6 candidate |
| Built-in voice | CPU | Open: no model chosen (D-036) |
| STT | CPU | faster-whisper `small` |
| Local LLM `qwen3.5:9b` | About 5.6 GB VRAM | Measured with NVML on the development PC (`STATE.md`) |
| Qwen3.6-35B-A3B Q4 on llama.cpp | About 3 GB VRAM plus 19.5 GB RAM | Measured; about 23 tokens/s (D-051) |
| GPT-SoVITS | NVIDIA GPU | VRAM not measured; 47 s to first answer after start; runs only while Read aloud is on (D-097) |

## 7. Assets, legal and brand

None of this is code, but each item can block a sale.

1. **Premades are paid content** (D-087): buyers pay for the app and for Luna and Yuri, each shipped complete (persona, voice clips with transcripts, VRM). Users can read her traits and how she behaves; the clips and VRM are used only inside the app, never exported, and are not open-sourced. Protection is an app-only packed format plus the licence terms; a file on the user's PC can never be made fully unreadable. Luna's and Yuri's VRMs are self-made; their voices were generated on the ElevenLabs website (D-041). To verify before release: the ElevenLabs plan's commercial rights, and the image tool's terms for the app icon (`THIRD-PARTY.md`).
2. **Audience: adults, 18+** (D-090), with an age check at first run. The premade personas carry explicit sexual instructions today, and every payment provider checked bans sexual products whatever the age; whether the premades stay explicit is open (§9). Research: `docs/research-age-content-2026-11.md`.
3. **Dependencies** must be permissive for closed-source sale; no GPL/AGPL or non-commercial dependency without a decision (RULES R-38). Model weights are never bundled.
4. **Brand:** the stage copies a camera framing, not xAI's character. No look-alikes of Ani or AI-company mascots. Run a trademark and domain check on "Kokyu" / "Kōkyū" before branding.
5. **Policies before sale:** privacy policy (what leaves the machine), terms (intended audience age), refunds, support.

## 8. Origin

This direction started from the user's product-vision handoff, archived at `docs/archive/product-vision-handoff-2026-11-11.md`.
Rejected from it: a model chosen per companion (D-038), the Microsoft Store, and "no restrictions" claims.
Everything else was adopted or adapted into the sections above.

## 9. Open business questions

The user will come back to these.

1. **The 1.0 voice for buyers.** The premades ship their clips and transcripts and GPT-SoVITS is set up automatically (D-080, D-087); a buyer without an NVIDIA GPU is still open (D-036).
2. **Premade content and payment fit.** 18+ is decided (D-090). Open: explicit premades or not, a written yes from Paddle or FastSpring, UK sales, a legal read on SB 243 (TODO B-10..12).
3. **Premade packs in git.** Recommendation: version `persona.md`, `waifu.yaml` and the transcripts in the private repo; VRM and WAV stay out of git with a separate backup.
4. **An API key for testing the API path** (path A has never run on the development PC).
5. **Price and trial.** $14.99 launch and $19.99 standard were discussed; whether a limited demo exists.
6. **Code signing.** Unsigned installers trigger SmartScreen warnings; certificate cost and eligibility for an individual publisher are unresearched.
