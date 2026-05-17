# Setting Up a New BrightBean Content Agent

This is the step-by-step manual for connecting a new content-creation
agent (a separate Claude Code session) to your running BrightBean Studio.
End state: you say "upload this image to my Brightbean and draft a post"
in any Claude Code window, and it just works.

Time required: **5 minutes** after the first setup.

---

## Pre-flight checklist

Before you start, make sure:

- [ ] BrightBean Studio is deployed and reachable at a URL (e.g. `https://socials.figus.ai`). The `/api/v1/whoami/` endpoint should return `401` for an unauthenticated `curl`.
- [ ] You have Railway CLI installed locally and are logged in (`railway login`) — needed to mint the first API key.
- [ ] The receiving machine has Claude Code installed (this is whichever computer your *content-creation* agent will run on; it can be the same machine that hosts brightbean-studio or a totally different one).
- [ ] Python 3 with `httpx` is available on the agent's machine (`pip install httpx`).

---

## Step 1 — Decide the scope

You're about to mint a credential that grants write access to one tenant
boundary. Pick one:

| Scope | Pick when |
|---|---|
| **Workspace** (recommended) | The agent writes for *one brand*. One agent per brand keeps the blast-radius small. The agent can only upload assets into that workspace and draft posts targeting that workspace's connected social accounts. |
| **Organization (shared)** | The agent writes assets that should be visible to *every* workspace in the org. No composer access — drafts always need a workspace. Use only for cross-brand asset libraries. |

You can have multiple keys per scope. The recommendation for a typical
agency: **one workspace key per client brand**, plus optionally one
org-shared key for evergreen assets.

---

## Step 2 — Mint the API key

### Option A — CLI (works today)

On your local machine, with the brightbean-studio repo as the linked
Railway project:

```bash
# Find the org and workspace IDs:
railway ssh --service brightbean-studio-web \
  'python manage.py shell --command "
from apps.organizations.models import Organization
from apps.workspaces.models import Workspace
for o in Organization.objects.all():
    print(o.id, o.name)
    for w in Workspace.objects.filter(organization=o):
        print(\" \", w.id, w.name)
"'

# Mint a workspace-scoped key:
railway ssh --service brightbean-studio-web \
  'python manage.py create_api_key \
    --org-id <ORG_UUID> \
    --workspace-id <WORKSPACE_UUID> \
    --name "Acme content agent"'

# Or an org-shared key (omit --workspace-id):
railway ssh --service brightbean-studio-web \
  'python manage.py create_api_key \
    --org-id <ORG_UUID> \
    --name "Org-wide asset agent"'
```

The command prints the full token **exactly once**. Copy it before
pressing Enter on the next thing. If you lose it, revoke the key (below)
and mint a new one.

### Option B — Settings UI (after the UI ships)

Workspace owners: `Settings → API Keys → Create new key`. Org owners:
`Organizations → Settings → API Keys → Create new key`. Same model, same
one-shot reveal, just no SSH.

---

## Step 3 — Set up the receiving machine

On whichever computer your agent will run on:

```bash
# Make a config dir for the agent's secrets
mkdir -p ~/.config/brightbean-agent
chmod 700 ~/.config/brightbean-agent

# Drop the credentials into a .env file (locked-down permissions)
cat > ~/.config/brightbean-agent/.env <<'EOF'
BRIGHTBEAN_URL=https://socials.figus.ai
BRIGHTBEAN_API_KEY=bbs_paste_the_full_token_here
EOF
chmod 600 ~/.config/brightbean-agent/.env
```

**Verify the credentials work** by running a one-shot whoami:

```bash
# Source the file into the current shell (one-time, just for verification)
set -a; source ~/.config/brightbean-agent/.env; set +a

curl -sS -H "Authorization: Bearer $BRIGHTBEAN_API_KEY" \
  "$BRIGHTBEAN_URL/api/v1/whoami/" | python3 -m json.tool
```

You should see a JSON response with `"scope"`, `"organization_name"`, and
`"workspace_name"`. If you see `401 invalid_token`, the token was
mistyped — fix the `.env` and retry. If you see `Connection refused` or
DNS errors, fix `BRIGHTBEAN_URL`.

---

## Step 4 — Install the agent skill

The brightbean-studio repo ships a Claude Code skill that teaches the
agent how to use the API. Copy it into the agent's machine's skills dir:

```bash
# If you have brightbean-studio checked out locally:
cp -r /path/to/brightbean-studio/docs/agent-skill \
      ~/.claude/skills/brightbean-studio-agent

# Or grab just the skill from GitHub:
mkdir -p ~/.claude/skills
git clone --depth 1 --filter=tree:0 --sparse \
  https://github.com/JorgeLerdoLTM/brightbean-studio.git /tmp/bb-clone
cd /tmp/bb-clone && git sparse-checkout set docs/agent-skill && cd -
cp -r /tmp/bb-clone/docs/agent-skill ~/.claude/skills/brightbean-studio-agent
rm -rf /tmp/bb-clone
```

