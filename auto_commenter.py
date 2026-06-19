"""
auto_commenter.py -- Threads Timeline Fetcher (Affiliate Commenter)
"""
import json
import logging
import os
import re
import sys
import time
import random
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import stats_tracker
import gemini_manager
import agent_loader

# WAJIB di paling atas untuk memuat semua variabel environment
from dotenv import load_dotenv
load_dotenv()

try:
    from google import genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

from services.session_manager import SessionManager, SessionStatus
from services.affiliate_strategy import get_random_affiliate_link

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)

ANTI_AI_PROMPT = """
ATURAN GAYA BAHASA (ANTI-AI WRITING LAYER):
1. HARUS terdengar seperti pengguna Threads Indonesia asli yang sedang ngobrol kasual. DILARANG menggunakan gaya bahasa AI, Customer Support, Motivator, atau Interviewer.
2. DILARANG KERAS menggunakan frasa basi: "sangat menarik", "terima kasih telah berbagi", "apa yang membuat kamu", "saya setuju", "hal yang menarik", "menurut saya", "bagaimana pendapatmu", "bisakah kamu menjelaskan".
3. Gunakan kata gaul secukupnya secara natural (contoh: wkwk, anjir, relate banget, gue juga, jujur, kadang, sering banget, ngl). DILARANG memaksakan slang di setiap balasan.
4. STRUKTUR YANG DIHARAPKAN: Reaksi -> Opini -> Observasi Pribadi. DILARANG KERAS banyak bertanya.
5. Biarkan ada sedikit ketidaksempurnaan atau kata kasual. JANGAN gunakan tata bahasa formal/kaku.
"""

_gemini_client = None
_comment_history = []

THREADS_HOME  = "https://www.threads.com/"
GRAPHQL_URL   = "https://www.threads.com/graphql/query"
GRAPHQL_DUMP  = "graphql_dump.json"
REPLY_ENDPOINT = "https://www.threads.com/api/v1/media/configure_text_only_post/"
AUTO_MODE = True

_TARGET_NAMES = {"BarcelonaFeedDirectQuery", "BarcelonaHomeTimeline", "BarcelonaFeedQuery"}

BASE_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.threads.com",
    "referer": "https://www.threads.com/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "x-ig-app-id": "238260118697367",
    "x-asbd-id": "359341",
    "x-fb-friendly-name": "BarcelonaFeedDirectQuery",
}



def parse_ai_reply(reply: str, product: Optional[Dict]) -> str:
    # 1. Cek SKIP Intent
    if reply.strip().upper() == "SKIP":
        return "SKIP"

    is_affiliate = False
    cleaned_reply = reply.strip()
    cleaned_reply_upper = cleaned_reply.upper()

    # Deteksi intent dari string utuh (sebelum prefix dibersihkan)
    if cleaned_reply_upper.startswith("AFFILIATE:"):
        is_affiliate = True
    elif cleaned_reply_upper.startswith("NO_AFFILIATE:"):
        is_affiliate = False
    else:
        # Fallback if no prefix but contains link
        if product and product.get('link_affiliate', '') in cleaned_reply:
            is_affiliate = True

    # Bersihkan semua variasi prefix di awal string agar tidak ter-post
    cleaned_reply = re.sub(r'^NO_AFFILIATE:?\s*', '', cleaned_reply, flags=re.IGNORECASE)
    cleaned_reply = re.sub(r'^AFFILIATE:?\s*', '', cleaned_reply, flags=re.IGNORECASE)
    cleaned_reply = cleaned_reply.strip()

    if not cleaned_reply:
        return "SKIP"

    # 2. Cek Banned Phrases (Post-Generation Validation)
    banned_phrases = ["bener banget nih", "semangat terus ya", "kalau butuh cek ini", "saya rekomendasikan", "coba produk ini"]
    if any(banned in cleaned_reply.lower() for banned in banned_phrases):
        print(f"[VALIDATION FAILED] Terdeteksi frasa dilarang: {cleaned_reply}")
        return "SKIP"

    MAX_REPLY_LENGTH = 350
    if is_affiliate and product:
        link = product.get('link_affiliate', '')
        # Hapus link yang digenerate AI (jika ada) agar tidak double
        cleaned_reply = cleaned_reply.replace(link, "").strip() 
        if len(cleaned_reply) + len(link) + 1 > MAX_REPLY_LENGTH:
            cleaned_reply = cleaned_reply[:MAX_REPLY_LENGTH - len(link) - 4] + "..."
        # Tempelkan link secara paksa di akhir
        cleaned_reply = f"{cleaned_reply} {link}"
    else:
        # Safeguard: Remove link if hallucinated under NO_AFFILIATE
        if product and product.get('link_affiliate', '') in cleaned_reply:
            cleaned_reply = cleaned_reply.replace(product.get('link_affiliate', ''), "").strip()
        if len(cleaned_reply) > MAX_REPLY_LENGTH:
            cleaned_reply = cleaned_reply[:MAX_REPLY_LENGTH - 3] + "..."

    return cleaned_reply

