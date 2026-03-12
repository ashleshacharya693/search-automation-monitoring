from config.opensearch_client import get_es_client, INDEX_NAME
from config.mongo_client import get_active_provider_ids
from datetime import datetime, timezone, timedelta

MAX_TOURNAMENTS = 30


def get_tournaments(limit=MAX_TOURNAMENTS):
    """
    Fetch tournaments from OpenSearch:
    - sport content only
    - published status
    - release_date within last 30 days
    - max 30 tournaments sorted by release_date desc
    - includes tournament_synonyms if available

    Returns list of:
    {
        "tournament_name": "Ayodhya Premier League",
        "tournament_synonyms": ["APL", "Ayodhya League"],
        "match_count": 3,
        "sample_match": "CC vs GW"
    }
    """
    provider_ids = get_active_provider_ids()
    es           = get_es_client()

    today      = datetime.now(timezone.utc)
    since_date = (today - timedelta(days=30)).isoformat()

    response = es.search(index=INDEX_NAME, body={
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {"term":  {"status.keyword": "published"}},
                    {"terms": {"content_type.keyword": ["sport"]}},
                    {"terms": {"where_to_watch.provider.id.keyword": provider_ids}},
                    {"range": {"release_date": {"gte": since_date}}},
                ],
                "must_not": [
                    {"terms": {"sub_format.keyword": ["extras", "Extras", "trailers", "Trailers"]}},
                    {"term":  {"is_live_match": False}},  # mirror search API behavior
                ]
            }
        },
        "aggs": {
            "tournaments": {
                "terms": {
                    "field": "tournament_name.keyword",
                    "size":  limit,
                    "order": {"latest_release": "desc"}
                },
                "aggs": {
                    "latest_release": {
                        "max": {"field": "release_date"}
                    },
                    "tournament_synonyms": {
                        "terms": {
                            "field": "tournament_synonyms.keyword",
                            "size":  20
                        }
                    },
                    "sample_match": {
                        "top_hits": {
                            "size": 1,
                            "_source": ["name", "release_date", "sports_category"]
                        }
                    }
                }
            }
        }
    })

    buckets     = response["aggregations"]["tournaments"]["buckets"]
    tournaments = []

    for bucket in buckets:
        name     = bucket["key"]
        count    = bucket["doc_count"]
        synonyms = [s["key"] for s in bucket["tournament_synonyms"]["buckets"]]

        sample = ""
        hits   = bucket["sample_match"]["hits"]["hits"]
        if hits:
            sample = hits[0]["_source"].get("name", "")

        tournaments.append({
            "tournament_name":     name,
            "tournament_synonyms": synonyms,
            "match_count":         count,
            "sample_match":        sample,
        })

    print(f"[sport_tournament] Tournaments fetched (last 30 days): {len(tournaments)}")
    return tournaments


def get_matches_for_tournament(tournament_name):
    """
    Fetch ALL matches under a specific tournament from OpenSearch.
    Returns list of:
    {
        "name":            "CC vs GW",
        "release_date":    "2026-03-12T00:00:00.000Z",
        "sports_category": "LIVE",
        "provider":        "FanCode"
    }
    """
    provider_ids = get_active_provider_ids()
    es           = get_es_client()

    today      = datetime.now(timezone.utc)
    since_date = (today - timedelta(days=30)).isoformat()

    response = es.search(index=INDEX_NAME, body={
        "size": 100,
        "_source": ["name", "release_date", "sports_category",
                    "where_to_watch.provider.name", "is_live_match"],
        "query": {
            "bool": {
                "filter": [
                    {"term":  {"status.keyword": "published"}},
                    {"terms": {"content_type.keyword": ["sport"]}},
                    {"terms": {"where_to_watch.provider.id.keyword": provider_ids}},
                    {"range": {"release_date": {"gte": since_date}}},
                ],
                "should": [
                    {"term":  {"tournament_name.keyword": tournament_name}},
                    {"match": {"synonyms": tournament_name}},
                ],
                "minimum_should_match": 1,
                "must_not": [
                    {"terms": {"sub_format.keyword": ["extras", "Extras", "trailers", "Trailers"]}},
                    {"term":  {"is_live_match": False}},  # mirror search API behavior
                ]
            }
        },
        "sort": [{"release_date": {"order": "desc"}}]
    })

    matches = []
    for hit in response["hits"]["hits"]:
        src      = hit["_source"]
        provider = ""
        wtw      = src.get("where_to_watch", [])
        if wtw and isinstance(wtw, list):
            provider = wtw[0].get("provider", {}).get("name", "")

        matches.append({
            "name":            src.get("name", ""),
            "release_date":    src.get("release_date", ""),
            "sports_category": src.get("sports_category", ""),
            "provider":        provider,
            "is_live_match":   src.get("is_live_match", None),
        })

    return matches


# ==============================
# 🔹 ENTRYPOINT
# ==============================
if __name__ == "__main__":
    tournaments = get_tournaments()
    for t in tournaments:
        print(f"\nTournament : {t['tournament_name']}")
        print(f"Synonyms   : {t['tournament_synonyms']}")
        print(f"Matches    : {t['match_count']}")
        print(f"Sample     : {t['sample_match']}")
        matches = get_matches_for_tournament(t['tournament_name'])
        for m in matches:
            print(f"  - {m['name']} | {m['sports_category']} | {m['provider']}")