Verify the skill registered:

```bash
ls ~/.claude/skills/brightbean-studio-agent/SKILL.md
```

The next Claude Code session you open will see the skill in its list of
available skills.

---

## Step 5 — Smoke-test the full loop

Open a fresh Claude Code session **on the agent's machine, in any
directory**. Say:

> Use the brightbean-studio-agent skill to check connectivity, then
> upload `~/Pictures/test.png` with alt text "test from agent" and a
> tag "smoke-test".

The agent should:

1. Read `~/.config/brightbean-agent/.env` (or the env vars).
2. Call `/whoami` and tell you which workspace it's connected to.
3. Validate the file (size + MIME).
4. POST the upload, get back an asset ID.
5. Poll the asset until `processing_status == "completed"`.
6. Show you the studio URL where you can see it.

Click the link the agent gives you. You should see your test PNG in the
Media Library grid with `source="agent"` and your tag.

---

## Step 6 — Real usage patterns

Once verified, here's what you can ask the agent to do. The skill
handles all the wire details automatically.

### Simple asset upload

> "Upload this image at `./generated.png` to BrightBean. Alt text:
> 'Spring 2026 campaign hero, model wearing the orange jacket on a
> beach.' Tag it `campaign-spring-2026`."

### Multi-asset draft for multiple platforms

> "Take these four images in `./out/`, upload them, then draft a single
> post for Instagram and LinkedIn Company with this caption:
>
> `Spring drop arrives Friday. 12 colorways, all sustainably sourced.`
>
> Give LinkedIn a more professional variant of the caption."

The agent will upload all four (in order), wait for processing, then
create a Post in the composer with a `compose_url` you can click to
review.

### Generate and upload in one go

> "Generate a 1080×1080 image of a black cat on a red rug using SDXL.
> Once generated, upload it to BrightBean with a clear alt-text."

(Requires whatever image-gen tool the agent has access to. The
brightbean side doesn't care how the file was produced.)

### Schedule directly from the agent

> "Upload `./hero.jpg` and draft a post for Instagram scheduled for
> Friday 9am Mexico City time. Caption: 'Available now.'"

The agent passes `schedule_at` as ISO-8601 with the right offset. A human
still has to approve the post in BrightBean's UI to actually publish —
the agent only drafts.

---

## Step 7 — Operating multiple agents

Each agent should have its **own key**. To add a second agent (for a
different brand, a different machine, a different model):

1. Repeat Step 2 with a new `--name` (e.g. "Beta brand agent").
2. Repeat Step 3 on that agent's machine with the new key.
3. Repeat Step 4 if the skill isn't already there.

Don't share a key between agents. If one leaks, you can revoke just that
one without impacting the others.

---

## Step 8 — Rotating and revoking keys

### Rotate a key

```bash
# Mint a new one with the same scope
railway ssh --service brightbean-studio-web \
  'python manage.py create_api_key --org-id <ORG> --workspace-id <WS> --name "Acme — rotated 2026-06-01"'

# Update the agent's .env on its machine
# Test with curl /whoami
# Revoke the old key (next section)
```

### Revoke a key

```bash
# Find it by its prefix (visible in your last successful curl, in API logs, or in the UI)
railway ssh --service brightbean-studio-web \
  'python manage.py shell --command "
from apps.api.models import APIKey
from django.utils import timezone
n = APIKey.objects.filter(token_prefix=\"bbs_kx9Lp2v8\", revoked_at__isnull=True).update(revoked_at=timezone.now())
print(f\"Revoked {n} keys\")
"'
```

Once the Settings UI ships, this becomes a "Revoke" button on each row.

---

## Troubleshooting

| Symptom | Diagnosis | Fix |
|---|---|---|
| `curl /whoami/` returns `401 missing_or_malformed_authorization` | No `Authorization: Bearer ...` header on the request. | Add the header. Check your `.env` is being sourced. |
| `curl /whoami/` returns `401 invalid_token` | Token doesn't match any hash in DB. | Mistyped or revoked. Re-mint. |
| Agent says "I don't know how to upload to BrightBean" | The skill isn't installed (or the agent's Claude Code session was opened before the skill was added). | Confirm `~/.claude/skills/brightbean-studio-agent/SKILL.md` exists and restart the session. |
| Upload returns `422 validation_failed` | File too big or wrong MIME. | Convert / shrink. Limits: 20 MB images, 1 GB video. |
| Draft creation returns `422 no_connected_account_for_platforms` | One of the requested platforms has no connected social account in the workspace. | Connect the missing account in the studio first. The error body lists which platforms are missing. |
| Upload returns `429` | You've hit 600 requests / hour on this token. | Back off 60 s and retry, or split work across multiple agents (each with its own key). |

