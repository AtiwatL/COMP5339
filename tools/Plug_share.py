"""Retrieve PlugShare candidates for DC chargers still unmatched by OCM.

The script keeps the notebook's retrieval settings: source coordinates, 1 km radius,
up to two results per location, full details, resumable JSON cache, and no duplicate
POST for a completed search. It does not perform matching; 03_data_augmentation.ipynb
does that.
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Apify Actor and search settings used for every unmatched TfNSW charger.
ACTOR_ID = "iegpJoOXgbMKB6myS"  # getascraper/plugshare-scraper
API_BASE = "https://api.apify.com/v2"
LOCATION_LIMIT = None
RESULTS_PER_LOCATION = 2
SEARCH_RADIUS_KM = 1
ACTOR_TIMEOUT_SECONDS = 300
CACHE_PATH = PROJECT_ROOT / "data/raw/plugshare/coordinate_searches.json"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save_cache(cache):
    """Write the cache atomically so interruption cannot replace a valid file."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE_PATH.with_suffix(".part")
    temporary.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(CACHE_PATH)


def api_json(session, method, endpoint, **kwargs):
    """Retry temporary GET failures; never retry a paid POST."""
    attempts = 5 if method.upper() == "GET" else 1
    for attempt in range(attempts):
        response = None
        try:
            response = session.request(method, API_BASE + endpoint, timeout=(15, 45), **kwargs)
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            temporary_error = response is None or response.status_code in {429, 500, 502, 503, 504}
            if not temporary_error or attempt == attempts - 1:
                raise
            time.sleep(min(2 ** (attempt + 1), 30))


def search_key(actor_input):
    """Create a reproducible key from the Actor and its complete request input."""
    identity = {"actor_id": ACTOR_ID, "input": actor_input}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def comparable_input(actor_input):
    """Return request settings that affect results, excluding the display label."""
    comparable = json.loads(json.dumps(actor_input))
    for area in comparable.get("searchAreas", []):
        area.pop("label", None)
    return comparable


def cached_search(cache, search):
    """Find an exact or compatible completed search for one source charger."""
    # Prefer the current full hash when the request is unchanged.
    key = search_key(search["input"])
    if key in cache["searches"]:
        return key, cache["searches"][key]

    # Older cache entries used an address-only label. Reuse them when the
    # charger ID and every result-affecting request parameter still agree.
    charger_ids = search["charger_ids"]
    request = comparable_input(search["input"])
    for cached_key, entry in cache["searches"].items():
        if entry.get("charger_ids") == charger_ids and comparable_input(
            entry.get("input", {})
        ) == request:
            return cached_key, entry
    return key, None


def fetch_items(session, dataset_id):
    return api_json(session, "GET", f"/datasets/{dataset_id}/items", params={"format": "json"})


