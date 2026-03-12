import requests

BASE_URL   = "https://api2.ottplay.com/api/search-service/v1.1/universal-search"
AUTH_TOKEN = "YOUR_TOKEN"


def search_api(query, platform_config, user_config, page=1, limit=10):
    """Single page search API call."""

    headers = {
        "accept":       "application/json",
        "authorization": f"Bearer {AUTH_TOKEN}",
        "platform":     platform_config["platform"],
        "source":       platform_config["source"],
        "apiversion":   "1",
        "pc_type":      "0",
        "plan_code":    "NA",
        "no_redis":     "true"
    }

    if user_config["client_id"]:
        headers["client_id"] = user_config["client_id"]

    params = {
        "query":        query,
        "limit":        limit,
        "type":         "all",
        "listing":      "true",
        "source":       platform_config["source"],
        "page":         page,
        "ispremium":    "true",
        "is_parental":  "true",
        "request_type": "DIRECT",
        "randomId":     789
    }

    return requests.get(BASE_URL, headers=headers, params=params)


def search_api_all_pages(query, platform_config, user_config, limit=50):
    """
    Paginate through ALL pages of search results.
    Returns combined list of all results across all pages.

    Uses limit=50 per page for faster fetching.
    Stops when:
    - results returned < limit (last page)
    - empty results
    - max 20 pages safety limit
    """
    all_results = []
    page        = 1
    max_pages   = 20  # safety limit

    while page <= max_pages:
        response = search_api(query, platform_config, user_config, page=page, limit=limit)
        results  = response.json().get("result", [])

        if not results:
            break

        all_results.extend(results)

        # If results returned less than limit → last page
        if len(results) < limit:
            break

        page += 1

    print(f"[api] '{query}' → {len(all_results)} total results across {page} pages")
    return all_results