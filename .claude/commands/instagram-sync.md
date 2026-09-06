# Instagram Saves: sync and manage

Manage the Instagram saves sync. Arguments: **$ARGUMENTS**

All commands run from the project root (the directory containing `sync.py`). Locally, credentials live in `config.json`; in the cloud they are GitHub repository secrets.

## Actions

### Run a sync now (local)

```bash
.venv/bin/python3 sync.py
```

Report how many new saves landed. A normal run stops at the first page already in Notion. To walk the whole saved list, set `FULL_SYNC=1`.

### Run a sync now (cloud)

Trigger the "Daily Instagram sync" workflow in the GitHub repository with the GitHub tools (`workflow_dispatch` on `daily-sync.yml`). Tick `full_sync` to walk the whole list, or `dedupe` to archive duplicate posts.

### Discover collection ids

```bash
.venv/bin/python3 sync.py --discover-collections
```

Instagram no longer lists collections through the web API. This prints the collection ids found in the newest saves with sample authors, so the user can match them to collection names in the Instagram app. Write the mapping into `config.json` as `"collection_ids": {"Name": "id"}`, and for the cloud sync set the `COLLECTION_IDS` repository variable to the same JSON object.

### Check status

Local: read `state.json` and the last lines of `sync.log`. Cloud: read the latest run of `daily-sync.yml` with the GitHub tools and report its conclusion and the "Sync complete" line from its log.

### Refresh the Instagram session

1. Chrome, instagram.com, logged in
2. Developer Tools, Application, Cookies, https://www.instagram.com
3. Copy `sessionid` and `csrftoken`
4. Update `config.json` (local) and the `IG_SESSION_ID` and `IG_CSRFTOKEN` secrets (cloud)
5. Run a sync to confirm "Logged in as @"

### Process queued saves

Use `/instagram-process`. It analyses saves that are flagged or marked Recreate by the digest and writes content ideas.
