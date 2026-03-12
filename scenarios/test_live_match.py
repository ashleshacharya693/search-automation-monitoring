from scripts.live_match import get_live_match_titles
from scripts.fuzzy_synonym import validate_generic_synonym_results, GENERIC_SYNONYMS
import pytest
from config.platforms import PLATFORMS
from config.users import USERS
from utils.api_client import search_api

if not hasattr(pytest, "live_results_summary"):
    pytest.live_results_summary = []

# Fetch today's live match titles
live_match_titles = get_live_match_titles(limit=100)

if not live_match_titles:
    pytest.skip("No live matches scheduled for today", allow_module_level=True)




# ==============================
# 🔹 TEST 1 — Each live match appears in search
# Across all platforms and user types
# ==============================
@pytest.mark.live_match
@pytest.mark.parametrize("query", live_match_titles)
def test_live_match_search(query):
    """
    For each today's live match title — check it appears
    in top 5 results across all platforms and user types.
    """
    expected_title      = query
    top_limit           = 5
    failed_combinations = []

    for platform_name, platform_config in PLATFORMS.items():
        for user_type, user_config in USERS.items():

            response      = search_api(query, platform_config, user_config)
            response_time = response.elapsed.total_seconds()

            results     = response.json().get("result", [])
            top_results = results[:top_limit]

            position = -1
            for index, item in enumerate(top_results):
                if expected_title.lower() in item.get("name", "").lower():
                    position = index + 1
                    break

            status = "PASSED" if position != -1 else "FAILED"

            pytest.live_results_summary.append({
                "Query":               query,
                "Test Type":           "live_match_search",
                "Platform":            platform_name,
                "User Type":           user_type,
                "Top Limit":           top_limit,
                "Position Found":      position if position != -1 else "Not Found",
                "Found Live Matches":  "",
                "Missing Live Matches": "",
                "Response Time (sec)": round(response_time, 3),
                "Status":              status,
            })

            if position == -1:
                failed_combinations.append(f"{platform_name}-{user_type}")

    if failed_combinations:
        pytest.fail(
            f"FAILED → Query: '{query}' | Failed for: {failed_combinations}"
        )


# ==============================
# 🔹 TEST 2 — Generic synonym quality check
# e.g. "today's match", "live sport" → ALL live matches should appear
# ==============================
@pytest.mark.live_match
@pytest.mark.parametrize("query", sorted(GENERIC_SYNONYMS))
def test_generic_synonym_live_coverage(query):
    """
    For generic synonyms like 'today's match', 'live sport' etc.
    ALL today's live matches must appear in search results.
    Tested across all platforms and all user types.
    Missing matches = real bug.
    """
    failed_combinations = []

    for platform_name, platform_config in PLATFORMS.items():
        for user_type, user_config in USERS.items():

            result = validate_generic_synonym_results(query, platform_config, user_config)

            if result["total_live"] == 0:
                pytest.skip(f"No live matches today — skipping generic synonym test for '{query}'")

            status = "PASSED" if result["passed"] else "FAILED"

            found_titles = [t for t in result["all_live_titles"] if t not in result["missing"]]
            found_str    = ", ".join(found_titles)       if found_titles        else "None"
            missing_str  = ", ".join(result["missing"])  if result["missing"]   else "None"

            pytest.live_results_summary.append({
                "Query":                query,
                "Test Type":            "synonym_generic",
                "Platform":             platform_name,
                "User Type":            user_type,
                "Top Limit":            result["total_live"],
                "Position Found":       f"{result['found_in_results']}/{result['total_live']} found",
                "Found Live Matches":   found_str,
                "Missing Live Matches": missing_str,
                "Response Time (sec)":  round(result["response_time"], 3),
                "Status":               status,
            })

            if not result["passed"]:
                failed_combinations.append(f"{platform_name}-{user_type}")

    if failed_combinations:
        pytest.fail(
            f"FAILED → [synonym_generic] Query: '{query}' | "
            f"Missing live matches on: {failed_combinations}"
        )