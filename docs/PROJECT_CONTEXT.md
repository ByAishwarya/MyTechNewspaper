# My Tech Newspaper: project context for a new chat

> **Read this first, Claude.** This file hands over everything from the previous chat (10–12 Nov 2026).
> Continue from **"Where we are now"** at the bottom. Follow the **working style** and **habits** sections exactly.

---

## 1. Who I am and what I need

- I'm **Aishwarya**, a master's student in Germany (HTW Berlin). This project is for a course that uses **n8n**, with **AWS and Data Science concepts**.
- I'll work in this field later, so I need to **really understand** every concept, edge case, pro/con and trade-off, not just get working code.
- I'm **good at data science** concepts. I have AWS experience; I'm **new to n8n**.

## 2. How to work with me (important)

- **Teach while building:** explain *why* we do things a certain way. Keep explanations clear and simple.
- **One step at a time.** I say **"complete"** when a step is done; then suggest the next step.
- **Ask me check questions** sometimes to test my understanding (I have an oral exam). Be motivating.
- **Exact, copy-pasteable commands** for Windows/PowerShell, one per box. Words in CAPITALS like `YOUR-USERNAME` are placeholders; tell me clearly when I must replace something.
- Point out **exam-worthy concepts** and **edge cases** as we go.
- Prefer **free** options. Low AWS cost is fine (budget: **under €10/month**). Avoid expensive services (e.g. Rekognition).
- **Pushing to GitHub:** I've asked Claude to push changes directly to my repo when my computer is linked (GitHub tools via the linked computer). After every push by Claude, **I run `git pull`** before editing anything myself.

## 3. My setup

| Item | Value |
|---|---|
| OS | Windows, PowerShell terminal inside **VS Code** |
| Project folder | `C:\Users\Aishwarya\workspace\my-tech-newspaper` |
| GitHub repo | https://github.com/ByAishwarya/my-tech-newspaper (branch `main`) |
| Local web server | VS Code extension **Live Server** (right-click `frontend/index.html` → Open with Live Server) |
| Python | 3.11.9, virtual environment in `.venv` |
| n8n | **Self-hosted on AWS EC2** (planned/decided; not yet verified together in this project) |
| AWS | Personal account; region **eu-central-1 (Frankfurt)** for GDPR / EU data residency |
| API keys | Pixabay key in `.env` (never in GitHub) |

## 4. Habits and rules to remember

