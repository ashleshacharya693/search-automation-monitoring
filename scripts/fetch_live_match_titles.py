from opensearchpy import OpenSearch
import csv
from datetime import datetime, timezone

# ==============================
# 🔹 OPENSEARCH CONNECTION
# ==============================
OPENSEARCH_HOST = "pc-ott-es-prod-tno62hs6fe7gs6zojencjn4eai.ap-south-1.es.amazonaws.com"
INDEX_NAME = "ott_search_tv"

PROVIDER_IDS = [
    "67977987ed126c0029b9f20c",
    "5f456c2aff9ccd034434e6fd",
    "5f456c2aff9ccd034434e700",
    "60abaef7b17a77001df4b8fa",
    "63ce216c483822001ca300a4",
    "64e7112f105f75001d713cea",
    "665f05ca565609001dee29b3",
    "5f456c2aff9ccd034434e705",
    "5f456c2aff9ccd034434e706",
    "5f456c2aff9ccd034434e713",
    "5f456c2aff9ccd034434e721",
    "68b57d739c2b5a002f8f4d9d",
    "656eac199f837f001cb887b4",
    "61b3340b51556a001dd7ece2",
    "6901ac5234daf800291779cf",
    "63747d3f0fd109001c1b302c",
    "655758703c4251001caa45b0",
    "62a6c1eabf03c8001db38b98",
    "648c5261bfe063001d8e02b7",
    "6458a76066ccfa001cfb104e",
    "6992d0402d8a3c002b99981c",
    "657acb644edf1b001ca2bdd0",
    "6579a5f503afe0001c3e6a23",
    "65851af3a00d86001cdca2ee",
    "65ddcb8be19c75001d00c986",
    "63747ca1891654001d2a2f42",
    "672caa844a4ed6002f058025",
    "66ec1ff95753cc002f36999d",
    "66ec1f89d63b300029dd6314",
    "6800a0c30d5b7a00295b9715",
    "680bb24905893a003054e58b",
    "657ac2c694b812001c12d277",
]


def get_live_match_titles(limit=100):
    """
    Fetch published live match titles for TODAY from OpenSearch.
    - is_live_match must be True
    - match_start_time falls within today's UTC date range
    - Excludes extras/trailers
    - Returns list of title names sorted by match_start_time ascending
    """

    es = OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": 443}],
        use_ssl=True,
        verify_certs=True,
        ssl_show_warn=False,
    )

    # ✅ Today's UTC date boundaries
    now         = datetime.now(timezone.utc)
    today_start = now.replace(hour=0,  minute=0,  second=0,  microsecond=0).isoformat()
    today_end   = now.replace(hour=23, minute=59, second=59, microsecond=999000).isoformat()

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
                            "where_to_watch.provider.id.keyword": PROVIDER_IDS
                        }
                    },
                    {"term": {"is_live_match": True}},      # ✅ live matches only
                    {
                        "range": {                          # ✅ only today's matches
                            "match_start_time": {
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
        "sort": [{"match_start_time": {"order": "asc"}}],  # ✅ earliest match first
    }

    response = es.search(index=INDEX_NAME, body=query)

    total = response["hits"]["total"]["value"]
    print(f"Today's live matches found in index: {total}")

    titles = [
        hit["_source"]["name"]
        for hit in response["hits"]["hits"]
        if "name" in hit["_source"]
    ]

    return titles


def save_to_csv(titles):
    """Save list of titles to a timestamped CSV file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"live_match_titles_{timestamp}.csv"

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
    titles = get_live_match_titles(limit=100)
    print(f"\nFetched {len(titles)} titles")
    for t in titles:
        print(f"  • {t}")

    if titles:
        save_to_csv(titles)