def generate_reply(caption: str, product: Optional[Dict] = None) -> str:
    global _gemini_client, _comment_history
    
    total_keys = gemini_manager.get_total_keys()
    if total_keys == 0:
        return "(Error: GEMINI_API_KEY tidak ditemukan di .env)"

    recent_comments = "\n".join([f"- {c}" for c in _comment_history]) if _comment_history else "(Belum ada komentar sebelumnya)"

    base_prompt = agent_loader.load_agent('marketing-threads-affiliate-agent')
    
    if base_prompt:
        system_prompt = base_prompt.replace("{caption}", caption).replace("{recent_comments}", recent_comments)
    else:
        system_prompt = f"""Kamu adalah netizen Threads Indonesia yang asik, natural, dan manusiawi.

EVALUASI CAPTION BERIKUT: "{caption}"

TUGAS UTAMA:
Kamu WAJIB merespons dengan memilih SATU dari format berikut:
AFFILIATE:
<komentar>
ATAU
NO_AFFILIATE:
<komentar>

ATURAN PEMILIHAN FORMAT:
Gunakan "AFFILIATE:" HANYA JIKA caption menunjukkan salah satu:
- mencari rekomendasi barang
- ingin membeli sesuatu
- membandingkan produk
- meminta saran produk
- mencari solusi yang secara jelas berhubungan dengan produk
- review produk
- pertanyaan sebelum membeli
- kebutuhan yang dapat diselesaikan oleh produk tertentu

Gunakan "NO_AFFILIATE:" JIKA caption termasuk:
- nostalgia, meme, cerita sehari-hari, curhat, opini
- politik, agama, berita, duka
- posting umum, obrolan santai, pengalaman pribadi
- posting yang TIDAK menunjukkan intent membeli

ATURAN KOMENTAR (KEDUANYA):
- JIKA caption sangat tidak pantas dibalas (duka berat/politik kotor), balas dengan 1 kata: SKIP
- Balesan harus natural, nyambung dengan konteks caption, dan seperti manusia sungguhan.
- MAKSIMAL 2-3 kalimat santai.
- DILARANG KERAS menggunakan frasa filler basi ini: "Bener banget nih", "Semangat terus ya", "Kalau butuh cek ini", "Saya rekomendasikan", "Coba produk ini".
- DILARANG terdengar seperti AI, bot, sales marketing, atau motivator.

MEMORI KOMENTAR LAMA (Jangan pernah ulangi frasa dari komentar lama ini):
{recent_comments}
"""

    if product:
        system_prompt += f"""
JIKA KAMU MEMILIH "AFFILIATE:":
- Kamu hanya boleh menyebutkan nama produk ini secara natural: {product.get('nama', '')}
- DILARANG menulis link apapun di dalam komentarmu. Link akan ditambahkan otomatis oleh sistem.

JIKA KAMU MEMILIH "NO_AFFILIATE:":
- DILARANG menyebut produk.
- DILARANG menyebut link apapun.
- DILARANG mempromosikan apapun.
"""
    else:
        system_prompt += "\nBalaslah secara natural, maksimal 2 kalimat santai."
        
    system_prompt += "\n" + ANTI_AI_PROMPT

    last_exc = None
    
    if gemini_manager.is_quota_locked():
        logger.warning("[API] Quota lock aktif. Mengandalkan router (Groq fallback).")
        
    try:
        cached_reply = gemini_manager.check_cache(caption)
        if cached_reply:
            parsed_cache = parse_ai_reply(cached_reply, product)
            if parsed_cache == "SKIP":
                return "SKIP"
            return parsed_cache

        import llm_router
        reply = llm_router.generate(system_prompt)
        
        print("\n========== ROUTER DEBUG ==========")
        print(f"[RAW LLM RESPONSE]: {reply}")
        print("==================================\n")

        reply = parse_ai_reply(reply, product)
        if reply == "SKIP":
            return "SKIP"

        is_aff_logged = product and product.get('link_affiliate', '') in reply
        print("\n========== FINAL DEBUG ==========")
        print(f"[FINAL REPLY]: {reply}")
        print(f"[FINAL LENGTH]: {len(reply)}")
        print(f"[INTENT DETECTED]: {'AFFILIATE' if is_aff_logged else 'NO_AFFILIATE'}")
        print("=================================\n")
        
        gemini_manager.save_to_cache(caption, reply)
        _comment_history.append(reply)
        if len(_comment_history) > 3:
            _comment_history.pop(0)
            
        return reply
    except Exception as exc:
        stats_tracker.log_error(f"LLM Router Error: {exc}")
        stats_tracker.increment("llm_router_errors")
        return f"Error AI: {exc}"