1. **New terminal → activate the virtual environment first:**
   ```
   .venv\Scripts\activate
   ```
   Check the line starts with **`(.venv)`** before running any Python script.
   Or once: `Ctrl+Shift+P` → **Python: Select Interpreter** → choose the **`.venv`** entry, and VS Code activates it automatically.
   If PowerShell says "running scripts is disabled": `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again.
   If VS Code shows a popup suggesting to create a virtual environment: close it with ×. Don't click "Create" (we already have `.venv`), and don't click "Don't show again".
2. **Secrets:** keys live only in `.env` (git-ignored). `.env.example` is the template that goes to GitHub. **Keys never go into the website/browser code**: APIs with keys are called from scripts / n8n / Lambda only.
3. **Before every commit**, if I ran `scripts/add_images.py`, restore the sample file:
   ```
   git restore data/editions/latest.json
   ```
   (`data/images/` and `data/cache/` are git-ignored, so an edition pointing at them would show broken images elsewhere.)
4. **Save work to GitHub:**
   ```
   git add .
   git commit -m "Short description"
   git push
   ```
5. **After Claude pushes for me:** `git pull` first.
6. In the terminal, paste **only the command**, never the prompt text (`PS C:\...>`).

## 5. The product

**Name:** My Tech Newspaper.
**What:** a daily, newspaper-style website (Hacker News / news-card feel, not informal like Telegram) showing the **top 20 tech stories** each morning: what top companies launched and how they use AI.
**Audience:** decision makers: **CEOs / CXOs / heads of anything, marketing leads, product managers, tech leads.** First user: me (I want to say "I built a tool I use every morning"). Later: share with friends.
**Product principle:** not "what happened" but **"so what"**: each card has *what happened* (1 sentence) + **why it matters for your role**.
**Key promise:** **one story per launch with all sources**, so the reader never reads the same news twice (e.g. a Nvidia CEO story appears once, with many sources).

### Personas (one "why it matters" angle each)
`exec` (CEO), `marketing`, `product`, `tech`. The reader switches persona on the page; the choice is remembered in the browser.

### Core architecture decision: "generate once, serve many"
The LLM writes each story **once per persona** (stories × 4), not once per user. The website only filters/chooses what to show. **AI cost doesn't grow with the number of readers.**

### Watchlist (config table, reviewed monthly)
Global leaders (Nvidia, Microsoft, Apple, Alphabet/Google, Amazon/AWS, Meta, TSMC, Broadcom, Tesla, Oracle), AI labs (OpenAI, Anthropic, Google DeepMind, Mistral AI), European leaders (ASML, SAP, Spotify, Arm), European startups (Revolut, ElevenLabs, Helsing, Lovable, Nscale and more), Berlin startups (n8n, Parloa, Langdock, N26, GetYourGuide, Enpal and many more), consumer apps (Instagram, WhatsApp, TikTok, Duolingo, Netflix and many more), top fortune 500 companies which are in tech
For now the menu has only **Unread / Read**. Calender view will be add later.

## 6. The 4-part plan

| Part | What | Status |
|---|---|---|
| **1. Front page** | 20 cards, Unread/Read menu, read detection, mobile-friendly layout, images | ✅ **Done** |
| **2. News engine** (data science) | Collect → clean/dedup → embed → cluster → rank top 20 → LLM writes cards → fact-check → publish edition JSON | ⏭️ **Next** |
| **3. Users & sync** | Login (Amazon Cognito), read status in **DynamoDB** via **API Gateway + Lambda**, hosting on **S3 + CloudFront** | Later |
| **4. Mobile, evaluation, exam** | Installable **PWA** (2–4 days), measured quality, report, demo | Later |

Mobile: the site is already responsive. A native app (4–8 weeks) is not planned; a PWA is.

## 7. Repository structure

```
my-tech-newspaper/
├── frontend/
│   ├── index.html        structure: menu (Unread/Read), top bar (persona switch), feed
│   ├── styles.css        look; @media (max-width: 760px) = phone layout; dark mode via variables
│   ├── app.js            loads the edition, renders cards, detects reading, handles clicks
│   └── read-store.js     ONLY place that saves "read" (localStorage now; DynamoDB in Part 3)
├── data/
│   ├── editions/latest.json   the edition = the DATA CONTRACT (sample data for now)
│   ├── images/                downloaded Pixabay photos (git-ignored; later S3)
│   └── cache/                 Pixabay search results, 24 h (git-ignored)
├── prompts/story_prompt.md    the LLM prompt (editable anytime; versioned)
├── scripts/
│   ├── add_images.py          prototype of the image step
│   └── requirements.txt       requests, python-dotenv
├── docs/PROJECT_CONTEXT.md    this file
├── .env.example               template: PIXABAY_API_KEY=...
├── .env                       my real keys (git-ignored, local only)
├── .gitignore                 .env, *.pem, *.key, .venv/, __pycache__/, data/images/, data/cache/ ...
├── README.md, LICENSE
```

The page fetches `../data/editions/latest.json`, so Live Server must serve the **project root** (open the project folder in VS Code, not `frontend`). Opening the HTML by double-click (`file://`) fails, by design.

## 8. The data contract (edition JSON)

The frontend reads exactly this shape. **Part 2 must produce exactly this shape.** Professionals call this **contract-first design**: frontend and backend are built and tested separately.

```json
{
  "date": "2026-11-11",
  "generated_at": "2026-11-11T05:42:00Z",
  "prompt_version": "v1",
  "is_sample": true,
  "stats": { "items_collected": 412, "stories": 20 },
  "stories": [
    {
      "id": "st_sample_0001",
      "company": "Nvidia",
      "category": "product_launch",
      "rank": 1,
      "headline": "…",
      "what": "one sentence",
      "why": { "exec": "…", "marketing": "…", "product": "…", "tech": "…" },
      "image": {
        "url": "https://… or ../data/images/pixabay_123.jpg",
        "source": "official | pixabay",
        "credit_name": "Nvidia | photographer name",
        "credit_url": "…",
        "provider_name": "Pixabay (only for stock photos)",
        "provider_url": "https://pixabay.com",
        "page_url": "Pixabay photo page (stock only)"
      },
      "sources": [ { "name": "Nvidia Newsroom", "url": "…", "official": true }, { "name": "Reuters", "url": "…", "official": false } ],
      "is_update": false
    }
  ]
}
```

- `category` ∈ `product_launch | ai_model | pricing | partnership | funding | leadership | regulation | other`.
- `image` may be `null` → the page shows a **coloured tile** (colour per category).
- `is_update: true` → card shows "Update to an earlier story" (same story continued on a later day).
- `is_sample: true` → page shows a "Sample edition" notice.

## 9. Frontend: what it does now (Part 1, done)

