from opensearchpy import OpenSearch
from config.mongo_client import get_active_provider_ids

# ==============================
# 🔹 OPENSEARCH CONNECTION
# ==============================
OPENSEARCH_HOST = "vpc-ott-es-prod-tno62hs6fe7gs6zojencjn4eai.ap-south-1.es.amazonaws.com"
INDEX_NAME      = "ott_search_tv"


def get_premium_titles(limit=10):
    """
    Fetch latest published premium titles directly from OpenSearch.
    Provider IDs fetched dynamically from MongoDB via config/mongo_client.py
    Returns list of title names.
    """

    # ✅ Always fresh from MongoDB — no hardcoding needed
    provider_ids = get_active_provider_ids()

    es = OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": 443}],
        use_ssl=True,
        verify_certs=True,
        ssl_show_warn=False,
    )

    query = {
        "size": limit,
        "_source": ["name"],
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
                            "where_to_watch.provider.id.keyword": provider_ids  # ✅ dynamic
                        }
                    }
                ]
            }
        },
        "sort": [{"release_date": {"order": "desc"}}]
    }

    response = es.search(index=INDEX_NAME, body=query)

    titles = [
        hit["_source"]["name"]
        for hit in response["hits"]["hits"]
        if "name" in hit["_source"]
    ]

    return titles


# Optional: allow manual testing
if __name__ == "__main__":
    titles = get_premium_titles(limit=10)
    print(f"Fetched {len(titles)} titles")
    for t in titles:
        print(t)