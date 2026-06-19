import json
import os
import random
import logging
from typing import Dict, Any, Optional

import gemini_manager
try:
    from google import genai
except ImportError:
    pass

logger = logging.getLogger(__name__)

ANTI_AI_PROMPT = """
ATURAN GAYA BAHASA (ANTI-AI WRITING LAYER):
1. HARUS terdengar seperti pengguna Threads Indonesia asli yang sedang ngobrol kasual. DILARANG menggunakan gaya bahasa AI, Customer Support, Motivator, atau Interviewer.
2. DILARANG KERAS menggunakan frasa basi: "sangat menarik", "terima kasih telah berbagi", "apa yang membuat kamu", "saya setuju", "hal yang menarik", "menurut saya", "bagaimana pendapatmu", "bisakah kamu menjelaskan".
3. Gunakan kata gaul secukupnya secara natural (contoh: wkwk, anjir, relate banget, gue juga, jujur, kadang, sering banget, ngl). DILARANG memaksakan slang di setiap balasan.
4. STRUKTUR YANG DIHARAPKAN: Reaksi -> Opini -> Observasi Pribadi. DILARANG KERAS banyak bertanya.
5. Biarkan ada sedikit ketidaksempurnaan atau kata kasual. JANGAN gunakan tata bahasa formal/kaku.
"""

# Configurable Mode: "FAST" (1 call) or "ADVANCED" (2 calls)
MODE = os.getenv("ENGAGEMENT_MODE", "ADVANCED")

STYLES = [
    "casual", "curious", "experienced user", 
    "beginner", "helpful", "humorous", "friendly"
]

BANNED_PHRASES = [
    "buy now", "best price", "limited offer", 
    "promo", "discount today", "click here",
    "bener banget nih", "semangat terus ya",
    "kalau butuh cek ini", "saya rekomendasikan",
    "coba produk ini"
]

def _get_client():
    api_key = gemini_manager.get_current_key()
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

def _call_gemini(system_prompt: str, response_format: str = "text") -> str:
    import llm_router
    return llm_router.generate(system_prompt, response_format)

def score_intent(caption: str) -> Dict[str, int]:
    """Phase 1: Score the intent using Gemini JSON output."""
    prompt = f"""EVALUATE THIS THREADS POST CAREFULLY.
POST: "{caption}"

You must score the following metrics from 0 to 100 based on the post context:
- buying_intent: Likelihood user wants to buy.
- commercial_intent: Likelihood user is looking for products/recommendations.
- problem_solving_intent: Likelihood user mainly wants advice or solutions.
- engagement_opportunity: Likelihood a meaningful conversation can happen.
- affiliate_probability: Likelihood an affiliate recommendation feels natural, helpful, and not spammy.
- confidence: Your confidence in this assessment.

Return ONLY a valid JSON object matching this exact schema:
{{
  "buying_intent": 0,
  "commercial_intent": 0,
  "problem_solving_intent": 0,
  "engagement_opportunity": 0,
  "affiliate_probability": 0,
  "confidence": 0
}}
"""
    try:
        res = _call_gemini(prompt, response_format="json")
        data = json.loads(res)
        return {
            "buying_intent": data.get("buying_intent", 0),
            "commercial_intent": data.get("commercial_intent", 0),
            "problem_solving_intent": data.get("problem_solving_intent", 0),
            "engagement_opportunity": data.get("engagement_opportunity", 0),
            "affiliate_probability": data.get("affiliate_probability", 0),
            "confidence": data.get("confidence", 0)
        }
    except Exception as e:
        logger.error(f"[AI ENGINE] Intent scoring failed: {e}")
        # Default fail-safe (forces tier 1 or skip)
        return {
            "buying_intent": 0,
            "commercial_intent": 0,
            "problem_solving_intent": 0,
            "engagement_opportunity": 50,
            "affiliate_probability": 0,
            "confidence": 0
        }

def determine_tier(scores: Dict[str, int]) -> str:
    affiliate_prob = scores["affiliate_probability"]
    commercial = scores["commercial_intent"]
    buying = scores["buying_intent"]
    
    if affiliate_prob >= 75 and commercial >= 80 and buying >= 80:
        return "TIER_3"
    elif affiliate_prob >= 40:
        return "TIER_2"
    else:
        return "TIER_1"

