import os
import json
import random
import logging
from typing import Dict, Any, Optional, List
import threading

import llm_router
import stats_tracker

logger = logging.getLogger(__name__)

ANTI_AI_PROMPT = """
ATURAN GAYA BAHASA — WAJIB DIPATUHI:
1. Kamu adalah netizen Threads Indonesia biasa. Bukan motivator, bukan AI, bukan CS, bukan guru.
2. Panjang balasan: MAKSIMAL 1-2 kalimat pendek. DILARANG lebih dari itu.
3. DILARANG KERAS frasa ini (langsung SKIP jika terpakai):
   "sangat menarik", "terima kasih telah berbagi", "proses belajar", "terus berkembang",
   "semangat terus", "jangan menyerah", "menurut saya", "saya setuju", "bagaimana pendapatmu",
   "hal ini", "luar biasa", "sangat relevan", "penting untuk", "perjalanan hidup",
   "fokus pada", "jangan lupa", "tetap semangat", "keep going", "percaya diri".
4. DILARANG komentar yang terdengar seperti motivator Instagram atau caption seminar.
5. Boleh singkat, nyambung, dan sedikit bego/kasual — itu lebih natural.
6. Tidak harus bertanya balik. Satu reaksi singkat sudah cukup.
7. Tulis persis seperti orang ngetik di HP, bukan essay.
"""

CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "product_theme_cache.json")
_cache_lock = threading.Lock()

def _load_cache() -> Dict[str, Any]:
    if not os.path.exists(CACHE_FILE):
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load product theme cache: {e}. Rebuilding.")
        return {}

def _save_cache(cache: Dict[str, Any]):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save product theme cache: {e}")
        stats_tracker.increment("cache_write_failures")

