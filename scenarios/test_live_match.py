from scripts.live_match import get_live_match_titles
import pytest
from config.platforms import PLATFORMS
from config.users import USERS
from utils.api_client import search_api

# ✅ Separate key — does NOT interfere with premium results
if not hasattr(pytest, "live_results_summary"):
    pytest.live_results_summary = []

live_match_titles = get_live_match_titles(limit=10)


@pytest.mark.live_match
@pytest.mark.parametrize("query", live_match_titles)
def test_live_match_dataset(query):
    """
    Checks that each today's live match title appears in search results.
    Not checking user_type — just verifying content is reachable.
    """

    expected_title = query
    top_limit = 5
    failed_combinations = []

    for platform_name, platform_config in PLATFORMS.items():

        # Single neutral user — we only care if content exists, not user entitlement
        user_type   = "anonymous"
        user_config = USERS.get(user_type, {})

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

        # ✅ Append to live_results_summary, NOT results_summary
        pytest.live_results_summary.append({
            "Query":               query,
            "Platform":            platform_name,
            "User Type":           user_type,
            "Top Limit":           top_limit,
            "Position Found":      position,
            "Response Time (sec)": round(response_time, 3),
            "Status":              status,
        })

        if position == -1:
            failed_combinations.append(platform_name)

    if failed_combinations:
        pytest.fail(
            f"FAILED → Query: '{query}' | Not found on: {failed_combinations}"
        )