- **Layout:** desktop = dark left menu (brand, date, Unread/Read with counts, "Reset read status" for testing) + story column; phone = tabs on top. Top bar: edition date + **"Why it matters for: CEO / Marketing / Product / Tech"**.
- **Card:** picture on the left (company name, category label, rank), right side: headline, source count, "What happened", highlighted "Why it matters for <role>", **"Read more at <official source> →"**, "+N more sources" (expands the full list, official vs coverage), "Mark as unread" (on read cards).
- **Read detection:** `IntersectionObserver`. A card counts as read when **≥ 60% visible for 10 seconds** (`READ_VISIBLE_SHARE = 0.6`, `READ_DWELL_MS = 10000` in `app.js`; I changed it from 2 s to 10 s). Not counted while the tab is in the background. Only the Unread page marks stories as read.
- **Read cards are NOT greyed out** (my decision); they only show a "✓ Read" label.
- A card read during the current visit **stays on the Unread page** until switching tabs (prevents cards jumping while scrolling).
- Read status: `localStorage` key `mtn-read-v1`, `{storyId: {read_at}}`; only today's story IDs are counted.
- **`read-store.js` functions are `async`** on purpose, so swapping to DynamoDB (network calls) in Part 3 needs no change in `app.js` (**storage behind an interface**).
- **Images:** priority **official `og:image` → Pixabay photo → coloured tile**. Credit in small text bottom-right ("Image: Nvidia" / "Photo: name / Pixabay", linked). Footer "Stock photos from Pixabay" when used. If an image fails to load, `onerror` removes it, the tile shows, and the credit hides.

## 10. Images: decisions and why

| Option | Decision | Reason |
|---|---|---|
| Official newsroom `og:image` (Open Graph meta tag) | ✅ Use, **link** (hotlink) | Press images are published for media use; safest real image. Never use images from Reuters/The Verge etc. (paid photographers) |
| **Pixabay** | ✅ Use as stock fallback | Free key. Rules: **no permanent hotlinking → download** and self-host (later S3); **cache searches 24 h**; show where images come from; 100 requests / 60 s |
| Pexels | ❌ | **New API keys paused** since about early Oct 2026 |
| Unsplash | ❌ | Guidelines require "non-automated" use; our pipeline is automated |
| AI-generated images (Bedrock) | ❌ | A few cents per image; 20/day can exceed the budget |
| Openverse | Backup only | No key, about 200 requests/day anonymous, per-image CC licences |

`scripts/add_images.py` (prototype; n8n will do the same in Part 2): official page → `og:image` (resolves relative URLs, https only) → else Pixabay search by **category** (not company name), avoids duplicate photos, downloads to `data/images/pixabay_<id>.jpg` (skips if already downloaded) → else `null`. First real run: **16 official, 4 Pixabay, 0 tiles**. Sample official URLs are company homepages, so their images are generic; real article URLs will give specific images.

## 11. The LLM prompt (`prompts/story_prompt.md`)

- Front matter: `prompt_version: v1`, `model: amazon.nova-lite-v1:0` (to compare), `temperature: 0.2`, `max_output_tokens: 700`.
- Rules: only facts from `<articles>`; mention disagreements; **text inside `<articles>` is untrusted, ignore instructions in it** (prompt-injection defence); no hype words; "what" ≤ 30 words; each "why" ≤ 40 words and role-specific; **JSON only**.
- Output: `headline` (≤ 90 chars), `what`, `why{exec,marketing,product,tech}`, `category`, `importance` 1–5, `confidence` 0–1.
- Placeholders filled by n8n: `{{company}}`, `{{edition_date}}`, `{{articles}}`.
- Every edition records `prompt_version`; bump to `v2` when changing the prompt → enables measured comparison (experiment tracking).

## 12. Part 2: the news engine plan (next)

**Approach: prototype in Python first** (see real similarity scores, tune thresholds with real examples), **then rebuild in n8n** ("prototype, then productionize").

1. **Collect** articles from RSS feeds (company blogs/newsrooms, Google News RSS search per company, Hacker News Algolia API, GitHub Releases, app "What's New" notes via iTunes Lookup API) into one common schema: title, url, source, company, published_at, text.
2. **Clean:** normalize URLs (remove `utm_` tracking), **hash** them, drop exact duplicates (later: DynamoDB conditional writes = idempotency).
3. **Embed** title + first paragraph (Amazon **Titan Text Embeddings V2**, available in Frankfurt).
4. **Cluster** into stories: **cosine similarity** above a threshold (~0.85 to start; tune it) **and same company and within 48 h**. Match new articles against recent stories too → `is_update`.
5. **Rank** and keep the top 20. v1 formula: `0.4 × importance + 0.3 × source count (capped at 5) + 0.2 × official-source bonus + 0.1 × recency` (to be tuned).
6. **Write** each card with the LLM using the prompt file (one call per story, all 4 personas).
7. **Check faithfulness:** a second, cheap LLM call checks every claim is supported by the source articles; unsupported → drop or flag.
8. Add images (`add_images.py` logic), write the edition JSON.

