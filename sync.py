#!/usr/bin/env python3
"""
Instagram Saves → Notion Sync

Fetches saved posts from Instagram's web API and syncs new ones
to a Notion database. Designed to run 1-2x daily via launchd.

Uses Instagram's web REST API (same as the browser) rather than
the mobile/private API, so a web session cookie is sufficient.
"""

import json
import os
import sys
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from notion_client import Client as NotionClient

# Paths
SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config.json"
STATE_FILE = SCRIPT_DIR / "state.json"
LOG_FILE = SCRIPT_DIR / "sync.log"

# Instagram web API constants
IG_BASE = "https://www.instagram.com"
IG_APP_ID = "936619743392459"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# Environment variable fallback (used by the GitHub Actions cloud sync,
# where there is no config.json). Each maps to the same-named config key.
ENV_KEYS = {
    "ig_session_id": "IG_SESSION_ID",
    "ig_csrftoken": "IG_CSRFTOKEN",
    "ig_user_id": "IG_USER_ID",
    "notion_token": "NOTION_TOKEN",
    "notion_database_id": "NOTION_DATABASE_ID",
}


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)

    config = {key: os.environ.get(env, "") for key, env in ENV_KEYS.items()}
    missing = [env for key, env in ENV_KEYS.items() if not config[key]]
    if missing:
        log.error(f"Config file not found: {CONFIG_FILE}")
        log.error("Copy config.example.json to config.json and fill in your credentials,")
        log.error(f"or set environment variables: {', '.join(ENV_KEYS.values())}")
        log.error(f"Missing: {', '.join(missing)}")
        sys.exit(1)

    raw_filter = os.environ.get("COLLECTIONS_FILTER", "").strip()
    try:
        config["collections_filter"] = json.loads(raw_filter) if raw_filter else []
    except json.JSONDecodeError:
        log.error('COLLECTIONS_FILTER must be a JSON array, e.g. ["Inspo","Tools"]')
        sys.exit(1)
    log.info("Loaded config from environment variables")
    return config


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"synced_media_ids": [], "last_sync": None}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def make_ig_session(config):
    """Create a requests session with Instagram web API headers."""
    session = requests.Session()
    session.cookies.set("sessionid", config["ig_session_id"], domain=".instagram.com")
    session.cookies.set("csrftoken", config["ig_csrftoken"], domain=".instagram.com")
    session.cookies.set("ds_user_id", config.get("ig_user_id", ""), domain=".instagram.com")
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "X-CSRFToken": config["ig_csrftoken"],
        "X-IG-App-ID": IG_APP_ID,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.instagram.com/",
        "Accept": "*/*",
    })
    return session


def test_session(session):
    """Test if the Instagram session is valid."""
    resp = session.get(f"{IG_BASE}/api/v1/accounts/edit/web_form_data/")
    if resp.status_code == 200:
        data = resp.json()
        username = data.get("form_data", {}).get("username", "unknown")
        return username
    return None


def fetch_saved_posts(session, max_pages=50):
    """Fetch all saved posts using Instagram's web REST API."""
    all_items = []
    max_id = None

    for page in range(max_pages):
        params = {"count": "50"}
        if max_id:
            params["max_id"] = max_id

        resp = session.get(f"{IG_BASE}/api/v1/feed/saved/posts/", params=params)
        if resp.status_code != 200:
            log.error(f"Failed to fetch saved posts (page {page + 1}): HTTP {resp.status_code}")
            log.error(f"Response: {resp.text[:300]}")
            break

        data = resp.json()
        items = data.get("items", [])
        all_items.extend(items)
        log.info(f"  Page {page + 1}: {len(items)} items (total: {len(all_items)})")

        if not data.get("more_available", False):
            break

        max_id = data.get("next_max_id")
        if not max_id:
            break

        time.sleep(1)  # Rate limit courtesy

    return all_items


