from opensearchpy import OpenSearch
from config.mongo_client import get_offboarded_provider_ids
import csv
from datetime import datetime

# ==============================
# 🔹 OPENSEARCH CONNECTION
# ==============================
OPENSEARCH_HOST = "vpc-ott-es-prod-tno62hs6fe7gs6zojencjn4eai.ap-south-1.es.amazonaws.com"
INDEX_NAME      = "ott_search_tv"


def get_offboarded_titles(limit=10):
    """
    Fetch latest published titles for offboarded providers from OpenSearch.
    Provider IDs fetched dynamically from MongoDB (is_provider_off_boarded=True)
    Returns list of dicts: [{"name": "...", "provider": "..."}, ...]
    """

    # ✅ Offboarded provider IDs from MongoDB > providers collection
    provider_ids = get_offboarded_provider_ids()

    if not provider_ids:
        print("No offboarded providers found — nothing to fetch.")
        return []

    es = OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": 443}],
        use_ssl=True,
        verify_certs=True,
        ssl_show_warn=False,
    )

    query = {
        "size": limit,
        "_source": ["name", "where_to_watch.provider.name", "where_to_watch.provider.id"],  # ✅ fetch provider name too
        "track_total_hits": True,
        "query": {
            "bool": {
                "must": [
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
                    }
                ]
            }
        },
        "sort": [{"release_date": {"order": "desc"}}]
    }

    response = es.search(index=INDEX_NAME, body=query)

    total = response["hits"]["total"]["value"]
    print(f"[offboarded] Total titles found: {total}")

    results = []
    for hit in response["hits"]["hits"]:
        source = hit.get("_source", {})
        name   = source.get("name")
        if not name:
            continue

        # Extract matching offboarded provider names from where_to_watch
        wtw            = source.get("where_to_watch", [])
        provider_names = []
        for entry in wtw:
            provider = entry.get("provider", {})
            if provider.get("id") in provider_ids:
                pname = provider.get("name")
                if pname and pname not in provider_names:
                    provider_names.append(pname)

        results.append({
            "name":     name,
            "provider": ", ".join(provider_names) if provider_names else "Unknown"
        })

    return results


def save_to_csv(results):
    """Save list of results to a timestamped CSV file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"offboarded_titles_{timestamp}.csv"

    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "provider"])
        for r in results:
            writer.writerow([r["name"], r["provider"]])

    print(f"Saved {len(results)} titles to {filename}")
    return filename


# ==============================
# 🔹 ENTRYPOINT
# ==============================
if __name__ == "__main__":
    results = get_offboarded_titles(limit=100)
    print(f"\nFetched {len(results)} offboarded titles")
    for r in results:
        print(f"  • {r['name']}  [{r['provider']}]")

    if results:
        save_to_csv(results)