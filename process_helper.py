#!/usr/bin/env python3
"""
Notion I/O helper for the analysis and ideation stage.

Deterministic read/write commands so a Claude session (the daily Routine,
or /instagram-process run by hand) never hand-rolls Notion API JSON. All
creative work (hook analysis, content ideas) arrives as JSON files; this
script only moves data.

Credentials come from config.json or the environment, exactly like
sync.py (NOTION_TOKEN, NOTION_DATABASE_ID, plus CONTENT_IDEAS_DB_ID or
"content_ideas_db_id" in config.json for the ideas database).

Commands:
  list-queue [--limit N] [--collection NAME]
      Saves eligible for processing, oldest first: Process checkbox ticked,
      OR Verdict is Recreate/Both and Status is not Used.
  write-analysis --page-id ID --file F
      Set Hook / Format / Why It Worked / Steal from a JSON file, optionally
      appending page-body blocks.
  create-idea --file idea.json
      Create one row in the Content Ideas database.
  set-status --page-id ID --status S
      Update a save's Status and clear the Process checkbox.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from notion_client import Client as NotionClient

import sync

TEXT_CHUNK = 1900


def load_settings():
    config = sync.load_config()
    ideas = config.get("content_ideas_db_id") or os.environ.get("CONTENT_IDEAS_DB_ID", "").strip()
    if not ideas:
        sys.exit("content_ideas_db_id (config.json) or CONTENT_IDEAS_DB_ID (environment) is required")
    notion = NotionClient(auth=config["notion_token"])
    saves_ds = sync.resolve_data_source_id(notion, config["notion_database_id"])
    ideas_ds = sync.resolve_data_source_id(notion, ideas)
    return notion, saves_ds, ideas_ds


def rich_text(value, limit=None):
    """Split a string into Notion rich_text objects under the 2000-char cap."""
    value = value or ""
    chunks = [value[i:i + TEXT_CHUNK] for i in range(0, len(value), TEXT_CHUNK)] or [""]
    if limit:
        chunks = chunks[:limit]
    return [{"text": {"content": c}} for c in chunks]


def plain(prop):
    return "".join(t.get("plain_text", "") for t in (prop or []))


def markdown_to_blocks(md):
    """Minimal markdown -> Notion blocks: #/## headings, - bullets, paragraphs."""
    blocks = []
    for raw in (md or "").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("## "):
            blocks.append({"heading_2": {"rich_text": rich_text(line[3:])}})
        elif line.startswith("# "):
            blocks.append({"heading_1": {"rich_text": rich_text(line[2:])}})
        elif line.startswith("- "):
            blocks.append({"bulleted_list_item": {"rich_text": rich_text(line[2:])}})
        else:
            blocks.append({"paragraph": {"rich_text": rich_text(line)}})
    return blocks


def queue_filter():
    """Notion filter for saves that should be processed."""
    return {
        "or": [
            {"property": "Process", "checkbox": {"equals": True}},
            {
                "and": [
                    {"or": [
                        {"property": "Verdict", "select": {"equals": "Recreate"}},
                        {"property": "Verdict", "select": {"equals": "Both"}},
                    ]},
                    {"property": "Status", "select": {"does_not_equal": "Used"}},
                    {"property": "Status", "select": {"does_not_equal": "Archived"}},
                ]
            },
        ]
    }


def cmd_list_queue(args):
    notion, saves_ds, _ = load_settings()
    results = []
    cursor = None
    while True:
        kwargs = {
            "data_source_id": saves_ds,
            "filter": queue_filter(),
            "sorts": [{"property": "Saved", "direction": "ascending"}],
            "page_size": 100,
        }
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.data_sources.query(**kwargs)
        for page in resp["results"]:
            p = page["properties"]
            collection = (p.get("Collection", {}).get("select") or {}).get("name", "")
            if args.collection and collection != args.collection:
                continue
            results.append({
                "page_id": page["id"],
                "name": plain(p["Name"]["title"]),
                "url": p["URL"]["url"],
                "author": plain(p["Author"]["rich_text"]),
                "caption": plain(p["Caption"]["rich_text"]),
                "collection": collection,
                "type": (p.get("Type", {}).get("select") or {}).get("name", ""),
                "verdict": (p.get("Verdict", {}).get("select") or {}).get("name", ""),
                "digest_note": plain(p.get("Digest Note", {}).get("rich_text")),
            })
        if not resp.get("has_more"):
            break
        cursor = resp["next_cursor"]
    if args.limit:
        results = results[:args.limit]
    json.dump(results, sys.stdout, indent=2)
    print()


