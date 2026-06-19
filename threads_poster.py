"""
threads_poster.py -- Auto Poster for original Threads content (Pure Opinion)
"""
import json
import logging
import os
import sys
import time
import random
import random
from urllib.parse import urlencode

import stats_tracker
import gemini_manager

# WAJIB di paling atas untuk memuat semua variabel environment
from dotenv import load_dotenv
load_dotenv()

try:
    from google import genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

from services.session_manager import SessionManager, SessionStatus

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
_post_history = []
POST_ENDPOINT = "https://www.threads.com/api/v1/media/configure_text_only_post/"

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

def generate_thread_content() -> str:
    global _gemini_client
    
    total_keys = gemini_manager.get_total_keys()
    if total_keys == 0:
        return "(Error: GEMINI_API_KEY tidak ada di .env)"

    global _post_history

    topics = [
        "daily life",
        "work",
        "relationships",
        "technology",
        "football",
        "internet culture",
        "trending discussions",
        "unpopular opinions",
        "funny observations",
        "social issues"
    ]
    topic = random.choice(topics)

    recent_posts = "\n".join([f"- {p}" for p in _post_history]) if _post_history else "(Belum ada postingan sebelumnya)"

    system_prompt = f"""Kamu adalah pengguna Threads asal Indonesia asli.
Karaktermu:
- Warga lokal Indonesia.
- Santai (casual).
- Suka mengobservasi keadaan sekitar.
- Kadang lucu, kadang kritis, kadang sangat 'relatable'.
- BUKAN akun perusahaan/korporat.
- BUKAN akun motivator/guru.

TUGAS:
Buat SATU postingan Threads pendek tentang topik: "{topic}"

ATURAN MUTLAK (JANGAN DILANGGAR):
1. DILARANG menggunakan gaya bahasa AI yang generik.
2. DILARANG menggunakan klise motivasi (seperti "Tetap semangat!", "Terus berjuang!", dll).
3. DILARANG menggunakan format yang berulang-ulang.
4. DILARANG membuat postingan "engagement bait" murahan (seperti "Coba kasih komentar di bawah!").
5. DILARANG KERAS menyisipkan link promosi atau jualan!
6. Panjang tulisan MAKSIMAL 500 karakter.

MEMORI POSTINGAN TERAKHIRMU (Jangan bahas ini lagi atau gunakan gaya bahasa yang persis sama):
{recent_posts}
"""
    system_prompt += "\n" + ANTI_AI_PROMPT

    try:
        import llm_router
        post_content = llm_router.generate(system_prompt)
        
        _post_history.append(post_content)
        if len(_post_history) > 3:
            _post_history.pop(0)
            
        return post_content
    except Exception as e:
        stats_tracker.log_error(f"LLM Router Error: {e}")
        stats_tracker.increment("llm_router_errors")
        return f"(Gagal membuat konten thread: {e})"

def post_thread(session, text: str) -> bool:
    csrf = os.getenv("THREADS_CSRF_TOKEN") or session.cookies.get("csrftoken") or ""
    headers = BASE_HEADERS.copy()
    headers["x-csrftoken"] = csrf

    data = urlencode({
        "caption": text,
        "publish_mode": "text_post",
        "upload_id": str(int(time.time() * 1000)),
        "text_post_app_info": json.dumps({"text_with_entities": {"entities": [], "text": text}}),
    })

    try:
        resp = session.post(POST_ENDPOINT, data=data, headers=headers, timeout=30)
        return resp.status_code == 200
    except Exception as exc:
        logger.error("post_thread error: %s", exc)
        return False

def human_post_delay():
    delay = 172800 # 48 Jam (2 Hari)
    print(f"\n[INFO] Bot Poster beristirahat 48 jam sebelum membuat opini berikutnya...")
    time.sleep(delay)

def main():
    # Load env explicit check
    _ = os.getenv("THREADS_SESSION_ID")
    
    sm = SessionManager()
    if not sm.load_session() or sm.validate_session().status != SessionStatus.VALID:
        print("[ERROR] Session invalid. Cek kredensial THREADS di .env Anda.")
        sys.exit(1)

    session = sm.inject_session()

    while True:
        try:
            app_mode = os.getenv("APP_MODE", "normal").lower()
            if app_mode in ("affiliate", "trend_affiliate"):
                print("\n[INFO] Membuat opini organik dengan selipan afiliasi...")
                from services.affiliate_strategy import generate_affiliate_thread, get_random_affiliate_link
                product = get_random_affiliate_link()
                if product:
                    thread_content = generate_affiliate_thread(product, _post_history)
                    if thread_content == "(Gagal)" or thread_content == "SKIP":
                        print("  >> Affiliate thread failed. Triggering failsafe fallback to normal mode.")
                        thread_content = generate_thread_content()
                else:
                    thread_content = generate_thread_content()
            else:
                print("\n[INFO] Membuat opini organik murni (NO LINK)...")
                thread_content = generate_thread_content()
            
            if "(Gagal" in thread_content or "(Error" in thread_content:
                time.sleep(3600)
                continue

            print(f"  DRAF OPINI: {thread_content}")
            
            success = post_thread(session, thread_content)
            if success:
                print("  >> Berhasil memposting opini!")
                stats_tracker.increment("posts_created")
            else:
                stats_tracker.increment("post_failures")
            
            human_post_delay()

        except Exception as e:
            stats_tracker.log_error(str(e))
            logger.error("Terjadi error: %s", e)
            time.sleep(3600)

if __name__ == "__main__":
    main()
