"""Fetches ads from TikTok via Apify."""

import logging
from apify_client import ApifyClient
from app.config import settings

log = logging.getLogger(__name__)

ACTOR_ID = "hyperbach/tiktok-ad-library-scraper"

def fetch_stale_ads(country: str = "US", limit: int = 10) -> list[dict]:
    if not hasattr(settings, "APIFY_API_TOKEN"):
        log.error("APIFY_API_TOKEN is missing!")
        return []

    client = ApifyClient(settings.APIFY_API_TOKEN)
    
    run_input = {
        "topAdsCountries": [country],
        "topAdsPeriod": "30",
        "topAdsSortBy": "ctr",
        "topAdsMetrics": True,
        "maxAds": limit
    }

    log.info("Starting TikTok Apify actor for country: %s...", country)
    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input, timeout_secs=180)
        if not run:
            return []

        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        log.info("Apify returned %d TikTok ads.", len(dataset_items))
        
        leads = []
        for item in dataset_items:
            brand = item.get("advertiser_name") or "Unknown Brand"
            domain = "unknown.com"
            dest_url = item.get("destination_url", "")
            if dest_url:
                domain = dest_url.split("//")[-1].split("/")[0]

            primary_text = item.get("body_text", "")
            profile_uri = f"https://www.tiktok.com/search?q={brand.replace(' ', '%20')}"
            
            leads.append({
                "domain": domain,
                "brand": brand,
                "ad_archive_id": str(item.get("creative_id", "")),
                "days_active": 60,
                "ad_headline": "",
                "ad_primary": primary_text,
                "ad_image_url": item.get("image_url", ""),
                "page_profile_uri": profile_uri,
            })
            
        return leads
    except Exception as e:
        log.error("Apify TikTok error: %s", e)
        return []
