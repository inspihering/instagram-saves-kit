# Install

This sets up automatic syncing of your Instagram saved posts into a Notion database, running on a daily schedule via macOS launchd. macOS only.

## Step 1 - Prerequisites

Gather these before continuing.

**Instagram sessionid, csrftoken, and user id:**
1. Open Chrome, log in to instagram.com.
2. Press Cmd+Option+I to open DevTools.
3. Go to the Application tab.
4. In the left sidebar, expand Cookies and select `https://www.instagram.com`.
5. Copy the Value column for these three cookies: `sessionid`, `csrftoken`, and `ds_user_id`.

**Notion integration token:**
1. Go to notion.so/profile/integrations.
2. Click New integration, name it "Instagram Saves".
3. Under Capabilities, enable Read content, Insert content, and Update content.
4. Copy the Internal Integration Secret (starts with `ntn_`).

## Step 2 - Provision the Notion database

Ask the user: do you already have a Notion database set up for this with the required schema below, and do you want to reuse it?

- If yes: get the database id and skip to the connection step below.
- If no: create a new database in the user's Notion (via a connected Notion integration if available, otherwise give the user manual create-it steps) with EXACTLY these properties:
  - `Name` (title)
  - `URL` (url)
  - `Type` (select: Post, Reel, Carousel, IGTV)
  - `Author` (text / rich_text)
  - `Status` (select: New, Reviewed, Used, Archived)
  - `Media ID` (text / rich_text)
  - `Saved` (date)
  - `Caption` (text / rich_text)
  - `Collection` (select)
  - `Verdict` (select: Build, Recreate, Both, Skip)
  - `Digest Note` (text / rich_text)
  - `Process` (checkbox)
  - `Hook`, `Format`, `Why It Worked`, `Steal`, `Notes` (text / rich_text)

  The first nine are used by the sync; the rest by the digest and the
  analysis stage (see `DIGEST.md`).

Also create a second database, **Content Ideas**, where generated ideas land:
  - `Name` (title), `Angle`, `Hook Options`, `Talking Points`, `CTA` (text)
  - `Status` (status: Not started, In progress, Done)
  - `Platform` (multi-select: Instagram, TikTok, YouTube)
  - `Format` (select: Reel, Carousel, Short Video, Long-form Video)
  - `Pillar` (select: Teach, Proof, Behind the Build, Objections, Problems, Process, Tools, Point of View, Personal; ask the user if they want different pillars)
  - `Priority` (select: High, Medium, Low)
  - `Created By` (select: Claude, ChatGPT)
  - `Week Of` (date), `Source URL` (url), `Source Author` (text), `Grade` (number)

And a plain page, **Brand Brief (Instagram Saves)**, with sections Business,
Customer, Primary CTA, Strong Opinion / Wedge, Story Vault, Voice, Content
Pillars. Fill it in with the user by asking, one at a time: what they sell;
one real customer; the one action they want; a strong opinion most peers
would push back on; one recent story or win; their voice in 2 or 3 traits.

IMPORTANT: whether the database is new or existing, the integration must be connected to it. In Notion: open the database, click the `...` menu, go to Connections, and add the "Instagram Saves" integration.

Capture the resulting database id (from the database URL or share link) before moving on.

## Step 3 - Configure

Copy `config.example.json` to `config.json`.

Ask the user for each of these choices one at a time. Offer the default, never assume:

1. **Which saved collections to sync?** All of them (default: leave `collections_filter` as `[]`), or specific ones (ask for the exact Instagram collection names as a JSON array).
2. **What times should the daily sync run?** Default: 9am and 9pm (21:00). These become `{{HOUR_1}}` and `{{HOUR_2}}` in the scheduler.

3. **Collection names.** Instagram no longer lists collections through its web
   API, so collection names are only filled in when the ids are configured. After
   the first sync, run `.venv/bin/python3 sync.py --discover-collections`, match
   each id to a collection name in the Instagram app, and write the mapping into
   `collection_ids`. Skip this if the user does not care about the Collection column.

Write into `config.json`:
- `ig_session_id`
- `ig_csrftoken`
- `ig_user_id`
- `notion_token`
- `notion_database_id`
- `content_ideas_db_id`
- `collections_filter`
- `collection_ids`

## Step 4 - Install runtime

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Step 5 - Render the scheduler

From `instagram-saves-sync.plist.template`, replace:
- `{{APP_LABEL}}` with `com.instagram-saves-sync` (or a label the user prefers)
- `{{PYTHON_PATH}}` with the absolute path to `<install-dir>/.venv/bin/python3`
- `{{INSTALL_DIR}}` with the absolute path to the install directory
- `{{HOUR_1}}` and `{{HOUR_2}}` with the chosen sync hours (from Step 3)

Write the rendered file to `~/Library/LaunchAgents/<label>.plist` and load it:

```
launchctl load ~/Library/LaunchAgents/<label>.plist
```

## Step 6 - Verify

Run one sync manually:

```
.venv/bin/python3 sync.py
```

Confirm it logs "Logged in as @..." and completes without errors.

Note: the scheduler only runs when the Mac is awake at the scheduled time.

## Cloud sync (optional, runs without the Mac)

The repository ships a GitHub Actions workflow, `.github/workflows/daily-sync.yml`,
that runs the same `sync.py` once a day from GitHub's servers. It reads
credentials from repository secrets instead of `config.json`.

1. On GitHub open the repository, then Settings, then Secrets and variables, then
   Actions. Add these repository secrets with the same values as `config.json`:
   - `IG_SESSION_ID`
   - `IG_CSRFTOKEN`
   - `IG_USER_ID`
   - `NOTION_TOKEN`
   - `NOTION_DATABASE_ID`
2. Optional: under the Variables tab add `COLLECTIONS_FILTER` as a JSON array,
   for example `["Inspo","Tools"]`, to sync only those collections, and
   `COLLECTION_IDS` as a JSON object mapping names to ids, for example
   `{"Inspo":"17841400000000000"}`, so the Collection column is filled in. Find
   the ids with `sync.py --discover-collections` on any machine with a
   `config.json`. Leave both unset to sync everything without collection names.
3. The workflow must live on the default branch to run on its schedule. Open the
   Actions tab, pick "Daily Instagram sync", and use "Run workflow" once to
   confirm it goes green.

The workflow runs at 10:30 UTC. Because the sync dedupes against Notion, the
Mac schedule can stay on as a backup, but the Mac must be running this version
of `sync.py` (or later). An older copy that only checks `state.json` will
create duplicates of posts the cloud synced first.

A routine run stops paging as soon as it reaches a page of posts Notion already
has, so it usually finishes in under a minute. If a run was interrupted part-way
through a large backfill, older posts can be left behind below that first
synced page. To catch them, run the workflow by hand with the "full_sync" box
ticked (or set `FULL_SYNC=1` when running `sync.py` locally). A full walk of a
few thousand saves takes 20 to 40 minutes.

When the Instagram cookies expire, update both `config.json` on the Mac and the
two GitHub secrets.

The daily digest email is a separate scheduled Claude session; see `DIGEST.md`.

## Troubleshooting

- Instagram session invalid: refresh `ig_session_id` and `ig_csrftoken` from Chrome cookies (Step 1) and update `config.json`.
- Notion sync fails: confirm the integration is connected to the database (Step 2, Connections menu).
