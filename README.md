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
- Runs twice daily via launchd on the Mac, and once daily in the cloud via
  GitHub Actions. The sync dedupes against Notion itself, so running from
  both places never creates duplicates.
- A daily digest (see `DIGEST.md`) reads the new saves each morning, sorts
  them into builds worth pursuing and content worth recreating, emails the
  result, and marks them reviewed in Notion.
- For every save worth recreating, the same session analyses the hook against
  the free Blotato viral-hooks library, writes Hook / Format / Why It Worked /
  Steal into the save, and creates 3 graded content ideas in your voice in a
  Content Ideas database. Tick the `Process` checkbox on any save to queue it
  by hand. `/instagram-process` runs the same stage on demand.

## Note

The launchd schedule is macOS only. The cloud sync and the digest run without
the Mac; see the "Cloud sync" section of `INSTALL.md`.
