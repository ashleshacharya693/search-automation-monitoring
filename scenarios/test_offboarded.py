from scripts.offboarded import get_offboarded_titles
import pytest
from config.platforms import PLATFORMS
from config.users import USERS
from utils.api_client import search_api

if not hasattr(pytest, "offboarded_results_summary"):
    pytest.offboarded_results_summary = []

# Fetch offboarded titles with their provider names
offboarded_data = get_offboarded_titles(limit=100)

if not offboarded_data:
    pytest.skip("No offboarded content found", allow_module_level=True)

# Parametrize as (name, provider) tuples
offboarded_params = [(r["name"], r["provider"]) for r in offboarded_data]


@pytest.mark.offboarded
@pytest.mark.parametrize("query,provider_name", offboarded_params)
def test_offboarded_dataset(query, provider_name):
    """
    Checks that offboarded provider content does NOT appear in search results.
    If the content IS found — test FAILS (offboarded content should not be visible).
    Runs across all platforms and all user types.
    """

    expected_title = query
    top_limit      = 5
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

            # ✅ For offboarded: PASSED means NOT found, FAILED means it appeared
            status = "FAILED" if position != -1 else "PASSED"

            pytest.offboarded_results_summary.append({
                "Query":               query,
                "Provider":            provider_name,    # ✅ offboarded provider name
                "Platform":            platform_name,
                "User Type":           user_type,
                "Top Limit":           top_limit,
                "Position Found":      position if position != -1 else "Not Found",
                "Response Time (sec)": round(response_time, 3),
                "Status":              status,
            })

            if position != -1:
                failed_combinations.append(f"{platform_name}-{user_type}")

    if failed_combinations:
        pytest.fail(
            f"FAILED → Offboarded content '{query}' [{provider_name}] "
            f"still appearing on: {failed_combinations}"
        )