def main():
    # Read credentials from the project .env without replacing shell values.
    for env_path in (PROJECT_ROOT / ".env", PROJECT_ROOT.parent / ".env"):
        load_dotenv(env_path, override=False)

    # The deduplicated OCM review defines the records that still need the
    # fallback source. Invalid coordinates cannot be searched safely.
    review_path = PROJECT_ROOT / "data/interim/ocm_matching_review.csv"
    if not review_path.exists():
        raise FileNotFoundError("Run OCM matching first: ocm_matching_review.csv is missing.")
    review = pd.read_csv(review_path)
    targets = review.loc[~review.match_status.eq("accepted")].copy()
    targets["latitude"] = pd.to_numeric(targets["latitude"], errors="coerce")
    targets["longitude"] = pd.to_numeric(targets["longitude"], errors="coerce")
    targets = targets.loc[targets.latitude.between(-90, 90) & targets.longitude.between(-180, 180)]

    # Build one traceable Apify request for each remaining source record.
    searches = []
    # Keep one request per charger_id. Two source chargers can share coordinates
    # while representing different operators or equipment; their results must be
    # traceable independently even when the API search point is identical.
    for _, row in targets.sort_values("charger_id").iterrows():
        latitude, longitude = float(row.latitude), float(row.longitude)
        address = str(row.station_address).strip() if pd.notna(row.station_address) else ""
        label = address or f"{latitude}, {longitude}"
        label = f"charger {int(row.charger_id)}: {label}"
        searches.append({
            "address": label,
            "addresses": [address] if address else [],
            "latitude": latitude,
            "longitude": longitude,
            "charger_ids": [int(row.charger_id)],
            "operators": [str(row.operator)] if pd.notna(row.operator) else [],
            "source_records": [row[["charger_id", "station_address", "operator", "latitude", "longitude"]].to_dict()],
            "input": {
                "searchAreas": [{"latitude": latitude, "longitude": longitude,
                                 "radiusKm": SEARCH_RADIUS_KM, "label": label}],
                "maxItemsPerArea": RESULTS_PER_LOCATION,
                "includeDetails": True,
                "fastChargersOnly": False,
                "includeReviews": False,
                "onlyNewOrChanged": False,
            },
        })
    searches.sort(key=lambda item: (item["address"], item["latitude"], item["longitude"]))
    selected = searches if LOCATION_LIMIT is None else searches[:LOCATION_LIMIT]

    # Resume a compatible cache or initialise a new one.
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if cache.get("actor_id") != ACTOR_ID or not isinstance(cache.get("searches"), dict):
            raise ValueError("Unexpected PlugShare cache format or actor ID")
        print(f"Existing PlugShare JSON found: {CACHE_PATH}")
        print(f"Cached searches: {len(cache['searches'])}")
    else:
        cache = {"actor_id": ACTOR_ID, "actor_name": "getascraper/plugshare-scraper", "searches": {}}
        print("No PlugShare JSON found; retrieval will start.")

    # A token is unnecessary when every current request is already cached.
    token = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    needs_api = any(
        not (cached_search(cache, search)[1] or {}).get("download_complete")
        for search in selected
    )
    if needs_api and not token:
        raise RuntimeError("Set APIFY_TOKEN in .env before downloading PlugShare data.")

    with requests.Session() as session:
        session.headers["Authorization"] = "Bearer " + token if token else ""
        for number, search in enumerate(selected, start=1):
            key, entry = cached_search(cache, search)

            # Never submit another paid Actor run for a completed search.
            if entry and entry.get("download_complete"):
                print(f"[{number}/{len(selected)}] Cached: {search['address']}")
                continue

            # Save the request before POSTing. If execution stops after the
            # POST, the run ID can still be recovered from the cache entry.
            if entry is None:
                entry = {**search, "status": "START_UNCONFIRMED", "requested_at": utc_now()}
                cache["searches"][key] = entry
                save_cache(cache)
                run = api_json(session, "POST", f"/actors/{ACTOR_ID}/runs",
                               params={"timeout": ACTOR_TIMEOUT_SECONDS}, json=search["input"])["data"]
                entry.update(run_id=run["id"], status=run["status"])
                save_cache(cache)
            # Poll the Actor until it reaches a terminal state, saving its
            # latest state after every check so the process is resumable.
            while True:
                run = api_json(session, "GET", f"/actor-runs/{entry['run_id']}")["data"]
                entry.update(status=run["status"], checked_at=utc_now(),
                             dataset_id=run.get("defaultDatasetId"), usage_total_usd=run.get("usageTotalUsd"))
                save_cache(cache)
                if run["status"] in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
                    break
                time.sleep(5)
            if run["status"] != "SUCCEEDED":
                raise RuntimeError(f"PlugShare run ended {run['status']}")

            # Download the resulting dataset only after a successful run and
            # mark it complete only after the items have been written safely.
            entry.update(items=fetch_items(session, entry["dataset_id"]), download_complete=True, downloaded_at=utc_now())
            save_cache(cache)
            print(f"[{number}/{len(selected)}] Saved {len(entry['items'])} result(s): {search['address']}")
    print(f"PlugShare JSON ready: {CACHE_PATH}")


if __name__ == "__main__":
    main()

