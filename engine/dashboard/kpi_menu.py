"""Standard KPI library for per-client dashboards. Pick a subset at setup.

Each client's dashboard is assembled from these. Values that are not backed by a
live integration are marked is_mock=True everywhere they are used (honesty gate).
"""

KPI_MENU = {
    "followers":           {"label": "Followers",           "source": "social"},
    "engagement_rate":     {"label": "Engagement rate",     "source": "social"},
    "website_visits":      {"label": "Website visits",      "source": "GA4"},
    "website_conversions": {"label": "Website conversions", "source": "GA4"},
    "top_landing_pages":   {"label": "Top landing pages",   "source": "GA4"},
    "posts_shipped":       {"label": "Posts shipped",       "source": "pipeline"},
    "leads":               {"label": "Leads / DMs",         "source": "social"},
    "seo_rank":            {"label": "SEO rank",            "source": "GSC/DataForSEO"},
    "aeo_citations":       {"label": "AEO citations",       "source": "AEO"},
    "revenue_mrr":         {"label": "Revenue / MRR",       "source": "Stripe"},
    "ctr":                 {"label": "CTR",                 "source": "Meta/Zernio"},
    "roas":                {"label": "ROAS",                "source": "Meta"},
}

DEFAULT_KPIS = [
    "followers", "engagement_rate", "website_visits",
    "website_conversions", "posts_shipped", "leads",
]

# Demo values, always surfaced with is_mock=True until a real integration lands.
MOCK_VALUES = {
    "followers": "4,210", "engagement_rate": "5.8%", "website_visits": "1,860",
    "website_conversions": "42", "top_landing_pages": "/spring-routine",
    "posts_shipped": "12", "leads": "37", "seo_rank": "#6 avg",
    "aeo_citations": "3", "revenue_mrr": "$0", "ctr": "n/a", "roas": "n/a",
}


def resolve(kpi_keys):
    """Return [(key, label, source)] for valid keys, in order. Falls back to defaults."""
    out = []
    for k in (kpi_keys or DEFAULT_KPIS):
        if k in KPI_MENU:
            out.append((k, KPI_MENU[k]["label"], KPI_MENU[k]["source"]))
    return out