def fetch_collection_map(session):
    """Fetch collection ID → name mapping from Instagram."""
    params = {
        "collection_types": '["ALL_MEDIA_AUTO_COLLECTION","PRODUCT_AUTO_COLLECTION","MEDIA"]',
        "get_cover_media_lists": "true",
        "include_public_only": "0",
    }
    resp = session.get(f"{IG_BASE}/api/v1/collections/list/", params=params)
    if resp.status_code != 200:
        log.warning(f"Failed to fetch collections: HTTP {resp.status_code}")
        return {}
    data = resp.json()
    coll_map = {}
    for item in data.get("items", []):
        cid = str(item.get("collection_id", ""))
        cname = item.get("collection_name", "")
        if cid and cname:
            coll_map[cid] = cname
    return coll_map


def get_collection_names(media, collection_map):
    """Get collection names for a media item using saved_collection_ids."""
    coll_ids = media.get("saved_collection_ids", [])
    return [collection_map[str(cid)] for cid in coll_ids if str(cid) in collection_map]


def get_media_type(media):
    """Determine the content type from a media dict."""
    media_type = media.get("media_type", 1)
    product_type = media.get("product_type", "")

    if media_type == 8:
        return "Carousel"
    elif media_type == 2:
        if product_type == "clips":
            return "Reel"
        elif product_type == "igtv":
            return "IGTV"
        return "Reel"
    return "Post"


def get_media_url(media):
    """Build the Instagram URL for a media item."""
    code = media.get("code", "")
    media_type = get_media_type(media)
    if media_type == "Reel":
        return f"https://www.instagram.com/reel/{code}/"
    return f"https://www.instagram.com/p/{code}/"


def get_media_author(media):
    """Extract username from media dict."""
    user = media.get("user", {})
    return user.get("username", "unknown")


def get_media_caption(media):
    """Extract caption text from media dict."""
    caption = media.get("caption")
    if caption and isinstance(caption, dict):
        text = caption.get("text") or ""
    elif isinstance(caption, str):
        text = caption
    else:
        return ""
    return text[:1900]


def resolve_data_source_id(notion, database_id):
    """Return the data source id behind a database (Notion API 2025-09-03)."""
    db = notion.databases.retrieve(database_id=database_id)
    sources = db.get("data_sources") or []
    if not sources:
        log.error("Notion database has no data sources. Is the integration connected to it?")
        sys.exit(1)
    return sources[0]["id"]


