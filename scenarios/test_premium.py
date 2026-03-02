from scripts.premium import get_premium_titles
import pytest
from config.platforms import PLATFORMS
from config.users import USERS
from utils.api_client import search_api

results_summary = []

premium_titles = get_premium_titles(limit=100)

@pytest.mark.premium
@pytest.mark.parametrize("query", premium_titles)
def test_premium_dataset(query):

    expected_title = query   # Expected result is same as query
    top_limit = 5            # Fixed rule → must appear within Top 5

    for platform_name, platform_config in PLATFORMS.items():
        for user_type, user_config in USERS.items():

            response = search_api(query, platform_config, user_config)
            response_time = response.elapsed.total_seconds()

            results = response.json().get("result", [])
            top_results = results[:top_limit]

            position = -1

            for index, item in enumerate(top_results):
                if expected_title.lower() in item.get("name", "").lower():
                    position = index + 1
                    break

            status = "PASSED" if position != -1 else "FAILED"

            results_summary.append({
                "Query": query,
                "Platform": platform_name,
                "User Type": user_type,
                "Top Limit": top_limit,
                "Position Found": position,
                "Response Time (sec)": round(response_time, 3),
                "Status": status
            })

            if position == -1:
                pytest.fail(
                    f"FAILED → Query:{query} | Platform:{platform_name} | User:{user_type}"
                )