def post_reply(session, post_id: str, text: str) -> bool:
    csrf = (
        session.cookies.get("csrftoken", domain=".threads.com")
        or session.cookies.get("csrftoken")
        or ""
    )

    headers = {
        "accept":           "*/*",
        "accept-language":  "en-US,en;q=0.9",
        "content-type":     "application/x-www-form-urlencoded",
        "origin":           "https://www.threads.com",
        "referer":          "https://www.threads.com/",
        "sec-fetch-dest":   "empty",
        "sec-fetch-mode":   "cors",
        "sec-fetch-site":   "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "x-ig-app-id":   "238260118697367",
        "x-csrftoken":   csrf,
    }

    data = urlencode({
        "caption": text,
        "barcelona_source_reply_id": post_id,
        "publish_mode": "text_post",
        "upload_id": str(int(time.time() * 1000)),
        "text_post_app_info": json.dumps({"reply_id": post_id, "entry_point": "create_reply", "text_with_entities": {"entities": [], "text": text}}),
    })
    
    try:
        resp = session.post(REPLY_ENDPOINT, data=data, headers=headers, timeout=30)
        return resp.status_code == 200
    except Exception as e:
        print(f"[REPLY_ERROR] {e}")
        return False

def human_delay():
    delay = random.randint(840, 1020) # 14-17 Menit
    print(f"\n[INFO] Bot beristirahat {int(delay/60)} menit agar natural...")
    time.sleep(delay)

def load_latest_query_config() -> Dict[str, str]:
    if not os.path.exists(GRAPHQL_DUMP):
        raise FileNotFoundError(f"{GRAPHQL_DUMP} not found.")
    with open(GRAPHQL_DUMP, "r", encoding="utf-8") as f:
        dumps = json.load(f)
    for entry in dumps:
        payload    = entry.get("request_payload") or {}
        doc_id     = entry.get("doc_id") or payload.get("doc_id", "")
        friendly   = entry.get("friendly_name") or payload.get("fb_api_req_friendly_name", "")
        variables  = payload.get("variables", "")
        if friendly in _TARGET_NAMES and doc_id:
            return {"doc_id": doc_id, "variables": variables}
        if "pagination_source" in variables and "text_post_feed_threads" in variables and doc_id:
            return {"doc_id": doc_id, "variables": variables}
    raise ValueError("No timeline config found.")

def get_fresh_tokens(session) -> Dict[str, str]:
    tokens: Dict[str, str] = {"lsd": "", "fb_dtsg": ""}
    try:
        resp = session.get(THREADS_HOME, timeout=20)
        for pat in [r'"LSD",\[\],\{"token":"([^"]+)"\}', r'"lsd":"([^"]+)"']:
            m = re.search(pat, resp.text)
            if m: tokens["lsd"] = m.group(1); break
        for pat in [r'"DTSGInitialData",\[\],\{"token":"([^"]+)"\}', r'"fb_dtsg":"([^"]+)"']:
            m = re.search(pat, resp.text)
            if m: tokens["fb_dtsg"] = m.group(1); break
    except Exception:
        pass
    return tokens

def fetch_timeline(session, tokens: Dict[str, str], query_config: Dict[str, str]) -> Optional[Dict[str, Any]]:
    headers = dict(BASE_HEADERS)
    friendly  = query_config.get("friendly_name", "BarcelonaFeedDirectQuery")
    headers["x-fb-friendly-name"] = friendly
    csrf = session.cookies.get("csrftoken")
    if csrf: headers["x-csrftoken"] = csrf

    payload = urlencode({
        "lsd":       tokens.get("lsd", ""),
        "fb_dtsg":   tokens.get("fb_dtsg", ""),
        "doc_id":    query_config["doc_id"],
        "variables": query_config["variables"],
        "server_timestamps":        "true",
        "fb_api_req_friendly_name": friendly,
    })

    try:
        resp = session.post(GRAPHQL_URL, data=payload, headers=headers, timeout=30)
        return json.loads(resp.text) if resp.status_code == 200 else None
    except Exception:
        return None

