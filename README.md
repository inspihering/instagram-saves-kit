# Instagram Saves to Notion

Syncs your Instagram saved posts into a Notion database automatically on a daily schedule. macOS only.

## What you'll need

- An Instagram account
- A Notion account
- About 10 minutes

## Setup

Open this folder in Claude Code and say "set this up for me." Claude will follow `INSTALL.md` and walk you through it step by step.

## How it works

- Pulls your saved posts via Instagram's web API using your session cookie.
- Writes new ones to a Notion database you control.
- Runs twice daily via launchd. State is tracked locally so posts are never duplicated.

## Note

macOS only, since scheduling uses launchd.
