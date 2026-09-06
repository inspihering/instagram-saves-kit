#!/usr/bin/env python3
"""
One-off maintenance: archive duplicate posts in the Notion database.

Two rows are duplicates when they share the same post URL. Within a
duplicate group the row(s) written by sync.py (numeric Media ID, the
Instagram media pk) are kept and every other row is archived (moved to
Notion's trash, recoverable for 30 days). If no row in the group has a
numeric Media ID, the oldest-created row is kept.

Reads NOTION_TOKEN and NOTION_DATABASE_ID from config.json or the
environment, like sync.py. Pass --dry-run to only report.
"""

import sys
import logging
from collections import defaultdict

from notion_client import Client as NotionClient

import sync

log = logging.getLogger("dedupe")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def fetch_rows(notion, data_source_id):
    rows = []
    cursor = None
    while True:
        kwargs = {"data_source_id": data_source_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.data_sources.query(**kwargs)
        for page in resp.get("results", []):
            props = page.get("properties", {})
            url = (props.get("URL") or {}).get("url") or ""
            media_id = "".join(
                part.get("plain_text", "") for part in (props.get("Media ID") or {}).get("rich_text", [])
            ).strip()
            rows.append({
                "id": page["id"],
                "url": url.strip().rstrip("/"),
                "media_id": media_id,
                "created": page.get("created_time", ""),
            })
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return rows


def choose_keep(group):
    numeric = [r for r in group if r["media_id"].isdigit()]
    pool = numeric or group
    return min(pool, key=lambda r: r["created"])


def main(argv):
    dry_run = "--dry-run" in argv
    config = sync.load_config()
    notion = NotionClient(auth=config["notion_token"])
    data_source_id = sync.resolve_data_source_id(notion, config["notion_database_id"])

    rows = fetch_rows(notion, data_source_id)
    by_url = defaultdict(list)
    for r in rows:
        if r["url"]:
            by_url[r["url"]].append(r)

    groups = {u: g for u, g in by_url.items() if len(g) > 1}
    to_archive = []
    for url, group in groups.items():
        keep = choose_keep(group)
        to_archive.extend(r for r in group if r["id"] != keep["id"])

    log.info(f"{len(rows)} rows, {len(groups)} duplicate URLs, {len(to_archive)} rows to archive")
    if dry_run:
        for r in to_archive[:20]:
            log.info(f"  would archive {r['url']} (Media ID {r['media_id']!r}, created {r['created']})")
        return 0

    errors = 0
    for i, r in enumerate(to_archive, 1):
        try:
            notion.pages.update(page_id=r["id"], archived=True)
            if i % 50 == 0:
                log.info(f"  archived {i}/{len(to_archive)}")
        except Exception as e:
            errors += 1
            log.error(f"  failed to archive {r['id']} ({r['url']}): {e}")
    log.info(f"Done: archived {len(to_archive) - errors}, errors {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