def extract_posts(json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    posts: List[Dict[str, Any]] = []
    data = json_data.get("data") or {}
    feed_data = data.get("feedData") or (data.get("viewer") or {}).get("home_feed_units")
    if not feed_data: return posts

    edges = feed_data.get("edges", []) if isinstance(feed_data, dict) else []
    for edge in edges:
        items = (edge.get("node") or {}).get("text_post_app_thread", {}).get("thread_items", [])
        if not items: continue
        post = items[0].get("post") or {}
        

        
        # --- METRICS DISCOVERY LOGGING ---
        like_count = post.get("like_count")
        text_post_app_info = post.get("text_post_app_info", {})
        triage_comments = post.get("triage_comments")
        
        reply_count = None
        if isinstance(text_post_app_info, dict):
            reply_count = text_post_app_info.get("direct_reply_count") or text_post_app_info.get("reply_count")
            
        print(f"[POST_METRICS] like_count={like_count} | reply_count={reply_count}")
        print(f"[TEXT_POST_APP_INFO] {text_post_app_info}")
        print(f"[TRIAGE_COMMENTS] {triage_comments}")
        print(f"[TREND_METRICS] likes={like_count} replies={reply_count}")
        # ---------------------
        
        user = post.get("user") or {}
        posts.append({
            "username": user.get("username") or "(unknown)",
            "post_id":  post.get("pk") or post.get("id") or "?",
            "caption":  (post.get("caption") or {}).get("text", ""),
            "like_count": like_count,
            "reply_count": reply_count,
            "raw_post": post
        })
    return posts

def calculate_trend_score(likes: int, replies: int) -> int:
    like_score = 0
    if likes >= 300:
        like_score = 30
    elif likes >= 100:
        like_score = 20
    elif likes >= 30:
        like_score = 10
        
    reply_score = 0
    if replies >= 30:
        reply_score = 30
    elif replies >= 10:
        reply_score = 20
    elif replies >= 3:
        reply_score = 10
        
    return like_score + reply_score

def process_timeline(session):
    query_config = load_latest_query_config()
    tokens = get_fresh_tokens(session)
    raw = fetch_timeline(session, tokens, query_config)
    
    if not raw:
        return False
        
    posts = extract_posts(raw)
    if not posts:
        return False

    app_mode = os.getenv("APP_MODE", "normal").lower()
    is_trend_candidate = False

    if app_mode == "trend_affiliate":
        from services.affiliate_strategy import find_relevant_product_with_score
        
        trend_candidates = []
        stats_tracker.increment("trend_posts_found")
        for p in posts:
            likes = p.get("like_count") or 0
            replies = p.get("reply_count") or 0
            if likes >= 30 and replies >= 3:
                trend_score = calculate_trend_score(likes, replies)
                _, relevance_score = find_relevant_product_with_score(p.get("caption", ""))
                final_score = trend_score + relevance_score
                
                trend_candidates.append({
                    "post": p,
                    "trend_score": trend_score,
                    "relevance_score": relevance_score,
                    "final_score": final_score
                })
        
        if trend_candidates:
            trend_candidates.sort(key=lambda x: (x["final_score"], x["relevance_score"], x["trend_score"]), reverse=True)
            top_candidate = trend_candidates[0]
            
            stats_tracker.increment("trend_posts_selected")
            stats_tracker.log_error(f"highest_trend_score:{top_candidate['trend_score']}")
            stats_tracker.log_error(f"highest_final_score:{top_candidate['final_score']}")
            
            p = top_candidate["post"]
            print(f"\n[TREND_SCORE] {top_candidate['trend_score']}")
            print(f"[TREND_LIKE_COUNT] {p.get('like_count', 0)}")
            print(f"[TREND_REPLY_COUNT] {p.get('reply_count', 0)}")
            print(f"[TREND_RELEVANCE_SCORE] {top_candidate['relevance_score']}")
            print(f"[TREND_FINAL_SCORE] {top_candidate['final_score']}")
            
            posts = [p]
            is_trend_candidate = True
        else:
            stats_tracker.increment("trend_fallbacks")
            print("[TREND_FALLBACK] No candidate passed criteria. Falling back to affiliate mode.")
            random.shuffle(posts)
    else:
        random.shuffle(posts)

    for p in posts[:1]:
        username = p.get("username", "?")
        post_id = p.get("post_id", "?")
        caption = p.get("caption", "")
        
        print(f"\n[INFO] Menemukan target: @{username}")
        
        if is_trend_candidate:
            from services.affiliate_strategy import find_relevant_product, generate_trend_affiliate_comment
            product = find_relevant_product(caption)
            if product:
                stats_tracker.increment("trend_relevant_products_used")
            else:
                stats_tracker.increment("trend_random_products_used")
                product = get_random_affiliate_link()
                print(f"[TREND_FALLBACK_PRODUCT] selected_product={product.get('nama', 'Unknown')}")
            
            print(f"[TREND_PRODUCT] {product.get('nama', '')}")
            reply_text = generate_trend_affiliate_comment(caption, product, _comment_history)
            
            if reply_text == "SKIP" or "(Gagal)" in reply_text:
                print("[TREND_FALLBACK] AI generation failed. Falling back to normal.")
                stats_tracker.increment("trend_fallbacks")
                reply_text = generate_reply(caption, None)
            else:
                stats_tracker.increment("trend_affiliate_comments")
                print("[TREND_LINK_INSERTED] Mandatory link inserted.")
        elif app_mode == "affiliate" or (app_mode == "trend_affiliate" and not is_trend_candidate):
            from services.affiliate_strategy import find_relevant_product, generate_affiliate_comment
            
            # 1. Match relevant product
            product = find_relevant_product(caption)
            if product:
                print(f"  >> Relevant product found: {product.get('nama', '')}")
                # 2. Decision: 50% Affiliate / 50% Normal
                try:
                    reply_text = generate_affiliate_comment(caption, product, _comment_history)
                    if reply_text == "SKIP" or "(Gagal)" in reply_text:
                        print("  >> Affiliate generation failed/skipped. Fallback to normal.")
                        reply_text = generate_reply(caption, None)
                except Exception as e:
                    print(f"  >> Affiliate failsafe triggered: {e}")
                    reply_text = generate_reply(caption, None)
            else:
                print("  >> No relevant product found. 100% Normal Reply.")
                reply_text = generate_reply(caption, None)
        else:
            product = get_random_affiliate_link()
            reply_text = generate_reply(caption, product)
        
        if reply_text == "SKIP":
            print("  >> AI memutuskan untuk SKIP thread ini (Tidak relevan/Banned Phrase/No Intent).")
            time.sleep(15) # Jeda pendek agar tidak spam request API Threads
            continue
            
        print("--------------------------------------------------")
        print(f"  DRAF AI: {reply_text}")
        print("--------------------------------------------------")
        if AUTO_MODE:
            # === HOOK LIKE POST ===
            try:
                pass
            except Exception as e:
                # Error handling tingkat akhir agar tidak menghentikan proses komentar
                print(f"[LIKE] Exception tidak tertangani: {e}")
            # ======================
            
            # --- DEBUG LOGGING ---
            print("\n=== DEBUG: RAW POST STRUCTURE SEBELUM REPLY ===")
            import json
            # Safety fallback so json.dumps doesn't fail on complex objects
            try:
                print(json.dumps(p.get("raw_post", {}), indent=2))
            except Exception as err:
                print(f"Failed to dump JSON: {err}")
                print(p.get("raw_post", {}))
            print("===============================================\n")
            # ---------------------

            success = post_reply(session, str(post_id), reply_text)
            if success:
                print("  >> Status Pengiriman: Berhasil!")
                stats_tracker.increment("comments_sent")
            else:
                print("  >> Status Pengiriman: Gagal.")
                stats_tracker.increment("comment_failures")
        human_delay()
    return True

def main():
    # Load .env variables explicit check for user
    _ = os.getenv("SHOPEE_RAW_COOKIE")  # Explicit load as requested
    
    sm = SessionManager()
    if not sm.load_session() or sm.validate_session().status != SessionStatus.VALID:
        print("[ERROR] Session invalid. Cek THREADS_SESSION_ID dll di .env")
        sys.exit(1)
    
    session = sm.inject_session()

    while True:
        try:
            if not process_timeline(session):
                time.sleep(60)
        except Exception as e:
            stats_tracker.log_error(str(e))
            logger.error("Error: %s", e)
            time.sleep(60)

if __name__ == "__main__":
    main()
