from config.opensearch_client import get_es_client, INDEX_NAME
from config.mongo_client import get_active_provider_ids
from datetime import datetime, timezone
import random

# ==============================
# 🔹 OPENSEARCH CONNECTION
# ==============================

MAX_SYNONYMS_PER_TITLE = 3

GENERIC_SYNONYMS = {
    "live sport", "live match", "today live", "today match",
    "today's match", "today's match live", "live", "live tv",
    "live sports", "sport live", "match live", "live today"
}


# ==============================
# 🔹 TYPO GENERATOR
# ==============================
def generate_typo(text):
    words      = text.split()
    candidates = [(i, w) for i, w in enumerate(words) if len(w) > 3]
    if not candidates:
        return text

    idx, word = random.choice(candidates)
    strategy  = random.choice(["swap", "delete", "replace"])
    pos       = random.randint(1, len(word) - 2)

    if strategy == "swap":
        w = list(word)
        w[pos], w[pos + 1] = w[pos + 1], w[pos]
        typo_word = "".join(w)
    elif strategy == "delete":
        typo_word = word[:pos] + word[pos + 1:]
    else:
        keyboard_neighbors = {
            "a": "s", "b": "v", "c": "x", "d": "s", "e": "r",
            "f": "g", "g": "h", "h": "j", "i": "o", "j": "k",
            "k": "l", "l": "k", "m": "n", "n": "m", "o": "p",
            "p": "o", "q": "w", "r": "e", "s": "a", "t": "r",
            "u": "y", "v": "b", "w": "q", "x": "z", "y": "u",
            "z": "x",
        }
        char      = word[pos].lower()
        replace   = keyboard_neighbors.get(char, "x")
        typo_word = word[:pos] + replace + word[pos + 1:]

    words[idx] = typo_word
    return " ".join(words)


def is_generic_synonym(synonym):
    return synonym.strip().lower() in GENERIC_SYNONYMS


# ==============================
# 🔹 OPENSEARCH CLIENT
# ==============================
def _get_es_client():
    return get_es_client()


def is_currently_live(title_name):
    """Check if a title currently has is_live_match=True in OpenSearch."""
    es       = _get_es_client()
    response = es.search(index=INDEX_NAME, body={
        "size": 1,
        "_source": ["name", "is_live_match"],
        "query": {
            "bool": {
                "must": [
                    {"match": {"name": title_name}},
                    {"term": {"is_live_match": True}}
                ]
            }
        }
    })
    return response["hits"]["total"]["value"] > 0


# ==============================
# 🔹 FETCH
# ==============================
def _fetch_from_opensearch(extra_filters=None, limit=10):
    provider_ids = get_active_provider_ids()
    es           = _get_es_client()

    filters = [
        {"term": {"status.keyword": "published"}},
        {"terms": {"content_type.keyword": ["movie", "show", "live_tv", "live TV", "live-tv", "sport"]}},
        {"terms": {"where_to_watch.provider.id.keyword": provider_ids}},
    ]
    if extra_filters:
        filters.extend(extra_filters)

    response = es.search(index=INDEX_NAME, body={
        "size": limit,
        "_source": ["name", "synonyms"],
        "track_total_hits": True,
        "query": {
            "bool": {
                "filter": filters,
                "must_not": [{"terms": {"sub_format.keyword": ["extras", "Extras", "trailers", "Trailers"]}}],
            }
        },
        "sort": [{"release_date": {"order": "desc"}}],
    })
    return response["hits"]["hits"]


def _build_result(hit, source_label):
    source   = hit.get("_source", {})
    name     = source.get("name", "").strip()
    synonyms = source.get("synonyms", [])

    if not name:
        return None

    typo = generate_typo(name)

    classified_synonyms = []
    for syn in synonyms[:MAX_SYNONYMS_PER_TITLE]:
        if syn and syn.strip():
            classified_synonyms.append({
                "text": syn.strip(),
                "type": "generic" if is_generic_synonym(syn) else "specific"
            })

    return {
        "name":     name,
        "typo":     typo,
        "synonyms": classified_synonyms,
        "source":   source_label,
    }


def get_premium_fuzzy_synonym_data(limit=10):
    hits    = _fetch_from_opensearch(limit=limit)
    results = []
    for hit in hits:
        r = _build_result(hit, "premium")
        if r is not None:
            results.append(r)
    print(f"[fuzzy_synonym] Premium titles fetched: {len(results)}")
    return results


def get_live_match_fuzzy_synonym_data(limit=10):
    now         = datetime.now(timezone.utc)
    today_start = now.replace(hour=0,  minute=0,  second=0,  microsecond=0).isoformat()
    today_end   = now.replace(hour=23, minute=59, second=59, microsecond=999000).isoformat()

    extra_filters = [
        {"term": {"is_live_match": True}},
        {"range": {"sort_priority_release_date": {"gte": today_start, "lte": today_end}}},
    ]

    hits    = _fetch_from_opensearch(extra_filters=extra_filters, limit=limit)
    results = []
    for hit in hits:
        r = _build_result(hit, "live_match")
        if r is not None:
            results.append(r)
    print(f"[fuzzy_synonym] Live match titles fetched: {len(results)}")
    return results


def get_all_fuzzy_synonym_data(limit=10):
    return get_premium_fuzzy_synonym_data(limit) + get_live_match_fuzzy_synonym_data(limit)


# ==============================
# 🔹 ENTRYPOINT
# ==============================
if __name__ == "__main__":
    data = get_all_fuzzy_synonym_data(limit=5)
    for d in data:
        print(f"\n  Title   : {d['name']}")
        print(f"  Typo    : {d['typo']}")
        print(f"  Synonyms: {d['synonyms']}")
        print(f"  Source  : {d['source']}")