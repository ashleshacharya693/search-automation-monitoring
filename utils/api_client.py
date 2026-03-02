import requests

BASE_URL = "https://api2.ottplay.com/api/search-service/v1.1/universal-search"
AUTH_TOKEN = "YOUR_TOKEN"

def search_api(query, platform_config, user_config):

    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {AUTH_TOKEN}",
        "platform": platform_config["platform"],
        "source": platform_config["source"],
        "apiversion": "1",
        "pc_type": "0",
        "plan_code": "NA",
        "no_redis": "true"
    }

    if user_config["client_id"]:
        headers["client_id"] = user_config["client_id"]

    params = {
        "query": query,
        "limit": 10,
        "type": "all",
        "listing": "true",
        "source": platform_config["source"],
        "page": 1,
        "ispremium": "true",
        "is_parental": "true",
        "request_type": "DIRECT",
        "randomId": 789
    }

    return requests.get(BASE_URL, headers=headers, params=params)