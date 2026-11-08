"""Outreach Bridge — sends approved leads to Warmbly for sequencing."""

import logging
import httpx
from app.config import settings
from app.db.client import get_db

log = logging.getLogger(__name__)


async def send_to_warmbly(lead_id: str) -> dict:
    """Called when the user taps [Approve & Send]."""
    db = get_db()
    
    # 1. Load the lead + audit + store
    lead = db.table("leads").select("*").eq("id", lead_id).execute().data
    if not lead:
        return {"ok": False, "error": "lead_not_found"}
    lead = lead[0]
    store = db.table("stores").select("*").eq("id", lead["store_id"]).execute().data[0]
    audit = db.table("audits").select("*").eq("lead_id", lead_id).execute().data
    if not audit:
        return {"ok": False, "error": "audit_not_found"}
    audit = audit[0]
    
    # 2. Build the Warmbly payload
    payload = {
        "email": f"contact@{store.get('domain', 'example.com')}",
        "first_name": store.get("name", "Team"),
        "company": store.get("name", ""),
        "subject": audit["email_subject"],
        "body": audit["email_body"],
        "metadata": {
            "lead_id": lead_id,
            "source": "special-agent-tiktok",
            "platform": "tiktok",
        }
    }
    
    # 3. Send to Warmbly
    if not settings.WARMBLY_WEBHOOK_URL:
        log.warning("WARMBLY_WEBHOOK_URL not set. Payload would be: %s", payload)
        return {"ok": True, "mode": "dry_run", "payload": payload}
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(settings.WARMBLY_WEBHOOK_URL, json=payload)
            r.raise_for_status()
            return {"ok": True, "status": r.status_code}
    except Exception as e:
        log.error("Warmbly call failed: %s", e)
        return {"ok": False, "error": str(e)}
