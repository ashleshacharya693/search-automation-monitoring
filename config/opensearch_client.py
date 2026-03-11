from opensearchpy import OpenSearch

# ==============================
# 🔹 OPENSEARCH CONNECTION
# ==============================
OPENSEARCH_HOST = "vpc-ott-es-prod-tno62hs6fe7gs6zojencjn4eai.ap-south-1.es.amazonaws.com"
INDEX_NAME      = "ott_search_tv"


def get_es_client():
    """Return a connected OpenSearch client."""
    return OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": 443}],
        use_ssl=True,
        verify_certs=True,
        ssl_show_warn=False,
    )