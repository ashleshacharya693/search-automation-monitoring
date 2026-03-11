from scripts.live_match import get_live_match_titles
import pytest
from config.platforms import PLATFORMS
from config.users import USERS
from utils.api_client import search_api

if not hasattr(pytest, "live_results_summary"):
    pytest.live_results_summary = []

# Fetch today's live match titles
live_match_titles = get_live_match_titles(limit=10)

if not live_match_titles:
    pytest.skip("No live matches scheduled for today", allow_module_level=True)


@pytest.mark.live_match
@pytest.mark.parametrize("query", live_match_titles)
def test_live_match_dataset(query):
    """
    Checks that each today's live match title appears in search results
    across all platforms and all user types.
    """

    expected_title = query
    top_limit = 5
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
                "Platform":            platform_name,
                "User Type":           user_type,
                "Top Limit":           top_limit,
                "Position Found":      position,
                "Response Time (sec)": round(response_time, 3),
                "Status":              status,
            })

            if position == -1:
                failed_combinations.append(f"{platform_name}-{user_type}")

    if failed_combinations:
        pytest.fail(
            f"FAILED → Query: '{query}' | Failed for: {failed_combinations}"
        )