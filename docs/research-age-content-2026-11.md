# Research: audience age, sexual content, laws and payment providers (B-9, D-088)

Written 2026-11-17 for the user's decision. Nothing here is legal advice. No other doc was changed.

**How to read the evidence labels**
- **[P]** read on the publisher's or lawmaker's own page by a fetch agent in this session.
- **[S]** secondary source only (law firm, news, review site). Treat as likely, not certain.
- **[?]** could not be confirmed. A claim marked this way must not be relied on.

Every URL was opened or returned by a search on 2026-11-17 unless a page says otherwise. Pages change; re-check before launch.

## 0. Short answer

1. **Every comparable app that allows sexual content is 18+.** None of the apps I could check sells sexual content at 16+. Character.AI went the other way and removed open-ended chat for under-18s (§1).
2. **The payment provider is the harder blocker, and it does not depend on age.** Lemon Squeezy, Paddle, Gumroad, Stripe and FastSpring all ban sexual or "adult" products in their own wording. Shipping personas with explicit sexual instructions puts the sale at risk whatever age we declare (§3). Lemon Squeezy is also closed to new sign-ups and shuts down on 31 March 2027 [P].
3. **16+ is the weakest option.** It is not a norm for this category, it is not an age line in any law found, and the laws that bind companion bots add duties exactly when a user is known to be a minor (§2).
4. **Recommended (analysis, not a finding): 18+, a first-run age gate, and premade personas that are not sexually explicit.** Details and alternatives in §5.

## 1. How comparable apps rate themselves

