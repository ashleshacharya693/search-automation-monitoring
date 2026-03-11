from config.opensearch_client import get_es_client, INDEX_NAME
from config.mongo_client import get_active_provider_ids
import csv
from datetime import datetime, timezone

# ==============================
# 🔹 OPENSEARCH CONNECTION
# ==============================


def get_live_match_titles(limit=10):
    """
    Fetch published live match titles for TODAY from OpenSearch.
    - Provider IDs fetched dynamically from MongoDB via config/mongo_client.py
    - is_live_match must be True
    - sort_priority_release_date falls within today's UTC date range
    - Excludes extras/trailers
    - Returns list of title names sorted by sort_priority_release_date ascending
    - Returns empty list gracefully if no matches found today
    """

    # ✅ Always fresh from MongoDB — no hardcoding needed
    provider_ids = get_active_provider_ids()

    es = get_es_client()

    # Today's UTC date boundaries
    now         = datetime.now(timezone.utc)
    today_start = now.replace(hour=0,  minute=0,  second=0,  microsecond=0).isoformat()
    today_end   = now.replace(hour=23, minute=59, second=59, microsecond=999000).isoformat()

    print(f"[live_match] Searching for matches on: {now.strftime('%Y-%m-%d')} (UTC)")

    query = {
        "size": limit,
        "_source": ["name"],
        "track_total_hits": True,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"status.keyword": "published"}},
                    {
                        "terms": {
                            "content_type.keyword": [
                                "movie", "show", "live_tv", "live TV", "live-tv", "sport"
                            ]
                        }
                    },
                    {
                        "terms": {
                            "where_to_watch.provider.id.keyword": provider_ids
                        }
                    },
                    {"term": {"is_live_match": True}},
                    {
                        "range": {
                            "sort_priority_release_date": {
                                "gte": today_start,
                                "lte": today_end,
                            }
                        }
                    },
                ],
                "must_not": [
                    {
                        "terms": {
                            "sub_format.keyword": ["extras", "Extras", "trailers", "Trailers"]
                        }
                    }
                ],
            }
        },
        "sort": [{"sort_priority_release_date": {"order": "asc"}}],
    }

    response = es.search(index=INDEX_NAME, body=query)

    total = response["hits"]["total"]["value"]
    print(f"[live_match] Today's live matches found: {total}")

    if total == 0:
        print("[live_match] ⚠️  No live matches scheduled for today — skipping tests.")
        return []

    titles = [
        hit["_source"]["name"]
        for hit in response["hits"]["hits"]
        if "name" in hit["_source"]
    ]

    return titles


def save_to_csv(titles):
    """Save list of titles to a timestamped CSV file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"live_match_titles_{timestamp}.csv"

    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name"])
        for title in titles:
            writer.writerow([title])

    print(f"Saved {len(titles)} titles to {filename}")
    return filename


# ==============================
# 🔹 ENTRYPOINT
# ==============================
if __name__ == "__main__":
    titles = get_live_match_titles(limit=10)
    print(f"\nFetched {len(titles)} titles")
    for t in titles:
        print(f"  • {t}")

    if titles:
        save_to_csv(titles)