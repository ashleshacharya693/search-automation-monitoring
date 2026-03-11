from scripts.fuzzy_synonym import get_all_fuzzy_synonym_data, is_currently_live
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
# 🔹 PARTIAL QUERY GENERATOR
# ==============================
def generate_partial(text):
    """
    Mimics how a real human types a partial search query —
    just the first 2 words of the title, like autocomplete behavior.
    e.g. "Sunderland vs Liverpool 2026" → "Sunderland vs"
         "ZEE Chitra Gaurav 2026"       → "ZEE Chitra"
    """
    words = text.split()
    return " ".join(words[:2]) if len(words) >= 2 else text


# ==============================
# Build parametrize list
# ==============================
test_params = []

for item in all_data:
    name   = item["name"]
    source = item["source"]

    # 1. Fuzzy test
    test_params.append((name, item["typo"], "fuzzy", "N/A", source))

    # 2. Partial search test
    partial = generate_partial(name)
    if partial.lower() != name.lower():
        test_params.append((name, partial, "partial", "N/A", source))

    # 3. Synonym tests
    for syn in item["synonyms"]:
        test_params.append((name, syn["text"], "synonym", syn["type"], source))


@pytest.mark.fuzzy_synonym
@pytest.mark.parametrize("expected_title,query,query_type,synonym_category,source", test_params)
def test_fuzzy_synonym_dataset(expected_title, query, query_type, synonym_category, source):
    """
    fuzzy   : typo query → expects original title at position 1
    partial : incomplete query → expects original title at position 1
    specific: specific synonym → expects original title at position 1
    generic : generic synonym → checks is_live_match first,
              if live → top 5, if not live → skip
    """

    if query_type == "synonym" and synonym_category == "generic":
        if not is_currently_live(expected_title):
            pytest.skip(f"'{expected_title}' is no longer live — skipping generic synonym test")
        top_limit = 5
    else:
        top_limit = 1

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
            f"FAILED → [{query_type.upper()} | {synonym_category}] "
            f"Query: '{query}' | Expected: '{expected_title}'"
        )