from config.opensearch_client import get_es_client, INDEX_NAME
from config.mongo_client import get_active_provider_ids
from datetime import datetime, timezone
import random

MAX_SYNONYMS_PER_TITLE = 3

GENERIC_SYNONYMS = {
    "live sport", "live match", "today live", "today match",
    "today's match", "today's match live", "live", "live tv",
    "live sports", "sport live", "match live", "live today"
}


# ==============================
# 🔹 QUERY GENERATORS
# ==============================

def generate_exact(text):
    """Return title as-is."""
    return text


def generate_partial_words(text):
    """First 2 words — like user stopped typing midway.
    e.g. 'Sunderland vs Liverpool 2026' → 'Sunderland vs'
    """
    words = text.split()
    return " ".join(words[:2]) if len(words) >= 2 else text


def generate_partial_prefix(text):
    """Cut first word mid-way — still typing.
    e.g. 'Sunderland vs Liverpool' → 'Sunderla'
    """
    first_word = text.split()[0]
    if len(first_word) <= 3:
        return first_word
    cut = random.randint(3, len(first_word) - 1)
    return first_word[:cut]


def generate_partial_nospace(text):
    """Remove all spaces — fast typer.
    e.g. 'Sunderland vs Liverpool' → 'sunderlandvsliverpool'
    """
    return "".join(text.split()).lower()


def generate_fuzzy_swap(text):
    """Swap two adjacent characters in a word.
    e.g. 'Sunderland' → 'Sunderlnad'
    """
    words = text.split()
    candidates = [(i, w) for i, w in enumerate(words) if len(w) > 3]
    if not candidates:
        return text
    idx, word = random.choice(candidates)
    pos = random.randint(1, len(word) - 2)
    w = list(word)
    w[pos], w[pos + 1] = w[pos + 1], w[pos]
    words[idx] = "".join(w)
    return " ".join(words)


def generate_fuzzy_delete(text):
    """Delete one character from a word.
    e.g. 'Sunderland' → 'Sunderand'
    """
    words = text.split()
    candidates = [(i, w) for i, w in enumerate(words) if len(w) > 3]
    if not candidates:
        return text
    idx, word = random.choice(candidates)
    pos = random.randint(1, len(word) - 2)
    words[idx] = word[:pos] + word[pos + 1:]
    return " ".join(words)


def generate_fuzzy_extra(text):
    """Add an extra character in a word.
    e.g. 'Sunderland' → 'Sunderlannd'
    """
    words = text.split()
    candidates = [(i, w) for i, w in enumerate(words) if len(w) > 3]
    if not candidates:
        return text
    idx, word = random.choice(candidates)
    pos = random.randint(1, len(word) - 2)
    words[idx] = word[:pos] + word[pos] + word[pos:]
    return " ".join(words)


def generate_case_lower(text):
    """All lowercase.
    e.g. 'Sunderland vs Liverpool' → 'sunderland vs liverpool'
    """
    return text.lower()


def generate_case_upper(text):
    """All uppercase.
    e.g. 'Sunderland vs Liverpool' → 'SUNDERLAND VS LIVERPOOL'
    """
    return text.upper()


def generate_special_dot(text):
    """Replace 'vs' with 'vs.'
    e.g. 'Sunderland vs Liverpool' → 'Sunderland vs. Liverpool'
    """
    return text.replace(" vs ", " vs. ").replace(" VS ", " VS. ")


def generate_special_ampersand(text):
    """Replace 'vs' with '&'
    e.g. 'Sunderland vs Liverpool' → 'Sunderland & Liverpool'
    """
    return text.replace(" vs ", " & ").replace(" VS ", " & ")


def is_generic_synonym(synonym):
    return synonym.strip().lower() in GENERIC_SYNONYMS


# ==============================
# 🔹 OPENSEARCH HELPERS
# ==============================

def is_currently_live(title_name):
    """Check if a title currently has is_live_match=True in OpenSearch."""
    es = get_es_client()
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


