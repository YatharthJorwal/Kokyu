> **Provenance:** verbatim copy of an external product-vision handoff that the user produced by researching and discussing with ChatGPT, supplied on 2026-11-11. It is **input, not an authority**: `docs/PRODUCT.md` §8 records how each item was treated (adopted, adapted, deferred, rejected). Where it disagrees with `DECISIONS.md`, the decisions win until the user changes them.

---

Kokyu — Product Vision & Scope Handoff

1. Product Overview

Kokyu is a Windows desktop AI companion application.

Its central purpose is to let users create, customise and interact with their own AI companions without having to manually configure complicated AI infrastructure.

The product is inspired by experiences like xAI’s Ani, but with significantly more user control over the companion, intelligence, appearance, voice and environment.

Kokyu is not an LLM, an AI model, an API provider or a hosted chatbot service.

It is the desktop application and orchestration layer that brings these components together into one accessible experience.

Core positioning

Your AI. Your waifu. Your world.

Create your own AI companion. Choose her appearance, personality, voice and intelligence. Talk to her, interact with her in 3D and customise the experience.

The primary use case is creating and interacting with a personalised AI girlfriend, but the platform should also support friends, assistants, roleplay characters and other companion types.

2. Core USP

The biggest selling point is personalisation without technical friction.

A user should be able to:

* Upload a VRM character.
* Define a custom personality and system prompt.
* Select or configure a voice.
* Choose an AI model or inference provider.
* Configure speech recognition.
* Start interacting with their companion.

The user should not need to understand Python environments, PowerShell, npm, model servers, ports or manual dependency configuration.

Kokyu should abstract away the infrastructure and expose it through a unified, approachable interface.

Product philosophy

* User-controlled rather than platform-controlled.
* Customisable rather than restricted to predefined characters.
* Local-first where possible.
* Bring Your Own Key (BYOK).
* Bring Your Own Model (BYOM).
* Easy for beginners, configurable for advanced users.

Avoid marketing claims such as literally having zero restrictions. Emphasise freedom of configuration, model choice and ownership of the experience instead.

3. AI Infrastructure and Integrations

Kokyu does not need to provide its own inference infrastructure.

Users can bring their preferred providers and services.

Inference

Potential supported integrations:

* Ollama.
* llama.cpp.
* API-based inference providers.
* Other compatible local or remote model endpoints.

Users should be able to select and switch models from within Kokyu.

Voice generation (TTS)

Potential integrations:

* GPT-SoVITS.
* ElevenLabs.
* Other compatible voice providers.

Custom voice configuration should support:

* Uploading a voice sample.
* Uploading its corresponding transcript.
* Configuring the voice-generation backend.
* Selecting a supported hosted voice using its ID and API credentials.

Speech recognition (STT)

Support an appropriate speech-to-text engine for live voice conversations.

The application should manage its setup and connection rather than requiring users to configure it manually.

Important architecture principle

Kokyu sells the software, not the underlying inference or voice services.

Users are responsible for their own API keys, provider subscriptions and usage charges.

Local infrastructure should remain an option for users who prefer to run models on their own hardware.

4. First-Launch Experience — Welcome to Kokyu

The first-launch setup window is a major part of the product.

It should feel like the onboarding experience of a polished desktop application, not a developer setup script.

Inspired by applications such as ComfyUI, the application should handle the complexity of installing and connecting the underlying components.

Proposed onboarding flow

Step 1 — Welcome

Introduce Kokyu and explain what it does.

Step 2 — Infrastructure detection

Check whether the required components are installed and available.

Examples:

* Ollama.
* GPT-SoVITS.
* Speech recognition engine.

Step 3 — Installation and configuration

If a component is missing, offer an installation option and guide the user through the process.

Kokyu should handle downloads, configuration and service management wherever technically feasible.

No manual PowerShell commands or terminal setup should be required for normal users.

Step 4 — Model selection

Allow the user to select an installed local model or configure a compatible API provider.

Step 5 — Voice setup

Allow the user to configure a voice provider, upload voice material and its transcript, or select an existing supported voice.

Step 6 — Character setup

Let the user select one of the included companions or create their own.

Step 7 — First conversation

Get the user into a working conversation as quickly as possible.

Optional features should not unnecessarily block the first conversation.