def get_product_intelligence(product: Dict[str, Any]) -> Dict[str, Any]:
    product_name = product.get("nama", "")
    if not product_name:
        return {"themes": [], "category": "umum", "subcategories": []}
        
    with _cache_lock:
        cache = _load_cache()
        if product_name in cache:
            entry = cache[product_name]
            if "category" in entry:
                stats_tracker.increment("cache_hits")
                stats_tracker.increment("cache_category_hits")
                return {
                    "themes": entry.get("themes", []),
                    "category": entry.get("category", "umum"),
                    "subcategories": entry.get("subcategories", [])
                }
            
    stats_tracker.increment("cache_misses")
    
    # Bypass LLM: Gunakan KEYWORD_ALIASES untuk mencari kategori secara lokal
    product_name_lower = product_name.lower()
    detected_cats = set()
    
    for alias, cat in KEYWORD_ALIASES.items():
        if alias in product_name_lower:
            detected_cats.add(cat)
            
    detected_cats_list = list(detected_cats)
    primary_category = detected_cats_list[0] if detected_cats_list else "umum"
    themes = detected_cats_list if detected_cats_list else ["umum"]
    
    with _cache_lock:
        cache = _load_cache()
        import datetime
        cache[product_name] = {
            "themes": themes,
            "category": primary_category,
            "subcategories": detected_cats_list,
            "created_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
        _save_cache(cache)
        
    stats_tracker.increment("products_categorized")
    
    return {
        "themes": themes,
        "category": primary_category,
        "subcategories": detected_cats_list
    }

def extract_post_context(caption: str) -> Dict[str, Any]:
    caption_lower = caption.lower()
    found_keywords = []
    
    # Bypass LLM: Gunakan KEYWORD_ALIASES untuk mencari kecocokan secara lokal
    for alias in KEYWORD_ALIASES:
        # Menggunakan regex atau in biasa, seperti permintaan user: if alias in caption
        if alias in caption_lower:
            found_keywords.append(alias)
            
    return {
        "keywords": found_keywords,
        "topics": [],
        "intent": "",
        "entities": []
    }

def calculate_relevance(context: Dict[str, Any], product: Dict[str, Any], intel: Dict[str, Any]) -> float:
    score = 0.0
        
    keywords_lower = [k.lower() for k in context.get("keywords", [])]
    topics_lower = [t.lower() for t in context.get("topics", [])]
    entities_lower = [e.lower() for e in context.get("entities", [])]
    
    prod_name_lower = product.get("nama", "").lower()
    prod_cat_lower = product.get("kategori", "").lower()
    themes_lower = [t.lower() for t in intel.get("themes", [])]
    
    # 1. Keyword Matches (* 3)
    for k in keywords_lower:
        if len(k) > 2 and (k in prod_name_lower or any(k in t for t in themes_lower)):
            score += 3.0
            
    # 2. Theme Matches (* 2)
    for t in topics_lower:
        if len(t) > 2 and (any(t in pt for pt in themes_lower) or t in prod_name_lower):
            score += 2.0
            
    # 3. Category Matches (* 2)
    if prod_cat_lower:
        for term in keywords_lower + topics_lower + entities_lower:
            if len(term) > 2 and term in prod_cat_lower:
                score += 2.0
                
    # 4. Entity Matches (* 4)
    for e in entities_lower:
        if len(e) > 2 and (e in prod_name_lower or any(e in t for t in themes_lower)):
            score += 4.0
            
    # 5. Category Intelligence Boost
    context_cats = detect_context_categories(context)
    intel_cat = intel.get("category", "").lower()
    
    category_matches = False
    if intel_cat and intel_cat in context_cats:
        score += 15.0  # Significant boost for direct category match
        category_matches = True
        stats_tracker.increment("category_boosts")
        
    if category_matches:
        stats_tracker.increment("category_matches")
                
    return score

def load_all_products(filepath: str = "shopee_affiliate_links.json") -> List[Dict[str, Any]]:
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path_file = os.path.join(base_dir, filepath)
        if not os.path.exists(path_file):
            return []
        with open(path_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

KEYWORD_ALIASES = {
    "hp": "smartphone",
    "hape": "smartphone",
    "android": "smartphone",
    "iphone": "smartphone",
    "samsung": "smartphone",
    "oppo": "smartphone",
    "vivo": "smartphone",
    "ip11": "smartphone",
    "ip12": "smartphone",
    "ip13": "smartphone",
    "ip14": "smartphone",
    "ip15": "smartphone",
    "baju": "fashion",
    "kaos": "fashion",
    "kemeja": "fashion",
    "hoodie": "fashion",
    "jaket": "fashion",
    "ootd": "fashion",
    "jersey": "sepak_bola",
    "timnas": "sepak_bola",
    "bola": "sepak_bola",
    "nobar": "sepak_bola",
    "liga": "sepak_bola",
    "gunung": "outdoor",
    "camping": "outdoor",
    "hiking": "outdoor",
    "trekking": "outdoor",
    "kursi": "furniture",
    "meja": "furniture",
    "tempat duduk": "furniture",
    "snack": "makanan",
    "cemilan": "makanan",
    "camilan": "makanan",
    "basreng": "makanan",
    "keripik": "makanan",
    "kopi": "minuman",
    "coffee": "minuman",
    "ngopi": "minuman",
    "matcha": "minuman",
    "hair dryer": "kecantikan",
    "skincare": "kecantikan",
    "bayi": "anak",
    "balita": "anak",
}

def detect_context_categories(context: Dict[str, Any]) -> List[str]:
    cats = set()
    terms = context.get("keywords", []) + context.get("topics", []) + context.get("entities", [])
    for t in terms:
        t_lower = t.lower()
        if t_lower in KEYWORD_ALIASES:
            cats.add(KEYWORD_ALIASES[t_lower])
        for alias, cat in KEYWORD_ALIASES.items():
            if alias in t_lower:
                cats.add(cat)
    return list(cats)

def normalize_term(term: str) -> str:
    term_lower = term.lower().strip()
    return KEYWORD_ALIASES.get(term_lower, term_lower)

def normalize_context(context: Dict[str, Any]) -> Dict[str, Any]:
    norm = {}
    for key in ["keywords", "topics", "entities"]:
        norm[key] = [normalize_term(x) for x in context.get(key, [])]
    norm["intent"] = context.get("intent", "")
    return norm

def find_relevant_product_with_score(caption: str) -> tuple[Optional[Dict[str, Any]], float]:
    products = load_all_products()
    if not products:
        return None, 0.0
        
    stats_tracker.increment("affiliate_match_attempts")
        
    raw_context = extract_post_context(caption)
    
    print("\n[AFFILIATE_CONTEXT]")
    print(f"Keywords: {raw_context.get('keywords', [])}")
    print(f"Topics: {raw_context.get('topics', [])}")
    print(f"Entities: {raw_context.get('entities', [])}")
    print(f"Intent: {raw_context.get('intent', '')}")
    
    context = normalize_context(raw_context)
    
    best_product = None
    best_score = 0.0
    
    for prod in products:
        intel = get_product_intelligence(prod)
        score = calculate_relevance(context, prod, intel)
        
        print(f"[AFFILIATE_SCORE]")
        print(f"Product: {prod.get('nama', 'Unknown')}")
        print(f"Score: {score}")
        
        if score > best_score:
            best_score = score
            best_product = prod
            
    stats_tracker.log_error(f"best_match_score:{best_score}") # Sending metric value to stats_tracker via log_error for tracking purposes 

    print("\n[AFFILIATE_BEST_MATCH]")
    if best_product:
        print(f"Product: {best_product.get('nama', '')}")
    else:
        print("NONE")
    print(f"Score: {best_score}")
    
    # Threshold for relevance. Adjust as needed.
    if best_score >= 5.0:
        print("[AFFILIATE_DECISION]")
        print("Relevant Product Found")
        stats_tracker.increment("affiliate_match_success")
        return best_product, best_score
        
    print("[AFFILIATE_DECISION]")
    print("No Relevant Product Found")
    stats_tracker.increment("affiliate_match_failures")
    return None, best_score

def find_relevant_product(caption: str) -> Optional[Dict[str, Any]]:
    prod, _ = find_relevant_product_with_score(caption)
    return prod

def get_random_affiliate_link(filepath: str = "shopee_affiliate_links.json") -> Optional[Dict[str, Any]]:
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path_file = os.path.join(base_dir, filepath)
        if not os.path.exists(path_file):
            return None
        with open(path_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data and isinstance(data, list):
                return random.choice(data)
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
    return None

def generate_affiliate_comment(caption: str, product: Dict[str, Any], history: List[str]) -> str:
    """Follows Section 5 rules for Affiliate Comments"""
    # 50% randomized insertion rate
    insert_affiliate = random.random() < 0.50
    
    intel = get_product_intelligence(product)
    themes = intel.get("themes", [])
    themes_str = ", ".join(themes) if themes else "umum"
    recent_comments = "\n".join([f"- {c}" for c in history]) if history else "Belum ada"
    
    prompt = f"""Kamu adalah netizen Threads Indonesia biasa yang lagi scroll HP.
POSTINGAN: "{caption}"

BALAS dengan 1-2 kalimat SAJA. Singkat, nyambung, dan manusiawi.
JANGAN bertanya balik. JANGAN kasih nasihat motivasi. JANGAN panjang-panjang.
JANGAN ulangi komentar ini:
{recent_comments}

CONTOH BALASAN YANG BAGUS:
- "relate, gue juga pernah kayak gitu wkwk"
- "anjir beneran? gue kirain cuman gue doang"
- "hahaha kira-kira bakal bertahan berapa lama"
- "nah ini, orang sering lupa hal simpel kayak gini"
"""

    if insert_affiliate:
        prompt += f"""
Setelah komentar singkat tadi, tambahkan rekomendasi produk secara super halus di kalimat terakhir.
Produk: {product.get('nama', '')}
Link: {product.get('link_affiliate', '')}

ATURAN LINK:
- Link di paling akhir, setelah komentar natural.
- JANGAN bilang "coba ini", "produk ini bagus", atau apapun yang berbau iklan.
- Kayak orang lagi ngobrol terus nyeletuk produk yang pernah dia pakai.
CONTOH: "Emang kadang hal kecil yang bikin beda. Ini yang gue pakai: [Link]"
"""
    else:
        prompt += """
JANGAN sertakan link atau rekomendasi produk apapun.
"""

    prompt += ANTI_AI_PROMPT
    try:
        return llm_router.generate(prompt)
    except Exception as e:
        logger.error(f"Affiliate comment generation failed: {e}")
        return "SKIP"

def generate_trend_affiliate_comment(caption: str, product: Dict[str, Any], history: List[str]) -> str:
    recent_comments = "\n".join([f"- {c}" for c in history]) if history else "Belum ada"
    
    prompt = f"""Kamu adalah netizen Threads Indonesia biasa yang lagi balas-balasan di Threads.
POSTINGAN: "{caption}"

BALAS dengan MAKSIMAL 1-2 kalimat yang terdengar kayak manusia ngetik di HP, bukan AI.
JANGAN ulangi:
{recent_comments}

WAJIB sertakan produk ini di akhir kalimat (bukan awal, bukan tengah):
Produk: {product.get('nama', '')}
Link: {product.get('link_affiliate', '')}

Cara sertakan link yang benar:
- Nyebut produk kayak lagi ngomongin sesuatu yang pernah kamu pakai/lihat.
- BUKAN kayak iklan. BUKAN kayak promosi. BUKAN kayak CS.
- Link langsung di akhir setelah kalimat natural.

CONTOH BAGUS: "relate banget, gue juga sering gitu wkwk. eh ini lumayan ngebantu btw: [Link]"
CONTOH JELEK: "Sangat relate! Proses ini memang penting. Coba produk ini: [Link]"
"""
    prompt += ANTI_AI_PROMPT
    try:
        return llm_router.generate(prompt)
    except Exception as e:
        logger.error(f"Trend affiliate comment generation failed: {e}")
        return "SKIP"

def generate_affiliate_thread(product: Dict[str, Any], history: List[str]) -> str:
    """Follows Section 6 rules for Affiliate Threads"""
    intel = get_product_intelligence(product)
    themes = intel.get("themes", [])
    topic = random.choice(themes) if themes else "kehidupan sehari-hari"
    
    recent_history = history[-5:] if history else []
    recent_posts = "\n".join([f"- {p}" for p in recent_history]) if recent_history else "Belum ada"
    
    formats = [
        "FORMAT A: Pengalaman pribadi.",
        "FORMAT B: Barang yang sering dipakai.",
        "FORMAT C: Travel / kerja / aktivitas harian.",
        "FORMAT D: Hal yang awalnya diremehkan tapi ternyata kepake.",
        "FORMAT E: Observasi lucu atau relatable."
    ]
    selected_format = random.choice(formats)
    
    prompt = f"""Kamu adalah pengguna Threads Indonesia. Buat postingan organik tentang: "{topic}"

ATURAN POSTINGAN:
1. Panjang 2-5 kalimat.
2. Maksimal 400 karakter.
3. Tulis seperti pengguna Threads Indonesia yang sedang cerita.
4. JANGAN terdengar seperti sales/iklan. BUKAN copy marketplace.
5. DILARANG KERAS menggunakan kata: "wajib beli", "buruan checkout", "recommended banget", "produk terbaik", "diskon besar", "jangan sampai kehabisan", "promo spesial".
6. Fokus pada: pengalaman pribadi, kegunaan sehari-hari, barang yang sering dipakai, barang yang mempermudah hidup, ATAU barang yang ternyata lebih berguna dari ekspektasi.
7. Format yang harus digunakan kali ini: {selected_format}
8. JANGAN PERNAH menghasilkan caption yang mirip dengan 5 postingan terakhir ini:
{recent_posts}
9. WAJIB menyisipkan link affiliate di bagian akhir (beri 1-2 baris kosong).

OUTPUT HARUS SEPERTI INI:
<caption natural>

<link_affiliate>

CONTOH YANG BAGUS:
"Awalnya beli karena suka modelnya doang, ternyata malah jadi tas yang paling sering gue bawa keluar. Muat banyak tanpa berasa bulky."

{product.get('link_affiliate', 'https://affiliate-link')}

CONTOH YANG BURUK (JANGAN DITIRU):
"Produk terbaik yang wajib kalian beli sekarang juga!"

{product.get('link_affiliate', 'https://affiliate-link')}

Data produk referensi (CERITAKAN SEBAGAI PENGALAMAN, JANGAN sebut nama lengkap produk seperti katalog): 
Nama: {product.get('nama', '')}
Link: {product.get('link_affiliate', '')}
"""

    prompt += ANTI_AI_PROMPT
    try:
        return llm_router.generate(prompt)
    except Exception as e:
        logger.error(f"Affiliate thread generation failed: {e}")
        return "(Gagal)"