def cmd_write_analysis(args):
    """JSON shape: {"hook": str, "format": str, "why": str, "steal": str, "body": str?}"""
    notion, _, _ = load_settings()
    data = json.load(open(args.file))
    properties = {
        "Hook": {"rich_text": rich_text(data["hook"], limit=2)},
        "Format": {"rich_text": rich_text(data["format"], limit=2)},
        "Why It Worked": {"rich_text": rich_text(data["why"], limit=2)},
        "Steal": {"rich_text": rich_text(data["steal"], limit=2)},
    }
    notion.pages.update(page_id=args.page_id, properties=properties)
    if data.get("body"):
        blocks = markdown_to_blocks(data["body"].strip())
        for i in range(0, len(blocks), 100):
            notion.blocks.children.append(block_id=args.page_id, children=blocks[i:i + 100])
    print(f"analysis written to {args.page_id}")


def cmd_create_idea(args):
    notion, _, ideas_ds = load_settings()
    idea = json.load(open(args.file))
    monday = idea.get("week_of")
    if not monday:
        today = datetime.now(timezone.utc).date()
        monday = datetime.fromordinal(today.toordinal() - today.weekday()).date().isoformat()

    properties = {
        "Name": {"title": rich_text(idea["title"], limit=1)},
        "Angle": {"rich_text": rich_text(idea.get("angle", ""))},
        "Hook Options": {"rich_text": rich_text(" | ".join(idea.get("hooks", [])))},
        "Status": {"status": {"name": "Not started"}},
        "Platform": {"multi_select": [{"name": p} for p in idea.get("platforms", ["Instagram"])]},
        "Format": {"select": {"name": idea.get("format", "Reel")}},
        "Pillar": {"select": {"name": idea.get("pillar", "Teach")}},
        "Priority": {"select": {"name": idea.get("priority", "Medium")}},
        "Created By": {"select": {"name": "Claude"}},
        "Week Of": {"date": {"start": monday}},
    }
    if idea.get("source_url"):
        properties["Source URL"] = {"url": idea["source_url"]}
    if idea.get("source_author"):
        properties["Source Author"] = {"rich_text": rich_text(idea["source_author"], limit=1)}
    if idea.get("talking_points"):
        properties["Talking Points"] = {"rich_text": rich_text(idea["talking_points"])}
    if idea.get("cta"):
        properties["CTA"] = {"rich_text": rich_text(idea["cta"])}
    if idea.get("grade") is not None:
        properties["Grade"] = {"number": float(idea["grade"])}

    page = notion.pages.create(
        parent={"data_source_id": ideas_ds},
        properties=properties,
        children=markdown_to_blocks(idea.get("body", ""))[:100],
    )
    print(f"idea created: {idea['title']} -> {page['id']}")


def cmd_set_status(args):
    notion, _, _ = load_settings()
    notion.pages.update(
        page_id=args.page_id,
        properties={
            "Status": {"select": {"name": args.status}},
            "Process": {"checkbox": False},
        },
    )
    print(f"{args.page_id} -> {args.status}, Process flag cleared")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list-queue")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--collection", default="")
    p.set_defaults(func=cmd_list_queue)

    p = sub.add_parser("write-analysis")
    p.add_argument("--page-id", required=True)
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_write_analysis)

    p = sub.add_parser("create-idea")
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_create_idea)

    p = sub.add_parser("set-status")
    p.add_argument("--page-id", required=True)
    p.add_argument("--status", required=True, choices=["New", "Reviewed", "Used", "Archived"])
    p.set_defaults(func=cmd_set_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
