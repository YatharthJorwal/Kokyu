# PRODUCT — Kōkyū

Product direction: who it is for, how it is sold, what ships when, and what is still open. Engineering detail lives in `SPEC.md` and `ARCHITECTURE.md`; this file is the bridge between the business idea and the build plan.

- **Version:** v0.1, 2026-11-11 (session 1).
- **Source:** the user's research handoff (kept verbatim in `notes/product-vision-handoff-2026-11-11.md`), weighed against `SCOPE.md`, `SPEC.md` and the Yuri inventory. §8 records what was adopted, adapted, deferred or rejected.
- **Status words:** **Decided** = user said so. **Direction** = user's intent, details open. **Proposal** = my recommendation, needs the user's OK. **Unverified** = a fact I could not check.

## 1. The vision in one paragraph

Kōkyū is a **one-time-purchase Windows app** that takes a non-technical person from download to a first conversation with *their own* AI companion (their character, personality, voice and model) without a terminal, while letting enthusiasts plug in local models, their own API keys and custom voices. We sell the **software and the setup experience**; the user brings the intelligence (local or API) and pays for it themselves. The differentiators are (1) a setup experience that installs and repairs the plumbing, (2) full in-app companion creation, (3) one model switcher and one waifu switcher that stay independent (a waifu is only voice and persona), and (4) embodiment: a VRM stage first, desktop pets and 3D rooms after.

## 2. Principles

1. Desktop software, not a hosted service. We sell no model access and no API credits. (Decided)
2. User-controlled: their model, key, voice, character. BYOK and BYOM. (Decided)
3. Local-first where possible; nothing leaves the machine except what the user chose to send. (Decided)
4. No terminal for ordinary install and use; advanced settings exist for advanced users. (Decided)
5. First conversation fast; optional features never block it. (Decided)
6. No mandatory subscription. (Decided)
7. Do not promise "no restrictions"; promise freedom of configuration and ownership. (Decided)

## 3. How a user reaches a first conversation (Proposal)

The wizard (FR-WIZ) offers paths in this order of friction. Estimates marked **est.** are from this development machine, not measurements.

| Path | User needs | Typical first-conversation time | Ongoing cost |
|---|---|---|---|
| **A. API key + built-in voice** | Any Windows PC with WebGL; an API key | Minutes; the key itself is the wall for non-technical users | Provider charges |
| **B. Local model + built-in voice** | NVIDIA GPU, about 8 GB VRAM or more recommended (est.); several GB model download | Download-bound | None beyond hardware |
| **C. + cloned voice (GPT-SoVITS)** | NVIDIA GPU; a multi-GB component; an 8 s voice clip | Advanced, optional | None |
| **D. + hosted voice (e.g. ElevenLabs)** | Provider key and a voice ID | Minutes | Provider charges |

Reality checks that shape the plan:

- **Many "ordinary customers" do not own a 12 GB NVIDIA card.** Local LLM plus local cloned voice plus a 3D stage is an enthusiast configuration. The product must work well on path A, and the wizard must say honestly what the PC can run (hardware check, never blocking).
- **Getting an API key is itself a barrier** for non-technical buyers. The wizard needs hand-holding screens (what it is, where to click, what it costs, a "test key" button) and the app must make clear that charges come from the provider.
- **Voice tiers matter.** Auto-installing GPT-SoVITS is the hardest component to make reliable (multi-GB, CUDA-specific, fast-moving upstream). Make a small built-in voice the default so a first conversation never waits for it (D-036).
- **Speech-to-text is easy:** faster-whisper on CPU, model downloaded by the app (already decided in Yuri).

## 4. Release boundaries (Proposal, D-034)

| Release | Contents | Phases |
|---|---|---|
| **1.0 First stable** | Installer; Welcome wizard and component manager; chat with Local and API models; waifu and model switchers; VRM stage; voice (built-in, GPT-SoVITS, hosted); in-app creator; 2 to 3 premade companions; memory; license key; updater | T, K0, K1, K1b, K2, K3, W, K6, K7 |
| **1.1 Embodiment** | 2D desktop pets; 3D rooms (apartment, garden) with one or two waifus | K4, K5 |
| **2.x Advanced** | Agent mode (file read/write), VR, more providers and scenes | D1, D2 |

This follows the handoff's own priorities (§11) with one change: the handoff lists multiple companions, memory and voice quality as priority 2, but the app is *built* on waifu packs and shared memory from K0, so those are not optional later work.