def fetch_notion_media_ids(notion, data_source_id):
    """Read every Media ID already in the Notion database.

    This makes the sync safe to run from more than one machine (the Mac
    schedule and the cloud schedule) without creating duplicate pages.
    """
    ids = set()
    cursor = None
    while True:
        kwargs = {"data_source_id": data_source_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.data_sources.query(**kwargs)
        for page in resp.get("results", []):
            rich = page.get("properties", {}).get("Media ID", {}).get("rich_text", [])
            text = "".join(part.get("plain_text", "") for part in rich).strip()
            if text:
                ids.add(text)
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return ids


def add_to_notion(notion, data_source_id, media, collection_name=None):
    """Create a new page in the Notion database for a saved post."""
    media_type = get_media_type(media)
    url = get_media_url(media)
    author = get_media_author(media)
    caption = get_media_caption(media)
    media_id = str(media.get("pk", media.get("id", "")))
    code = media.get("code", "")
    name = f"@{author}/{code}"
    now = datetime.now(timezone.utc).isoformat()

    properties = {
        "Name": {"title": [{"text": {"content": name}}]},
        "URL": {"url": url},
        "Type": {"select": {"name": media_type}},
        "Author": {"rich_text": [{"text": {"content": author}}]},
        "Status": {"select": {"name": "New"}},
        "Media ID": {"rich_text": [{"text": {"content": media_id}}]},
        "Saved": {"date": {"start": now}},
    }

    if caption:
        properties["Caption"] = {
            "rich_text": [{"text": {"content": caption}}]
        }

    if collection_name:
        properties["Collection"] = {
            "select": {"name": collection_name}
        }

    notion.pages.create(parent={"data_source_id": data_source_id}, properties=properties)


def sync():
    """Main sync: fetch Instagram saves → push new ones to Notion."""
    config = load_config()
    state = load_state()
    synced_ids = set(state.get("synced_media_ids", []))

    log.info("=" * 50)
    log.info("Instagram Saves → Notion Sync")
    log.info("=" * 50)

    # Create Instagram web session
    session = make_ig_session(config)

    # Test session
    username = test_session(session)
    if not username:
        log.error("Instagram session is invalid or expired.")
        log.error("Update ig_session_id and ig_csrftoken in config.json.")
        log.error("Get fresh values from Chrome DevTools → Application → Cookies → instagram.com")
        sys.exit(1)
    log.info(f"Logged in as @{username}")

    # Connect to Notion and learn what is already there
    notion = NotionClient(auth=config["notion_token"])
    database_id = config["notion_database_id"]
    data_source_id = resolve_data_source_id(notion, database_id)
    try:
        notion_ids = fetch_notion_media_ids(notion, data_source_id)
    except Exception as e:
        log.error(f"Could not read existing posts from Notion: {e}")
        log.error("Check notion_token and that the integration is connected to the database.")
        sys.exit(1)
    log.info(f"Notion already holds {len(notion_ids)} posts; local state knows {len(synced_ids)}")
    synced_ids |= notion_ids

    # Build collection filter
    filter_names = config.get("collections_filter", [])
    collection_map = fetch_collection_map(session)
    target_ids = None  # None = sync all

    if filter_names:
        # Resolve collection names to IDs
        name_to_id = {name: cid for cid, name in collection_map.items()}
        target_ids = set()
        for name in filter_names:
            if name in name_to_id:
                target_ids.add(name_to_id[name])
                log.info(f"Filtering to collection: {name} (id: {name_to_id[name]})")
            else:
                log.warning(f"Collection not found: '{name}' - available: {list(name_to_id.keys())}")
        if not target_ids:
            log.error("No matching collections found. Check collections_filter in config.json.")
            sys.exit(1)

    # Fetch all saved posts
    log.info("Fetching saved posts...")
    all_items = fetch_saved_posts(session)
    log.info(f"Total saved items: {len(all_items)}")

    new_count = 0
    skipped = 0
    errors = 0

    for item in all_items:
        media = item.get("media", item)
        media_id = str(media.get("pk", media.get("id", "")))
        if not media_id or media_id in synced_ids:
            continue

        # Filter by collection if configured
        if target_ids is not None:
            media_coll_ids = {str(cid) for cid in media.get("saved_collection_ids", [])}
            matched_ids = media_coll_ids & target_ids
            if not matched_ids:
                skipped += 1
                continue
            # Use first matched collection name
            coll_name = collection_map.get(next(iter(matched_ids)), "")
        else:
            # No filter - include collection names if available
            names = get_collection_names(media, collection_map)
            coll_name = ", ".join(names) if names else None

        try:
            add_to_notion(notion, data_source_id, media, coll_name)
            synced_ids.add(media_id)
            new_count += 1
            log.info(
                f"  + @{get_media_author(media)}/{media.get('code', '?')} "
                f"({get_media_type(media)}) → {coll_name or 'uncategorized'}"
            )
        except Exception as e:
            log.error(f"  Failed to sync {media.get('code', '?')}: {e}")
            errors += 1

    # Update state
    state["synced_media_ids"] = list(synced_ids)
    state["last_sync"] = datetime.now(timezone.utc).isoformat()
    state["total_synced"] = len(synced_ids)
    save_state(state)

    log.info("-" * 50)
    log.info(f"Sync complete: {new_count} new | {skipped} skipped | {len(synced_ids)} total | {errors} errors")
    log.info(f"Next sync: run this script again or wait for scheduled run")

    return new_count


if __name__ == "__main__":
    try:
        sync()
    except KeyboardInterrupt:
        log.info("\nSync cancelled.")
    except Exception as e:
        log.error(f"Sync failed: {e}")
        sys.exit(1)
