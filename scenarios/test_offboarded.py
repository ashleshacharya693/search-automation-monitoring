from scripts.offboarded import get_offboarded_titles
from config.mongo_client import get_offboarded_provider_ids, user_has_offboarded_provider
import pytest
from config.platforms import PLATFORMS
from config.users import USERS
from utils.api_client import search_api

if not hasattr(pytest, "offboarded_results_summary"):
    pytest.offboarded_results_summary = []

# Fetch offboarded titles with provider names
offboarded_data = get_offboarded_titles(limit=100)

if not offboarded_data:
    pytest.skip("No offboarded content found", allow_module_level=True)

# Fetch offboarded provider IDs once for user subscription check
offboarded_provider_ids = get_offboarded_provider_ids()

# ✅ Pre-check each user — does their active subscription include an offboarded provider?
# This is computed once at session start, not per test
user_has_offboarded = {}
for user_type, user_config in USERS.items():
    client_id = user_config.get("client_id")
    if client_id:
        user_has_offboarded[user_type] = user_has_offboarded_provider(
            client_id, offboarded_provider_ids
        )
    else:
        # non_logged_in has no client_id — never has a subscription
        user_has_offboarded[user_type] = False

print(f"\n[offboarded] User subscription check: {user_has_offboarded}")

# Parametrize as (name, provider) tuples
offboarded_params = [(r["name"], r["provider"]) for r in offboarded_data]


@pytest.mark.offboarded
@pytest.mark.parametrize("query,provider_name", offboarded_params)
def test_offboarded_dataset(query, provider_name):
    """
    Offboarded content visibility logic:

    - User HAS active subscription with offboarded provider
      → content SHOULD appear → PASSED if found, FAILED if not found

    - User does NOT have offboarded provider (expired, non-subscribed, non-logged-in)
      → content should be HIDDEN → PASSED if not found, FAILED if found
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

            found = position != -1

            # ✅ Logic depends on whether user has offboarded provider in subscription
            if user_has_offboarded[user_type]:
                # User subscribed to this provider → content MUST appear
                status   = "PASSED" if found else "FAILED"
                expected = "Should appear (active subscription with offboarded provider)"
            else:
                # User not subscribed / expired / non-logged-in → content must be HIDDEN
                status   = "PASSED" if not found else "FAILED"
                expected = "Should be hidden (no active subscription for offboarded provider)"

            pytest.offboarded_results_summary.append({
                "Query":               query,
                "Provider":            provider_name,
                "Platform":            platform_name,
                "User Type":           user_type,
                "Has Offboarded Sub":  user_has_offboarded[user_type],
                "Expected Behavior":   expected,
                "Top Limit":           top_limit,
                "Position Found":      position if found else "Not Found",
                "Response Time (sec)": round(response_time, 3),
                "Status":              status,
            })

            if status == "FAILED":
                failed_combinations.append(f"{platform_name}-{user_type}")

    if failed_combinations:
        pytest.fail(
            f"FAILED → '{query}' [{provider_name}] | "
            f"Failed for: {failed_combinations}"
        )