Onboarding principle

A user should be able to get their first companion conversation working without knowing anything about the underlying infrastructure.

5. Companion Creation and Customisation

This is one of Kokyu’s most important features.

Users should not be restricted to the included characters.

Custom companion creation

A companion should support:

* Custom name.
* Custom personality traits.
* Custom system prompt.
* VRM character upload.
* Voice selection or configuration.
* AI model selection.
* Associated animation and interaction settings.

The user should be able to create multiple companions and switch between them.

Included characters

The initial paid application is expected to include approximately 2–3 premade characters.

Custom companion creation should remain a central feature rather than being treated as a premium marketplace add-on.

Character asset compatibility

VRM is the intended character format.

The application should validate uploaded assets and communicate compatibility requirements rather than promising that every arbitrary VRM will work perfectly.

6. Main Application Features

The following represents the discussed product scope and intended direction.

Core interaction

* Standard chatbot interface.
* Persistent companion selection.
* Switch between companions.
* Switch between supported AI models.
* Custom personas and system prompts.
* Conversation history and memory capabilities.

Voice interaction

* Live voice conversations.
* Speech-to-text input.
* Text-to-speech output.
* Configurable voice providers.
* Companion-specific voice configuration.

3D experience

* VRM character rendered inside the application.
* Character animation and interaction.
* Multiple 3D environments.
* Potential environments such as an apartment and garden.
* Character interaction within the environment.

Advanced capabilities

* Agentic mode.
* File reading.
* File writing in agent mode.
* Camera and WebGL-related interactions.
* VR mode as a planned advanced capability.

These advanced features should be treated as a broader roadmap, not prerequisites for the first stable release.

7. Architecture and User Experience Principles

Kokyu must behave like a finished desktop application.

It should not require users to:

* Download loose source-code folders.
* Install Node.js manually.
* Run npm run dev.
* Open PowerShell to start services.
* Manually configure multiple Python environments.
* Search for model directories and connection settings.

Desired experience

1. Download Kokyu.
2. Run the installer.
3. Launch Kokyu.
4. Complete the graphical setup wizard.
5. Select or create a companion.
6. Start interacting.

Dependency management

The application should:

* Detect installed dependencies.
* Offer guided installation.
* Manage supported background services.
* Check whether services are running.
* Detect connection and compatibility problems.
* Display understandable error messages.
* Provide repair or retry options where possible.

Keep optional AI runtimes and large model downloads separate from the core application installer.

Do not unnecessarily bundle enormous models or every optional runtime into the main installer.

The application should be beginner-friendly by default while retaining advanced configuration for experienced users.

8. Licensing and Monetisation

Current licensing status

The project is currently open source.

The licensing approach is expected to change. Final licensing has not been decided.

Do not assume the current licence is the intended permanent commercial licence.

Business model

Kokyu is intended to be a paid desktop software product.

The user pays for the application itself, not for access to an LLM or hosted inference service.

Previously discussed pricing:

* Target price: approximately $15–20.
* Possible launch price: $14.99.
* Standard price under consideration: $19.99.
* One-time purchase rather than a mandatory subscription.

Users supply their own:

* API keys.
* Local models.
* Inference infrastructure.
* Voice providers and associated credentials.

No mandatory recurring Kokyu subscription is intended in the current business model.

Payment provider

Dodo Payments is the intended payment provider for direct website sales.

The objective is to support international customers without relying on UPI as the primary international payment method.

Payment verification, purchase entitlement, download delivery, refunds and licensing mechanisms still need to be designed.

9. Distribution Strategy

Current direction

The preferred direction is a standalone Windows EXE/MSI installer distributed through an official Kokyu website.

The customer should receive a proper installable product, not a ZIP containing source code.

Official website

The website is expected to provide:

* Product landing page.
* Screenshots and demonstrations.
* Feature information.
* Purchase and checkout flow.
* Installer downloads.
* Documentation.
* Support information.
* Version and release information.

Microsoft Store

Microsoft Store distribution was explored as an additional option.

The EXE/MSI distribution route is currently preferred if operating an official website and direct payment system.

Store distribution is not a confirmed requirement for the first release.

Release engineering

The production release should include:

