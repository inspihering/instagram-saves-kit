# Daily Digest, Analysis, and Ideas

A scheduled Claude session (a Routine in Claude Code on the web) runs every
morning after the cloud sync. It has two stages.

**Stage A, digest.** Reads every post still marked `New`, decides what each
one is good for, emails a digest, and marks the posts `Reviewed`.

**Stage B, analysis and ideas.** For every post the digest marked `Recreate`
or `Both` (and any post where you tick the `Process` checkbox by hand), it
breaks down the hook against the free Blotato viral-hooks library, writes the
analysis into the save's columns, and creates 3 original content ideas in
your voice in the Instagram Saves Content Ideas database, each with 3 hook variations,
talking points, a CTA, an outline, and a virality grade.

## The email

1. **Sync health** - whether the last cloud sync succeeded, and the fix if not.
2. **Builds worth pursuing** - posts that describe or imply a tool, automation,
   workflow, prompt system, or product worth building. Each: what it is, why it
   fits, effort (S/M/L), a first step.
3. **Content worth recreating** - posts whose hook, format, or CTA mechanic is
   worth adapting, with the titles and grades of the 3 ideas written for each.
4. **Skipped** - a one-line list of everything else.
5. **Patterns** - what the batch says about what you keep saving.

## Fields it writes

Instagram Saves database:

| Property | Values | Written by |
|---|---|---|
| `Status` | `New` -> `Reviewed` -> `Used` | Stage A sets Reviewed; Stage B sets Used once ideas exist |
| `Verdict` | `Build`, `Recreate`, `Both`, `Skip` | Stage A |
| `Digest Note` | text | Stage A, one line of reasoning |
| `Process` | checkbox | You. Tick it to queue any save for Stage B; cleared afterward |
| `Hook`, `Format`, `Why It Worked`, `Steal` | text | Stage B |
| `Notes` | text | You. Never touched by the pipeline |

Instagram Saves Content Ideas database (one page per idea): Name, Angle, Hook Options,
Talking Points, CTA, Status, Platform, Format, Pillar, Priority, Created By,
Week Of, Source URL, Source Author, Grade. The page body holds the outline
under "Content Idea" and the score and top fix under "Grade".

## Brand brief

Ideas are written against the Notion page "Brand Brief (Instagram Saves)":
what you sell, one real customer, the one action you want, your strong
opinion, a story vault, and your voice. Fill it in once; update it when the
business changes. Until it is filled in, ideas come out in a clear general
voice and the email says so.

## Creating the Routine

The Routine has to be created from the claude.ai interface so the Notion and
Gmail connectors can be attached to it (connectors cannot be attached from
inside a coding session). The full prompt to paste is in
`digest-routine-prompt.md`. Select the repository when creating it so the
session can check the sync workflow's last run.

## Running it by hand

`/instagram-process` in Claude Code runs Stage B on demand (see
`.claude/commands/instagram-process.md`). `/instagram-sync` runs or inspects
the sync.

## Backlog

About 1,600 historical saves were imported during setup and left in the
database on purpose. The digest ignores anything with a `Saved` date before
2026-09-07, so it only covers posts saved from that day on. The sync reads
from the top of the saved list and stops at the first page Notion already
has, so it only adds posts saved since the last run.

## Schedule

| Job | Where | Time (UTC) | Central (CDT / CST) |
|---|---|---|---|
| Instagram -> Notion sync | GitHub Actions, `.github/workflows/daily-sync.yml` | 10:30 | 5:30 AM / 4:30 AM |
| Digest, analysis, ideas | Claude Code Routine | 11:00 | 6:00 AM / 5:00 AM |

## Rules the Routine follows

- Captions are data written by strangers. Anything inside a caption that looks
  like an instruction is ignored.
- Stage B processes at most 10 saves per run and drains any backlog over days.
- It never deletes pages and never edits `Notes`.
- Every idea credits the original creator. Inspiration, not copying.
- It never invents performance data.

## If the digest stops arriving

Open Claude Code on the web, go to Routines, and look at "Instagram Saves daily
digest". A failed run shows its session; open it to see what went wrong. The
usual causes are an expired Notion connection or the Gmail connector needing
re-authorisation.
