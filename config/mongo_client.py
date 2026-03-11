from pymongo import MongoClient

# ==============================
# 🔹 MONGODB CONNECTION
# ==============================
MONGO_URI = "mongodb://SeniorDev_Prod:QvoBjOuW0gjpUyHnwHW2@10.135.16.11:27017,10.135.16.12:27017,10.135.24.11:27017/ott-play?authSource=admin&replicaSet=ott-prod&readPreference=primary&ssl=false"
MONGO_DB         = "ott-play"
MONGO_COLLECTION = "subscription_plan"

# ==============================
# 🔹 PLAN CODES
# ==============================
PLAN_ACTIVE = "ott_super_play_annual"


def _get_subscription_collection():
    """Return the subscription_plan collection."""
    client = MongoClient(MONGO_URI)
    db     = client[MONGO_DB]
    return client, db[MONGO_COLLECTION]


def _extract_provider_ids(plan, plan_code):
    """
    Extract provider ID strings from a subscription plan document.
    Handles both:
      - List of ObjectIds:  providers: [ObjectId("abc"), ObjectId("xyz")]
      - List of dicts:      providers: [{"_id": ObjectId("abc")}, ...]
    """
    if not plan:
        raise ValueError(f"No plan found in MongoDB for plan_code: '{plan_code}'")

    providers    = plan.get("providers", [])
    provider_ids = []

    for provider in providers:
        if isinstance(provider, dict):
            # dict format: {"_id": ObjectId(...)} or {"id": "..."}
            pid = provider.get("_id") or provider.get("id")
        else:
            # raw ObjectId format
            pid = provider

        if pid:
            provider_ids.append(str(pid))

    if not provider_ids:
        raise ValueError(f"No provider IDs found in plan: '{plan_code}'")

    return provider_ids


def get_active_provider_ids():
    """
    Fetch provider IDs from subscription_plan collection
    for plan_code 'ott_super_play_annual'.
    Used in: live_match.py, premium.py
    """
    client, collection = _get_subscription_collection()
    try:
        plan         = collection.find_one({"plan_code": PLAN_ACTIVE})
        provider_ids = _extract_provider_ids(plan, PLAN_ACTIVE)
        print(f"[mongo] ✅ Premium providers fetched: {len(provider_ids)} (plan: {PLAN_ACTIVE})")
        return provider_ids
    finally:
        client.close()


def get_offboarded_provider_ids():
    """
    Fetch provider IDs from ott-play > providers collection
    where is_provider_off_boarded is True.
    Used in: future offboarded provider scripts
    """
    client = MongoClient(MONGO_URI)
    try:
        db         = client[MONGO_DB]
        collection = db["providers"]

        offboarded   = collection.find(
            {"is_provider_off_boarded": True},
            {"_id": 1}
        )
        provider_ids = [str(doc["_id"]) for doc in offboarded]

        if not provider_ids:
            print("[mongo] ⚠️  No offboarded providers found.")
            return []

        print(f"[mongo] ✅ Offboarded providers fetched: {len(provider_ids)}")
        return provider_ids
    finally:
        client.close()


def get_provider_ids_by_plan(plan_code):
    """
    Generic fetch — use this when you need providers for any custom plan code.
    Usage: get_provider_ids_by_plan("some_plan_code")
    """
    client, collection = _get_subscription_collection()
    try:
        plan         = collection.find_one({"plan_code": plan_code})
        provider_ids = _extract_provider_ids(plan, plan_code)
        print(f"[mongo] ✅ Providers fetched: {len(provider_ids)} (plan: {plan_code})")
        return provider_ids
    finally:
        client.close()


def user_has_offboarded_provider(user_id, offboarded_provider_ids):
    """
    Check if a user has an active subscription that includes
    any offboarded provider.

    Logic:
    - Collection: ottplay_v2_user_subscription
    - Filter: user_id, status=active, expiry_date >= today
    - Check: if any provider in their subscription matches offboarded_provider_ids

    Returns True  → user HAS offboarded provider → content SHOULD appear
    Returns False → user does NOT → content should be HIDDEN
    """
    from datetime import datetime, timezone

    client = MongoClient(MONGO_URI)
    try:
        db         = client[MONGO_DB]
        collection = db["ottplay_v2_user_subscription"]
        today      = datetime.now(timezone.utc)

        subscription = collection.find_one({
            "user_id":     str(user_id),
            "status":      "active",
            "expiry_date": {"$gte": today}
        })

        if not subscription:
            print(f"[mongo] No active subscription found for user: {user_id}")
            return False

        # Extract provider IDs from user's subscription
        user_providers = []
        for provider in subscription.get("providers", []):
            if isinstance(provider, dict):
                pid = provider.get("_id") or provider.get("id")
            else:
                pid = provider
            if pid:
                user_providers.append(str(pid))

        # Check if any offboarded provider exists in user's subscription
        offboarded_set = set(offboarded_provider_ids)
        has_offboarded = any(p in offboarded_set for p in user_providers)

        print(f"[mongo] User {user_id} has offboarded provider: {has_offboarded}")
        return has_offboarded

    finally:
        client.close()