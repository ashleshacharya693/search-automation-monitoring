from scripts.fuzzy_synonym import (
    get_all_fuzzy_synonym_data,
    is_currently_live,
    validate_generic_synonym_results
)
import pytest
from config.platforms import PLATFORMS
from config.users import USERS
from utils.api_client import search_api

if not hasattr(pytest, "fuzzy_results_summary"):
    pytest.fuzzy_results_summary = []

# Fetch data
all_data = get_all_fuzzy_synonym_data(limit=50)

if not all_data:
    pytest.skip("No data available for fuzzy/synonym testing", allow_module_level=True)

# ✅ Fixed platform and user
_platform_name   = "web"
_platform_config = PLATFORMS[_platform_name]
_user_type       = "subscribed"
_user_config     = USERS[_user_type]

# ==============================
# 🔹 TOP LIMIT PER QUERY TYPE
# ==============================
TOP_LIMITS = {
    "exact":             1,
    "partial_words":     5,
    "partial_prefix":    10,
    "partial_nospace":   1,
    "fuzzy_swap":        1,
    "fuzzy_delete":      1,
    "fuzzy_extra":       1,
    "synonym_specific":  1,
    "case_lower":        1,
    "case_upper":        1,
    "special_dot":       1,
    "special_ampersand": 1,
}

# ==============================
# Build parametrize lists
# Separate generic synonyms from the rest
# ==============================
test_params          = []   # all non-generic tests
generic_synonym_params = []  # generic synonym tests (unique queries only)

seen_generic_queries = set()  # avoid duplicate generic queries

for item in all_data:
    name   = item["name"]
    source = item["source"]

    # Non-generic tests — check specific title position
    test_params.append((name, item["exact"],             "exact",             "N/A", source))
    test_params.append((name, item["partial_words"],     "partial_words",     "N/A", source))
    test_params.append((name, item["partial_prefix"],    "partial_prefix",    "N/A", source))
    test_params.append((name, item["partial_nospace"],   "partial_nospace",   "N/A", source))
    test_params.append((name, item["fuzzy_swap"],        "fuzzy_swap",        "N/A", source))
    test_params.append((name, item["fuzzy_delete"],      "fuzzy_delete",      "N/A", source))
    test_params.append((name, item["fuzzy_extra"],       "fuzzy_extra",       "N/A", source))
    test_params.append((name, item["case_lower"],        "case_lower",        "N/A", source))
    test_params.append((name, item["case_upper"],        "case_upper",        "N/A", source))
    test_params.append((name, item["special_dot"],       "special_dot",       "N/A", source))
    test_params.append((name, item["special_ampersand"], "special_ampersand", "N/A", source))

    for syn in item["synonyms"]:
        if syn["type"] == "specific":
            test_params.append((name, syn["text"], "synonym_specific", "specific", source))
        else:
            # Generic synonyms — deduplicate, test result quality not specific title
            if syn["text"] not in seen_generic_queries:
                seen_generic_queries.add(syn["text"])
                generic_synonym_params.append((syn["text"], source))


# ==============================
# 🔹 TEST 1 — All non-generic queries
# ==============================
@pytest.mark.fuzzy_synonym
@pytest.mark.parametrize("expected_title,query,query_type,synonym_category,source", test_params)
def test_fuzzy_synonym_dataset(expected_title, query, query_type, synonym_category, source):
    """
    Tests exact, partial, fuzzy, case, special char, and specific synonym queries.
    Checks if expected title appears within top_limit results.
    """
    top_limit = TOP_LIMITS.get(query_type, 1)

    response      = search_api(query, _platform_config, _user_config)
    response_time = response.elapsed.total_seconds()

    results     = response.json().get("result", [])
    top_results = results[:top_limit]

    position = -1
    for index, item in enumerate(top_results):
        if expected_title.lower() in item.get("name", "").lower():
            position = index + 1
            break

    status = "PASSED" if position != -1 else "FAILED"

    pytest.fuzzy_results_summary.append({
        "Expected Title":      expected_title,
        "Query Used":          query,
        "Query Type":          query_type,
        "Synonym Category":    synonym_category,
        "Content Source":      source,
        "Platform":            _platform_name,
        "User Type":           _user_type,
        "Top Limit":           top_limit,
        "Position Found":      position if position != -1 else "Not Found",
        "Response Time (sec)": round(response_time, 3),
        "Status":              status,
    })

    if position == -1:
        pytest.fail(
            f"FAILED → [{query_type}] "
            f"Query: '{query}' | Expected: '{expected_title}'"
        )


# ==============================
# 🔹 TEST 2 — Generic synonym quality check
# Checks ALL results are live, not just one title
# ==============================
@pytest.mark.fuzzy_synonym
@pytest.mark.parametrize("query,source", generic_synonym_params)
def test_generic_synonym_result_quality(query, source):
    """
    For generic synonyms like 'today's match', 'live sport' etc.
    Validates that ALL results returned are live matches.
    A non-live result appearing = real bug in search ranking.
    """
    result = validate_generic_synonym_results(query, _platform_config, _user_config)

    if result["total_live"] == 0:
        pytest.skip(f"No live matches today — skipping generic synonym test for '{query}'")

    status = "PASSED" if result["passed"] else "FAILED"

    # Build readable live match summary
    found_titles   = [t for t in result["all_live_titles"] if t not in result["missing"]]
    missing_titles = result["missing"]

    found_str  = ", ".join(found_titles)  if found_titles  else "None"
    missing_str = ", ".join(missing_titles) if missing_titles else "None"

    pytest.fuzzy_results_summary.append({
        "Expected Title":        f"ALL {result['total_live']} live matches should appear",
        "Query Used":            query,
        "Query Type":            "synonym_generic",
        "Synonym Category":      "generic",
        "Content Source":        source,
        "Platform":              _platform_name,
        "User Type":             _user_type,
        "Top Limit":             result["total_live"],
        "Position Found":        f"{result['found_in_results']}/{result['total_live']} found",
        "Found Live Matches":    found_str,
        "Missing Live Matches":  missing_str,
        "Response Time (sec)":   round(result["response_time"], 3),
        "Status":                status,
    })

    if not result["passed"]:
        pytest.fail(
            f"FAILED → [synonym_generic] Query: '{query}' | "
            f"Missing live matches: {result['missing']}"
        )