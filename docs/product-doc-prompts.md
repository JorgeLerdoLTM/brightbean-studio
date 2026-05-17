# Documentation Prompts — BrightBean Studio

This file contains three self-contained prompts for documenting **BrightBean Studio** from three audience angles. Open each fenced block, copy its contents, and paste it into a fresh Claude (or other capable LLM) session to generate the corresponding document.

**Detected:** Django 5.x on Python 3.12+, server-rendered HTML with HTMX + Alpine.js, Tailwind CSS v4 via django-tailwind, Gunicorn + Caddy in Docker; PostgreSQL 16+ in production (SQLite for local dev); django-background-tasks (no Redis required); django-allauth for auth (email + Google OAuth); Resend HTTPS API for email via a custom backend (`apps.common.email_backends.ResendBackend`); Pillow + FFmpeg for media; deployable via one-click on Heroku / Render / Railway or Docker Compose on a VPS. Fourteen primary user-facing views across eighteen Django apps, integrating with twelve first-party social platform APIs (Facebook, Instagram via Facebook Login, Instagram via Instagram Login, LinkedIn Personal, LinkedIn Company, TikTok, YouTube, Pinterest, Threads, Bluesky, Google Business Profile, Mastodon). Open-source under AGPL-3.0; ICP is creators, agencies, and SMBs who manage multiple client / brand accounts and want to avoid per-seat / per-channel SaaS fees.

---

## Prompt 1 — User Guide

```text
You are a technical writer producing a user-facing how-to guide for BrightBean Studio.

Product context (use exactly as factual basis — do not invent features):
- What it is: BrightBean Studio is an open-source, self-hostable social media management platform that lets creators, agencies, and SMBs plan, compose, schedule, approve, publish, and monitor content across 12 social platforms (Facebook, Instagram via Facebook Login, Instagram Direct via Instagram Login, LinkedIn Personal, LinkedIn Company, TikTok, YouTube, Pinterest, Threads, Bluesky, Google Business Profile, Mastodon) from a single multi-workspace dashboard. Every platform integration talks to the official first-party API using the deployer's own developer credentials — no aggregator middleman.
- Target users: Creators, marketing agencies, and SMBs managing multiple client or brand accounts who want to own their social stack instead of paying per-seat / per-channel SaaS fees.
- Primary views/pages (use as section structure, in this order): Onboarding (first-run setup), Social Accounts (connect platforms via OAuth or app password), Calendar (visual scheduling with recurring slots and named queues), Composer (post editor with per-platform overrides, version history, templates), Drafts, Idea Kanban Board, Approvals, Publish Queue, Inbox (unified comments / mentions / DMs / reviews with sentiment + assignments), Media Library (org/workspace-scoped, nested folders, auto-generated platform variants), Client Portal (passwordless 30-day magic-link review for external clients), Team Members & Roles (invitations, RBAC, custom roles, Client role for external collaborators), Notifications & Preferences (in-app / email / webhook with per-event preferences), Settings (workspace defaults for hashtags / first comments / templates, platform credentials).
- Notable integrations the user will see: connecting Facebook / Instagram / LinkedIn / TikTok / YouTube / Pinterest / Threads / Bluesky / Google Business Profile / Mastodon accounts via OAuth (or app password for Bluesky); Google SSO for sign-in; client portal magic links; email invitations to teammates and clients; webhook notifications for downstream automation; encrypted storage of OAuth tokens and platform credentials.

Produce a single Markdown user guide with this exact structure:

1. # BrightBean Studio — User Guide
2. ## Welcome — 1 paragraph: what this product is, what they'll learn here.
3. ## Getting Started — the first 5 minutes (sign-up → first meaningful action). Number every step.
4. ## <View Name> — one H2 per primary view, IN THE ORDER LISTED ABOVE. Each section must contain:
   - One-sentence "What this is for"
   - 2–4 numbered task walkthroughs ("How to <verb>") covering the most common things a user does on this view
   - At least one <!-- SCREENSHOT: [exact description of what the screenshot should show] --> placeholder per task walkthrough
   - "Tips & gotchas" subsection (3–5 bullets) — quirks, common mistakes, keyboard shortcuts
5. ## Troubleshooting — top 5 issues users actually hit, each with symptom → cause → fix
6. ## FAQ — 8 questions, ordered by likely frequency

Writing rules:
- Second person ("You can…"), present tense
- Reader is non-technical; explain jargon on first use
- Bold every UI element name on first reference (e.g., **Send Invitation**)
- Number every step (no bare bullet lists for procedures)
- Keep paragraphs ≤3 sentences
- Insert a screenshot placeholder before each procedure AND at every state change ("after clicking Submit, you'll see…")
- Do not invent features not listed in product context

Output: a single Markdown file ready to publish at docs/user-guide.md.
```

