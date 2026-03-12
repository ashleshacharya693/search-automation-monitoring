from scripts.sport_tournament import get_tournaments, get_matches_for_tournament
import pytest
from config.platforms import PLATFORMS
from config.users import USERS
from utils.api_client import search_api

if not hasattr(pytest, "tournament_results_summary"):
    pytest.tournament_results_summary = []

if not hasattr(pytest, "empty_tournament_results_summary"):
    pytest.empty_tournament_results_summary = []

# Fetch all tournaments (last 30 days, max 30)
all_tournaments = get_tournaments()

if not all_tournaments:
    pytest.skip("No tournaments found in last 30 days", allow_module_level=True)

# Split into tournaments with matches and without
tournaments_with_matches    = [t for t in all_tournaments if t["match_count"] > 0]
tournaments_without_matches = [t for t in all_tournaments if t["match_count"] == 0]

print(f"\n[tournament] With matches   : {len(tournaments_with_matches)}")
print(f"[tournament] Without matches: {len(tournaments_without_matches)}")


# ==============================
# 🔹 Build search queries per tournament
# tournament_name + synonyms (if any)
# ==============================
# (tournament_name, query, query_label, matches)
tournament_params = []

for t in tournaments_with_matches:
    matches = get_matches_for_tournament(t["tournament_name"])
    if not matches:
        continue

    # Search by tournament name
    tournament_params.append((
        t["tournament_name"],
        t["tournament_name"],
        "tournament_name",
        matches
    ))

    # Search by each synonym if available
    for syn in t["tournament_synonyms"]:
        tournament_params.append((
            t["tournament_name"],
            syn,
            "tournament_synonym",
            matches
        ))

# Empty tournament params
empty_tournament_params = [
    (t["tournament_name"], t["tournament_name"]) 
    for t in tournaments_without_matches
]


# ==============================
# 🔹 TEST 1 — Tournament match coverage
# All matches under tournament should appear in search results
# Across all platforms and user types
# ==============================
@pytest.mark.sport_tournament
@pytest.mark.parametrize("tournament_name,query,query_label,matches", tournament_params)
def test_tournament_match_coverage(tournament_name, query, query_label, matches):
    """
    Search by tournament name / synonym → all matches should appear in results.
    Tested across all platforms and all user types.
    """
    top_limit           = len(matches)   # expect all matches to appear
    failed_combinations = []

    for platform_name, platform_config in PLATFORMS.items():
        for user_type, user_config in USERS.items():

            response      = search_api(query, platform_config, user_config)
            response_time = response.elapsed.total_seconds()
            results       = response.json().get("result", [])
            result_names  = [r.get("name", "").lower() for r in results]

            for match in matches:
                match_name = match["name"]
                found      = any(match_name.lower() in r for r in result_names)
                position   = next(
                    (i + 1 for i, r in enumerate(result_names) if match_name.lower() in r),
                    None
                )

                status = "PASSED" if found else "FAILED"

                pytest.tournament_results_summary.append({
                    "Tournament Name":  tournament_name,
                    "Query Used":       query,
                    "Query Type":       query_label,
                    "Match Name":       match_name,
                    "Sports Category":  match["sports_category"],
                    "Provider":         match["provider"],
                    "Release Date":     match["release_date"][:10] if match["release_date"] else "",
                    "Platform":         platform_name,
                    "User Type":        user_type,
                    "Position Found":   position if found else "Not Found",
                    "Response Time (sec)": round(response_time, 3),
                    "Status":           status,
                })

                if not found:
                    failed_combinations.append(
                        f"{match_name} | {platform_name}-{user_type}"
                    )

    if failed_combinations:
        pytest.fail(
            f"FAILED → Tournament: '{tournament_name}' | Query: '{query}' | "
            f"Missing: {failed_combinations}"
        )


# ==============================
# 🔹 TEST 2 — Empty tournament check
# Tournaments with no matches should return no results
# ==============================
@pytest.mark.sport_tournament
@pytest.mark.parametrize("tournament_name,query", empty_tournament_params)
def test_empty_tournament_no_results(tournament_name, query):
    """
    Tournaments with no matches should return empty results.
    If results appear → ghost tournament bug.
    Tested across all platforms and all user types.
    """
    failed_combinations = []

    for platform_name, platform_config in PLATFORMS.items():
        for user_type, user_config in USERS.items():

            response      = search_api(query, platform_config, user_config)
            response_time = response.elapsed.total_seconds()
            results       = response.json().get("result", [])
            result_count  = len(results)

            status = "PASSED" if result_count == 0 else "FAILED"

            pytest.empty_tournament_results_summary.append({
                "Tournament Name":     tournament_name,
                "Query Used":          query,
                "Platform":            platform_name,
                "User Type":           user_type,
                "Results Returned":    result_count,
                "Response Time (sec)": round(response_time, 3),
                "Status":              status,
            })

            if result_count > 0:
                failed_combinations.append(
                    f"{platform_name}-{user_type} ({result_count} results)"
                )

    if failed_combinations:
        pytest.fail(
            f"FAILED → Empty tournament '{tournament_name}' showing results | "
            f"Failed for: {failed_combinations}"
        )