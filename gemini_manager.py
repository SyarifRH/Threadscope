import time
import json
import os
import threading

CACHE_FILE = "gemini_cache.json"
_lock = threading.Lock()

def _load_cache():
    if not os.path.exists(CACHE_FILE): return {}
    try:
        with open(CACHE_FILE, "r") as f: return json.load(f)
    except: return {}

def _save_cache(data):
    try:
        with open(CACHE_FILE, "w") as f: json.dump(data, f)
    except: pass

def check_cache(prompt):
    with _lock:
        cache = _load_cache()
        now = time.time()
        to_delete = [k for k, v in cache.items() if k not in ["_QUOTA_LOCK", "_LAST_REQ"] and now - v.get("timestamp", 0) > 86400]
        for k in to_delete: del cache[k]
        if to_delete: _save_cache(cache)
        return cache.get(prompt, {}).get("reply")

def enforce_cooldown():
    with _lock:
        cache = _load_cache()
        
        quota_lock_time = cache.get("_QUOTA_LOCK", 0)
        if quota_lock_time > 0:
            if time.time() < quota_lock_time:
                raise Exception("429 RESOURCE_EXHAUSTED (Local Quota Lock Active)")
            else:
                del cache["_QUOTA_LOCK"]
                _save_cache(cache)
        
        elapsed = time.time() - cache.get("_LAST_REQ", 0)
        if elapsed < 20: time.sleep(20 - elapsed)
        
        cache["_LAST_REQ"] = time.time()
        _save_cache(cache)

def save_to_cache(prompt, reply):
    with _lock:
        cache = _load_cache()
        cache[prompt] = {"reply": reply, "timestamp": time.time()}
        _save_cache(cache)

def set_quota_lock():
    with _lock:
        cache = _load_cache()
        cache["_QUOTA_LOCK"] = time.time() + 120
        _save_cache(cache)

def clear_quota_lock():
    with _lock:
        cache = _load_cache()
        if "_QUOTA_LOCK" in cache:
            del cache["_QUOTA_LOCK"]
            _save_cache(cache)

def is_quota_locked():
    with _lock:
        cache = _load_cache()
        quota_lock_time = cache.get("_QUOTA_LOCK", 0)
        if quota_lock_time > 0 and time.time() < quota_lock_time:
            return True
        elif quota_lock_time > 0 and time.time() >= quota_lock_time:
            del cache["_QUOTA_LOCK"]
            _save_cache(cache)
        return False

# --- KEY ROTATION LOGIC ---
_keys = []
_current_key_idx = 0

def _load_keys():
    global _keys
    if not _keys:
        # Load up to 4 keys
        for i in range(1, 5):
            k = os.getenv(f"GEMINI_API_KEY_{i}", "").strip()
            if k:
                _keys.append(k)
        # Fallback to standard key if others aren't defined
        if not _keys:
            k = os.getenv("GEMINI_API_KEY", "").strip()
            if k:
                _keys.append(k)

def get_current_key():
    _load_keys()
    if not _keys:
        return ""
    return _keys[_current_key_idx]

def get_total_keys():
    _load_keys()
    if not _keys:
        return 1
    return len(_keys)

def report_key_exhausted():
    global _current_key_idx
    _load_keys()
    if _keys:
        _current_key_idx = (_current_key_idx + 1) % len(_keys)
        print(f"[KEY_MANAGER] Switching to Key #{_current_key_idx + 1}")

def is_rotation_error(error_msg: str) -> bool:
    err = str(error_msg).upper()
    rotation_keywords = [
        "429", "RESOURCE_EXHAUSTED", "QUOTA_EXCEEDED", "RATE_LIMIT",
        "403", "PERMISSION_DENIED", "CONSUMER_SUSPENDED", "INVALID_API_KEY",
        "API_KEY_NOT_VALID", "UNAUTHENTICATED"
    ]
    return any(keyword in err for keyword in rotation_keywords)

def is_retryable_error(error_msg: str) -> bool:
    err = str(error_msg).upper()
    retry_keywords = ["503", "UNAVAILABLE", "HIGH DEMAND"]
    return any(keyword in err for keyword in retry_keywords)

# --- GROQ KEY ROTATION LOGIC ---
_groq_keys = []
_current_groq_key_idx = 0

def _load_groq_keys():
    global _groq_keys
    if not _groq_keys:
        for i in range(1, 5):
            k = os.getenv(f"GROQ_API_KEY_{i}", "").strip()
            if k:
                _groq_keys.append(k)
        if not _groq_keys:
            k = os.getenv("GROQ_API_KEY", "").strip()
            if k:
                _groq_keys.append(k)

def get_current_groq_key():
    _load_groq_keys()
    if not _groq_keys:
        return ""
    return _groq_keys[_current_groq_key_idx]

def get_total_groq_keys():
    _load_groq_keys()
    if not _groq_keys:
        return 1
    return len(_groq_keys)

def report_groq_key_exhausted():
    global _current_groq_key_idx
    _load_groq_keys()
    if _groq_keys:
        _current_groq_key_idx = (_current_groq_key_idx + 1) % len(_groq_keys)
        print(f"[KEY_MANAGER] Switching to Groq Key #{_current_groq_key_idx + 1}")