---

## Prompt 2 — Technical Architecture

```text
You are a senior engineer producing internal architectural documentation for BrightBean Studio.

Project facts (verified from the codebase — do not invent):
- Stack: Django 5.x on Python 3.12+, server-rendered HTML with HTMX + Alpine.js for interactivity, Tailwind CSS v4 via django-tailwind, Gunicorn + Caddy in Docker, django-allauth for auth (email + Google OAuth), Pillow + FFmpeg for media processing.
- Deployment target: Self-hosted via Docker Compose on a VPS (production override adds Caddy for auto-HTTPS and a one-shot migrate container) or one-click deploy to Heroku, Render, or Railway. Production runs three roles: web (Gunicorn), worker (django-background-tasks `process_tasks`), and PostgreSQL.
- Persistence: PostgreSQL 16+ in production; SQLite supported for local dev. ORM is Django's. Per-tenant scoping enforced via `apps/common` `OrgScopedManager`.
- External integrations: First-party API integrations to 12 social platforms (Facebook Graph, Instagram Graph via Facebook Login, Instagram API with Instagram Login, LinkedIn Personal v2 / Community Management, TikTok Login Kit + Content Posting, YouTube Data v3, Pinterest API, Threads API, Bluesky AT Protocol, Google Business Profile, Mastodon per-instance OAuth). Email via SMTP or — preferred at runtime — Resend HTTPS API through a custom backend `apps.common.email_backends.ResendBackend`. Media on local FS (dev) or S3-compatible storage (prod). Optional Sentry. Optional outbound webhook delivery for notifications.
- Multi-tenancy / data-scoping model: User → OrgMembership → Organization → Workspace → WorkspaceMembership (per-user, per-workspace role + custom permission overlay). Each model that holds tenant data uses `OrgScopedManager` to prevent cross-org leaks. Client users access only the Client Portal via 30-day passwordless magic links.
- Key modules / apps (use as deep-dive structure, in this order): accounts, organizations, workspaces, members, social_accounts, providers, composer, calendar, approvals, publisher, inbox, media_library, notifications, client_portal, onboarding, settings_manager, credentials, common.
- Repo root for path references: brightbean-studio (paths look like `apps/<app>/<file>.py:LN`, `config/settings/*.py`, `templates/<app>/<view>.html`, `theme/static_src/src/styles.css`, `providers/<platform>.py`).

Produce a single Markdown architecture document with this structure:

1. # Architecture — BrightBean Studio
2. ## Executive Summary — 200 words: what the system does, key architectural choices, why they were made
3. ## System Architecture
   - One Mermaid `graph TB` diagram showing major components and their relationships
   - One paragraph per major component
4. ## Deployment Topology
   - Where each component runs (web, worker, db, edge, third-party APIs)
   - Mermaid `graph LR` showing request and data flow at the infrastructure layer
5. ## Data Model
   - One Mermaid `erDiagram` covering the core entities (top 8–12 tables) — likely User, Organization, OrgMembership, Workspace, WorkspaceMembership, CustomRole, Invitation, SocialAccount, Post, ApprovalStage, NotificationDelivery, MediaAsset
   - One-paragraph description of the relationships and any unusual modeling choices (e.g., the dual Instagram connector paths via Facebook Login vs Instagram Login, OrgScopedManager enforcement at the manager level)
6. ## Request Lifecycle
   - One Mermaid `sequenceDiagram` of the most important user flow: composing → submitting for approval → publishing to a connected social account
   - Annotate which middleware/auth layers fire and in what order (allauth, org-scope middleware in apps/members, decorators like `@require_org_role`)
7. ## Module Deep-Dives — one H3 per module from the list above. Each must contain:
   - **Purpose:** 1–2 sentences
   - **Key files:** 3–6 paths with one-line role descriptions, format `path/to/file.ext:LN — role`
   - **Public interface:** what other modules call into this one (functions, models, signals)
   - **Notable patterns:** anything non-obvious (e.g., "uses django-background-tasks for async sends"; "providers/<platform>.py is the integration boundary — nothing outside providers/ talks raw to a platform API")
   - **One representative code excerpt:** ≤15 lines, fenced, with `path:LN` caption
8. ## External Integrations — one H3 per integration. Each must cover:
   - API used (REST / GraphQL / SDK)
   - Auth model (OAuth flow, API key, app password, signed JWT)
   - Where in the codebase the integration lives (typically `providers/<platform>.py` plus `apps/social_accounts/`)
   - Failure handling (retry, circuit-break, log-and-swallow, surface to user) — note the publisher's automatic retry, per-account rate-limit tracking, and 90-day audit log
9. ## Security Model
   - Authentication (allauth sessions, Google OAuth; MFA / 2FA TOTP roadmapped, not shipped)
   - Authorization (org role: owner / admin / member; workspace role: owner / manager / editor / contributor / client / viewer + custom permission overlays)
   - Tenant isolation (OrgScopedManager, decorators in apps/members, per-request `request.org` / `request.org_membership`)
   - Secrets handling (encrypted token storage in apps/credentials using Fernet-style encryption from apps/common, ENCRYPTION_KEY_SALT env var)
   - Known threats and mitigations (CSP, CSRF, encrypted-at-rest tokens, 14-day reversible org-deletion grace period)
10. ## Async / Background Jobs
    - Queue technology: django-background-tasks (no Redis required; uses the DB as queue)
    - Worker setup (`python manage.py process_tasks`)
    - Catalog: scheduled publishing, retry of failed publishes, daily notification digests, inbox webhook ingestion / backfill, OAuth token refresh, link expiry cleanup
11. ## Observability
    - Logging (StreamHandler to stdout, captured by Gunicorn → platform log streams; format `{levelname} {asctime} {module} {message}`)
    - Optional Sentry integration
    - HTTP access logs via the platform's edge (Caddy, Heroku router, Railway proxy)
12. ## Known Issues / Tech Debt — bulleted list, each with file path and 1-line description (e.g., the SMTP path in `config/settings/base.py:237` is preserved but unused in prod since `EMAIL_BACKEND_TYPE=resend` selects the HTTP backend; some HTMX listeners may still need the `.camel` modifier for HTMX 2.x camelCase events; Tailwind v4 uses an `@theme` block to remap orange-* utilities to the brand palette in `theme/static_src/src/styles.css` rather than rewriting every utility class)
13. ## Glossary — every domain term used in the doc

Writing rules:
- Cite real file paths everywhere (format: `path/to/file.py:42`)
- All diagrams in Mermaid (renders in GitHub)
- Use the codebase as ground truth — read files before claiming behavior
- One code excerpt per module section, no more
- Don't editorialize ("this is great") — describe behavior

Output: a single Markdown file ready for an engineering wiki at docs/architecture.md.
```

---

## Prompt 3 — Sales Pitch

```text
You are a B2B SaaS positioning expert producing a sales pitch deck for BrightBean Studio.

Product context:
- Tagline: "Own your social stack — schedule, approve, and publish across every channel without paying per seat or per workspace."
- One-paragraph description: BrightBean Studio is an open-source (AGPL-3.0), self-hostable social media management platform that does what Sendible / SocialPilot / ContentStudio do — plan, compose, schedule, approve, publish, and monitor content across 12 platforms — but free, with no per-seat / per-channel / per-workspace limits. Direct first-party API integrations (no aggregator middleman), encrypted credential storage, multi-workspace + RBAC, a built-in client portal with 30-day passwordless magic links, and a unified inbox that pulls comments, mentions, DMs, and reviews from every connected platform into one place.
- Core capabilities (used as outcome-focused slides): unlimited orgs / workspaces / members with granular RBAC and a dedicated Client role; rich content composer with per-platform caption / media overrides, version history, templates, content categories & tags, and a Kanban idea board; visual calendar with recurring per-account posting slots and named queues that auto-assign posts to the next available slot; first-party publishing engine with automatic retries, per-account rate-limit tracking, and a 90-day publish audit log; configurable approval workflows (none / optional / internal / internal + client) with threaded comments and reminders; unified social inbox with sentiment analysis, assignments, threaded replies, and historical backfill; org- and workspace-scoped media library with auto-generated platform-optimized variants; passwordless 30-day magic-link client portal; notifications across in-app / email / webhook with per-event preferences; encrypted credential storage and a 14-day reversible org-deletion grace period.
- Differentiators vs alternatives: open-source / self-hostable (data and OAuth tokens stay on the customer's infrastructure); no aggregator middleman (every platform call uses your own developer credentials); supports the long-tail platforms incumbents ignore (Mastodon, Bluesky, Threads, Google Business Profile) alongside the big four; permission system fine-grained enough for agency workflows including external client review; one-click deploy to Heroku / Render / Railway or Docker Compose on a VPS; AGPL license — every feature in every install, no paid tier, no feature gate, no upsell.
- Pricing model (if known): Open-source / self-hosted; no SaaS pricing tier shipped. (illustrative pricing slide should compare hosting cost vs. typical SaaS per-seat fees: $100–300/month per seat × team size.)
- Ideal customer profile: Marketing agencies running 5–50 client brands; in-house social/marketing teams of 3–15 at SMB and mid-market companies; multi-location operators (franchises, restaurant groups, real-estate brokerages, multi-clinic healthcare) where each location is a workspace; agencies that have outgrown a per-seat SaaS and want to control their data and OAuth credentials.
- Three vertical use cases to feature: Marketing & creative agencies managing 20+ client brands; multi-location franchise / restaurant groups (one workspace per location, central approval); D2C / e-commerce brands publishing across 6+ social channels with a small team that can't afford per-channel SaaS fees.

Produce a single Markdown deck outline. Use `## Slide N — <Title>` headings. Each slide MUST contain these labelled blocks:

**Headline:** one memorable line in customer language (≤10 words).
**Subhead:** ≤15 words, supporting the headline.
**Bullets:** 3–5 talking points written as customer outcomes, not features.
**Speaker notes:** 1–2 sentences with the underlying narrative beat the salesperson should land.
**Visual:** one suggestion in brackets (e.g., [Screenshot: …], [Chart: …], [Diagram: …]).

Slide list (use this exact order and count — 18 slides):

1. **Slide 1 — Title.** Product name, tagline, presenter name placeholder.
2. **Slide 2 — The Problem.** A real-world day-in-the-life vignette of the customer's current pain (e.g., a 12-person agency juggling 30 client brands across 8 platforms, paying $100+/seat to a SaaS that still meters channels).
3. **Slide 3 — The Old Way.** 1–2 incumbent alternatives (Sendible, SocialPilot, ContentStudio) and their concrete failure modes (per-seat caps, per-channel fees, vendor sitting between you and the platform's data, limited platform coverage, opaque rate limits).
4. **Slide 4 — Introducing BrightBean Studio.** The "after" world — what the customer's day looks like with the product (one calendar, one inbox, one approval flow, all platforms, one bill: their hosting).
5. **Slides 5–8 — Core Capabilities (4 slides).** One per top capability. Frame as "What you get" + "Why it matters." Pick the 4 that map most directly to the buyer's job (suggested: unlimited workspaces + RBAC; visual calendar with recurring slots & queues; approval workflow with built-in client portal; unified inbox across every platform).
6. **Slide 9 — Use Case: Marketing & creative agencies managing 20+ client brands.** Industry-specific scenario; concrete numbers; quote the buyer persona (e.g., agency operations director).
7. **Slide 10 — Use Case: multi-location franchise / restaurant groups (one workspace per location, central approval).** Same shape, different vertical (e.g., 40-location restaurant group, brand consistency, local content + local replies).
8. **Slide 11 — Use Case: D2C / e-commerce brands publishing across 6+ social channels with a small team.** Same shape, third vertical (e.g., a 4-person team running organic on Instagram + TikTok + Pinterest + YouTube + Facebook + Threads).
9. **Slide 12 — ROI.** Quantified value: time saved, revenue gained, cost reduced. Show the math even if illustrative — e.g., "12-person agency × $80/seat SaaS = $11,520/yr; self-hosted server = ~$300/yr; payback < 1 month."
10. **Slide 13 — Why Us.** Differentiation: open-source, no aggregator middleman, long-tail platform support, ownership of your data and OAuth tokens, every feature unlocked in every install.
11. **Slide 14 — Proof.** Customer logos placeholder; testimonial placeholder with [Name, Title, Company] brackets.
12. **Slide 15 — Pricing & Packaging.** Tiers (illustrative since pricing model is open-source self-host). Compare to per-seat SaaS at $100–300/mo × seats; show hosting-cost order of magnitude on Hetzner / DigitalOcean / Railway.
13. **Slide 16 — Time-to-Value.** Implementation timeline; days-to-first-value (one-click deploy in 15 min; OAuth credentials per platform 30 min – 2 days depending on platform review).
14. **Slide 17 — Call to Action.** One specific next step — e.g., "Spin up a 14-day pilot on Railway in 15 minutes — we'll walk through OAuth setup live."
15. **Slide 18 — Appendix: Technical Depth.** FAQ-style: AGPL-3.0 license, encrypted-at-rest credential storage, multi-workspace tenant isolation via OrgScopedManager, no Redis required (django-background-tasks), supported platforms matrix, deploy targets (Heroku / Render / Railway / Docker Compose), data residency (the customer's infrastructure), backup & DR posture.

Writing rules:
- Customer language, not vendor language. Avoid "robust," "best-in-class," "leverages."
- Concrete numbers wherever possible; mark estimates "(illustrative)".
- Each slide advances exactly one buying decision.
- Speaker notes carry the emotional beat; bullets carry the logical content.
- No marketing fluff in the appendix — be technical.

Output: a single Markdown file at docs/sales-pitch.md.
```