If you hit something not in this table, paste the response body into a
new Claude Code session in the brightbean-studio repo — it has the
codebase context and can dig in.

---

## Appendix A — Self-setup prompt (paste into a fresh agent session)

If you'd rather give the agent itself a single block of instructions for
self-setup, paste this into a new Claude Code session on the agent's
machine. The agent walks itself through Steps 3–5 above and confirms
ready.

```text
You are about to be configured as a BrightBean Studio content agent.
Your job, before doing any creative work, is to complete the connection
to a running BrightBean instance. Walk through these steps and stop only
when /whoami returns 200.

1. CHECK SKILL: Run `ls ~/.claude/skills/brightbean-studio-agent/SKILL.md`.
   If missing, ask the user where the brightbean-studio repo is checked
   out, then run:
     cp -r <repo>/docs/agent-skill ~/.claude/skills/brightbean-studio-agent
   Re-check that the file now exists.

2. CHECK CONFIG: Look for BRIGHTBEAN_URL and BRIGHTBEAN_API_KEY in:
   a) shell environment
   b) ~/.config/brightbean-agent/.env (parse `KEY=VALUE` lines)
   If both are missing, ask the user:
     - "What's your BrightBean URL? (e.g. https://socials.figus.ai)"
     - "Paste your API key (starts with bbs_):"
   Persist to ~/.config/brightbean-agent/.env, then `chmod 600` the file.
   Never echo the token back into the chat.

3. VERIFY: Call
     curl -sS -H "Authorization: Bearer $BRIGHTBEAN_API_KEY" \
       "$BRIGHTBEAN_URL/api/v1/whoami/"
   Expect HTTP 200 with a JSON body containing
   "scope", "organization_name", "workspace_name", "scopes".

4. CACHE: Write the whoami JSON to
     ~/.config/brightbean-agent/whoami.json
   so future calls in this session can read scope without another round-trip.

5. CONFIRM: Tell the user, in one sentence:
     "I'm connected to <workspace_name or organization_name> as
      <key_name> (prefix <key_prefix>). I can upload assets, list folders,
      and (workspace keys only) create draft posts. Ready when you are."

6. ERROR RECOVERY:
   - On 401: re-ask for the key once, retry once, then surface the error.
   - On any other non-200: surface the response body and stop.

After these steps complete successfully, await the user's first creative
task. When they describe one, load the
~/.claude/skills/brightbean-studio-agent/SKILL.md skill before responding.
```

---

## Appendix B — Meta-prompt for regenerating this manual

If you want to regenerate this manual for a fork, a customized deployment,
or a different agent runtime, paste this prompt into a fresh Claude
session with the brightbean-studio repo as your working directory:

```text
You are a technical writer producing a setup manual for a BrightBean
Studio content-creation agent. The manual is for an operator setting up
a new agent on their own machine, from scratch.

Project context (verify against the actual codebase before claiming
anything):
- BrightBean Studio is a Django app with a public REST API at /api/v1/
- Per-tenant API keys via apps/api/APIKey (see apps/api/models.py)
- Auth: bearer token in Authorization header
- Endpoints documented in docs/agent-integration.md
- Agent-side Claude Code skill at docs/agent-skill/SKILL.md
- Production base URL is in the BRIGHTBEAN_URL env var on the operator's
  side; the API is deployed wherever the operator runs the app

Produce a single Markdown manual at docs/setup-new-agent.md with this
structure:

1. Title + one-paragraph intent (what end-state we're heading to)
2. Pre-flight checklist (3–6 boxes the operator must satisfy)
3. Step-by-step numbered sections, one per major action:
   - Decide scope (workspace vs org)
   - Mint the API key (CLI now; UI when shipped)
   - Set up the receiving machine (config dir, .env, perms)
   - Install the agent skill (cp from local, or sparse-checkout from GitHub)
   - Smoke-test the full loop
   - Real usage patterns (4–6 concrete example prompts the operator can paste)
   - Operating multiple agents
   - Rotating and revoking keys
4. Troubleshooting table (symptom → diagnosis → fix), at least 6 rows
5. Appendix: a self-setup prompt the operator can paste into a fresh
   agent session to bootstrap it without reading the manual

Writing rules:
- Second person ("You can…")
- Reader has Claude Code experience but no specific BrightBean knowledge
- Every shell command must be copy-pasteable as-is (no <PLACEHOLDER> that
  blocks running)
- Cite real file paths from the repo when describing where things live
- No marketing fluff; this is operator documentation, not sales

Output a single .md file ready to commit at docs/setup-new-agent.md.
```