## 5. Distribution and commercial direction

| Topic | State | Notes |
|---|---|---|
| Model | **Direction:** paid, one-time purchase, no subscription | Price undecided; ideas on the table: $14.99 launch, $19.99 standard |
| Free trial | **Proposal** | A limited demo (for example one companion, API path) lowers refund risk and helps conversion; decide before pricing |
| Installer | **Direction:** signed Windows installer from our own site | NSIS per-user (no admin) preferred; MSI only if a customer or channel needs it |
| Microsoft Store | **Deferred** | Not for 1.0; adds packaging and content-policy friction |
| Payments | **Direction:** Dodo Payments for international sales | **Unverified:** whether Dodo acts as Merchant of Record (VAT/sales tax) and what its acceptable-use rules say about companion/adult content. Read both before building anything |
| Entitlement | **Proposal** | Signed license key (Ed25519), verified offline by the app; keys issued by a small serverless function behind the payment webhook (or Dodo's own license feature if it fits: check); optional revocation list. No accounts, no DRM arms race: a $15 desktop app will be cracked, so keep it light |
| Updates | **Proposal** | Tauri updater (signed updates) hosted on GitHub Releases or a CDN |
| Code signing | **Open** | Unsigned installers trigger SmartScreen warnings and a new publisher takes time to build reputation. Certificate options have cost and eligibility constraints for an individual publisher; research before launch |
| Diagnostics | **Proposal** | "Export diagnostics" zips redacted logs and component status for support; no telemetry by default |
| Website, checkout, docs | **Out of this repo** | Separate site; tracked in `TODO.md` Track B |

### License (D-032)

Today the repository carries **MIT**, and only documentation is published. The user says the license will change, and "open source" and "paid at $15 to $20" pull in opposite directions: anyone can legally build and redistribute MIT code for free. Options, none decided:

| Option | Meaning | Fit |
|---|---|---|
| A. Keep MIT, sell convenience | Installer, updates, premade assets and support are the product | Weak for a $15 app: easily cloned |
| B. Source-available | Code visible, commercial redistribution forbidden (for example a "no competing use" or delayed-open license) | Good middle path |
| C. Private source | Repo private; docs or a marketing repo public | Most common for paid indie desktop apps |

**Hold rule:** no product code is pushed to the public repository until the license is decided (TODO LIC-1). Only documentation is currently public, so deciding now costs nothing; code already published under MIT cannot be taken back. This is not legal advice; for a paid product consider a short consult.

## 6. Assets, legal and brand checklist

None of this is code, but several items can block a release.

1. **Premade companions (2 to 3):** each needs a VRM with documented rights to redistribute inside a paid product (commissioned, or self-made; check the terms of the tool used, for example VRoid Studio), plus an original voice recording or a voice you hold commercial rights to. **Do not ship Luna's or Yuri's current assets** unless their provenance is confirmed. Yuri's example reference clip has a file name that suggests a downloaded sample (**unverified**).
2. **Premade personas:** keep them conservative by default. User-created companions are the user's content; what the *product* ships and markets must fit the payment provider's and any store's rules.
3. **Animations:** Luna tracks an open-licensed VRMA pack with notices; keep the notices, record them in `docs/THIRD-PARTY.md`.
4. **Dependencies:** closed-source distribution needs permissive licenses (MIT, Apache, BSD). No GPL/AGPL or non-commercial dependency without a decision entry (R-38). Model weights are never bundled.
5. **Brand and IP:** the stage view copies a *camera framing*, not xAI's character. Do not ship look-alikes of Ani or of AI-company mascots, and get a review before using third-party logos or characters in marketing (the handoff's reference creator draws AI companies as characters: that is his IP and brand risk, not a template).
6. **Name:** run a basic trademark and domain check for "Kokyu" / "Kōkyū" before investing in branding.
7. **Policies:** privacy policy (what leaves the machine: text to the chosen model provider, spoken text to a cloud voice), terms (including the intended audience age), refund policy, support channel.

## 7. Hardware reality (est., to be measured)

| Component | Runs on | Note |
|---|---|---|
| VRM stage | Most GPUs including integrated (WebGL) | Auto-quality setting is a K6 candidate |
| Built-in voice | CPU | Candidate model to be evaluated in K2 |
| STT | CPU | faster-whisper `small` |
| Local LLM 9B Q4 | About 6.6 GB of VRAM on this machine | Smaller models for smaller cards |
| GPT-SoVITS | NVIDIA GPU recommended | VRAM not yet measured |

