"""Gemini audit generator — TikTok version."""

from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import settings

log = logging.getLogger(__name__)


class AdInput(BaseModel):
    domain: str
    brand: str | None = None
    sender: str = "the team"
    headline: str | None = None
    primary_text: str | None = None
    image_url: str | None = None
    days_active: int | None = None

class AuditResult(BaseModel):
    diagnosis: str
    hook1_angle_name: str
    hook1_target: str
    hook1_headline: str
    hook1_text: str
    hook1_image: str
    hook2_angle_name: str
    hook2_target: str
    hook2_headline: str
    hook2_text: str
    hook2_image: str
    email_subject: str
    email_body: str


SYSTEM = """You are a senior direct-response copywriter who writes cold outreach to founders of businesses running TikTok ads.

The reader is a busy founder. They care about: high CPCs, low conversion rates, wasted ad spend, and looking amateur next to competitors.

Rules:
- DIAGNOSIS: name the founder's pain in money terms. Never use phrases like "loses urgency", "credibility", or "aesthetic". Use language like "your TikTok ad spend is driving up your CAC".
- HOOKS: address the CONSUMER's underlying frustration, not the product feature. Each hook is a full angle with a psychological name, a target buyer, a headline, body copy, and a specific visual direction (TikTok native: UGC, POV, green screen, etc.).
- EMAIL: give both hooks away inside the email using the exact labeled format in the worked example. Tell them to steal the angles. Do not ask for a meeting. Do not ask "would you be open to". Close with one line of credibility.
- Never invent specific claims, prices, discount codes, or stats about the brand.
- Write in the voice of a direct-response marketer, not an AI assistant.
"""

WORKED_EXAMPLE = """
--- WORKED EXAMPLE ---
Input: Brand "GlowLab", 94 days, product: vitamin C serum, TikTok ad.

Subject: Quick creative fix for GlowLab's Vitamin C ad (Fatigue at 94 days)

Hi GlowLab team,

I noticed your "New Serum Just Dropped" TikTok campaign has been running for 94 days straight. While the aesthetic is beautiful, running a launch angle for over three months inevitably triggers heavy ad fatigue — meaning your TikTok CPCs are climbing, your ROAS is dipping, and you're bleeding budget on cold audiences who don't care about a "launch."

Cold audiences don't buy drops; they buy skin transformations.

To help protect your margins this week, I wrote two high-converting, benefit-driven angles based on your customers' deepest frustrations. Feel free to steal these and drop them right into Ads Manager:

Angle 1: The "Tired Skin" Interrupt (Targets the working professional)
• Headline: Looks Like 8 Hours Of Sleep In A Dropper.
• Text: If your skin looks dull and tired by 2 PM, your current moisturizer isn't cutting it. Our fast-absorbing Vitamin C targets dark spots and restores morning radiance without that sticky, greasy residue under your makeup.
• Visual Asset Idea: Split-screen overlay. Left: A phone screen showing a 7:00 AM alarm. Right: Active texture close-up showing the lightweight serum absorbing instantly into bare, glowing cheekbones.

Angle 2: The "Wasted Money" Callout (Targets the skeptical buyer)
• Headline: Tired of Vitamin C Serums That Do Nothing?
• Text: Most formulas oxidize before they even hit your skin. GlowLab's potent, stabilized formula delivers active antioxidants deep into the skin barrier to clear dark spots in seconds. Just 3 drops every morning for predictable luminosity.
• Visual Asset Idea: Close-up macro shot of the glass dropper dispensing a single, pristine golden droplet onto skin in bright, natural morning sunlight.

We build and deploy performance assets like this every day to scale e-commerce brands past ad fatigue. I hope these angles help lower your acquisition costs this week.

Best,
James Liberty
--- END WORKED EXAMPLE ---
"""


def _build_user_prompt(ad: AdInput) -> str:
    return f"""{WORKED_EXAMPLE}

Now produce the same for this input. Sender name for the signoff: {ad.sender}.

Platform: TikTok
Brand domain: {ad.domain}
Brand name:   {ad.brand or "(unknown)"}
Days this ad has been live: {ad.days_active or "(unknown)"}
Current headline: {ad.headline or "(none)"}
Current primary text: {ad.primary_text or "(none)"}
Image reference: {ad.image_url or "(none)"}
"""


_client: genai.Client | None = None

def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def generate_audit(ad: AdInput) -> AuditResult:
    client = _get_client()
    prompt = _build_user_prompt(ad)
    last_err: Exception | None = None

    for model_name in settings.GEMINI_MODELS:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM,
                    response_mime_type="application/json",
                    response_schema=AuditResult,
                    temperature=0.9,
                ),
            )
            return AuditResult.model_validate(json.loads(resp.text))
        except Exception as e:
            log.warning("model %s failed: %s", model_name, e)
            last_err = e
            continue

    raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")