* Proper application packaging.
* Code signing.
* Versioning.
* Installer and uninstaller.
* Update mechanism.
* Error handling.
* Crash diagnostics.
* Release documentation.

A future automated release pipeline should produce tested Windows installers from tagged releases.

10. Marketing and Audience Strategy

An important reference is the creator @thatlevco on Instagram.

His content represents AI companies, models and technologies as distinct anime characters.

This creates an interesting relationship between:

* AI-related content.
* Character recognition.
* Audience attachment.
* A desktop companion product using those characters.

The useful lesson is to build audience interest before the application is fully finished.

Proposed Kokyu marketing direction

Stage 1 — Build awareness

Publish content showing:

* AI companions.
* Character designs.
* Customisation possibilities.
* Interesting AI model integrations.
* Voice and animation demonstrations.

Stage 2 — Demonstrate the product

Show:

* VRM uploads.
* Personality customisation.
* Voice selection.
* Model switching.
* Live conversations.
* 3D environments.
* The Welcome to Kokyu setup experience.

Stage 3 — Build anticipation

Share development updates, working prototypes and public demonstrations.

Stage 4 — Release

Convert interested followers into customers when the software is stable and installable.

The goal is not to sell unfinished software. It is to establish demand and recognition before launch.

Marketing message

Lead with the emotional and practical use case:

“Create the AI companion you’ve always wanted.”

Then explain the technical freedom:

* Your character.
* Your personality.
* Your voice.
* Your AI model.
* Your environment.

Avoid leading with technical jargon such as BYOK, inference orchestration or TTS backends.

11. Product Priorities

Priority 1 — First stable release

* Production-ready desktop application.
* Welcome to Kokyu onboarding.
* Dependency detection and guided setup.
* Model selection and connection.
* Basic chatbot interface.
* VRM character rendering.
* Included companion characters.
* Custom companion creation.
* Basic voice integration.
* Proper Windows installer.

Priority 2 — Experience improvements

* Better live voice interaction.
* Multiple companions.
* Companion-specific voices and personas.
* More animation and interaction.
* Multiple 3D environments.
* Better memory and conversation management.

Priority 3 — Advanced capabilities

* Agentic mode.
* File operations.
* Camera-related capabilities.
* Advanced WebGL interactions.
* VR mode.
* Additional integrations.

These are priorities, not a promise that every feature must ship in the first release.

12. Important Product Constraints

1. Kokyu is a desktop application, not a hosted AI service.
2. The user controls their model and inference provider.
3. Kokyu does not sell model access or API credits.
4. Users should not need to use a terminal for ordinary installation and operation.
5. The main application should be installable and usable by nontechnical customers.
6. Custom companion creation is central to the product.
7. The application should support local-first workflows.
8. The first-launch experience is a major differentiator.
9. Avoid unnecessary subscriptions.
10. Do not make the first release dependent on every advanced roadmap feature.

13. Open Decisions — Do Not Assume These Are Finalised

The following require further technical or business decisions:

* Final software licence.
* Exact supported model-provider list.
* Exact STT implementation.
* Final TTS integration architecture.
* VRM/VRMA compatibility requirements.
* Companion memory architecture.
* Agentic mode implementation and permissions.
* Final 3D rendering and environment architecture.
* Installer technology and signing arrangements.
* Automatic update architecture.
* Website architecture.
* Dodo Payments integration and licence verification.
* Refund and customer support processes.
* Final launch price.
* Microsoft Store versus direct distribution strategy.
* Final first-release feature boundary.

14. Instructions for Development

Treat this document as the product direction and scope reference, not as an instruction to implement everything simultaneously.

Before making significant architectural decisions:

1. Inspect the existing Kokyu repository and implementation.
2. Identify what already exists.
3. Compare existing functionality against this scope.
4. Identify architectural gaps and technical risks.
5. Propose a staged implementation plan.
6. Preserve working functionality unless there is a clear reason to change it.
7. Update project documentation when implementation decisions change.

Do not invent completed features or assume that a discussed roadmap feature already exists.

The ultimate objective:

A person with no technical knowledge should be able to download Kokyu, install it, create or select an AI companion, choose its appearance, personality, voice and intelligence, and start having a conversation.

The complexity of the AI infrastructure should be handled by Kokyu—not pushed onto the user.