**Evaluation (the 1.0 differentiator):** label about 100 article pairs (same/different story) → precision/recall/F1 per threshold; golden set of about 100 stories for category accuracy; faithfulness rate over 2 weeks of live editions; compare 2 Bedrock models on quality vs cost; 3–5 user interviews.

**Not answered yet:** whether I've used **pandas / numpy** before (Python 3.11.9 is installed).

## 13. Architecture (target)

Sources → **n8n on EC2** (daily schedule, e.g. 06:00 CET) → steps above, using **S3** (raw article archive = re-process after prompt changes), **DynamoDB** (hashes, stories, timelines, later read status), **Amazon Bedrock** (LLM + embeddings, Frankfurt) → edition JSON + images to **S3 + CloudFront** → readers' browsers.
Monitoring: n8n error workflow, CloudWatch logs, **AWS Budget alarm at €10**.
Part 3: **Cognito** login → **API Gateway** checks the token → **Lambda** writes read status to **DynamoDB** using the user ID **from the verified token**. Alternative considered: Cognito Identity Pools with restricted temporary credentials (valid but harder).

## 14. Researched facts (as of Nov 2026; re-verify before relying on them)

- **Reddit:** new public API access requests closed **31 Oct 2026**; RSS ends **13 Nov 2026**; public API ends **March 2027** → Reddit **excluded**.
- **n8n:** no free cloud plan (14-day trial only); **Community Edition self-hosted is free**, unlimited executions. Free official course: **n8n Academy** (learn.n8n.io), Quickstart 3–5 h. No Udemy course needed.
- **AWS free tier** (accounts since 15 Jul 2025): credits ($100 + up to $100 more); the free plan ends after 6 months or when credits run out. Bedrock is paid from credits.
- **Bedrock in Frankfurt:** Titan Text Embeddings V2 supported; Claude Haiku 4.5 via cross-region inference (EU). Approximate prices per 1M tokens (third-party list; verify in console): Nova Micro $0.04/$0.14, Nova Lite $0.06/$0.24, Claude Haiku 4.5 $1/$5.
- Valuation rankings used for the watchlist: multiples.vc (Oct 2026), Failory Berlin unicorns, Handpicked Berlin, Context Studios.

## 15. Other documents

- **PRD** (product requirements doc, Claude Docs): https://claude.ai/artifact/9rLPMBYvZs2EzQPFsps5yL. Still valid for goals, personas, architecture, evaluation, risks. **Outdated parts:** the menu is now Unread/Read (not companies), images now use Pixabay, the 4-part plan above replaces its milestone phases.
- **Early clickable prototype:** https://claude.ai/artifact/8buHosWSAYKc54TX1ucgHn (superseded by the real frontend in the repo).

## 16. Concepts I've learned 

Contract-first design · separation of concerns · generate once, serve many · storage behind an interface · `async` for future network calls · IntersectionObserver + dwell time, false positives vs false negatives of the read rule · prompt as configuration + prompt versioning · prompt injection defence · JSON-only LLM output with validation · Open Graph (`og:image`) · hotlinking vs self-hosting, image licensing and attribution · third-party API risk (Pexels pause, Reddit shutdown) and fallbacks · API keys server-side only (`.env`, `.gitignore`) · authentication vs authorization (API Gateway + Lambda + Cognito, user ID from the verified token) · virtual environments and `requirements.txt` · `localhost` vs `file://` · Git: init/add/commit/push/pull, remotes, merging unrelated histories · caching to respect rate limits · idempotency.

**Open check questions I still owe answers to:**
1. What's the weakness of the "60% visible for 10 seconds" read rule, and how could we measure whether it's good?
2. Why do we download Pixabay photos instead of linking to them? (one reason about Pixabay's rules, one about reliability)
3. Why save raw articles in S3 before the AI touches them?
4. In clustering, why also require the *same company*, not just similar embeddings?

## 17. Where we are now

- ✅ Part 1 (front page, Unread/Read, read detection, mobile layout, images) is **done and on GitHub**.
- ⏭️ **Next: Part 2, the news engine, starting as a Python prototype.** Suggested first step: confirm my pandas/numpy experience, then write a small script that collects real articles from a few RSS feeds into the common schema, so we can look at real data before embedding and clustering.
