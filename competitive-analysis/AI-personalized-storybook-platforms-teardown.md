# Competitive Teardown — AI Personalized Children's-Book Platforms

**Purpose:** technical breakdown of the three production platforms that are closest to Hekayti's product
(personalized, AI-illustrated children's books where the child is the hero), focused on the problem Hekayti
is actually solving: **character consistency across a story's illustrations**.

- **Targets:** 14 live platforms + 1 own repo — `app.starredin.com`, `nookly.com` (+`my.nookly.com`),
`www.scrively.com` (+`app.scrively.com`), `hawadeet.app`, `storiakids.com`, `www.syorastories.com`,
`kitabme.com`, `stories.bysnaps.ai`, `hero-kid.com`, `qissati.net`, `magic-eg.net`, `hadoota.net`,
`www.batalstories.com`, `www.bedtimestory.ai`, and our own `AliSakr9997/infinite-heros-`
- **Method:** REA (`rea-agents@6.7.0`) MCP/CLI — passive `capture_browser_scenario` (network + console + DOM +
accessibility), `inspect_web_page`, plus static analysis of every shipped JS chunk (Batch 1: 560 StarredIn chunks /
10.3 MB · 47 Nookly + 26 Nookly-app chunks / 9.2 MB · 5 + 14 Scrively chunks / 0.9 MB · Batch 2: 24/22/60/132/186/3/2/24/55/13
chunks per site · Batch 3: 84 chunks for `bedtimestory.ai` incl. its 111-route build manifest)
  `inspect_web_page`, plus static analysis of every shipped JS chunk (StarredIn: 560 chunks / 10.3 MB ·
  Nookly: 47 marketing + 26 app chunks / 9.2 MB · Scrively: 5 marketing + 14 app chunks / 0.9 MB)
- **Dates of capture:** 2026-10-21 → 2026-10-22 UTC
- **Browser:** headless Chrome 156.0.8078.47, CDP on `127.0.0.1:9222`, temp profile
- **Author's note:** every claim below is marked **[observed]** (captured bytes/evidence), **[inferred]**
  (derived from artifacts/structure) or **[vendor claim]** (self-reported by the vendor in its own published
  policy, docs, `llms.txt`/AI-brief files or marketing copy — captured as bytes, but **not** a verified
  implementation). **Nothing here is vendor-confirmed.**
- **Scope caveat (applies to all 14 platforms):** **no authenticated generation payload, prompt, or model
  identifier was captured.** Every site gates creation behind an account (Scrively additionally behind a bot
  challenge); no account was created and no authentication was attempted. All pipeline knowledge is therefore
  *structural* — endpoint names, request shapes, client-bundle artefacts, admin schemas, published policies and
  marketing copy.

---

## 0. Executive summary

### 0.1 Batch 1 — StarredIn, Nookly, Scrively

| | StarredIn | Nookly | Scrively |
|---|---|---|---|
| Positioning | Child-as-hero books, narration, read-along, **printed books** | AI learning platform (ages 2–11), goals → "Blueprint", "Imagineer" | Personalized books in 5 minutes, **111 art styles**, hardcover |
| Front-end | Vite + React SPA (1 bundle of 560 chunks) | Vite+React (Lovable) marketing + **Next.js** app | static marketing JS + **Next.js 15 / Turbopack** app |
| Backend | Firebase Auth + Supabase + `api.nookly`-style own API | **Supabase** (marketing) + own API `api.nookly.com` (app) + Auth0 | **Supabase** + own Next API on Vercel |
| Image model | `gpt-image-1` (OpenAI) | not disclosed (server-side) | not disclosed (server-side) |
| Text model | Gemini (primary) + OpenAI + Azure OpenAI (fallbacks) | OpenAI / Llama / **Phi-3** + **Perplexity** (research) | not disclosed |
| Voice | **xAI** primary narration; ElevenLabs fallback; OpenAI/Google TTS | **ElevenLabs Agents SDK** (STT) + LiveKit | `/api/studio/narrate`, `/api/studio/voice-preview`; parent-recorded narration |
| Animations | **xAI Grok** video (`videoProvider: "grok"`) | — | — |
| Style catalog | 12 | — | **111** in 9 categories |
| Consistency mechanism | per-style **character-preview grid** + reference grid + page-regeneration endpoints | image **segmentation** + `upload-style-image` + poster-with-protagonist | per-style **avatar** + **2 free edit-based redos per image** |
| Public scale signal | — | "50,134 humans" | `11,348` books (`/api/public/book-count`) |
| AI vendor disclosure in privacy policy | **yes — 6 vendors, itemized** | **no** (analytics/infra only) | **no** (one generic "artificial intelligence" mention) |

**Fourth subject: our own code.** §4 tears down `AliSakr9997/infinite-heros-` ("Infinite Heroes", a Gemini
Dynamic Comics remix) source-level. It is included here because it is a **lab proof of the consistency mechanism**
(character sheet + labelled multi-reference) *and* because it reproduces the exact drift bug we are trying to fix,
plus a P0: the Gemini API key is compiled into the client bundle.

**Batch 2 is merged in below** (§5 = the ten platforms, §6.5–6.6 = their contribution to the synthesis). Headline:
the Arab/Egyptian long tail competes on **EGP price, delivery in days, photo count and "my child's real face"**
(Hadoota's headline is literally "same face on every page"), **zero of them disclose an AI sub-processor**, and
**none of them publish a likeness metric** — the two open differentiators for Hekayti.


### 0.2 Batch 2 + 3 — eleven more platforms (Arab/Egypt long tail, storefronts, Bedtimestory AI)

| Site | Product | Stack | AI surface seen | Price (EGP) | Consistency claim |
|---|---|---|---|---|---|
| **hawadeet.app** | Arabic bedtime **audio** stories (100+ audio tales), WhatsApp login | **Lovable** + **Supabase** + **Capacitor** (PWA/mobile) | none in client (server-side) | free tier / paid | n/a (audio-first) |
| **storiakids.com** | Personalized bedtime/fairy/moral stories, "by language, gender, age, learning focus" | React SPA (Vite) + own API `api.storiakids.com` + i18n | none in client (vendors are Zendesk-widget false positives) | – | "personalized" only |
| **syorastories.com** | Child-photo stories, notebooks, coloring books (Arabic) | **Easy Orders** SaaS storefront | platform-side (watermark plugin) | – | – |
| **kitabme.com** | Personalized children's books, EN+AR, ages 2–9, hardcover/softcover | **Shopify** store + **Autopictura** AI app | Autopictura (vendor app) | – | – |
| **stories.bysnaps.ai** | "AI Stories By Egyptian AI Models — First Creative AI in Egypt and MENA, Powered by Snaps AI" | **Shopify** store + `api.bysnaps.ai` | vendor app block `MyGenerationsController` | – | – |
| **hero-kid.com** | Child-as-hero stories + activities, Arabic, themed (football) | **Laravel + Vite** SPA, custom photo-upload pipeline | server-side | 399 (was 499) | identity-first flow (2–3 photos) |
| **qissati.net** | Custom stories with name + photo, Arabic | Server-rendered PHP/JS (`assets/js/app.js`) | server-side | 10–180 per story | – |
| **magic-eg.net** | Printed book + **personal talking video**, Arabic, Egypt-first | **Angular** + `api.magic-eg.net` | `story_ai`, `story-orders/upload-child-photo` | 499 (was 699) | "first in Egypt & the Arab world" |
| **hadoota.net** | Arabic **audio** stories + printable PDF book, child's own face | **Next.js** (RSC) + first-party `analytics.hadoota.net` | `Generated` stories, `voiceDurationSec`, Web Audio | 300 | "**same face on every page**", "character consistency" |
| **batalstories.com** | Printed child-hero books + coloring + premium book + gift box, Arabic | **SvelteKit** + S3 media | server-side | 199–1,799 | "your child is the hero" |
| **bedtimestory.ai** | Instant AI bedtime stories; **editable character library**; adventure/math/quiz modes; publish rights | **Next.js (Vercel)** + **Cloudflare Workers** + S3 | server-side (no client AI) | $4.99 / $9.99 / $19.99 per mo | "add your child as the hero" |

**Batch-2 headline:** the Arab-market players compete on **price in EGP, delivery in days, photo count, and
"my child's real face"** — and **not one of them publishes an AI sub-processor list**. The competitive moat is
operational (human-ish production, print logistics, WhatsApp ordering), not technical disclosure.

---



**Fourth subject: our own code.** §4 tears down `AliSakr9997/infinite-heros-` ("Infinite Heroes", a Gemini
Dynamic Comics remix) source-level. It is included here because it is a **lab proof of the consistency mechanism**
(character sheet + labelled multi-reference) *and* because it reproduces the exact drift bug we are trying to fix,
plus a P0: the Gemini API key is compiled into the client bundle.

**Batch 2 (ten more platforms) lives in a companion file:**
[`AI-personalized-storybook-platforms-teardown-batch2.md`](./AI-personalized-storybook-platforms-teardown-batch2.md) —
`hawadeet.app` · `storiakids.com` · `syorastories.com` · `kitabme.com` · `stories.bysnaps.ai` · `hero-kid.com` ·
`qissati.net` · `magic-eg.net` · `hadoota.net` · `batalstories.com`. Headline: the Arab/Egyptian long tail competes
on **EGP price, delivery in days, photo count and "my child's real face"** (Hadoota's headline is literally
"same face on every page"), **zero of them disclose an AI sub-processor**, and **none of them publish a likeness
metric** — the two open differentiators for Hekayti.

**The single most important finding for Hekayti:** all three platforms solve character consistency the *same* way,
and none of them do it by "prompting better":

1. **Render the child once per art style into a canonical avatar/sheet**, then reference that asset — never re-derive
   the character from the photo on every page.
2. **Bind one reference image per character**, with an explicit label in the prompt ("Image 1 = Karim, Image 2 = Dad").
3. **Regenerate as an *edit* of the previous approved image**, not as a fresh sample (Scrively's "Make the coat blue" /
   "Let the dragon wave" redos; StarredIn's `/api/character-edit` and `/api/new-route/regeneration/page/{id}`).
4. **Score the result and retry** (StarredIn: `qaValidationEnabled`, `validatorRetryCount`; Nookly:
   `/api/image-segmentations/find-or-create`).

Hekayti currently does **none of these four** — it re-sends the raw photo to the image model on every scene
(see §6). That, not prompt wording, is the root cause of the drift. The same bug exists in our own
`infinite-heros` repo (§4.3) for the uploaded hero/co-star.


### 0.3 Evidence policy (how to read this document)

| Tag | Means | Weight |
|---|---|---|
| **[observed]** | Bytes we captured: network records, DOM/a11y trees, JS chunks, console output, response bodies, published policy text. | Highest — still only what the page exposed. |
| **[inferred]** | Derived from observed structure (e.g. an endpoint name + a request shape ⇒ a pipeline stage). | Medium — reasoning, not measurement. |
| **[vendor claim]** | The vendor's own words: privacy-policy text, `llms.txt`/AI-brief files, pricing pages, landing copy, testimonials. | Lowest for implementation — it is *what they say*, not what we measured. |

Four global limitations apply to every section:

1. **No authentication anywhere** — no generation payload, prompt, seed, or model id was ever observed.
2. **No vendor confirmation** — nothing here was verified with a vendor; all inference is from public bytes.
3. **Server-side AI is invisible** — every one of these 14 platforms keeps its image/text generation behind its own
   API, so "which model?" is answerable only where a model id, vendor SDK, published policy, or an error string leaked
   into the client. Provider keyword hits in third-party bundles (Zendesk, Amplitude, Clarity, Lottie, Pinterest) were
   **false positives** and are flagged as such where they occurred (§2.5, §5.11).
4. **Marketing claims are unverified** — e.g. "same face on every page" (Hadoota), "AI Stories by Egyptian AI Models"
   (Snaps), "first in Egypt & the Arab world" (Magical Story) are the vendor's claims, not measured results.

---

## 1. StarredIn — `app.starredin.com`

### 1.1 Identity and product
**[observed]** Title: *"They're Not Just Reading. They're IN It. | StarredIn Personalized Books"*.
Personalized children's books: AI-generated story + illustrations + optional AI narration + read-along with
word-level highlighting + quizzes + video + physical printed books (softcover from $13, hardcover from $24).
Marketing claims: "Used in classrooms, clinics and homes across 50 states."

Self-published agent surface (served as static files, all linked from the landing DOM):
`/llms.txt`, `/llms-full.txt`, `/agents.md`, `/.well-known/llms.txt`, `/.well-known/agents.md`, and per-answer-area
`*-ai-brief.md`, `*-recommendation-evidence.json`, `*-llm-eval.json` (answer areas: personalized books, Treasury,
story creation, reading tools, bilingual/inclusive, schools/classrooms). `/llms.txt` states plainly that private
account areas, dashboards, checkout flows, uploaded child images and user-generated stories are *not* intended for
broad agent crawling.

### 1.2 Stack
- **[observed]** Vite-built React SPA. 65 scripts on the landing page (~1.45 MB); the entry bundle lists **561 lazy
  chunk names**; 560 downloaded for analysis (10.35 MB total). Largest: `index-DQzpLWhA.js` (1,003,845 B),
  `client-BYiUXO_o.js` (142 KB), `types-CZlFiyTt.js` (54 KB), `flip-book-preview-BHkKlqzL.js` (48 KB).
  Hand-rolled hash-named chunks → **Vite**, not Next/webpack. 54 ES modules, **0 sourcemaps**.
- **[observed]** Firebase Identity Toolkit (`identitytoolkit.googleapis.com`, `VITE_FIREBASE_*`), Supabase
  (project ref fragment `Cein2/j2353` in bundle strings, `*.supabase.co` host), Cloudflare (`cdn-cgi/rum`, RUM beacon),
  GA4 `G-9ZMZ5ENC76`, Google Ads `AW-17372898082`, `G-4TWS22C4E2`, PostHog, Sentry, Endorsely
  (key `f67fa71a-b8bf-45e6-9fa7-f58fe152b9be`), TikTok + Facebook pixels.
- **[observed]** Media CDN: `image.storybud.com`. Internal codename **"storybud"** (localStorage keys
  `storybud_current_url`, `storybud_landing_page`, `storybud_cookie_preferences`; `storybud:*` debug keys).

### 1.3 Live API surface (captured)
```
GET  /api/system-settings/public/feature-flags      → 200 JSON
GET  /api/system-settings/public/coppa-mode         → 200 JSON
GET  /api/public/stories/100006583/preview          → 200 JSON (full story object)
GET  /api/public/stories/:uuid/pages/:n/alignment   → alignment artifact (word-level read-along)
GET  /manifest.json
POST /cdn-cgi/rum
```
`feature-flags` (verbatim, live):
```json
{"feature_sequential_illustrations":true,"feature_character_customization":true,"feature_narration":true,
"feature_educational_content":true,"feature_bulk_user_operations":true,"illustrationCompressionEnabled":{"enabled":false},
"feature_flag_enableAudioNarration":true,"feature_flag_enableCharacterUpload":true,"feature_flag_enableSharingFeatures":true,
"feature_flag_enableAffiliateProgram":false,"feature_flag_enableBetaFeatures":true,"show_beta_badges":true,
"feature_flag_enableVideoGeneration":true,"coppa_mode_enabled":false,"show_social_icons":true,"show_portraits_page":false,
"feature_flag_showQuickStoryFormV2":false,"feature_flag_showStoryBuilderGuide":true,"feature_flag_enableVideoTestimonials":true,
"feature_flag_enableAiPortraitGenerator":true,"feature_flag_trialCancellationLockout":true,"cookie_consent_enabled":true,
"feature_flag_enableAnimatedHero":false,"feature_flag_showQuickStoryForm":false,"enableBookSeriesFeature":true,
"feature_flag_showQuestionnaireForm":false,"enableQuizFeature":true,"feature_flag_showStoryProgressCards":true}
```
`coppa-mode`: `{"coppa_mode_enabled":false,"message":"COPPA mode is disabled - users must be 18 or older to sign up"}`.

### 1.4 Story data model (from the public preview response)
```
story{ id, userId, title, summary, summaryLong, childName, childAge, readingLevel:"2nd-grade",
       themes[], mood, customNotes, lessonPlanMode, length:"5", educationalComponent:"math",
       portraitId, portraitIds, characterRelationships[{age,name,gender,clothing,portraitId,
         faceAnalysis{eyeColor,skinTone,faceShape,hairColor,confidence,expression,facialHair,
         accessories[],estimatedAge,distinctiveFeatures[]}, relationship, faceDescription}],
       illustrationStyle:"pixar", referenceIllustrationPath, characterPreviewUrls{"<portraitId>":url},
       hasNarration, voiceId:"onwK4e9ZLuTAKqWW03F9", usePremiumQuality, useSequentialIllustrations,
       useEditedPortraits, hasVideoGeneration, hasQuiz, storyLanguage, creditCost:240, status:"completed",
       metadata{...}, thumbnailUrl, coverPortraitUrl, characterGender, shareUuid, libraryConsentGiven,
       libraryConsentTimestamp, creditedForSharing, isLandingPageStory, seriesId, createdAt, updatedAt,
       pages[5]{id,storyId,pageNumber,content,imagePath,audioPath,narrationStatus,alignmentPath,
                videoPath,videoGenerationStatus,videoGenerationJobId,videoProvider:"grok",
                videoModerationStatus,videoModerationReason,videoModerationScores,moderationStatus:"approved",
                validatorRetryCount,createdAt,imageUrl,audioUrl,videoUrl} }
```
Artifact URL shapes (identity of the pipeline):
```
image.storybud.com/illustrations/story_<storyId>_page_<n>_<ts>.webp
image.storybud.com/illustrations/character-preview/grid/<portraitId>/<style>_<ts>.jpg
image.storybud.com/narrations/narrations/<storyId>/narration_<storyId>_<page>_<ts>.mp3
image.storybud.com/alignments/alignments/<storyId>/alignment_<storyId>_<page>_<ts>.json
image.storybud.com/videos/stories/<storyId>/videos/video_<storyId>_<page>_<ts>.mp4
```
**No prompt fields exist in any public payload** (verified: zero prompt-like keys in the preview JSON).

### 1.5 AI vendor map — [vendor claim] (verbatim from their Privacy Policy, "Third-Party Technology Services & Data Handling")
- **Google Gemini** — "Writes stories and quizzes, creates illustrations and portraits, analyzes uploaded photos for
  character creation, and checks content for safety. Receives story details, text, photos, and generated pictures."
- **OpenAI** — "Transcribes voice input in the app and may write stories, create illustrations and portraits, or check
  text and photos for safety as a backup or alternative."
- **Microsoft Azure OpenAI Service** — "Transcribes website voice input and may create illustrations and portraits."
- **xAI** — "Our **primary narration service**. Receives story text and its generated audio to match words to playback.
  It also **creates animations** from story prompts and illustrations."
- **ElevenLabs** — "Provides narration for supported **fallback** voices and languages."
- **Replicate** — "Creates **animations** from illustrations and provides **fallback illustration and portrait generation**."
- Retention notes: xAI default 30-day retention (no ZDR); ElevenLabs training opt-out since 2026-09-30 (not zero-retention);
  OpenAI abuse monitoring up to 30 days; Gemini on paid terms (no training on prompts/responses).

### 1.6 Admin configuration surface (shipped in the client bundle — full AI knobs)
```
illustrationModel        = "gpt-image-1"            (only option: "GPT-Image-1")
illustrationQuality      = standard | hd | ultra
narrationModel           = elevenlabs | openai-tts | google-tts
narrationVoice           = <voice id>
defaultModel             = <text model>             (server-configured)
illustrationCompressionEnabled, useReferenceGrid, colorCorrectionEnabled,
yellowReductionAmount (0-100), qaValidationEnabled
/api/admin/settings/openai-image  → {referenceImageSize:512, portraitImageSize:512,
                                    generatedImageSize:"1024x1024", jpegQuality:80}
/api/admin/settings/gemini-safety → harm categories (harassment, dangerous content, sexually explicit, …)
/api/admin/settings/system-setting/ai.useGeminiOnlyForImageModeration
```
Tiered credits: `freeTierCredits / sproutTierCredits / bloomTierCredits / wonderTierCredits`.

### 1.7 The prompt architecture — [observed structure, server-side prompts not captured] (from the three admin log viewers)
**Scene Director** — `GET /api/admin/scene-director-logs?storyId&pageId&limit`:
```
Tab "Input Prompt"      → "Prompt Text Sent to Gemini:"  → log.prompt
Tab "Scene Director Output" → log.directive = {
    scene, background, mood,
    characters: [ { name, inScene, pose, expression } ] }
Then a third block: "OpenAI Image Prompt Components"
   → Scene: directive.scene | Background: directive.background | Mood: directive.mood
   → "Characters in Scene:" directive.characters.filter(c => c.inScene)
            with per-character Pose: and Expression:
```
⇒ **Two-stage prompt pipeline:** text model writes the page → Gemini "Scene Director" converts it into a structured
*directive* → the directive is assembled into an **OpenAI image prompt** → `gpt-image-1` renders the page
(with reference grid + 512px character references).

**AI Editing logs** — `GET /api/admin/ai-editing-logs` → "Editing Prompt Sent to AI:" (`editingPrompt`),
plus original/edited story diff.
**Video Director logs** — `GET /api/admin/video-director-logs` → `systemPrompt` + `userPrompt` (LLM-authored video prompt).
**Reference image logs** — `GET /api/admin/reference-image-logs/story/:id` → `gridPath` (reference grid image) and
`promptPath` (**the exact generation prompt persisted as a downloadable file**).

### 1.8 Client-side API contracts (extracted from 560 chunks)
```
POST /api/stories/generate-async
  body: {childName, childAge, characterGender, readingLevel, themes[], mood, length,
         illustrationStyle("pixar"), hasNarration, voiceId, educationalComponent("none"),
         hasQuiz, hasVideoGeneration, characterPreviewUrls{}, selectedStyleUrl,
         preparationRunIds[], printBookOrderUuid}
  → {jobId}; poll GET /api/stories/generate-async/status/:jobId
     → {status: completed|failed|permanently_failed, story}

POST /api/v2/questionnaire/{init,create-temp-user,verify-temp-email,signup-and-convert,upload-photo,start-generation}
GET  /api/v2/questionnaire/{style-previews/:sessionId, story-status/:jobId, preview/:jobId}
POST /api/v2/questionnaire/resolve-assets {urls[]} → previewAssetIds

POST /api/new-route/story-builder/ai-generate-portrait/generate
  {description, childName, characterName, childAge, characterAge, characterGender, imageHash}
  → {jobId, status, result:{gridPreviews{}, sourceImageUrl}}
POST /api/new-route/story-builder/grid-preview-job  → poll .../grid-preview-job/:jobId → previews per style
POST /api/character-preview        {portraitId, characterName, illustrationStyle} → {imageUrl}
POST /api/character-preview-e2e    FormData{decryptedPortrait, portraitId, characterName, characterAge,
                                          illustrationStyle, isAutoGenerated} → jobId
POST /api/story-illustration-with-characters {prompt, characterImages[], illustrationStyle} → {imageUrl}
POST /api/character-edit           FormData{image, mask, prompt}      ← masked inpainting edit
POST /api/image/generate           {prompt, filename} → {base64Image, model}  ← GPT-Image-1 test page
POST /api/new-route/regeneration/{page,page-narration,page-video,cover,story-narration,add-videos}
GET  /api/portraits/{id}/previews/by-style/:style ; /api/portraits/{id}/all-previews/by-style/:style
GET  /api/voices ; /api/regeneration-usage ; /api/new-route/regeneration/status/:jobId
```
Client-computed credit math: `length × 20` (short 100 / medium 300 / long 600) + narration `ceil(pages/5) × 20`;
character preview 20 credits; illustration-with-characters 40 credits; a finished 5-page story with narration+video
reported `creditCost: 240`.

### 1.9 Illustration style catalog (client-side, 12 styles)
`pixar`→"3D Storybook / 3D animation with detailed textures and cinematic lighting" · `studio-ghibli`→"Watercolor
Whimsy" · `classic-disney`→"Vintage Toon" · `dr-seuss`→"Whimsical Lines" · `anime`→"Expressive Anime" ·
`claymation` · `knitted`→"Cozy Yarn" · `marvel`→"Bold Comic" · `video-game` · `barbie`→"Glossy Fashion" ·
`chibi` · `paper-cutout`. `pokemon` is remapped to `anime`. These id/description pairs are what get injected into
image prompts.

### 1.10 Notable engineering behaviours
- **Reader fast-path**: inline script adds `reader-boot` to `<html>` on `/stories/:id` and `/library/:id` for desktop,
  to avoid a white flash; `ReaderLoader` removes it.
- **Debug console capture** on production domains only, gated by `localStorage["starredin:debugConsole"]` or `?debug=true`.
- **Tracking suppression for printed books**: `__storybudIsPrintedBookTrackingBlocked()` disables GA/Ads
  (`ga-disable-G-9ZMZ5ENC76`, `AW-17372898082`, `G-4TWS22C4E2`) on `/book*` routes.
- **Analytics gating**: GA only loads on `*.starredin.com` unless `analytics_debug=true`; consent defaults from
  `storybud_cookie_preferences`.
- ~190 client routes incl. `/admin/{ai-editing-logs,scene-director-logs,video-director-logs,blog-covers}`,
  `/teacher-dashboard/*`, `/school/:organizationId/*`, `/student/*`, `/print-book/*`, `/treasury/*`,
  `/share/flipbook/:shareUuid`, plus many `/test-*` and `/debug/*` pages shipped in production.

### 1.11 Risk observations
- `GET /api/public/stories/:id/preview` is **unauthenticated** and returns the child's name, age, `portraitId` and the
  full `faceAnalysis` (eye/skin/hair/expression), for a demo story (`userId: 2`) — with `coppa_mode_enabled:false`.
- Zero AI sub-processor names in the public API surface is *not* the case (their policy is good); the risk is the
  public biometric-ish metadata above.

---

## 2. Nookly — `nookly.com` / `my.nookly.com`

### 2.1 Identity and product
"Personalized AI Learning for Kids", ages 2–11, by **Nookly, Inc.**. Two modes: **Goal-based** (a goal → a finite
"Blueprint" of stories/songs/games/activities, paced twice a week) and **On-demand** (one experience now).
The generation engine is called **the Imagineer**. Public resource library = "the Neighborhood".
Pricing: Learner $15 / Adventurer $30 / Trailblazer $50 per month, annual discounts, one-time creations, gift
memberships. `llms.txt` (116 KB, updated 2026-09-26) states the AI parenting assistant is "currently hidden and
unavailable" and that only **English + Arabic** are supported (Spanish planned).

### 2.2 Two different front-ends
| | `nookly.com` (marketing) | `my.nookly.com` (app) |
|---|---|---|
| Framework | Vite + React + Tailwind (`tw-*` classes) | **Next.js (Pages Router)** (`/_next/data/…json`) |
| Origin | built with **Lovable** (`lovable.dev` preview-auth code in bundle, `lovable-user-app-events` SDK 0.3.0, `/~api/analytics`, `/__l5e/trackevents`) | hand-rolled |
| Backend | **Supabase** `woqylpvmudkulxpmljeu` (+ storage project `lnqwqaicrepgyqtyxcnc`) | `api.nookly.com` (`NEXT_PUBLIC_APRENDI_BACKEND_URL`) |
| Auth | Supabase Auth | **Auth0** (`NEXT_PUBLIC_AUTH0_*`) |

### 2.3 Marketing-site API surface
```
supabase.functions.invoke("request-child-plan",  {body:{goalText, language, placement:"home_hero", campaign:"create_stage"}}) → {redirectUrl}
supabase.functions.invoke("elevenlabs-scribe-token")      → voice STT token
supabase.functions.invoke("create-checkout-session",   {email,item_ids,user_id,referral_code})
supabase.functions.invoke("submit-pricing-lead")
supabase.functions.invoke("verify-subscriber-token",  {token})
GET https://woqylpvmudkulxpmljeu.supabase.co/rest/v1/community_library?select=id,title,slug,thumbnail_url,
      description,type,theme,tags,price_cents,is_always_free,age_range_min,age_range_max,featured
```
`community_library` is **anonymously readable from the browser**. Sample row:
```json
{"id":"a58e6eee-…","title":"Calm Down Steps","slug":"calm-down-steps",
 "thumbnail_url":"https://lnqwqaicrepgyqtyxcnc.supabase.co/storage/v1/object/public/community-library/thumbnails/…avif",
 "description":"Calming strategies like deep breathing, finding a cozy space, and asking for help.",
 "type":"Visual Schedule","theme":"Self-Awareness & Emotions","tags":["emotions","routines"],
 "price_cents":300,"is_always_free":false,"age_range_min":2,"age_range_max":10,"featured":false}
```
Other browser-readable tables: `blog_posts`, `user_roles`.

### 2.4 App API surface — 262 endpoints on `api.nookly.com`
Highlights (full list captured in the artifacts):
```
AI / creation
  POST /api/imagineer/blueprint/generate, /api/imagineer/blueprint, /api/imagineer/build/:id,
       /api/imagineer/slot-fill/:id, /api/imagineer/pack/:id/rebuild/:itemId
  POST /api/contents/identify {text,types}          ← intent→content-type classification
  POST /api/goals/resolve-intent
  POST /api/children/infer-extra-details {message}
  POST /api/image-segmentations/find-or-create        ← locate the child in a generated image
  POST /api/contents/upload-style-image
  POST /api/generated-stories, /brief, /poster/background, /poster/brief,
       /poster/with-protagonist, /printed-book-drafts
  GET  /api/generated-stories?status=generating_images   (…then status=complete)
  POST /api/transcription/elevenlabs/token          ← voice STT token (10 s timeout, no retry)
  GET  /api/voices
Safety / rights
  POST /api/rights-check, /api/reports
  GET|POST /api/users/parental-consent ; POST /api/signup-codes/redeem
  GET  /api/charter/pillars, /api/charter/clauses
Content families (each GET/POST/PATCH/DELETE)
  contents, generated-stories, bundles, folders, goals, lesson-plans, lullabies, picture-decks,
  emotion-decks, visual-decks, sound-decks, first-then-decks, word-problems-sheets,
  spelling-exercises-sheets, numerical-exercises-sheets, matching-exercises-sheets,
  fill-in-the-blanks-sheets, reflection-prompts-sheets, role-play-scenarios-sheets,
  word-search-sheets, tool-runs, tools, social-stories, content-templates (+/personalize, /inspired,
  /explore-deck, /quiz-recommendation, /recess-approved), imagineer, conversations, messages, queries,
  notifications, organizations, children, store-books, book-credits, leaderboards, sessions, referral-partners
Commerce
  api/payment/* (Stripe: checkout, setup-intent, portal-session, cancel + retention flows, promo codes,
                 native RevenueCat story-credit), api/billing/*, api/auth/marketplace-token
```

### 2.5 AI vendors actually visible in the shipped app bundle
- **ElevenLabs Agents SDK** (`@elevenlabs/client`, `react_sdk` v1.18.0) with **Scribe** STT over **LiveKit**
  (`wss://livekit.rtc.elevenlabs.io`), convai token endpoint
  `https://api.elevenlabs.io/v1/convai/conversation/token?agent_id=…&source=…&v=…`, PCM 48 kHz, ASR keywords,
  TTS overrides `{voice_id, speed, stability, similarity_boost}`. Client error states:
  `permission-denied | unsupported | token-failed | session-limit | connection-failed` (HTTP 429 → "session-limit").
- **LLM playground endpoints** (proving a multi-model stack): `POST playground/openai`, `playground/llama`,
  `playground/nookly/llama`, `playground/nookly/phi3`, `GET playground/task/{id}`.
- **Perplexity** for grounded research: `researchQuery.researchResults.perplexity` + `citations[]`
  (source URL + icon thumbnail).
- **Image CDN transform**: `?w={width}&q={quality|75}&f=webp` on `NEXT_PUBLIC_IMAGE_CDN_HOST`.
- Client-visible AI content types: "Create a personalized learning plan for a Goal, or make one story, song, podcast,
  game, or visual resource on demand…", "…personalized animated song…", "…personalized visual schedule…",
  "…personalized story…".

### 2.6 Tracking, analytics and privacy
- **Amplitude with session replay enabled**: `sr_sampling_config.sample_rate: 0.5`, `capture_enabled: true`,
  `defaultMaskLevel: "light"`, and **`maskSelector: []` / `blockSelector: []` / `unmaskSelector: []`** → replay is not
  masking form input by default on a site where parents type about their children.
- Microsoft Clarity, GTM `G-2TRTT6HQPJ`, Google Ads `AW-11388354338` (+ view-through), Meta Pixel, Pinterest tag,
  Mixpanel proxy env vars, Intercom (`widget/qhs2z9if`), GA4 server-side via `meta-server.nookly.com`,
  Rewardful (referral), Shopify discount codes, RevenueCat (mobile IAP), Cloudflare RUM, Lovable analytics.
- Landing TTFB measured **6009 ms ("poor")** by Lovable's own `lovable.web_vital` beacon.
- **Privacy Policy (25 KB) names only Google Analytics/Mixpanel, hosting & security providers, MongoDB Atlas Security
  Monitoring and AWS GuardDuty — and no AI vendor at all** (no OpenAI/Anthropic/ElevenLabs/Perplexity), despite the
  bundle showing all four. It also cites Mixpanel while the site actually runs Amplitude + Clarity.

---

## 3. Scrively — `www.scrively.com` / `app.scrively.com`

### 3.1 Identity and product
**Bryxen, Inc.** — *"Make a Free Personalized Children's Book in 5 Minutes"*. One sentence + one photo → AI writes,
illustrates and lays out a book; optional printed hardcover; one-click **coloring-book** conversion; AI voice
narration + music + SFX; **parent-recorded narration in their own voice**; shareable link for grandparents.
Public counter `app.scrively.com/api/public/book-count` → **11,348 books created**; ~4 minutes to a book.
Free funnel: describe → preview cover + several pages → *then* register ("No sign up required" to preview).

### 3.2 Stack
- **[observed]** Marketing: static `www.scrively.com/assets/js/*.js?v=YYYYMMDD-<tag>` (5 files, 35 KB).
  App: **Next.js 15 with Turbopack** on **Vercel** (`dpl_9mXmdR868mhzkjqYh5c4xtkhFLYQ`),
  **Supabase** `ruqxkdchwmccfdugnjmm`, **PostHog** (`us.i.posthog.com`), GTM `GTM-TV45RLNW`,
  GA4 `G-9XQ4N7QCKY` + `G-1D8HC643Z9`, Google Ads `AW-1071897635` + `AW-17178611609`, Meta Pixel `519345574551238`,
  Cloudflare RUM, **Voomly** video embeds (`embed.voomly.com`, `api.voomly.com/embed-videos/*`,
  `waf.voomly.com` → 403 "Bot detected"), **Chatwoot** support widget.
- **[observed]** AI endpoints are wrapped in a **bot-challenge layer** (DataDome-style):
  `getChallenge()` → headers `x-is-human`, `x-path`, `x-method`, `advancedOptions.checkLevel: "deepAnalysis"`,
  applied to `/api/ai/cover-badge`, `/api/studio/narrate`, `/api/studio/voice-preview`.
  Generation is additionally **auth-gated** (both `app.scrively.com/` and `?free=1` redirect to `/sign-in`).

### 3.3 API surface
```
POST /api/ai/character   {action:"guess-gender", name}                    → {gender}
POST /api/ai/character   {action:"guess-gender-from-image", image, name}  → {gender}
POST /api/ai/cover-badge            POST /api/studio/narrate
POST /api/studio/voice-preview      GET  /api/addons
GET  /api/broadcast                 GET  /api/tracking/{codes,email,purchase}
GET  /api/me/heartbeat              GET  /api/me/wizard-heartbeat
POST /api/ac/signup-sync            GET  /api/auth/password-reset
GET  /api/registration-gate/oauth-provider-status
GET  /api/public/book-count         GET  https://www.scrively.com/auth-nav-state.php
```
**[observed]** `/api/ai/character` runs a **vision model on the child's photo** to infer gender; a client-side
lexicon (girl/woman/boy/man/animal name sets) is the fast path, the API is the fallback. **No prompt strings in the
client** — all prompts are server-side.

### 3.4 The character-consistency mechanism (their own marketing shows it)
- Landing section "Your child becomes the hero" shows a **style matrix**: *Original Lena* (photo) → *Lena in 3D
  animated / Bold Comic / Watercolor / Pixel Art / Soft Felt*, plus a separate **"Lena's avatar"** asset used in
  the finished books.
  ⇒ **per-style avatar generated once**, reused across the book.
- **Two free regenerations per image** (not per book), and the redos are **edits**:
  *"Make the coat blue"* → *"Let the dragon wave"* → *"preserving the watercolor style"*.
  Their copy: *"a 25-page book isn't 25 chances to get it right. It's 75. Your credits are for making books — not for
  do-overs."*
- Failure-mode copy (verbatim): *"what if the AI gets my kid's face wrong? … Sometimes it does. The hair comes out a
  shade too dark. The smile lands a little strange."* → answered with free redos.
- 10 sample children with real photos: Lena, Tristan, Oliver, Mira, Lila, Luna, Benji, …

### 3.5 Product system (from the shipped bundle)
- **111 art styles in 9 categories**:
  - *3D & Animated (10)*: Modern Animated Film (3D) [default], Cinematic Prehistoric 3D, Snowy Fantasy 3D, Glossy 3D
    Toy Figures, Clay Sculpted Stop-Motion, Low-Poly 3D Cartoon, Bubble Pop Mascot, Soft 3D Pastel Clay, Cel Shading,
    Hyperreal CGI, Retro 80s Cartoon
  - *Paint & Watercolor (13)*, *Illustrated & Pastel (14)*, *Comic & Cartoon (23)*, *Manga & Anime (4)*,
    *Handcrafted & Traditional (14)*, *Ink & Line Art (15)*, *Digital & Abstract (11)*, *Decorative & Historical (7)*
  - **Trademark-aware aliasing**: `{"Pixar 3D": "Modern Animated Film (3D)"}` — renamed for legal safety, alias kept
    for search/SEO.
- **Reading levels**: Ages 2-3 (simple words) · 4-5 (short sentences) · 6-7 (early reader) · 8-10 (longer stories).
- **Story formats (9)**: Silly Gross-Out Humor, Dialogue Driven, Gentle Mystery, Magical Fantasy, Educational Explorer,
  Adventure Quest, Bedtime Calm, Heartfelt Social-Emotional, Rhyming Read-Aloud.
- **Character presets**: Juniper Thistlewick (girl, wild curly hair, fireflies, Whispering Woods),
  Bramblewood (bear cub, patched scarf, lost buttons).
- **User book-preference schema**: `default_reading_level, default_language, default_pages,
  default_sentences_per_page, default_characters, default_art_style, default_book_layout, default_book_dimensions,
  default_book_font, default_book_highlight_font, default_use_art_style_fonts`.
- **Plan page limits**: `free 10 · plus 30 · plus_annual 30 · pro 50 · pro_annual 50 · one-time 30`.

### 3.6 Legal + privacy
- **`/commercial-rights.php`** contains a clause prohibiting *"a personalized book creation service where a customer
  sends you specific inputs, such as their child's name or photo, and you create a customized Scrively-generated book
  just for them."* — a deliberate anti-reseller/anti-white-label moat. **[observed]**
- **Privacy policy (5.3 KB)** says only: *"Generated Content: Content you create using our Software, including text
  and images generated through artificial intelligence."* — **no AI sub-processors named**, no visible COPPA section
  in the text captured, despite uploading children's photos. **[observed]**

---

## 4. Own codebase — `AliSakr9997/infinite-heros-` (Infinite Heroes)

> Not a competitor — **our own repo**, torn down with the same rigour so the findings feed straight back into the
> Hekayti pipeline. Cloned: `git clone --depth 1 https://github.com/AliSakr9997/infinite-heros-.git`
> → `C:\Users\alisa\AppData\Local\Temp\opencode\infinite-heros`

### 4.1 What it is

> **No evidence caveat here:** this is our own source tree, so prompts, payloads and call sites are read
> directly rather than inferred from public bytes.
- **Repo:** `https://github.com/AliSakr9997/infinite-heros-` (note the trailing dash in the repo name).
  Single commit `e34462c "feat: add comic book generation UI and API gating"`, branch `main`, no other branches,
  **no deployment config** (no Pages/Vercel/Netlify manifest) → nothing live to capture, so this is a **source-level
  teardown**.
- **Origin:** a fork/remix of Google's **"Gemini Dynamic Comics"** demo (the app footer still says
  *"Build with Gemini"* and *"Created by @ammaar"*). `metadata.json`:
  `{"name":"Remix: Infinite Heroes","description":"Localized and personalized comic book generator"}`.
- **Product:** an interactive, branching **comic book** generator. You upload a **HERO** photo (and optionally a
  **CO-STAR** photo), pick a genre/tone/language, and it writes + illustrates a 10-page issue with a decision page
  (page 3), a cover, a back cover, a CSS 3D page-flip reader, and a PDF export.
- **Our additions over the original demo:** 15-language localization, photo upload for the cast, genre/tone/premise
  selection, NOVEL MODE, the decision-page branch, and PDF export.

### 4.2 Stack
| Layer | Detail |
|---|---|
| Build | Vite 6 + `@vitejs/plugin-react` 5 + TypeScript 5.8; dev server `0.0.0.0:3000` |
| UI | React 19.2, Tailwind **loaded at runtime from `cdn.tailwindcss.com`**, fonts Bangers + Comic Neue (Google Fonts) |
| Deps | Delivered via **importmap → esm.sh** (`react@^19.2.0`, `@google/genai@^1.27.0`, `jspdf@^3.0.3`, `recharts@^3.3.0`) — i.e. the browser fetches them at runtime, bypassing `package.json`/lockfile |
| Backend | **None.** All model calls are made from the browser. |
| Model | **One model for both jobs:** `const MODEL_V3 = "gemini-3-pro-image-preview"` → `MODEL_TEXT_NAME = MODEL_IMAGE_GEN_NAME = MODEL_V3` |
| PDF | `jsPDF` 3.0.3, page `480 × 720 pt` (2:3), saved as `Infinite-Heroes-Issue.pdf` |
| Dead weight | `recharts` is a dependency but no chart code exists; `index.css` is 0 bytes |

### 4.3 The consistency mechanism — the right pattern, applied to only half the cast
**[observed]** `App.tsx:207-223` `generatePersona()` is exactly the production pattern this teardown recommends:
```
STYLE: Masterpiece {genre} comic book art character sheet, detailed ink, neutral background.
FULL BODY. Character: {desc}          → aspectRatio 1:1  → canonical CHARACTER SHEET
```
**[observed]** `App.tsx:225-267` `generateImage()` sends **one labelled reference per character**:
```
contents = [ {text:"REFERENCE 1 [HERO]:"}, {inlineData: hero.base64},
             {text:"REFERENCE 2 [CO-STAR]:"}, {inlineData: friend.base64},
             {text: prompt} ]
prompt += "INSTRUCTIONS: Maintain strict character likeness.
            If scene mentions 'HERO', you MUST use REFERENCE 1.
            If scene mentions 'CO-STAR' or 'SIDEKICK', you MUST use REFERENCE 2."
```
→ multi-image, explicitly-labelled reference binding works on `gemini-3-pro-image-preview`. **This validates the
mechanism end-to-end, from a lab demo, independently of StarredIn/Scrively.**

**[observed] P0 — the hero never gets a character sheet.** `handleHeroUpload()` (`App.tsx:404-409`) only does
`setHero({base64, desc:"The Main Hero"})` and **never calls `generatePersona()`**. `generatePersona` is invoked in
exactly one place — the *auto-generated sidekick* fallback (`App.tsx:287-292`). Therefore:

| Character | Reference actually sent to the image model | Result |
|---|---|---|
| HERO (uploaded photo) | the **raw photo**, re-sent on every one of the 11 pages | model re-interprets photo→comic each page → **identity drift** (same root cause as Hekayti's current DashScope pipeline) |
| CO-STAR (uploaded photo) | raw photo, every page | same drift |
| CO-STAR (auto-generated) | **canonical character sheet** (1:1) | consistent |

**Fix (one function):** in `handleHeroUpload` / `handleFriendUpload`, after base64-encoding, call
`generatePersona(desc)` once and store the returned sheet as the reference; keep the original photo only for that
single call. Cost: +2 image calls per issue; benefit: the entire drift class disappears.

### 4.4 The story engine — better than it needs to be, and the best part of the repo
**[observed]** `generateBeat()` (`App.tsx:77-205`) is a structured "beat" generator using
`responseMimeType: 'application/json'` on the same image model, returning a strict schema:
```
{ caption, dialogue, scene,                      // scene ALWAYS IN ENGLISH for the artist model
  focus_char: "hero" | "friend" | "other",
  choices: [] }                                   // only on decision pages
```
Prompt composition (all verbatim structure, `App.tsx:150-179`):
1. **Language lock** — "ALL OUTPUT TEXT (Captions, Dialogue, Choices) MUST BE IN {LANG}".
2. **Core driver** — `GENRE: {genre}. TONE: {tone}.` or, for *Custom*, `STORY PREMISE: {premise}` with
   "(Follow this premise strictly over standard genre tropes)".
3. **Negative constraints (guardrails)** — e.g. "UNLESS GENRE IS *Dark Sci-Fi* OR *Superhero Action* OR *Custom*: DO
   NOT use technical jargon like 'Quantum', 'Timeline', 'Portal', 'Multiverse', or 'Singularity'"; for Teen Drama /
   Comedy "the stakes must be SOCIAL, EMOTIONAL, or PERSONAL … Do NOT make it life-or-death"; "Avoid 'The artifact'
   or 'The device' unless established earlier".
4. **Narrative arc per page** — p1 inciting incident · p2-4 rising action · p5-8 complication · else climax.
5. **Final page** — "KARMIC CLIFFHANGER REQUIRED. You MUST explicitly reference the User's choice from PAGE 3 …
   Text must end with 'TO BE CONTINUED...'" (localized equivalent).
6. **Decision page** — "End with a PSYCHOLOGICAL choice about VALUES, RELATIONSHIPS, or RISK … The options must NOT
   be simple physical actions like 'Go Left'."
7. **Rich/NOVEL MODE** — caption ≤35 words, dialogue ≤30 (vs ≤15/≤12 in plain mode).
8. **Continuity** — the full history of previous panels is injected as
   `[Page N] [Focus: x] (Caption: "…") (Dialogue: "…") (Scene: …) -> USER CHOICE: "…"`; plus
   "NO REPETITION" and "If page N-1 was an action shot, make this one a reaction or wide shot."
9. **Co-star injection** — when a friend exists: "ACTIVE and PRESENT (User Provided)", and with
   `Math.random() > 0.4` a "MANDATORY: FOCUS ON THE CO-STAR FOR THIS PANEL." (stochastic balance).
10. **Output contract** — "OUTPUT STRICT JSON ONLY (No markdown formatting)" with per-field word limits.

**[observed]** Branching: `handleChoice()` stores `resolvedChoice` and the next pages see it as
`-> USER CHOICE: "…"`; the final page is contractually required to pay it off.
**[observed]** Paging: `MAX_STORY_PAGES 10` + `BACK_COVER_PAGE 11` = 11 pages; `INITIAL_PAGES 2`,
`GATE_PAGE 2` (the cover's "READ ISSUE #1" button unlocks once page 2 exists), `BATCH_SIZE 6`,
`DECISION_PAGES [3]`.
**[observed]** Localisation: 15 languages (en-US, **ar-EG**, de-DE, es-MX, fr-FR, hi-IN, id-ID, it-IT, ja-JP, ko-KR,
pt-BR, ru-RU, ua-UA, vi-VN, zh-CN) — the comic *text* is localized, the *visual scene description* is always English.

### 4.5 Findings, ranked
| # | Sev | Finding | Evidence |
|---|---|---|---|
| 1 | **P0** | **Gemini API key is baked into the client bundle.** `vite.config.ts` does `define: {'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY)}` → the key is readable in the built JS by anyone. Also `.gitignore` does **not** ignore `.env` / `.env.local`. | `vite.config.ts:13-16`, `.gitignore` |
| 2 | **P0** | **Hero/CO-STAR identity drift** — raw photo re-sent per page; the character-sheet step is only used for the auto sidekick. | `App.tsx:287-292`, `404-409` |
| 3 | **P1** | **Captions/dialogue are baked into the pixels** (`INCLUDE CAPTION BOX: "…"`, `INCLUDE SPEECH BUBBLE: "…"`). Changing language or fixing a typo ⇒ re-render the panel; Arabic/Chinese/Hindi text-in-image is the most failure-prone path. The app already has a DOM overlay layer (decision buttons) → move text out of the image. | `App.tsx:248-249` |
| 4 | **P1** | **No identity QA, no redo.** No similarity score, no "regenerate this panel". Scrively gives 2 free redos/image; StarredIn ships `qaValidationEnabled` + `validatorRetryCount`. Gemini accepts image+image input, so an edit-based redo (previous panel as base) is available. | — |
| 5 | **P1** | **Silent failure.** `generateBeat` catch → `"Generic scene for page N."`; `generateImage` catch → `''`. A user gets a broken issue with no error state and no retry. | `App.tsx:195-204`, `263-266` |
| 6 | **P2** | **Cost/latency.** ~23 **sequential** model calls per issue (11 × [text+image] + persona) on a *preview* image SKU; no concurrency, no caching, no persistence (all state is in React refs → a refresh loses the issue). | `App.tsx:299-333` |
| 7 | **P2** | **Nondeterminism** from `Math.random()` (co-star focus, LoadingFX) with no seed ⇒ same input, different issue; untestable. | `App.tsx:100`, `LoadingFX.tsx:15-19` |
| 8 | **P2** | **Preview-model dependency** (`gemini-3-pro-image-preview`): no SLA, behaviour drift, billing tiers. Model id is hardcoded in two constants. | `App.tsx:17-19` |
| 9 | **P2** | **Runtime CDN supply chain**: React/SDK/jsPDF from esm.sh, Tailwind from cdn.tailwindcss.com — no SRI, no lockfile enforcement, prod build behaviour differs from the importmap dev path; `recharts` unused. | `index.html:246-256` |
| 10 | **P2** | **Repo hygiene**: no README, no LICENSE file (only SPDX headers), no `.env.example`, no CI, no deploy config, `index.css` empty. | root |
| 11 | **P3** | **Kids' product hygiene**: the child's photo goes browser→Google with only "The Prohibited Use Policy applies" as disclosure; no consent gate, no retention statement, no policy link, no deletion path. StarredIn/Nookly publish sub-processor lists; Scrively's is thin; we can be better. | `Setup.tsx:153-157` |
| 12 | **P3** | **No RTL/i18n for the app chrome**: only generated comic text is localized; the UI is English-only and LTR-only (no `dir="rtl"` for `ar-EG`); the PDF cover title is not localized. | `index.html:2`, `App.tsx:241` |

### 4.6 What this repo already proves for the Hekayti question
1. **Labelled multi-reference works.** `REFERENCE 1 [HERO]` / `REFERENCE 2 [CO-STAR]` + "you MUST use REFERENCE 1"
   is enough to bind a character to a reference on a modern image model — the same grammar StarredIn uses
   (`directive.characters[]` + per-character references). The grammar is portable to DashScope `qwen-image-2.0-pro`.
2. **The character-sheet prompt is trivially portable.** `Masterpiece {style} character sheet, detailed ink, neutral
   background. FULL BODY. Character: {desc}` at 1:1 → a canonical sheet we can feed to *any* model
   (qwen-image-2.0-pro, InstantID, gpt-image-1) and reuse across all 11 pages.
3. **"The LLM never writes the image prompt" can be done client-side too.** Here the beat model returns a
   *structured beat* (JSON schema) and a deterministic function assembles the image prompt. That is precisely
   StarredIn's Scene-Director discipline, one layer flatter.
4. **Per-page continuity is cheap and worth it.** The history injection
   (`[Page N] [Focus: …] (Caption: …) (Dialogue: …) (Scene: …)`) is a template Hekayti can reuse verbatim for
   Arabic scene continuity (and to stop the child from "changing the subject" between pages).

### 4.7 Repo inventory
| File | Size | Purpose |
|---|---|---|
| `App.tsx` | 21 KB | **the whole engine**: API-key handling, `generateBeat`, `generatePersona`, `generateImage`, batching, branching, PDF export |
| `Setup.tsx` | 13 KB | cast upload, genre/language/premise pickers, NOVEL MODE, "START ADVENTURE!", POW! transition, remix-idea footer |
| `index.html` | 9.3 KB | importmap (esm.sh), Tailwind CDN, the entire 3D book CSS (gloss, spine, page-flip, mobile rules) |
| `types.ts` | 2.2 KB | `MAX_STORY_PAGES 10`, `BACK_COVER_PAGE 11`, `INITIAL_PAGES 2`, `GATE_PAGE 2`, `BATCH_SIZE 6`, `DECISION_PAGES [3]`, 9 genres, 6 tones, 15 languages, `ComicFace`/`Beat`/`Persona` |
| `Panel.tsx` | 3.6 KB | one page: image, decision buttons, cover "PRINTING n/2 → READ ISSUE #1", back-cover download/reset |
| `Book.tsx` | 2.3 KB | sheet/spread mapping, flip state, 3D transform |
| `ApiKeyDialog.tsx` | 2.5 KB | paywall / AI-Studio key-picker dialog ("Gemini 3 Pro Image Preview … requires a billing-enabled project") |
| `useApiKey.ts` | 1.5 KB | `window.aistudio.hasSelectedApiKey()` / `openSelectKey()` integration |
| `LoadingFX.tsx` | 2.6 KB | "POW!/BAM!/ZAP!" particle loader, "INKING PAGE..." |
| `vite.config.ts` | 0.6 KB | dev server + **the API-key `define` (P0)** |
| `package.json` | 0.5 KB | react 19.2, @google/genai 1.27, jspdf 3.0.3, recharts 3.3 (unused), vite 6, ts 5.8 |
| `metadata.json` | 0.2 KB | "Remix: Infinite Heroes" (AI Studio metadata) |

### 4.8 Recommended next moves for this repo
1. **Move the key server-side** (Cloudflare Worker / Vercel function) and add `.env*` to `.gitignore`; ship a
   `.env.example`.
2. **Route every cast member through `generatePersona()`** and use the sheet as the page reference (fixes P0 #2).
3. **Add a per-panel "regenerate"** that re-prompts with the previous approved panel as the base image (edit-based),
   plus a cheap identity sanity check before accepting a panel.
4. **Move captions/dialogue out of the pixels** into the DOM overlay; ask the model for text-free art.
5. **Persist the issue server-side** (pages, personas, decisions) so a refresh doesn't destroy work, and parallelise the
   per-page calls with a small concurrency limit.
6. **Add README + LICENSE + CI + a deploy config**, and a parent-facing consent/retention statement for child photos.

---

## 5. Eleven more platforms (Batch 2 + Bedtimestory AI)
## 5.1. `hawadeet.app` — حواديت (Arabic audio-story platform)

**[observed] Product:** "حواديت – عالم الحكايات السحرية للأطفال قبل النوم" ("thousands of entertaining & useful
stories for your kids before bed"). The landing page is a **login wall** implemented as name + WhatsApp number
("سنبعتلك كود التفعيل" — an activation code is sent to your WhatsApp) + a "most listened" carousel of Arabic
religious/folk tales ("روكي وعضمة الصلصال", "أشرعة الصمود: سر سفينة سيدنا نوح", "يونس والأميرة سلمى") and a
"🎧 +100 حدوتة صوتية" badge. The A11Y tree is tiny (906 chars) — the whole page is a login form.

**[observed] Stack:** Vite/React with **Lovable** fingerprints — `__l5e/trackevents` (Lovable event endpoint),
`/~api/analytics`, `version.json` (Lovable deploy versioning), console `[Hawadeet] BUILD_VERSION=8d2dde20-0-…`.
**Capacitor** chunk present (`/assets/capacitor-CgGNtl3a.js`) → they ship a **native app** wrapper as well as PWA
(`/manifest.webmanifest`). Backend: **Supabase** project `xwkfjntksmwaeufswxaa`; browser-readable tables
`pricing_settings`, `free_story_overlay_settings` (both `select=*&order=created_at.asc&limit=1` — i.e. the pricing
and free-tier overlays are **configuration tables read from the client**). Supabase functions invoked from the
client: `get-pixel-id`, `track-event`; broadcast channel `/api/broadcast`.

**[observed] Tracking:** TikTok Pixel `DALC093C77UES97565PG`, Meta Pixel `1007670161267764`, Microsoft Clarity
`xhnku87c02`, Google **SODAR**/Conversions API gateway (`gw.conversionsapigateway.com`), Tinybird
(`api.tinybird.co` — event analytics), plus `ads.tiktok.com/marketing_api/docs?id=1739585700402178` (a TikTok
*Marketing API* event id → they run **TikTok Ads API** conversions, not just the pixel).

**[observed] Disclosure:** `/llms.txt` → **"Not found"**; `/privacy-policy` → 404 (client-routed).

**[inferred]** Generation is server-side (no image/voice API in the client); the "audio story" product implies TTS
(or human narration) plus an illustration pipeline, both invisible from the marketing page.

**Hekayti takeaway:** they own the **pre-bed audio** habit in Arabic (WhatsApp-native activation loop, 100+ audio
catalogue, zero-friction entry). If Hekayti wants Arabic share-of-voice, "audio + your child's face" is a
differentiation axis they have *not* combined with personalization — yet.

---

## 5.2. `storiakids.com` — StoriaKids (English, multi-language, own API)

**[observed] Product:** "Create personalized bedtime stories, fairy tales and moral stories for children.
Customized by **language, gender, age, and learning focus**." Nav: Home / Stories / Offers / Pricing / Cart /
Log In / Sign Up, with an **"ع"** language toggle. 135 requests, 0 page errors, YouTube embeds, Zendesk messenger.

**[observed] Stack:** React SPA on Vite (`/assets/react-vendor`, `radix-vendor`, `i18n-vendor`, `util-vendor` — Radix
UI + i18next), **own API** at `api.storiakids.com`:
```
GET /api/settings/public
GET /api/countries?isAll=true
GET /api/stories/website?language=en&country_id=…&sort=new_to_old
GET /api/offers/website?country_id=…
GET /api/banners/website-banners
GET /api/website?locale=en
GET /api/stats/          GET /api/stats/qoe        ← quality-of-experience telemetry
```
plus i18n bundles served from the site itself (`/locales/en.json`), static assets on
`storia-prod-assets.s3.us-east-1.amazonaws.com`, **country-based pricing/offer targeting** (one offer set per
`country_id`).

**[observed] Tracking:** GA4 `G-P494LKYT0P` + GTM, Meta Pixel `653496143798336`, Sentry, **Cloudflare
Conversions API gateway**, `jnn-pa.googleapis.com` (Google Ads / "Ads" JS service).

**[observed] False-positive warning:** `openai`, `anthropic`, `langchain` strings appear **only inside
`static.zdassets.com` (the Zendesk web-widget bundle)** — they are *not* evidence that StoriaKids uses those
vendors. Their own bundles contain no AI-provider reference.

**[observed] Disclosure:** `/llms.txt` and `/privacy-policy` are not served (SPA fallback).

**Hekayti takeaway:** the cleanest **per-country pricing/offer matrix** of the batch (`country_id` on every public
endpoint) and a `qoe` (quality-of-experience) telemetry endpoint — worth copying for latency/quality monitoring of
generated books.

---

## 5.3. `syorastories.com` — Syora Stories (Arabic, Easy Orders platform)

**[observed] Product:** Arabic storefront selling **"قصةصورة طفلك"** (a story with your child's photo),
**"نوت بوك بصورة طفلك"** (notebook with your child's photo) and **"كتب تلوين بصورة طفلك"** (coloring books with
your child's photo), plus a premium product page (`/collections/hyturr0LLLLLLLL` — machine-generated slug) and
policy pages (refund/shipping). Socials: WhatsApp `wa.me/201032866780`, Instagram `syora.stories`, TikTok.

**[observed] Stack:** **Easy Orders** (Egyptian storefront SaaS) — `cdn.easy-orders.net` Next.js storefront,
`apps.easy-orders.net/api/v1/...`, `api.easy-orders.net/api/v1/...` (newsletter, ui-blocks, google-merchant-data,
cart-items/guest, pages/home, plugins/store-plugins/is-active/*, themes/settings/navigation, products?fields=…,
categories). Notable plugin probes: **`remove-watermark`** (they watermark free generations),
**`multi-lang`** (AR/EN), `spam-blocker`, `sales-popup`, `downsell`, `social-links`. Anti-bot: `captcha_bg.wasm`
(a WASM CAPTCHA) and `statics.easy-orders.net/api/v1/events/visit`.

**[observed] Tracking:** TikTok Pixel + `analytics.tiktok.com/api/v2/pixel/act`, Meta Pixel, and console warnings
"Multiple pixels with conflicting versions were detected".

**[observed] Disclosure:** no `llms.txt`; privacy page names only **Google** among third parties (no AI vendor).

**Hekayti takeaway:** the **watermark-on-free-tier** mechanic is a cheap, effective conversion lever for a
photo-based product (Scrively/StarredIn instead gate *edits* behind paid plans). Also: a pluggable storefront
means **the AI product is decoupled from the storefront** — relevant if Hekayti wants to sell print via an existing
Egyptian print-on-demand partner without building e-commerce.

---

## 5.4. `kitabme.com` — Kitabme (Shopify + Autopictura)

**[observed] Product:** "Children's Books | Books for Kids | Personalized Gifts for Kids — Kitabme.com";
"Put Your Child At The Center Of Their Own Story … Perfect for ages 2–9 · **Available in English & Arabic** ·
Hardcover & softcover versions"; rating block "4.8/5 based on 1,000+ happy readers"; "Money Back Guarantee" (30 days
or damaged); Arabic locale at `/ar`. Free shipping over 2 books.

**[observed] Stack:** **Shopify Online Store 2.0** (theme `t/7`, storefront web components, `login_with_shop` /
`shop.app` accelerated checkout, `/api/2026-07/graphql.json` Storefront API, web-pixels, `monorail` telemetry,
OTLP metrics/logs to `otlp-http-production.shopifysvc.com`). Third-party apps detected:
- **Autopictura** — console: `🎨 Autopictura data provided to SDK: {aiEnabled: null, lastUpdated: null, productId: null, variantIds: Array(0), productTitle: null}` → the **AI-image app is a Shopify app**, and on the homepage its config was `null` (not enabled for that product).
- **Hextom** TMS (`tms.hextom.com`, `usb.hextom.com`) — translation/theme management.
- **Elevar** (`hits.getelevar.com`), **Bugsnag** (`BSS Banner Init`), `cdn.hextom.com`.

**[observed] Tracking:** GA4 `G-VQFFQFVMPN`, Google Ads `360754875`, TikTok Pixel + **TikTok Shop Pixel**
(`/api/v2/shopify_pixel`), Meta Pixel `1357326881320105`, Google Merchant Center (`mc/collect`, `MC-ZGE7DBT8PR`).

**[observed] Disclosure:** `/llms.txt` exists but is the **Shopify "Agent Instructions"** template (Shop skill +
UCP/WebMCP) — no AI vendor disclosure. `/pages/privacy-policy` returns a 493-char stub.

**Hekayti takeaway:** the **AI app is pluggable into Shopify** (Autopictura) — meaning a small seller can ship
"child-photo books" with zero custom stack. That is the *cheapest possible competitor*: Kitabme itself is a
storefront, not a model owner. Differentiate on the **model quality + Arabic typography + delivery**, not the
storefront.

---

## 5.5. `stories.bysnaps.ai` — Snaps Stories ("AI Stories by Egyptian AI Models")

**[observed] Product:** meta description: **"AI Stories By Egyptian AI Models, First Creative AI in Egypt and MENA,
Powered by Snaps AI."** Arabic + English store, collections: Stories / Coloring Books / About Us, promo band
"✨ BUY 2 STORIES, GET 1 FREE ✨", WhatsApp `wa.me/201039402869`, socials `storiesbysnapsai`.

**[observed] Stack:** **Shopify** storefront (theme `t/31`) + **first-party API `api.bysnaps.ai`** and
`preview.bysnaps.ai` (image/CDN previews), plus `preview.bysnaps.ai` and `order.buywithprime.amazon` (Amazon
Pay), `app.manychat.com` (ManyChat), `mccdn.me` (Mailchimp/Connected Cloud), Clarity, Meta Pixel
`1428162332746883`, TikTok Shop Pixel.

**[observed] Key artefact:** console warning **`MyGenerationsController: Required DOM elements not found, skipping
initialization`** → a Shopify app block named **MyGenerations** (the AI-generation UI) is installed on the theme but
did not initialise on the homepage — the generation UI is app-block driven.

**[observed] Disclosure:** `/llms.txt` = Shopify Agent Instructions (Shop skill/UCP). `/pages/privacy-policy` =
1,037-char stub, **no AI vendor names**.

**Hekayti takeaway:** **Snaps AI is a model house, not just a store** — "AI Stories by Egyptian AI models" implies
a vertically-stacked Arabic-first model layer (image + text + video). If they publish an Arabic-specialised image
model, that is the single most important competitive variable for Hekayti's roadmap (and a potential **partner**,
not only a rival). Worth a direct conversation/benchmark before committing to a model.

---

## 5.6. `hero-kid.com` — HeroKid (Arabic, Laravel, identity-first)

**[observed] Product:** "قصص أطفال مخصصة تجعل طفلك بطل القصة بوجهه الحقيقي | HeroKid" — *"customized stories that make
your child the hero of the story **with his real face**"*. Nav: القصص / مكتبة القصص / منتجات مخصصة / أنشطة وتعلّم /
باقات / **هوية طفلك** (your child's identity) / دليل / سلة / تتبع طلبك / دخول.

**[observed] The identity flow is the most interesting thing in Batch 2.** `/child-identity`:
> "اصنع هوية طفلك … أدخل البيانات الأساسية واختر **صورتين أو ٣ صور**. يبدأ إنشاء الهوية تلقائيًا بعد الإرسال …
> نحتاج صورتين واضحتين على الأقل، ويمكنك إضافة صورة ثالثة اختيارية" — plus an explicit consent checkbox:
> "أوافق على معالجة الصور وحفظها بأمان لتنفيذ الهوية والقصة وفق سياسة الخصوصية".

**[observed] Stack:** **Laravel** backend + **Vite/React** SPA (`/build/assets/app-BVPuJoMV.js`, 137 KB) with a
**batched, session-token-based photo pipeline** visible in the bundle:
`photo-uploads` · `upload_session_token` · `upload_batch_token` · `uploadUrl` · `uploadId` · `upload_ids` ·
`photo_upload_ids` · `child-photo` · `photo-input` · `photo-queue` · `photo-picker` · `upload-config` ·
`photo-requirement` · `child-identity`.
→ **Multi-photo identity extraction**: they ask for 2–3 photos up front and mint an upload session/batch token —
exactly the input contract a face/identity model wants, and it doubles as the **identity QA source** (3 photos =
better embedding than 1).

**[observed] Catalogue & pricing:** themed stories (football with Ronaldo/Messi/Salah/Halland, dinosaur, dream world,
behavioural stories, "the 90th-minute goalkeeper"), age bands **3–6 / 6–9 / 9–12**, each needing "بيانات الطفل
وصورتين أو ٣ صور" — price **399 EGP (was 499)**, and "خصّص القصة" (personalize the story) as the CTA.

**[observed] Tracking:** Meta Pixel `1011553001490691`, `gw.conversionsapigateway.com` (Cloudflare Conversions API).

**[observed] Disclosure:** no `llms.txt`; `/privacy-policy` 404.

**Hekayti takeaway — the single most actionable idea in Batch 2:** *ask for 2–3 photos, create an "identity" object
first, then generate.* It (a) gives the model more to work with than a single photo, (b) gives you a natural
place to run identity QA *before* burning image credits, (c) is a defensible UX differentiator, and (d) creates a
reusable, per-child asset that makes every later page consistent. The bundle already models the token/batch
upload contract.

---

## 5.7. `qissati.net` — قصتي (Arabic, classic server-rendered shop)

**[observed] Product:** "اصنع لطفلك قصة سحرية باسمه" — *"make a magical story with your child's name"*; headline
"أكثر من 5000+ عميل سعيد" (5,000+ happy customers); 3-step flow (اختر قصة / أضف اسم طفلك / استلم الكتاب);
categories: المغامرات، الخيال، التعليمية، قبل النوم، الصداقة، العائلة; `/stories`, `/about`, `/contact`, `/cart`,
`/login`, `/register`, `/lang/en`.

**[observed] Stack:** **plain server-rendered app** — one JS file (`/assets/js/app.js`) + `assets/css/app.css` +
`front.css` + Bootstrap Icons from jsDelivr; client calls only `/cart/add`, `/cart/remove`, `/cart/update`,
`/wishlist/toggle`. **No SPA, no API client, no analytics SDK on the page** — the cheapest possible stack, and
therefore the hardest competitor to out-engineer on tech.

**[observed] Catalogue & pricing (per story, EGP):**
```
مغامرة في الفضاء      4–10 سنوات · 24 صفحة · 5 أيام · 180.00
أميرة الحديقة السحرية  3–18 سنة  · 20 صفحة · 4 أيام · 160.00
رحلة إلى أعماق البحار  4–9 سنوات  · 24 صفحة · 5 أيام · 170.00
بطل كرة القدم          5–12 سنة  · 22 صفحة · 5 أيام · 150.00
… 10.00 ج.م (entry tier)
```
→ **per-story, per-page-count, human-production delivery in 4–5 days**, entry price 10 EGP.

**[observed] Tracking:** none observed (no GA/pixel/meta on the landing capture); only localStorage cart.
**Disclosure:** `/privacy-policy` (3.2 KB) — **no AI vendor named**.

**Hekayti takeaway:** this is the **price floor** of the market — 10 EGP for a story, 4–5 day delivery, and a
"5000+ happy customers" claim. The battleground is therefore **speed + price + Arabic quality**, and any AI-pipeline
advantage must show up as *same-day* delivery or a materially better child likeness.

---

## 5.8. `magic-eg.net` — قصتي السحرية (Egypt-first, print + personal video)

**[observed] Product:** "اطلب قصة سحرية مخصصة لطفلك باسمه وصورته الحقيقية — **كتاب مطبوع، فيديو شخصي ناطق، أو
الاثنين معًا**. أول منصة قصص أطفال مخصصة بهذه التجربة في مصر والوطن العربي" — *"the first platform with this
experience in Egypt and the Arab world"*. Also a *personal talking video* (a video where the child "speaks" the
story). Categories by gender (أولاد/بنات/الكل), "الأكثر مبيعًا", e.g. "شقيقة جديدة لفتاة" 699 → **499 EGP**,
"يا فتى، الديناصورات بحاجة إليك".

**[observed] Stack:** **Angular** (main-*.js + chunk-*.js + `chunk-YFTKKHL6.js` = Angular router/forms) +
`api.magic-eg.net` (own API) + `cdn.ipwhois.io` (**IP → country geo-detection** → per-country pricing) +
Lottie animation runtime (`assets/animation/Halloween Pumpkin Black Cat.json`).
**[observed] API surface (from the Angular chunks):**
```
GET  /api/geo/country
GET  /api/admin/stories?ShowOnHomePage=true
GET  /api/order-reviews/carousel-visible
POST story-orders/upload-child-photo      ← child photo upload
story_ai / story-card--digital|--print|--full   ← three product types: digital, print, print+digital
uploadChildPhoto / uploadChildPicture / upload-card / upload-area
story-video / storyVideoSection / storyVideoMedia  ← the talking-video product
```
**[observed] Tracking:** GA4 `G-W4DKPDXZ1P` only (no pixels observed), and `transformers` appears only as a CSS
property utility in the Lottie runtime → **no client-side AI model**.

**Hekayti takeaway:** **"video + printed book"** is a product axis nobody else in this batch offers except
Hekayti's own audio plans. If a talking video of the child can be generated (image→talking-head + Arabic TTS),
that is a *moat-sized* differentiator in Egypt/MENA — and it is exactly what "Snaps AI" (MENA model house) and
Nookly (`/api/studio/narrate`) are converging on.

---

## 5.9. `hadoota.net` — حدوتة (Arabic audio + PDF book; *the closest Arabic analogue to Hekayti*)

**[observed] Product:** "حوّل صورة طفلك لـ بطل حدوتة حقيقية" — *"turn your child's photo into a real story hero …
the AI writes and draws a story **in his own shape** — **the same face on every page**"*. You get a **narrated audio
story + a printable PDF book**. Order page states: "تسليم خلال ٢٤–٤٨ ساعة · صوت + كتاب PDF", "يبدأ من ٣٠٠ ج.م",
"+٢٬٥٠٠ كتاب اتعمل", "تقييم ٤٫٩ من الأمهات", "خصوصية الصور مضمونة", and a feature strip:
**"ثبات الشخصية في كل صفحة" (character consistency on every page) · "محتوى آمن ١٠٠٪ للأطفال" · "كتاب PDF جاهز
للطباعة" · "صوت احترافي بمشاعر لكل مشهد" · "تعديلات مجانية حتى ترضى"**.

**[observed] The ordering funnel is currently paused:** `/ar/order/new` shows *"خدمة طلب القصص المخصصة متوقفة مؤقتاً
… تم تعطيل تقديم الطلبات"* (custom-story ordering temporarily disabled) with the 5-step wizard still visible
(فكرة / الستايل / البوكسار / الباقة) and a **"باقة قصيرة — قصة صوتية ٢–٣ دقائق … الإجمالي ٣٠٠ ج.م أو اطلب عن
طريق الواتساب"** (short pack, 2–3 min audio, 300 EGP total, or order via WhatsApp) — i.e. they have moved to
**manual/assisted production with WhatsApp ordering**, likely while they rebuild the pipeline.

**[observed] Stack:** **Next.js (App Router, RSC)** — `_rsc=` prefetches, `turbopack-` chunk, `/api/csp-report`
(CSP reporting endpoint), `/api/auth/me`, `/api/subscriptions/me`, `/api/auth/google?returnTo=…` (Google OAuth),
`/manifest.webmanifest` (PWA "تثبيت التطبيق"), `/order/hero-before.jpg` + `/order/hero-after.jpg` (a **before/after
slider: real photo vs. the character version** — same pattern as Scrively's "Original Lena → styles").
Story model in the client: `storyDetail.book`, `StoryPlayOverlay`, `StoryShareMenu`, `StoryCategoryTags`,
`voiceDurationSec`, `story-play`, `story-played`, `Generated` (AI-generated story flag), `audioworklet` (Web Audio
playback of the narration). **[observed] first-party analytics:** `analytics.hadoota.net` (GA4 `G-Z87J7G77MM`
forwarded to their own subdomain) + Google AdSense (`ca-pub-6961346703007849`) + Google **SODAR** traffic-quality
runner + reCAPTCHA v3.

**[observed] `llms.txt` is real and hand-written (Arabic)**: "حدوتة — منصة قصص صوتية عربية أولاً للأطفال …
قصص صوتية مناسبة للأطفال، بأعمار وميول مختلفة، متاحة مجاناً وباشتراك بسيط", with a category map
(`/ar/category/visual-and-sensory-development`, `/ar/category/independence-and-rules`, …), sitemap/robots links and
an English home at `/en`. → **They publish an LLM-readable product map; nobody else in Batch 2 except Shopify
stores does.**

**Hekayti takeaway — highest relevance in the batch:**
1. They sell the *same* promise we do ("same face on every page") and it is their **headline differentiator** — proof
   the market rewards it.
2. Their delivery is **human-assisted** (24–48 h, WhatsApp, free edits) — the market tolerates slow delivery, so
   **speed is not a moat; likeness quality is**.
3. Their technical position is *weak* (ordering paused, manual fulfilment) → an opening for a fully automated,
   faster pipeline.
4. Their `llms.txt` + Arabic category taxonomy is the best agent/SEO surface in the batch.

---

## 5.10. `batalstories.com` — بطل ستوريز (SvelteKit, print-led, EGP)

**[observed] Product:** "بطل ستوريز — طفلك بطل الحدوتة" ("your child is the hero of the story"); "حواديت أطفال
مطبوعة باسم طفلك وصورته. اختار من مكتبتنا أو اكتب فكرتك، والكتاب يوصل لباب البيت." A 6-item hero carousel with
**prices and discounts in EGP**:
```
3 stories                     499 EGP (was 747)
single story                  249 EGP (was 299)
premium book (3 stories, 16 pages, hardcover)  1,299 EGP (was 1,599)
coloring book (B5, 90 options)                  199 EGP (was 250)
gift box (book + coloring + dedication)         1,799 EGP (was 2,200)
up to 20% account discount, welcome credit
```
Catalog: **90 stories** ("من مكتبتنا (90 حدوتة)"), i18n paths `/en`, `/sa`, `/sa/en`, `/ae`, `/ae/en` (Gulf locales),
`/p/story`, `/p/book`, `/p/coloring`, `/p/box`, `/account`, `/cart/review`, `/store?tab=story#search`.

**[observed] Stack:** **SvelteKit** (immutable chunks) + Next-style image optimizer (`/_next/image?url=…&w=&q=&dpl=`)
and media on **`batal-media-staging.s3.eu-central-1.amazonaws.com/stories/<sha256>.webp`** (content-addressed
story assets). Facebook Pixel `2635313103593665`, `gw.conversionsapigateway.com`.

**[observed] Disclosure:** no `llms.txt`; `/privacy` (3.4 KB) — **no AI vendor named**.

**Hekayti takeaway:** **90 pre-made stories + a 3-tier product ladder (single / book / box) + a coloring book at
199 EGP** is the most complete *commerce* model in the batch. Coloring books are a nearly-free extra revenue line
(Scrively ships a one-click coloring conversion too). Also note the **S3 content-addressed story media** pattern:
their story *assets* are pre-generated and cached, so "your child" versions are a re-render of a known-good template.

---

## 5.11. `www.bedtimestory.ai` — Bedtimestory AI (Next.js + Cloudflare Workers; character library + ControlNet-style editing)

**[observed] Product:** "AI Story Generator | Bedtimestory.ai" — *"Create instant, personalised bedtime stories
created in seconds using AI. Incorporate your child and family members as characters, add genre, art style,
moral, and more."* Scale claim: **"Loved & trusted by 80k+ happy members"**; testimonial *"Best 10 dollars I spend every
month by far."* Three segments on the page: **For parents / For authors / For educators**, and the FAQ states
*"You own the rights to the stories you generate"* (publish/share). Landing CTA: *"Type any idea, add your child as
the hero… No idea? Just hit create — we'll suggest one."* (`/api/story/lucky`).

**[observed] Pricing** (`/pricing`): **$4.99 / $9.99 / $19.99 per month** for 1 / 3 / 10 "pop-up books" per month,
each tier "Unlimited stories, every night" — the cheapest per-story pricing in the whole teardown.

**[observed] Stack:** **Next.js (Pages Router) on Vercel** (Sentry env `vercel-production`, release
`b501500bd04a821e7612f8b256db589878bfb734`), **Supabase** auth (`/api/auth/login|me|logout`,
`screen_hint=signup`), **Cloudflare Workers** backend `kneit3p1t5.execute-api.us`, image bucket
`storytime-backend-dev-storybucketstoryimageupload-sj7s0e95t0rs.s3.us…` (note the **dev** name leaking into
production config), CloudFront CDN, **TipTap** rich-text editor (stories are *editable text*, not baked pixels),
Lottie, Radix UI, Typekit, **Mixpanel**, Google Ads `AW-11344066364`, Sentry, Product Hunt, and **Pixi** for
payments (`/pixi-support`, `/legal/pixi/privacy`).

**[observed] Product surface = 111 routes** (from `_buildManifest.js`), which is a *product map* in itself:
`/create` · `/new-character` · `/onboard-characters` · `/[user]/characters` · `/[user]/character/[id]/modify` ·
`/illustrations` · `/magicimage` · `/magic` · `/superstory` · `/teleporter` · `/teleporting` ·
`/streaming` · `/streamingStory` · `/streamingSuperStory` · `/streamingTeleport` · `/flapbook/new` ·
`/flapbook/[id]` · `/flapbook-preview` · `/flap-demo-{davinci,sky-secret}` · `/sketch` · `/math` ·
`/math-adventure` · `/adventure` (+ `/adventure-time`, `/adventure_old`) · `/quiz` (algebra) · `/pdf` ·
`/audio` · `/browse` · `/library` · `/libraryCategory` · `/toppicks` · `/credits` · `/store` · `/cart` ·
`/affiliate` · `/authors` · `/changelog` · `/control` · `/pixi-support` · `/sentry_sample_error` ·
**14 story sitemaps + 3 author sitemaps** · `/[user]/story/[story]` (+ `/edit`, `/quiz`) · `/[user]/editor` ·
`/[user]/image-library` · `/[user]/settings/subscription`.

**[observed] API map (from 84 shipped chunks) — the most complete generation surface in the teardown**
```
CHARACTERS (the identity layer)
  POST /api/character/create      POST /api/character/imageGen      POST /api/character/update
  GET  /api/user/characters
STORY GENERATION (streaming)
  /api/streaming/{create,generate,title,saveTitle,saveImage,saveStory,okay,imagev3}
  /api/streamingStory/{create,imagev4}     /api/streamingSuperStory/create
  /api/streamingTeleport/{create,imagev3,saveImage}
  /api/adventure/{start,continue,lesson,image,saveImage,error,end,load}
  /api/superStory/request       /api/story/super/request
  /api/flapbook/create          /api/story/teleport/{create,teleport,get}
  /api/math/{start,continue,lesson,end}        /api/quiz/algebra/{start,continue,lesson}
  /api/story/lucky
EDITOR / REDO SURFACE  (the consistency mechanism)
  POST /api/story/edit/{generateImage,imageToImage,save,discard,publish}
  POST /api/story/edit/sketch/generate         ← ControlNet-style SKETCH conditioning
  POST /api/story/edit/control/generate        ← ControlNet-style CONTROL conditioning
  POST /api/story/edit/magicImage              POST /api/imageLibrary/save   ← persistent image library
LIBRARY / SOCIAL / COMMERCE
  /api/story/{like,dislike,bookmark,flag,delete,pdf?url=}   /api/search/{books,authors}
  /api/store/{checkout,sample/,purchased-stories}            /api/user/{get,post,create,detectLanguage}
  /api/adventure/error   /api/error
```

**Why this matters for Hekayti — four transferable ideas:**
1. **The character is a first-class, editable, persistent object.** `/api/character/create` + `/imageGen` +
   `/update`, `/[user]/character/[id]/modify`, `/onboard-characters`, `/api/user/characters` — a *character
   library*, not a per-story photo. This is the productised form of the "Character Bible" we recommended, and it
   also gives cross-story consistency for free.
2. **The redo mechanism is canvas-based, not prompt-based.** `/api/story/edit/sketch/generate` (canny),
   `/api/story/edit/control/generate` (control/pose/depth) and `/api/story/edit/imageToImage` mean the user can
   *paint* the change they want instead of re-describing it — strictly better than Scrively's "Make the coat blue"
   text redo, and it is what keeps the rest of the frame (and the face) untouched.
3. **A persistent image library** (`/api/imageLibrary/save` + `/[user]/image-library`) turns generated art into a
   reusable asset pool — the same idea as StarredIn's reference grid, exposed to the user.
4. **Streaming text *and* images** (`/api/streaming/*`, `imagev3/v4`) is how "generated in seconds" is
   actually delivered: the first pages appear while later ones are still rendering.

**[observed] Paywall shape:** *"Upgrade to pro for magic images! You can choose your illustration style and create
illustrations in seconds from just a few words."* → **art-style choice and image generation quality are the paid
tier**; free users get generic art. And the free-text fallback: *"If you want to tailor the images you can describe
the characters in more detail."*

**[observed] Scope:** no authenticated generation payload was captured here either — the creation flow sits behind
`/api/auth/login` and the image/text pipeline lives in the Cloudflare Worker.

**[observed] AI vendors: none identifiable.** Every provider keyword in their bundles is a **false positive** —
`luma` = Lottie's `loadLumaCanvas`, `kling` = "mi**xing**" inside a placeholder, `openai`/`veo`/`sora` only in
vendor SDK code (Amplitude/Clarity). Their pipeline is **entirely server-side**, behind
`kneit3p1t5.execute-api.us` (Cloudflare Workers). Their 15 KB privacy policy names **Firebase** (auth + Google SSO),
**Stripe** (payments), **Help Scout** (support) and AWS boilerplate — **no AI sub-processor is disclosed**
(14 platforms, 1 disclosure).

**[observed] Debug residue shipped to production:** `/sentry_sample_error`, `/control`, `/pixi-support`,
`/adventure_old`, and a dev-named S3 bucket in the live image URL.

---

## 6. Cross-platform synthesis — what actually makes characters stay consistent

### 6.1 The four mechanisms, and who does what
| Mechanism | StarredIn | Nookly | Scrively |
|---|---|---|---|
| Canonical per-style character asset (avatar/sheet) | ✅ `character-preview/grid/<portraitId>/<style>.jpg`, `useReferenceGrid` | ✅ `upload-style-image`, `character-preview` grid job | ✅ per-style "Lena" variants, "Lena's avatar" |
| One reference image per character, labelled | ✅ directive.characters[] + 512px refs | ✅ segmentation + protagonist poster | ✅ (implied by per-style avatar) |
| Redo as **edit of prior image** (chain editing) | ✅ `/api/character-edit` (image+mask+prompt), `/api/new-route/regeneration/page/:id` | ⚠️ not observed | ✅ "Make the coat blue" / "Let the dragon wave" (2 free per image) |
| Automated identity QA + retry | ✅ `qaValidationEnabled`, `validatorRetryCount`, `moderationStatus` | ✅ `/api/image-segmentations/find-or-create` | ❌ (human redo loop instead) |
| Prompt text kept server-side, exposed only to admins | ✅ scene-director / ai-editing / video-director logs, `promptPath` files | ✅ (no client prompts) | ✅ (no client prompts) |

### 6.2 Prompt architecture comparison
```
StarredIn : page text ──► Gemini "Scene Director" ──► directive{scene,background,mood,
                                                          characters[{name,pose,expression}]}
                        ──► (server) OpenAI image prompt components
                        ──► gpt-image-1 (reference grid + character refs) ──► 1024×1024 jpeg q80
Nookly    : free text ──► /api/contents/identify (intent→content type)
                        ──► /api/goals/resolve-intent, /api/children/infer-extra-details
                        ──► /api/imagineer/blueprint/generate (server-side prompts)
                        ──► /api/generated-stories (server-side) ──► image CDN ?w&q&f=webp
Scrively  : free text ──► /api/ai/character (vision: gender from photo)
                        ──► server-side pipeline (prompts not in client) ──► 111-style render + free edit-redos
```
Common denominator: **the LLM never writes the final image prompt in the client; the image prompt is compiled
server-side from a structured scene directive.**

### 6.3 Vendor map (who does what, consolidated)
| Capability | StarredIn | Nookly | Scrively | Hekayti today |
|---|---|---|---|---|
| Story/quiz text | Gemini + OpenAI | OpenAI / Llama / Phi-3 | not disclosed | Qwen `deepseek-v4-flash` (DashScope intl) |
| Scene direction | Gemini | — | — | Qwen (scene split + EN prompt) |
| Image | **gpt-image-1** | not disclosed | not disclosed | **qwen-image-2.0-pro** (DashScope) + InstantID experiments |
| Narration | **xAI** primary, ElevenLabs fallback | ElevenLabs (STT) | `/api/studio/narrate` | **XTTS-v2** (self-hosted) |
| Animation | **xAI Grok** | — | — | — |
| Research | — | **Perplexity** | — | — |
| Safety/moderation | Gemini + OpenAI image moderation toggle | `/api/rights-check`, `/api/reports`, charter | — | — |

### 6.4 Product-framing lessons
- **Free redos are a feature, not a cost** (Scrively: 2/image; 25-page book = 75 attempts; credits only for the book).
  Hekayti currently charges nothing for redos but also has no redo UX.
- **No sign-up to preview**: describe → preview cover + several pages → then register (Scrively). Nookly does the same
  (`create-temp-user` before conversion).
- **Style breadth is the marketing weapon** (Scrively: "tons of art styles", 111; Hekayti currently has one Pixar-ish style).
- **A style-name alias table** (Scrively: "Pixar 3D" → "Modern Animated Film (3D)") avoids trademark exposure while
  keeping SEO. Hekayti's prompts say "Disney Pixar 3D animation" — that is a real legal exposure in a commercial product.

### 6.5 Batch 2 adds three more data points to the synthesis
*(Full breakdown: `AI-personalized-storybook-platforms-teardown-batch2.md` — 10 platforms.)*

1. **The "same face" claim is the market's headline, not a feature bullet.** `hadoota.net` sells
   *"نفس الوش في كل صفحة"* ("the same face on every page") as its #1 differentiator, with a free before/after
   photo slider (`/order/hero-before.jpg` → `hero-after.jpg`) — exactly Scrively's "Original Lena → 5 styles"
   pattern. **Hekayti should ship that slider and put the claim on the landing page.**
2. **The intake contract is 2–3 photos, not 1.** `hero-kid.com/child-identity` requires *"صورتين أو ٣ صور"*
   (min 2 clear photos, optional 3rd) with an explicit photo-processing consent checkbox, and its bundle models a
   real upload pipeline (`upload_session_token`, `upload_batch_token`, `photo_upload_ids`, `child-identity`).
   More photos = better identity = a QA checkpoint before you spend image credits.
4. **The most advanced implementation in the teardown is `bedtimestory.ai` (14th platform):** it ships a
   **persistent, editable character library** (`/api/character/create|imageGen|update`, `/[user]/character/[id]/modify`),
   a **canvas-based redo surface** (`/api/story/edit/sketch/generate` = ControlNet sketch,
   `/api/story/edit/control/generate` = control conditioning, `/api/story/edit/imageToImage`), a
   **persistent image library** (`/api/imageLibrary/save`) and **streaming text+image generation**
   (`/api/streaming/*`). That is the full §8 Hekayti pipeline — already shipping, at $4.99/month.
3. **Disclosure is still an open differentiator — now across 14 platforms.** StarredIn itemizes 6 AI sub-processors;
   Nookly, Scrively and **all ten Batch-2 sites** name none. Hadoota is the only Batch-2 site with a hand-written
   `llms.txt` (Arabic category map). A published, *measured* likeness guarantee (embedding score per page +
   sub-processor list) is unclaimed territory in this market.

---

### 6.6 Batch-2 synthesis — what the Arab/Egyptian long tail does differently

#### 6.6.1 Where the money is
| Player | Entry price | Premium | Fulfilment |
|---|---|---|---|
| qissati | 10 EGP | 180 EGP | 4–5 days, per-story |
| hadoota | 300 EGP (2–3 min audio pack) | — | 24–48 h, audio + PDF, WhatsApp ordering |
| hero-kid | 399 EGP (was 499) | packages | upload → identity → story |
| magic-eg | 499 EGP (was 699) | video + print | print + personal talking video |
| syorastories / kitabme / bysnaps | Shopify-priced | bundles | print partner |
| batal | 199 EGP (coloring) → 1,799 EGP (box) | — | 90-story catalogue, 3 tiers |

#### 6.6.2 Six patterns worth stealing
1. **Identity-first intake (hero-kid).** 2–3 photos → a child-identity object → then generation. Better model input,
   a natural QA point, a reusable asset, and a defensible UX.
2. **Sell the "same face" claim (hadoota, scrively).** It is the *headline*, not a footnote. Hekayti should put
   "نفس الوش في كل صفحة" on the landing page and measure it in-product.
3. **Before/after proof slider (hadoota `/order/hero-before.jpg` → `hero-after.jpg`, scrively "Original Lena" →
   5 styles).** Free, high-converting, and it *shows* the consistency you are selling.
4. **Manual-assisted fulfilment as a fallback (hadoota, WhatsApp ordering everywhere).** Even when the pipeline
   breaks, taking the order on WhatsApp preserves revenue. Hekayti needs an equivalent degraded mode
   (e.g. "order by WhatsApp, we deliver by hand") — but must not use it to hide a broken pipeline.
5. **Commerce layering (batal's 3 tiers + coloring; syorastories' notebook/coloring; kitabme hardcover/softcover).**
   The AI story is the *hook*; the money is in the printed object and the add-ons.
6. **Publish an LLM-readable product map (hadoota's hand-written `llms.txt`)** — cheap SEO/discovery, and only one
   player in the whole teardown (13 sites) besides Shopify stores does it deliberately.

#### 6.6.3 What nobody in Batch 2 does (our opportunity)
- **Zero AI sub-processor disclosure** across all ten. Hadoota/Scrively-style vendor lists are still open ground.
- **Zero published identity metrics.** Nobody states how they measure "same face" (embedding score? human review?).
  Publishing *"we score likeness on every page and regenerate below threshold"* is a credible differentiator for
  schools/clinics (the segment Nookly and HeroKid both target).
- **No editable/composable pipeline.** The ordering is a wizard that ends in a PDF; there is no "regenerate this page,
  keep everything else" surface. Scrively's 2 free redos/image and StarredIn's per-page regeneration are still ahead.
- **No Arabic-native typography in the image pipeline.** Every competitor bakes text into images or ships a bare
  PDF; Hekayti's `diacritize_arabic` + XL/Voice work (XTTS) and DOM-overlay approach is a real edge — especially
  **text-out-of-image** rendering, which fixes the single most failure-prone step for Arabic.
- **No voice in most of them.** hadoota does narrated audio; hero-kid/others don't. Arabic TTS with the child's own
  voice is still rare in this market (only Scrively offers parent-recorded narration).

#### 6.6.4 Where the technical risk actually is
Batch 2 is mostly **storefronts and thin clients** (Shopify ×3, Easy Orders ×1, PHP ×1, Angular ×1, Laravel ×1,
Next ×1, SvelteKit ×1, Lovable/Supabase ×1) with **no client-side AI** anywhere — so their pipelines are entirely
server-side and invisible. Two exceptions matter:
- **Snaps AI (bysnaps)** positions as an *Egyptian AI model house* — the only real model-layer competitor in the
  region. Benchmark their Arabic image quality before committing to a model.
- **Autopictura on kitabme** proves the AI layer is a **pluggable Shopify app** → the low end of this market is
  commoditized; quality and Arabic craft are the only defensible axes.

---

## 7. Gap analysis vs Hekayti (as the code stands)

Current Hekayti image path (`image model/image-deploy/model_utils.py`, `app.py`):
`Arabic story → Qwen scene split (EN prompts) → per-scene DashScope qwen-image-2.0-pro call with the child's RAW PHOTO
as reference → PNG base64`.

| Hekayti gap | Production answer |
|---|---|
| Raw photo re-sent and re-stylized for every scene → identity drift | Render a **canonical avatar per style once**; never re-send the photo (Scrively "Lena"; StarredIn `character-preview/grid`) |
| Single reference, single hard-coded protagonist (`build_prompt`: *"The main character is a young {gender} named {name}"*) → multi-character mixing | **One labelled reference per character** + a cast registry (StarredIn `directive.characters[]`) |
| Style instruction duplicated in `build_prompt` *and* `generate_scene_image`; negatives concatenated into the prompt tail | Compile the prompt **once, server-side, deterministically**; use DashScope's `negative_prompt` field |
| `prompt_extend=True` → DashScope rewrites the prompt per call → drift | `prompt_extend=False` for determinism |
| No seed, no QA, no retry on identity mismatch | Identity QA gate + targeted repair hint + bounded retries (StarredIn `qaValidationEnabled` / `validatorRetryCount`) |
| 10 independent generations, each with its own 429 backoff, no concurrency | 1 generation + 9 **edits**; `asyncio` + `Semaphore(4)`; shared cooldown; lock the model counter (`_image_model_counter` is racy under FastAPI's threadpool) |
| Photo squashed to 1024×1024 (aspect distortion) before the model sees it | `ImageOps.fit`/pad, and never upload the raw photo after the avatar exists (privacy + cost) |
| Public copy says "Disney Pixar" in prompts | Style aliases, StarredIn/Scrively style |

**Note on Hekayti's existing experiments:** `image model/instantid_api.txt` shows an **InstantID** Gradio client
(`identitynet_strength_ratio`, `adapter_strength_ratio`, `seed`, `scheduler`, `enhance_face_region`, style presets
Watercolor/Film Noir/Neon/Snow/Line art…) — a legitimate *self-hosted* identity-preservation path, and
`result_qwen-image-2.0-pro-2026-06-22.png` / `result_wan2.7-image-pro.png` show hosted-model comparisons.
**Decision needed:** InstantID (self-hosted, single-face ID, style-locked) vs hosted multi-reference
(`qwen-image-2.0-pro` / `gpt-image-1`, per-character refs + edit-redos, no GPU). Both can coexist:
InstantID for the **avatar sheet**, hosted editing for **page redos**.

---

## 8. Recommended Hekayti pipeline (6 stages)

```
Stage 0  Character Bible  (once per child, 1–2 image gens)
         vision LLM on the photo → frozen descriptor {faceShape, hairColor/Style, skinTone, eyeColor,
         distinctiveFeatures[], bodyProportions, canonicalOutfit}
         → render a CHARACTER SHEET (3–4 poses/expressions, target style) → characterSheetUrl
         → the photo is never sent again
Stage 1  Scene Director    (structured, LLM)
         per page → {scene_text_ar, characters[{id,name,pose,expression,action}],
                     environment, props, camera, mood}  + a cast registry (child + ≤2 others)
Stage 2  Prompt Compiler   (deterministic code, not LLM)
         {style block} + SCENE + CHARACTER 1/2/3 (each bound to a named reference) + ACTION + PROPS
         + negative_prompt (field, not tail) ; prompt_extend=False
Stage 3  Reference binding (one labelled image per character; fixed order; ≤3 characters)
Stage 4  Chain editing      page 0 = generate(sheet, p0) ; page i = edit(base=page[i-1], prompt=pi)
Stage 5  Identity QA gate  face/embedding similarity + palette check per character crop
         fail → 1–2 repair retries ("same hairstyle, same shirt colour, do not redesign the character")
         → store identity_score / attempts / validator_retry_count per page
```

**Acceptance test:** 3 stories × 10 pages × 3 children; report mean pairwise identity similarity, % pages passing
threshold, cost/page, p95 latency. No claim of "fixed" without this measurement.

---

## 9. Evidence, artifacts and reproduction

### 9.1 Captures (REA evidence IDs)
| Target | Evidence ID | Tool |
|---|---|---|
| app.starredin.com (passive) | `ev_f1cb5a…` | `rea_inspect_web_page` |
| app.starredin.com (navigated) | `ev_75d420ed…` (landing) / `ev_d48c3058…` (app) | `rea_capture_browser_scenario` |
| nookly.com | `ev_75d420ed…` / `ev_d48c3058…` | `rea_capture_browser_scenario` |
| www.scrively.com | `ev_98ade53c…` | `rea_capture_browser_scenario` |
| app.scrively.com | `ev_ae7a947b…` | `rea_capture_browser_scenario` |

### 9.2 Local artifacts (`C:\Users\alisa\AppData\Local\Temp\opencode\`)
```
starredin : rea_scenario_out.json (1.3 MB)  rea_scenario_summary*.txt  rea_story_tree.txt
            rea_bundles\ rea_bundles_all\ rea_chunks\ (560 chunks, 10.3 MB)
            rea_api_paths.txt (625)  rea_pipeline*.txt  rea_prompt_ctx.txt  rea_privacy_text.txt
nookly    : nookly_capture.json (3.2 MB)  nookly_app_capture.json (1.6 MB)
            nookly_bundles\ (47)  nookly_app_bundles\ (26)  nookly_app_api.txt (262 endpoints)
            nookly_supabase.txt  nookly_bundle_scan.txt  nookly_privacy_text.txt
scrively  : scrively_capture.json (3.8 MB)  scrively_app_capture.json (190 KB)
            scrively_bundles\ (5)  scrively_app_bundles\ (14)
            scrively_app_scan.txt  scrively_styles2.txt (111 styles)  scrively_char.txt  scrively_privacy.txt
own repo  : infinite-heros\  (git clone --depth 1 https://github.com/AliSakr9997/infinite-heros-.git)
            → App.tsx, Setup.tsx, Book.tsx, Panel.tsx, types.ts, useApiKey.ts, ApiKeyDialog.tsx,
              LoadingFX.tsx, vite.config.ts, package.json, index.html, metadata.json
```
Tooling note: the REA CLI was used directly (`npx -y rea-agents@6.7.0 <command>`) because the MCP server was not
exposed as tools in the analysis session; the same MCP tools were used earlier in the project.

### 9.3 Reproduction
```powershell
# 1. headless Chrome
chrome.exe --headless=new --remote-debugging-port=9222 `
          --user-data-dir=%TEMP%\opencode\rea-chrome-profile --no-first-run --disable-gpu

# 2. open a target
Invoke-WebRequest -Method Put "http://127.0.0.1:9222/json/new?https://app.starredin.com/"

# 3. capture (navigate + network + console + DOM + a11y)
npx -y rea-agents@6.7.0 capture-browser-scenario scenario.json --format json --full-output > out.json

# 4. bundle sweep
npx -y rea-agents@6.7.0 inspect-web-page http://127.0.0.1:9222 <targetId> --allowed-origins https://… --format json
#    then download every chunk URL and grep for /api/, providers, prompt strings
```

### 9.4 Known limitations of this teardown
- StarredIn: `rea analyze-web-bundle` crashed with a **Node JS heap OOM** (4 GB and 6 GB heap) on the 1 MB Vite bundle
  → the static sweep was done on the raw chunks instead.
- Nookly marketing capture dropped **172 events** (`max-total-event-allocation-bytes`); the app capture dropped 0.
- Scrively marketing capture dropped **447 events** (79 images on the page).
- No site was authenticated; Scrively's generation path is auth-gated **and** bot-challenged, so **no live prompt
  payloads were captured anywhere** — all prompt knowledge is structural (schemas, directives, endpoint names, logs).
- Kaspersky Script Injection (local AV) appears in all captures; it is **not** part of any of the three products.
### 9.5 Batch-2 artifacts and limitations

*(Batch 3 — `bedtimestory.ai` — artifacts: `C:\Users\alisa\AppData\Local\Temp\opencode\batch3\` →
`bedtimestory_capture.json` (718 KB), `bedtimestory_summary.txt`, `bedtimestory_js/` (84 chunks incl. the
111-route `_buildManifest.js`), `bts_scan2.txt` (API map), `bts_models.txt` (provider false-positive check).)*

**Local artifacts** (`C:\Users\alisa\AppData\Local\Temp\opencode\batch2\`):
```
<slug>_capture.json     raw REA capture (0.95–4.1 MB each)
<slug>_summary.txt      network/console/DOM/a11y digest
<slug>_scan.txt         bundle scan: API paths, hosts, provider keywords, prompt-like strings
<slug>_js/              downloaded JS chunks (up to 30/site)
DIGEST.txt  DIGEST2.txt  DEEP.txt  DEEP2.txt
```
**Reproduction** — same recipe as Batch 1: `PUT /json/new?<url>` → `rea_capture_browser_scenario` (connect mode,
`service_workers: allow`, `request_body/response_body: true`) → download chunk URLs → grep `/api/`, `functions.invoke(`,
provider names, prompt-like literals.

**Limitations of Batch 2**
- No authentication anywhere → **no generation payloads, no prompts, no AI vendor names** could be observed; every AI
  claim here is either a client-bundle artefact, a console message, or the vendor's own marketing copy.
- `syorastories`, `kitabme`, `bysnaps` are **storefronts** — their AI runs in third-party apps/Easy Orders plugins,
  invisible from the page.
- `hero-kid` and `qissati` expose almost no client-side API surface (Laravel/PHP) → their pipeline is entirely
  server-side; only their *input contract* (photos) was observable.
- `snaps.ai` did not respond to plain `curl` (JS-only landing) → the model claims could not be verified.
- 3 of 10 sites had 400-series console errors on load (missing/geo-dependent resources) — not attributed to the
  products themselves.
- Kaspersky Script Injection traffic is present in every capture and is **not** part of any of these products.