def generate_comment(caption: str, tier: str, product: Optional[Dict], recent_comments: list) -> str:
    """Phase 2: Generate the comment based on tier."""
    style = random.choice(STYLES)
    history_str = "\n".join([f"- {c}" for c in recent_comments]) if recent_comments else "None"
    
    prompt = f"""Kamu adalah pengguna Threads Indonesia yang membalas postingan berikut.
POSTINGAN: "{caption}"

GAYA BAHASA: {style} (natural, layaknya manusia biasa di Indonesia, hindari bahasa kaku/marketing/robot).
ATURAN UMUM:
- Jangan gunakan template membosankan.
- Maksimal 2-3 kalimat santai.
- JANGAN mengulang komentar yang pernah dibuat:
{history_str}
"""

    if tier == "TIER_1":
        prompt += """
TUGAS (HUMAN ENGAGEMENT TIER):
- Berikan komentar empati, lucu, atau sekadar ikut nimbrung obrolan.
- DILARANG merekomendasikan produk atau menyisipkan link apapun.
Contoh: "wah aku juga pernah ngalamin", "penasaran juga hasilnya gimana", "relate banget sih".
"""
    elif tier == "TIER_2":
        prompt += """
TUGAS (HELPFUL RECOMMENDATION TIER):
- Berikan saran atau rekomendasi solusi berdasarkan pengalaman pribadi.
- Boleh menyebutkan nama barang secara umum atau jenis produk, namun DILARANG memberikan link afiliasi.
Contoh: "aku biasanya pakai produk brand X lumayan ngebantu sih".
"""
    elif tier == "TIER_3" and product:
        prompt += f"""
TUGAS (MONETIZATION TIER):
- Postingan ini menunjukkan niat beli tinggi. Berikan rekomendasi spesifik.
- Sisipkan link berikut ini secara sangat natural di akhir atau tengah kalimat.
- Nama Produk: {product.get('nama', '')}
- Link: {product.get('link_affiliate', '')}
Contoh: "Aku pakai yang ini hampir setahun dan masih awet. Kalau mau lihat detailnya cek aja di sini: [LINK]"
"""
    else:
        # Fallback if Tier 3 but no product
        prompt += "\nBerikan komentar empati tanpa link."

    prompt += "\nTulis komentarnya secara langsung tanpa tanda kutip."
    prompt += ANTI_AI_PROMPT
    
    try:
        reply = _call_gemini(prompt)
        return reply
    except Exception as e:
        logger.error(f"[AI ENGINE] Comment generation failed: {e}")
        return "SKIP"

def generate_fast_mode(caption: str, product: Optional[Dict], recent_comments: list) -> Dict[str, Any]:
    """Single call that attempts to do everything (fallback for speed)."""
    style = random.choice(STYLES)
    history_str = "\n".join([f"- {c}" for c in recent_comments]) if recent_comments else "None"
    
    prompt = f"""Kamu adalah pengguna Threads Indonesia. 
POSTINGAN: "{caption}"

TUGAS:
1. Evaluasi apakah postingan ini cocok untuk disisipi link afiliasi (niat beli tinggi).
2. Jika cocok, gunakan gaya bahasa '{style}' untuk menyisipkan: {product.get('nama', '')} - {product.get('link_affiliate', '')}
3. Jika tidak cocok untuk afiliasi, berikan komentar santai tanpa link.
4. Jika postingan sama sekali tidak relevan/obrolan sensitif, balas dengan tepat 1 kata: "SKIP".

ATURAN:
- Maksimal 2-3 kalimat santai.
- JANGAN terdengar seperti bot/sales.
- JANGAN mengulang komentar ini: {history_str}

Tulis langsung komentarnya."""
    prompt += ANTI_AI_PROMPT

    try:
        reply = _call_gemini(prompt)
        is_skip = "SKIP" in reply.upper() or reply.strip().upper() == "SKIP"
        if is_skip:
            return {"selected_tier": "SKIP", "comment": "SKIP", "affiliate_used": False}
            
        uses_link = product and product.get('link_affiliate', '') in reply
        return {
            "selected_tier": "FAST_MODE",
            "comment": reply,
            "affiliate_used": uses_link
        }
    except:
        return {"selected_tier": "SKIP", "comment": "SKIP", "affiliate_used": False}

def safety_filter(reply: str) -> bool:
    """Returns True if the reply is safe, False if it contains banned phrases."""
    reply_lower = reply.lower()
    for phrase in BANNED_PHRASES:
        if phrase in reply_lower:
            return False
    return True

def run_engagement_pipeline(username: str, caption: str, product: Optional[Dict], recent_comments: list = None) -> Dict[str, Any]:
    """Main Orchestrator for the AI Engagement Engine."""
    recent_comments = recent_comments or []
    
    # 1. Check if we should use FAST or ADVANCED mode
    if MODE.upper() == "FAST":
        result = generate_fast_mode(caption, product, recent_comments)
        if result["comment"] != "SKIP" and not safety_filter(result["comment"]):
            return {"selected_tier": "SKIP", "reasoning": "Safety filter failed (FAST)", "comment": "SKIP", "affiliate_used": False}
        return result
        
    # 2. ADVANCED MODE: Intent Scoring
    scores = score_intent(caption)
    
    # Check if thread is even worth engaging (too low engagement opportunity)
    if scores["engagement_opportunity"] < 20:
        return {
            "intent_scores": scores,
            "selected_tier": "SKIP",
            "reasoning": "Low engagement opportunity",
            "comment": "SKIP",
            "affiliate_used": False
        }
        
    # 3. Decision Engine
    tier = determine_tier(scores)
    
    # 4. Humanization Layer & Comment Generator
    comment = generate_comment(caption, tier, product, recent_comments)
    
    if comment == "SKIP" or "SKIP" in comment.upper():
         return {
            "intent_scores": scores,
            "selected_tier": "SKIP",
            "reasoning": "Generator opted to skip or failed",
            "comment": "SKIP",
            "affiliate_used": False
        }
        
    # 5. Safety Filter
    if not safety_filter(comment):
        return {
            "intent_scores": scores,
            "selected_tier": "SKIP",
            "reasoning": "Failed safety filter (Banned phrases detected)",
            "comment": "SKIP",
            "affiliate_used": False
        }
        
    # 6. Final Polish (ensure link is correctly appended if Tier 3)
    affiliate_used = False
    if tier == "TIER_3" and product and product.get('link_affiliate', '') in comment:
        affiliate_used = True
        
    return {
        "intent_scores": scores,
        "selected_tier": tier,
        "reasoning": "Pipeline successful",
        "comment": comment,
        "affiliate_used": affiliate_used
    }