| App | Minimum age (stated) | Sexual content | How age is enforced | Source |
|---|---|---|---|---|
| Character.AI | Under-18s lost open-ended chat (phased out by 25 Nov 2025). Terms page was unreadable, so exact wording is [?] | Not stated in the post read. Adult stance [?] | Own age-estimation model; third-party tools incl. Persona reported [S]; facial or ID checks as a fallback [S] | [C.AI blog 2026-09-03 [P]](https://blog.character.ai/continuing-to-build-upon-our-safety-priorities/), [TechCrunch 2025-10-29 [S]](https://techcrunch.com/2025/10/29/character-ai-is-killing-the-chatbot-experience-for-minors/), [Engadget 2025-10-29 [S]](https://www.engadget.com/ai/characterai-to-ban-teens-from-talking-to-its-chatbots-180027641.html) |
| Replika | 18 ("only for adults"; terms updated 2026-10-28) | Bans uploading "obscene" or "pornographic" content; zero tolerance for sexualising anyone under 18. What the companion itself says to adults is filtered; paid tiers are described inconsistently [S] | Date of birth at sign-up; "may use age-assurance measures" | [Terms [P]](https://replika.com/legal/terms), [EDPB on the Italian fine [S]](https://www.edpb.europa.eu/news/news_en) |
| Chai | 18 (rated 18+ in app stores) | EULA allows "adult-oriented content, including mature themes" in text; bans sexually explicit images and video. The safety page and the EULA do not fully agree | Persona selfie age estimation or government ID | [Safety Center [P]](https://www.chai-research.com/safety), [EULA, 2026-07-28 [P]](https://www.chai-research.com/app-eula/) |
| Nomi | 18 ("under any circumstances") | The terms do not mention sexual content. Reviews say adult sexual content is allowed [S] | Self-declared date of birth; says it "intends to" add verification. A review reports checks only in Australia and Kansas [S] | [Terms, 2026-01-16 [P]](https://nomi.ai/terms-of-service), [eSafety guide [S]](https://esafety.gov.au/key-topics/esafety-guide/nomiai) |
| Kindroid | 18 or the local age of majority, whichever is greater (one review quotes the terms) [S] | Reviews say NSFW is allowed for adults in private chats [S] | Review says a paid subscription counts as proof of age and flagged free accounts use a Yoti selfie or ID [S]. Another review says self-certification only [S] | [Review 1 [S]](https://aicompanionpick.com/kindroid-vs-nomi-privacy-and-content-policy-2026). The terms page returned 404 [?] |
| SillyTavern | None. It is a locally installed, open-source (AGPL-3.0) frontend: "We do not provide any online or hosted services." | No policy; the chosen model decides | None | [GitHub README [P]](https://github.com/SillyTavern/SillyTavern) |

Observations:
- Four of the five hosted apps state 18+ (Character.AI's exact wording is [?]), and the one that moved furthest (Character.AI) exited minors after lawsuits [S].
- Enforcement is uneven: Chai uses ID or selfie checks; Replika and Nomi lean on a self-declared birth date. Regulators have punished the weak version (Replika, §2).
- Not checked: Candy.ai, Crushon, JanitorAI, Talkie, PolyBuzz.

## 2. Laws

### 2.1 United States

| Law | What it does | Reaches a solo seller of a local app? | Source |
|---|---|---|---|
| **California SB 243** (in force 2026-01-01) | "Companion chatbot" operators must disclose the bot is not human where a person could be misled, run a published suicide and self-harm protocol, and (for minors) disclose AI status, remind them to take a break at least every three hours by default, and take reasonable measures against sexually explicit visuals or urging sexually explicit conduct. Private right of action: the greater of actual damages or $1,000 per violation, plus fees. Annual reporting from 2027-07-01. | **Unclear [?].** "Operator" is defined as someone who makes a companion chatbot platform available to a user in California. Neither source I read addresses a downloadable app where the buyer supplies the model. Whether the minor duties trigger on knowledge of age or on all users was not settled by the statute text, which I could not read (HTTP 403). | [Troutman 2026-01-08 [S]](https://www.troutmanprivacy.com/2026/01/analyzing-the-new-ai-companion-chatbot-laws/), [Skadden 2025-10 [S]](https://www.skadden.com/insights/publications/2025/10/new-california-companion-chatbot-law) |
| **New York GBL Art. 47** (in force 2025-11-05 per Troutman) | Operators of an "AI companion" (simulates a sustained human-like relationship) need a self-harm detection and crisis-referral protocol and must say "not a human" at the start and at least every three hours. Attorney General enforcement only, up to $15,000 a day. No minor or age-verification duty, no private right of action. | **Plausibly yes.** The definition fits a persona app that keeps memory and asks personal questions. No small-business exemption in the sections read. | [NY Senate §§1700-1703 [P]](https://www.nysenate.gov/legislation/laws/GBS/1700) |
| **Other state laws** | One tracker lists about 12 states with companion-chatbot laws by mid-2026 (e.g. Oregon and Washington from 2027-01-01, Nebraska and Idaho from 2027-07-01, Hawaii 2026-07-14, Georgia disclosure every three hours and hourly for minors). Trackers disagree on counts and bill numbers. | **[?]** Not individually verified. | [Orrick 2026-04 [S]](https://www.orrick.com/en/Insights/2026/04/2026-State-Chatbot-Laws-Key-Provisions-and-Regulatory-Trends) (not readable by the agent), [multistate.ai [S]](https://www.multistate.ai/updates/vol-105-state-ai-companion-chatbot-laws) |
| **COPPA** (FTC rule, under-13s) | Applies to services directed to children or with *actual knowledge* they collect data from under-13s. The FTC FAQ says the rule "does not require operators to ask the age of visitors" and that neutral age screens may be relied on. Amended rule published 2025-04-22; the April 2026 compliance date is [?] (not read in a primary source). In February 2026 the FTC said it will not enforce COPPA against general-audience services that collect data only to check age, under conditions. | **Low risk** if the app is 18+ or 16+, is not child-directed, and collects no personal data (local-first). Ignoring a known under-13 user is the real exposure. | [FTC FAQ [P]](https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions), [FTC policy statement 2026-02-25 [P]](https://www.ftc.gov/news-events/news/press-releases/2026/02/ftc-issues-coppa-policy-statement-incentivize-use-age-verification-technologies-protect-children) |
| **FTC 6(b) study of companion bots** (2025-09-11) | An information request to seven large companies (Character.AI, Meta, OpenAI and others). Not an enforcement action and not aimed at small sellers. | No. Signals regulator attention. | [FTC [P]](https://www.ftc.gov/news-events/news/press-releases/2025/09/ftc-launches-inquiry-ai-chatbots-acting-companions) |
| **Federal bills** (GUARD Act, App Store Accountability Act) and Utah/Texas app-store age laws | Not verified. The agent guessed a wrong bill URL. | **[?]** Check before launch. App-store laws target stores, and the user rejected the Microsoft Store (`PRODUCT.md` §8). | none |

### 2.2 United Kingdom: Online Safety Act

- Ofcom says an AI chatbot is **out of scope** only if it (1) lets people interact only with the chatbot and no other users, (2) does not search multiple websites or databases, **and** (3) cannot generate pornographic content. Services that publish pornographic content, "including via chatbots", must use "highly effective age assurance" (HEAA). [Ofcom explainer, 2025-12-18 [P]](https://www.ofcom.org.uk/online-safety/illegal-and-harmful-content/ai-chatbots-and-online-regulation-what-you-need-to-know)
- The "conjunctive" reading (all three must hold) is the fetch agent's inference, not Ofcom's words. If it is right, limb (3) is hard for a bring-your-own-model app, because the seller cannot promise the model never writes explicit text. **[?]**
- Ofcom's pages say nothing about offline or locally installed software. Whether a local app is an "internet service" under Part 5 is unanswered in what I read. **[?]** Ofcom's own jurisdiction test includes "capable of being used by UK users" plus a material risk of significant harm. [Ofcom pornography hub [P]](https://www.ofcom.org.uk/online-safety/pornography)
- Fines: up to 10% of qualifying worldwide revenue or £18 million, whichever is greater. [Ofcom age-assurance page, updated 2026-11-16 [P]](https://www.ofcom.org.uk/online-safety/protecting-children/age-assurance)
- Precedent: Ofcom opened an investigation into Novi Ltd (Joi.com, a gen-AI companion site) on 2026-01-15 and closed it on 2026-07-31 without findings after Novi added age assurance. [Ofcom case page [P]](https://www.ofcom.org.uk/online-safety/protecting-children/investigation-into-novi-ltds-compliance-with-the-duty-to-prevent-children-from-encountering-pornographic-content-through-the-use-of-age-assurance)
- Ofcom's route for a small provider is to run its regulation checker or email the porn supervision team (address on the "Adults Only" page). [Ofcom "Adults Only" [P]](https://www.ofcom.org.uk/online-safety/pornography/adults-only-what-to-do-if-your-online-service-allows-pornography)
- Simplest compliance: block UK sales of an explicit product, or keep personas non-explicit and the app local with no hosting, sharing or web search. Both are options, not findings.

### 2.3 European Union

- **DSA Article 28 and the Commission's minors guidelines (published 2025-07-14):** non-binding but the Commission's benchmark. They say self-declaration of age is not appropriate, and age estimation should come from an independent or audited provider. The duty is on *online platforms*; a snippet says micro and small enterprises are exempt unless designated very large, but it was truncated **[S, ?]**. A locally installed app with no hosted platform is probably not a "platform" (my inference **[?]**). Primary page was not reachable. [Taylor Wessing [S]](https://www.taylorwessing.com/en/insights-and-events/insights/2025/07/rd-european-commission-guidelines-on-protection-of-minors-under-the-digital-services-act), [DSA Observatory [S]](https://dsa-observatory.eu/2025/07/30/do-the-dsa-guidelines-on-protecting-minors-online-strike-the-right-balance/)
- **AI Act Article 50 (tell people they are talking to an AI):** secondary sources say it applies from 2026-08-02 and was not delayed by the Digital Omnibus (Regulation 2026/1744 per one source), except machine-readable marking of AI output for systems already on the market, moved to 2026-12-02. Whether a seller of a BYO-model app counts as the "provider" is **[?]**. Cheap to satisfy anyway: persona UI says it is an AI. [Jones Walker [S]](https://www.joneswalker.com/en/insights/blogs/ai-law-blog/yes-august-2-still-matters-the-eu-approved-a-high-risk-ai-delay-but-most-trans.html), [Houthoff [S]](https://www.houthoff.com/insights/news/ai-act-transparency-obligations-and-the-ai-omnibus-regulation/). The agent could not read EUR-Lex.
- **GDPR and Replika:** the Italian regulator fined Luka Inc. €5 million (decision dated 2025-04-10 per the Enforcement Tracker), citing no age verification at sign-up despite an adults-only claim. The date and amount come from search results, not a page I read. [EDPB [S]](https://www.edpb.europa.eu/news/ai-the-italian-supervisory-authority-fines-company-behind-chatbot-replika_cs), [Enforcement Tracker [S]](https://www.enforcementtracker.com/ETid-2611). GDPR is limited here if the app sends no personal data to the seller; the model provider and any age-check vendor still process data. Digital consent age (Art. 8) varies 13 to 16 by member state **[?]**, not verified.

### 2.4 India

- **DPDP Rules 2025:** a child is under 18, and verifiable parental consent is required before processing a child's data; tracking and targeted ads aimed at children are barred, with exemptions. Penalties up to ₹200 crore are reported. The duty is on a data fiduciary that processes personal data. A local-first app that collects nothing may fall outside it **[?]**. Sources disagree on exemptions; check the notified text. [India Briefing [S]](https://www.india-briefing.com/news/dpdp-rules-2025-india-data-protection-law-compliance-40769.html), [The Week [S]](https://www.theweek.in/theweek/business/2025/12/20/indias-dpdp-rules-2025-a-deep-dive-into-the-new-data-privacy-law.html)
- **IT Act s.67 (obscene) and s.67A (sexually explicit):** publishing or transmitting is criminal (up to 3 and 5 years for first conviction per commentary). Aimed at publishing or transmission; no source applied it to a local single-user tool **[?]**. [Internet Democracy Project [S]](https://internetdemocracy.in/laws/the-information-technology-amendment-act-2008/section-67-and-67a/)
- No MeitY rule specific to AI companions was found. The IT Rules were amended with effect from 2026-02-20 on synthetic content and takedowns, aimed at intermediaries. [YourStory [S]](https://yourstory.com/ai-story/govt-tightens-social-media-rules-on-ai-content). Which law governs the seller personally depends on where the seller is based, which this report does not assume.

### 2.5 What applies to a small solo seller (summary)

| Item | Applies? |
|---|---|
| New York Art. 47 duties (AI disclosure, self-harm protocol) | Probably, if sold to New York users. Cheap to build. |
| California SB 243 | Possibly. Unresolved for BYO-model desktop apps. Highest-liability item (private suits). |
| COPPA | Only with knowledge of under-13s or child-directed marketing. |
| UK Online Safety Act | Unresolved for local software. Explicit output makes it riskier. |
| EU DSA Art. 28 | Probably not (not a platform). |
| EU AI Act Art. 50 | Disclosure only; cheap. |
| India DPDP, IT Act | Unresolved. |

## 3. Payment providers and Merchants of Record

Read on 2026-11-17 by a fetch agent unless marked. Nobody ruled on this product. Each provider reserves discretion and says to ask when unsure.

| Provider | Sexual or adult content | Chatbots or AI companions | Fit for 18+ non-explicit roleplay | Source |
|---|---|---|---|---|
| **Lemon Squeezy** | Bans "Sexually-oriented or pornographic content of any kind, including NSFW chatbots" and "Dating sites" | Names only NSFW chatbots | Judgment call. **Closed to new sign-ups; shuts down 2027-03-31.** Not an option for a new launch. | [Prohibited products [P]](https://docs.lemonsqueezy.com/help/getting-started/prohibited-products) |
| **Paddle** | Category 8: "Adult and other age-restricted content and services, including sexually-oriented or pornographic products"; also bans dating apps | Not named. Category 16 restricts "Human-like faces in realistic, stylized, or animated forms" and voice impersonation, which could touch VRM characters and voices | **Risky.** "Age-restricted" wording means an 18+ framing is itself a flag. Ask Paddle in writing. Paddle AUP, last updated 2026-04-13. The help article returned 404. | [Paddle AUP [P]](https://paddle.com/support/aup/) |
| **Gumroad** | Bans sexually oriented content, dating and "companion or escort services" (item 48) | Item 2 bans "AI services which includes selling access to AI tools, chatbots...". The scope of the qualifier is unclear. | **Worst fit.** A chatbot product looks banned whatever the rating. Revised 2026-09-16. | [Prohibited [P]](https://gumroad.com/prohibited) |
| **Stripe** | Bans pornography and mature content "designed for the purpose of sexual gratification", "adult live-chat features", and AI-generated content meeting those criteria. Dating is restricted (due diligence), not banned. Updated 2026-09-22; the copy read was the India-locale page. | Not named | Depends on purpose. Non-explicit "mature themes" is not clearly covered. Direct use of Stripe means no Merchant of Record, so sales tax is the seller's job (not researched). | [Stripe list [P]](https://stripe.com/legal/restricted-businesses), [FAQ [S]](https://support.stripe.com/questions/prohibited-and-restricted-businesses-list-faqs) |
| **FastSpring** | "Adult content, pornography and sex-related merchandising are prohibited", defined by "primary purpose" of sexual arousal, and "sites that may infer sexual content" | Not named. It markets AI products (page not read). | Test is purpose, but "may infer sexual content" is broader and FastSpring decides what counts. | [Terms of use [P]](https://fastspring.com/terms-use/) |

Cross-check: a Freemius blog (a competing vendor) says AI-labelled products may go to manual review at Paddle and Lemon Squeezy. That is a vendor's claim about rivals. [S] [Freemius](https://freemius.com/blog/payment-platform-restrictions-ai-apps/)

Other MoRs listed in search results ban the case outright: Dodo Payments excludes "NSFW chatbots" [S] [Dodo](https://docs.dodopayments.com/miscellaneous/merchant-acceptance). Adult-specialist processors (e.g. Segpay, CCBill) exist but were not researched **[?]**.

What this means:
- Explicit personas shipped inside the paid product are the risk. Providers judge the product and its marketing (website, store page, screenshots), not what the user later does with their own model.
- No provider requires an age gate as a condition. They either ban the content or they do not.
- Before choosing a provider, send each shortlisted one a plain description of the product and ask for a written yes. That is the only authoritative answer.

## 4. Age-gate options for a desktop app

| Option | What it is | What expects or accepts it | Cost and trade-offs |
|---|---|---|---|
| **Self-declaration** (date of birth or "I am 18+" at first run, plus terms) | No evidence needed | COPPA: a *neutral* age screen is a recognised practice ([FTC FAQ [P]](https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions)). Ofcom lists self-declaration as **not** highly effective, and the EU DSA guidelines say it is not appropriate for platforms ([Osborne Clarke [S]](https://www.osborneclarke.com/insights/uk-online-safety-ofcom-assesses-highly-effective-age-assurance-methods-online-services), [Taylor Wessing [S]](https://www.taylorwessing.com/en/insights-and-events/insights/2025/07/rd-european-commission-guidelines-on-protection-of-minors-under-the-digital-services-act)). The Italian fine against Replika was about lacking a gate at all. | Free, no data leaves the PC. Trivial to bypass: reinstall, or edit settings (my inference). Sensible baseline, not a defence for explicit content in the UK or EU. |
| **Payment as proof** (a paid purchase with a *credit* card) | Ofcom counts credit-card checks as capable of HEAA at 18; debit cards or cards usable by non-adults do not count ([Osborne Clarke [S]](https://www.osborneclarke.com/insights/uk-online-safety-ofcom-assesses-highly-effective-age-assurance-methods-online-services)). Kindroid is reported to treat a paid subscription as proof [S]. | A one-time purchase through a Merchant of Record might give weak evidence. Whether the MoR checkout is a "credit card check" in Ofcom's sense is **[?]**. | No extra cost. Not controllable by the seller; payment method is the provider's. |
| **Third-party age estimation or ID check** (Yoti, Persona, k-ID and similar) | Selfie age estimation or ID photo through a vendor | Ofcom lists facial age estimation, photo-ID matching, digital ID, open banking and mobile-network checks as capable of HEAA at 18. The EU guidelines accept estimation only from independent or audited providers. Chai uses Persona; Kindroid reportedly uses Yoti [S]. | Per-check prices are not public for Yoti or k-ID; I found no Persona price. A competitor's marketing says $0.10 a check [S], not verified. Needs a network call and an account with the vendor, so a selfie or ID goes to a third party. That conflicts with the "nothing leaves the machine" design for camera data (CLAUDE.md invariant 3) unless it is an explicit, separate flow. Needs a server or a vendor SDK that works for a local app; not researched **[?]**. |

Other points:
- Whether a gate is *legally required* for a local app that ships sexual text depends on the open UK question (§2.2). In the US, no law found requires age verification for companion chatbots; SB 243 duties turn on minors, so a declared 18+ gate also helps by making "we did not know" credible **[inference]**.
- Hard to verify: how app-level age signals would work on Windows. No OS-level age signal was found. Not researched.

## 5. Options and recommendation

| Option | Content | Age gate | Payment provider | Legal exposure | Cost and effort | Main risks |
|---|---|---|---|---|---|---|
| **A. 16+ as in D-088, personas as written** | Explicit instructions in premades | Self-declared, 16 | Likely banned (all five providers, §3) | Highest: minors plus sexual content. SB 243 minor duties; UK and EU treat sexual content with minors as the core harm | Lowest build cost | Payment accounts refused or frozen; no comparable app does this; D-088 premise ("category is already 16+") is not supported by the sources found |
| **B. 16+ with non-explicit premade personas** | Romantic or suggestive at most | Self-declared, 16 | Better, but "age-restricted" and dating wording still apply | Medium. SB 243 minor duties apply once a user is known to be a minor; GDPR digital-consent ages up to 16; India treats under-18s as children | Rewrite two personas; add AI disclosure and self-harm protocol | A 16+ line matches no law or rating norm found; BYO-model users can still make explicit content, so the seller's "non-explicit" claim is only about what ships |
| **C. 18+ with non-explicit premade personas** (recommended) | Premades safe for providers; adults can write their own personas and bring their own models | Neutral date-of-birth screen at first run; terms say 18+; block on a failed check | Best fit for Paddle or FastSpring after a written yes | Lower: 18+ matches every comparable app; still do NY Art. 47 duties and consider SB 243 | Rewrite two personas; first-run gate; terms and privacy policy; AI disclosure and crisis-protocol features | UK and EU regulators call self-declaration weak if the seller is found to be a pornography publisher; the premades are a worse product for people who bought for explicit roleplay |
| **D. 18+ with explicit premades and a strong age gate** | Explicit as written | ID or age-estimation check | Needs an adult-friendly processor (not researched) | Medium. UK Part 5 HEAA likely applies if the app counts; high compliance burden | Vendor integration, per-check cost, privacy conflict (§4), possibly a different merchant account | Most work and the weakest payment-provider fit; solo seller carries the burden |
| **E. Split: 18+ with an optional explicit pack** | Core app non-explicit; explicit persona pack as separate opt-in content | Age gate before the pack | Pack likely needs its own channel | As D, but isolated | Two products to maintain | Complexity; marketing the pack on the same account can still trip provider reviews |

My recommendation is **C**, with these steps (all inferred, for the user to approve):
1. Change D-088 to 18+ and the premades to non-explicit before choosing a processor.
2. Email the shortlisted providers (Paddle, FastSpring) a plain description and get a written reply. Drop Lemon Squeezy (closing) and Gumroad (bans chatbots).
3. Add a neutral age screen at first run, 18+ in terms, an AI-disclosure line and a crisis-referral protocol (cheap, and covers NY Art. 47; SB 243 likely).
4. Block sales to the UK unless Ofcom confirms the app is out of scope, or keep the app local with no hosting, sharing or web search. Ask Ofcom's checker.
5. Get a lawyer's read on SB 243 for a BYO-model desktop app before launch. This is the main unknown with a private right of action.

## 6. What I could not verify

- Character.AI terms and sexual-content stance; Kindroid terms (both pages 404); Nomi's sexual-content stance in its own terms.
- The text of SB 243 (403 from the legislature site), so the "knows the user is a minor" trigger and BYO-model coverage.
- The COPPA April 2026 compliance date; federal bills and Utah/Texas app-store laws.
- Anything primary on the EU DSA, AI Act (EUR-Lex returned an empty response) and India (MeitY returned 403).
- Paddle's help article (404) and Gumroad's adult-content help article (title only), FastSpring's AI page, Stripe's non-India page and its AI-companies guidance.
- Per-check prices for any age-verification vendor.
- Whether Ofcom treats locally installed software as an "internet service".

## 7. Sources

All accessed 2026-11-17. Publication or update dates are given where the page showed one.

- Character.AI blog, 2026-09-03: https://blog.character.ai/continuing-to-build-upon-our-safety-priorities/
- TechCrunch, 2025-10-29: https://techcrunch.com/2025/10/29/character-ai-is-killing-the-chatbot-experience-for-minors/
- Engadget, 2025-10-29: https://www.engadget.com/ai/characterai-to-ban-teens-from-talking-to-its-chatbots-180027641.html
- Replika terms, updated 2026-10-28: https://replika.com/legal/terms
- Chai safety page and EULA (2026-07-28): https://www.chai-research.com/safety, https://www.chai-research.com/app-eula/
- Nomi terms, 2026-01-16: https://nomi.ai/terms-of-service
- SillyTavern: https://github.com/SillyTavern/SillyTavern
- Troutman, 2026-01-08: https://www.troutmanprivacy.com/2026/01/analyzing-the-new-ai-companion-chatbot-laws/
- Skadden, 2025-10: https://www.skadden.com/insights/publications/2025/10/new-california-companion-chatbot-law
- NY GBL Art. 47: https://www.nysenate.gov/legislation/laws/GBS/1700
- FTC COPPA FAQ and 2026-02-25 policy statement, FTC 6(b) 2025-09-11: URLs in §2.1
- Ofcom pages (2025-12-18, 2026-09-09, 2026-11-16 and others): URLs in §2.2
- EDPB / Enforcement Tracker (Replika fine): https://www.edpb.europa.eu/news/ai-the-italian-supervisory-authority-fines-company-behind-chatbot-replika_cs, https://www.enforcementtracker.com/ETid-2611
- EU DSA guidelines commentary: https://www.taylorwessing.com/en/insights-and-events/insights/2025/07/rd-european-commission-guidelines-on-protection-of-minors-under-the-digital-services-act, https://dsa-observatory.eu/2025/07/30/do-the-dsa-guidelines-on-protecting-minors-online-strike-the-right-balance/
- AI Act Art. 50 commentary: https://www.joneswalker.com/en/insights/blogs/ai-law-blog/yes-august-2-still-matters-the-eu-approved-a-high-risk-ai-delay-but-most-trans.html, https://www.houthoff.com/insights/news/ai-act-transparency-obligations-and-the-ai-omnibus-regulation/
- India: https://www.india-briefing.com/news/dpdp-rules-2025-india-data-protection-law-compliance-40769.html, https://internetdemocracy.in/laws/the-information-technology-amendment-act-2008/section-67-and-67a/, https://yourstory.com/ai-story/govt-tightens-social-media-rules-on-ai-content
- Payment providers: Lemon Squeezy https://docs.lemonsqueezy.com/help/getting-started/prohibited-products; Paddle https://paddle.com/support/aup/ (2026-04-13); Gumroad https://gumroad.com/prohibited (2026-09-16); Stripe https://stripe.com/legal/restricted-businesses (2026-09-22); FastSpring https://fastspring.com/terms-use/; Dodo https://docs.dodopayments.com/miscellaneous/merchant-acceptance; Freemius https://freemius.com/blog/payment-platform-restrictions-ai-apps/
- Age assurance methods: https://www.osborneclarke.com/insights/uk-online-safety-ofcom-assesses-highly-effective-age-assurance-methods-online-services
