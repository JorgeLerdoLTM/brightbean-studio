# BrightBean Studio Agent Skill

A Claude Code skill that teaches another Claude Code instance how to push
AI-generated images, videos, and draft posts into a running BrightBean
Studio deployment.

## Install

In the **receiving** Claude Code session (the one that runs your
content-generation agent — usually a different repo / directory than
brightbean-studio):

```bash
mkdir -p ~/.claude/skills
cp -r /path/to/brightbean-studio/docs/agent-skill ~/.claude/skills/brightbean-studio-agent
```

Replace `/path/to/brightbean-studio` with wherever you have the
brightbean-studio repo checked out. After this, the next Claude Code
session in that directory (and every directory) sees the skill.

## Configure

Set two environment variables on the agent's machine — the skill checks
them on first use, then caches the resolved scope in
`~/.config/brightbean-agent/whoami.json` so subsequent calls are zero-config:

```bash
export BRIGHTBEAN_URL=https://socials.figus.ai
export BRIGHTBEAN_API_KEY=bbs_<the_full_token_from_create_api_key>
```

Or put them in `~/.config/brightbean-agent/.env` (file mode `600`):

```env
BRIGHTBEAN_URL=https://socials.figus.ai
BRIGHTBEAN_API_KEY=bbs_<the_full_token>
```

Either way the skill auto-detects.

## Use

In the receiving Claude Code session, just describe what you want done.
The skill is triggered by any of these patterns:

- "Upload `foo.png` to my Brightbean media library."
- "Save this image to the figus media library with alt text 'X'."
- "Create a draft post in Brightbean with this image and these captions."
- "Push these four images to BrightBean as a draft for Instagram and LinkedIn."

The agent uses [httpx](https://www.python-httpx.org/) (already a brightbean
runtime dep, but on the AGENT's machine you may need
`pip install httpx`) — no other dependencies.

## What gets created on the BrightBean side

- A new MediaAsset (or several) in the workspace's library, tagged with
  `source="agent"` so admins can filter by provenance.
- Optionally, a draft Post in the composer with the caption you provided,
  pre-targeted at the platforms you listed, ready for a human to review
  and schedule.

## Troubleshooting

See [`../agent-integration.md`](../agent-integration.md) for the full
endpoint reference and error-code table. The skill includes inline
diagnostic checks that re-validate `BRIGHTBEAN_API_KEY` and clear the
cached `whoami.json` when scope mismatches are detected.