## 8. Reconciliation with the external handoff

| Handoff item | Treatment | What happened |
|---|---|---|
| Product is the app and orchestration layer, not a model or service | **Adopted** | Already the KASANE role |
| BYOK, BYOM, local-first | **Adopted** | D-033; generic OpenAI-compatible provider (D-037) |
| "AI model selection" as part of each companion; "Companion-specific … intelligence" | **Rejected** | Contradicts D-003 (a waifu is only voice and persona). "Choose her intelligence" is satisfied by the global model switcher |
| Companion = name, traits, prompt, VRM, voice | **Adopted** | Matches FR-CR; "animation and interaction settings" deferred |
| Not in the handoff: desktop pets, effort slider, shared memory, invariance tests, paste-only prompt box | **Kept** | User decisions stay |
| Seven-step Welcome wizard | **Adapted** | New phase W; order becomes model → voice → companion; API path first; optional steps skippable (FR-WIZ) |
| Detect, install and manage Ollama, GPT-SoVITS, STT | **Adapted** | Component manager (FR-COMP). Ollama, llama.cpp and the STT model are straightforward; GPT-SoVITS is the risky one and becomes an advanced, hardware-gated component |
| Voice providers: GPT-SoVITS, ElevenLabs, others | **Adapted** | Provider interface (FR-VP, D-036); small built-in voice as default; hosted voices opt-in and badged as cloud |
| Included 2 to 3 characters | **Adopted with conditions** | Built-in read-only packs; asset-rights checklist (§6) |
| Priorities 1, 2, 3 | **Adapted** | Release boundaries §4 (pets and 3D move to 1.1) |
| Paid, one-time, $14.99 to $19.99 | **Direction** | Price undecided; free-trial proposal |
| Open source now, license to change | **Adopted, made actionable** | D-032 and the LIC-1 hold |
| Dodo Payments | **Direction** | MoR and acceptable-use checks first; license-key sketch §5 |
| EXE/MSI from the website | **Adopted** | NSIS per-user preferred |
| Microsoft Store | **Deferred** | After 1.0 at the earliest |
| Code signing, versioning, updater, uninstaller, crash diagnostics, release pipeline | **Adopted** | K7; diagnostics opt-in, no telemetry by default |
| Marketing strategy | **Out of repo scope** | Short IP caution in §6; planning belongs in Track B |
| "No terminal for ordinary use" | **Adopted** | Dev instructions stay dev-only |
| "Inspect the repo, compare, propose a staged plan" | **Done** | `notes/yuri-inventory.md` plus this file |

### What was added beyond the handoff

1. **Component manager** abstraction shared by the Doctor panel, the wizard and the TTS backend (ARCHITECTURE §15).
2. **Walking-skeleton installer right after K1 (K1b)**, so packaging risk (Python sidecar, antivirus false positives, clean-machine install) surfaces early instead of at the end.
3. **Voice tiers** with a built-in default and a K2 spike to choose it.
4. **End-user key storage** in the Windows Credential Manager instead of `.env`.
5. **License hold rule** before any code is pushed publicly.
6. **Release train** (1.0 / 1.1 / 2.x) and the hardware and API-key reality checks.
7. **Asset, brand and policy checklist**, free-trial proposal, diagnostics export, signed-license-key sketch.

## 9. Open decisions

| Decision (from the handoff §13) | Where it stands |
|---|---|
| Final license | Open: D-032, options A/B/C, decide before code is pushed |
| Model-provider list | Proposal: Ollama, llama.cpp, any OpenAI-compatible endpoint (AI Router, OpenRouter, DeepSeek and others as presets) |
| STT | Decided in Yuri: faster-whisper on CPU |
| TTS architecture | Proposal: provider interface (D-036) |
| VRM/VRMA compatibility | FR-CR-2 validation list; VRM 0.x and 1.0 via three-vrm |
| Memory architecture | Decided: Yuri memory v2, shared (D-005) |
| Agent mode | Deferred to 2.x |
| 3D architecture | three.js scene packs (K5) |
| Installer technology | Proposal: Tauri NSIS per-user; verified by the K1b spike |
| Signing | Open: research cost and eligibility |
| Auto-update | Proposal: Tauri updater |
| Website | Separate repo; Track B |
| Payments and license verification | Direction; §5 sketch |
| Refunds and support | Open; Track B |
| Launch price | Open |
| Store vs direct | Direct first |
| First-release boundary | Proposal: §4 |