def _fetch_from_opensearch(extra_filters=None, limit=10):
    provider_ids = get_active_provider_ids()
    es = get_es_client()

    filters = [
        {"term":  {"status.keyword": "published"}},
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
                "must_not": [
                    {"terms": {"sub_format.keyword": ["extras", "Extras", "trailers", "Trailers"]}},
                    {"term":  {"is_live_match": True}},   # exclude live matches → test_live_match.py
                ],
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

    # Classify synonyms
    classified_synonyms = []
    for syn in synonyms[:MAX_SYNONYMS_PER_TITLE]:
        if syn and syn.strip():
            classified_synonyms.append({
                "text": syn.strip(),
                "type": "generic" if is_generic_synonym(syn) else "specific"
            })

    return {
        "name":     name,
        "synonyms": classified_synonyms,
        "source":   source_label,

        # All query variations
        "exact":              generate_exact(name),
        "partial_words":      generate_partial_words(name),
        "partial_prefix":     generate_partial_prefix(name),
        "partial_nospace":    generate_partial_nospace(name),
        "fuzzy_swap":         generate_fuzzy_swap(name),
        "fuzzy_delete":       generate_fuzzy_delete(name),
        "fuzzy_extra":        generate_fuzzy_extra(name),
        "case_lower":         generate_case_lower(name),
        "case_upper":         generate_case_upper(name),
        "special_dot":        generate_special_dot(name),
        "special_ampersand":  generate_special_ampersand(name),
    }


# ==============================
# 🔹 PUBLIC FETCH FUNCTIONS
# ==============================

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
    # Only premium content (movies, shows, live_tv, sport — excluding live matches)
    # Live matches are tested separately in test_live_match.py
    return get_premium_fuzzy_synonym_data(limit)


# ==============================
# 🔹 ENTRYPOINT
# ==============================
if __name__ == "__main__":
    data = get_all_fuzzy_synonym_data(limit=3)
    for d in data:
        print(f"\n  Title          : {d['name']}")
        print(f"  Exact          : {d['exact']}")
        print(f"  Partial Words  : {d['partial_words']}")
        print(f"  Partial Prefix : {d['partial_prefix']}")
        print(f"  Partial NoSpace: {d['partial_nospace']}")
        print(f"  Fuzzy Swap     : {d['fuzzy_swap']}")
        print(f"  Fuzzy Delete   : {d['fuzzy_delete']}")
        print(f"  Fuzzy Extra    : {d['fuzzy_extra']}")
        print(f"  Case Lower     : {d['case_lower']}")
        print(f"  Case Upper     : {d['case_upper']}")
        print(f"  Special Dot    : {d['special_dot']}")
        print(f"  Special Amper  : {d['special_ampersand']}")
        print(f"  Synonyms       : {d['synonyms']}")
        print(f"  Source         : {d['source']}")


def get_all_live_match_titles():
    """
    Fetch ALL current live matches from OpenSearch sorted by release_date desc.
    These are the titles that MUST appear when searching generic synonyms.
    """
    now         = datetime.now(timezone.utc)
    today_start = now.replace(hour=0,  minute=0,  second=0,  microsecond=0).isoformat()
    today_end   = now.replace(hour=23, minute=59, second=59, microsecond=999000).isoformat()

    es = get_es_client()
    response = es.search(index=INDEX_NAME, body={
        "size": 100,   # get all live matches
        "_source": ["name", "release_date"],
        "track_total_hits": True,
        "query": {
            "bool": {
                "filter": [
                    {"term":  {"is_live_match": True}},
                    {"range": {"sort_priority_release_date": {
                        "gte": today_start,
                        "lte": today_end
                    }}}
                ]
            }
        },
        "sort": [{"release_date": {"order": "desc"}}]
    })

    titles = [hit["_source"]["name"] for hit in response["hits"]["hits"]]
    print(f"[fuzzy_synonym] Total live matches today: {len(titles)}")
    return titles


def validate_generic_synonym_results(query, platform_config, user_config):
    """
    For generic synonyms like 'today's match', 'live sport' etc.

    Logic:
    1. Fetch ALL live matches from OpenSearch (sorted by release_date desc)
    2. Call search API with the generic query
    3. Check if ALL live matches appear in search results
    4. Report which live matches are MISSING from results (real bugs)

    Returns:
        {
            "total_live":       total live matches in OpenSearch today,
            "found_in_results": how many appear in search results,
            "missing":          list of live titles NOT in search results (bugs),
            "passed":           True if all live matches appear in results,
            "response_time":    API response time
        }
    """
    from utils.api_client import search_api

    # Step 1 — get all live matches from OpenSearch
    all_live_titles = get_all_live_match_titles()

    if not all_live_titles:
        return {
            "total_live":       0,
            "found_in_results": 0,
            "missing":          [],
            "passed":           True,   # no live matches today, skip
            "response_time":    0
        }

    # Step 2 — call search API with generic query
    response      = search_api(query, platform_config, user_config)
    response_time = response.elapsed.total_seconds()
    results       = response.json().get("result", [])

    # Step 3 — check which live titles appear in results
    result_names = [r.get("name", "").lower() for r in results]

    missing      = []
    found_count  = 0

    for live_title in all_live_titles:
        found = any(live_title.lower() in r for r in result_names)
        if found:
            found_count += 1
        else:
            missing.append(live_title)

    return {
        "total_live":       len(all_live_titles),
        "all_live_titles":  all_live_titles,
        "found_in_results": found_count,
        "missing":          missing,
        "passed":           len(missing) == 0,
        "response_time":    response_time
    }