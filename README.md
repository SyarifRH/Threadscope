# 🚀 ThreadScope — Threads × Shopee Affiliate Automation Bot

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Playwright](https://img.shields.io/badge/Playwright-Browser%20Automation-orange.svg)
![curl_cffi](https://img.shields.io/badge/curl__cffi-TLS%20Bypass-green.svg)
![Groq](https://img.shields.io/badge/Groq-llama--3.3--70b-purple.svg)
![Gemini](https://img.shields.io/badge/Gemini-AI%20Fallback-blue.svg)
![Threads](https://img.shields.io/badge/Threads-Meta-black.svg)
![Shopee](https://img.shields.io/badge/Shopee-Affiliate-red.svg)
![Status](https://img.shields.io/badge/Status-Active%20Development-yellowgreen.svg)

---

## Apa Ini?

ThreadScope adalah bot otomasi riset yang bisa **scroll timeline Threads, baca konteks post, dan balas dengan komentar yang terdengar kayak manusia beneran** — bukan kayak bot sales garing.

Kalau ada post yang nyebut-nyebut soal produk, gadget, fashion, atau apapun yang nyambung sama katalog Shopee, bot ini bakal nyisipin link affiliate secara halus. Kalau nggak relevan? Ya udah, bot kasih komentar biasa aja, ngobrol santai.

Flow besarnya simpel:

```
Scroll Timeline → Baca Post → Analisis Intent → Generate Komentar AI → Kirim Reply (+ Link Affiliate kalau relevan)
```

---

## Kenapa Dibangun Dengan Cara Ini?

Proyek ini nggak lahir langsung jadi, ada banyak jalan yang udah dicoba sebelumnya. Yang paling menyakitkan? **Ngehancurin sistem login HTTP yang udah dibangun dari nol**, karena akhirnya tau bahwa Meta punya trust-layer yang literally nolak semua login otomatis — bahkan kalau credentials-nya bener sekalipun.

Sekarang bot jalan pakai **session yang udah terautentikasi duluan** dari browser, bukan nge-login saat runtime. Simple, stabil, dan nggak ada retry loop gila-gilaan.

---

## Status Fitur Saat Ini

| Komponen | Status | Keterangan |
|----------|--------|------------|
| Session Management (load, validate, inject) | ✅ **Selesai** | Bypass mode + multi-domain cookie injection |
| Network Discovery via Playwright | ✅ **Selesai** | Capture semua traffic browser 30 detik |
| Timeline Fetcher (GraphQL) | ✅ **Selesai** | `BarcelonaFeedDirectQuery` endpoint |
| Auto Reply / Komentar | ✅ **Selesai** | `auto_commenter.py` — fully functional |
| Auto Post / Original Content | ✅ **Selesai** | `threads_poster.py` — 48 jam jeda antar posting |
| AI Comment Generation (Groq + Gemini) | ✅ **Selesai** | LLM Router dengan key rotation & fallback |
| Anti-AI Language Layer | ✅ **Selesai** | Prompt engineering buat nulis kayak manusia |
| Intent Detection + Tiering | ✅ **Selesai** | 3 tier: Engagement, Recommendation, Monetisasi |
| Affiliate Product Matching | ✅ **Selesai** | Keyword-based + category scoring |
| Trend Affiliate Mode | ✅ **Selesai** | Target post viral (30+ likes, 3+ replies) |
| Stats Tracker | ✅ **Selesai** | Persistent JSON stats per sesi |
| Gemini API Key Rotation | ✅ **Selesai** | Rotasi otomatis sampai 4 key |
| Groq API Key Rotation | ✅ **Selesai** | Llama 3.3 70B sebagai primary LLM |
| Response Cache | ✅ **Selesai** | Cache 24 jam buat prompt yang sama |
| Shopee Affiliate Link Gen | ✅ **Selesai** | Load dari `shopee_affiliate_links.json` |
| Feed Schema Discovery | 🚧 **Parsial** | Perlu valid session buat test penuh |
| Agent Loader (custom prompts) | 🟡 **Opsional** | Bisa override prompt via agent file |

---

## Arsitektur Sistem

```
┌──────────────────────────────────────────────────────────────────┐
│                         Entry Points                             │
│           main.py  │  auto_commenter.py  │  threads_poster.py   │
└──────────────────────┬───────────────────────────────────────────┘
                       │
         ┌─────────────┼──────────────────────────┐
         ▼             ▼                          ▼
   ┌───────────┐  ┌──────────────┐        ┌─────────────────┐
   │  Session  │  │  LLM Router  │        │  Affiliate      │
   │  Manager  │  │              │        │  Strategy       │
   │           │  │ 1. Groq      │        │                 │
   │ load()    │  │    llama-70b │        │ find_product()  │
   │ validate()│  │ 2. Gemini    │        │ gen_comment()   │
   │ inject()  │  │    fallback  │        │ gen_thread()    │
   └───────────┘  └──────────────┘        └─────────────────┘
         │
         ▼
   ┌───────────────────────────────┐
   │  services/                    │
   │  ├── session_manager.py       │  ← Validasi + inject cookies
   │  ├── network_discovery.py     │  ← Playwright traffic capture
   │  ├── feed_explorer.py         │  ← HTML endpoint discovery
   │  ├── affiliate_strategy.py    │  ← Product matching + AI gen
   │  └── shopee_generator.py      │  ← Link affiliate generator
   └───────────────────────────────┘
```

### Kenapa Session-First?

Dulu pake login otomatis. Gagal terus. Meta punya sistem yang ngedeteksi request otomatis bahkan sebelum password dikirim.

| Aspek | Legacy (Login) | Sekarang (Session-First) |
|-------|---------------|--------------------------|
| Stabilitas | Retry loop tak berujung | Stabil, deterministic |
| Debugging | Kompleks banget | Simple |
| Failure mode | Silent (masih jalan tapi gagal) | Langsung berhenti + info jelas |
| Autentikasi | Login saat runtime | Cookie pre-loaded dari browser |
| Trust-layer | Selalu ditolak | Dilewati via session legit |

---

## Cara Kerja AI Engine

### Mode Komentar

Bot punya 2 mode operasi yang bisa diset via `.env`:

**`ADVANCED` mode (default):**
1. Post masuk → Gemini/Groq **score intent** (JSON output: buying_intent, commercial_intent, dll)
2. Skor diproses → masuk salah satu dari 3 tier:
   - **TIER 1** — Engagement biasa, komentar natural tanpa produk
   - **TIER 2** — Recommendation, sebutin produk tapi tanpa link
   - **TIER 3** — Monetisasi, sisipkan link affiliate secara halus
3. Komentar di-generate → Safety filter (banned phrases check)
4. Kalau lolos → kirim ke Threads

**`FAST` mode:**
1. Satu API call langsung minta AI putuskan: pakai affiliate atau tidak
2. Lebih hemat token, cocok kalau API key terbatas

### Anti-AI Writing Layer

Salah satu bagian yang paling banyak diiterasikan. Intinya AI punya ruleset ketat:
- **Dilarang keras** pakai frasa kayak "sangat menarik", "terima kasih telah berbagi", "semangat terus", dll
- Wajib terdengar kayak netizen Threads Indonesia yang scroll HP
- Struktur: Reaksi → Opini → Observasi Pribadi
- Maksimal 2-3 kalimat santai
- Boleh ada typo/kata kasual — itu justru bikin lebih human

### Trend Affiliate Mode (`APP_MODE=trend_affiliate`)

Kalau di mode ini, bot prioritasin post yang lagi viral (30+ likes, 3+ replies). Scoring-nya:

```
final_score = trend_score + relevance_score

Trend Score:
- 300+ likes  → +30 poin
- 100+ likes  → +20 poin
- 30+ likes   → +10 poin
- 30+ replies → +30 poin
- 10+ replies → +20 poin
- 3+ replies  → +10 poin

Relevance Score: dari keyword matching produk vs konteks post
```

Post dengan skor tertinggi yang dipilih, terus dicari produk Shopee yang paling relevan, baru di-generate komentarnya.

---

## Struktur Proyek

```
threads-aff-final/
│
├── main.py                       # Entry point untuk network discovery mode
├── auto_commenter.py             # 🔥 Bot komentar utama (loop tiada henti)
├── threads_poster.py             # Bot buat post opini organik (48 jam jeda)
├── threads_liker.py              # Module like post (hook dalam auto_commenter)
├── threads_timeline_debug.py     # Debug timeline fetcher
│
├── ai_engagement_engine.py       # AI intent scoring + tiered comment gen
├── llm_router.py                 # Router: Groq (primary) → Gemini (fallback)
├── gemini_manager.py             # API key rotation + cooldown + cache
├── stats_tracker.py              # Persistent stats tracker (JSON)
├── agent_loader.py               # Load custom agent prompt files
│
├── services/
│   ├── session_manager.py        # SessionManager + ThreadsAuth
│   ├── network_discovery.py      # Playwright traffic capture
│   ├── feed_explorer.py          # HTML endpoint discovery
│   ├── affiliate_strategy.py     # Product matching + AI comment gen
│   └── shopee_generator.py       # Shopee affiliate link generator
│
├── config/
│   └── browser.js                # Playwright browser config
│
├── docs/
│   └── feed_schema.md            # Skema feed (masih INFERRED, belum diverifikasi)
│
├── data/                         # Runtime data (cache, captures)
│
├── shopee_affiliate_links.json   # Database produk affiliate Shopee
├── graphql_dump.json             # Dump GraphQL query (dari network capture)
│
├── .env                          # Environment variables (jangan di-commit!)
├── .env.example                  # Template konfigurasi
├── .gitignore
└── requirements.txt
```

---

## Instalasi

```bash
# Clone repo
git clone <repo-url>
cd threads-aff-final

# Buat virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# atau
source venv/bin/activate     # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Install Playwright + browser
pip install playwright
python -m playwright install chromium

# Setup konfigurasi
cp .env.example .env
# Edit .env sesuai instruksi di bawah
```

---

## Konfigurasi `.env`

```env
# ── Threads Session (wajib) ──────────────────────────────────────
# Ambil dari browser: buka instagram.com → F12 → Application → Cookies
THREADS_SESSION_ID=your_session_id_here
THREADS_CSRF_TOKEN=your_csrf_token
THREADS_DS_USER_ID=your_user_id
THREADS_MID=your_mid
THREADS_IG_DID=your_ig_did

# ── Gemini API Keys (bisa sampai 4, auto-rotate) ─────────────────
# Dapet dari: https://aistudio.google.com/apikey
GEMINI_API_KEY_1=AIza...
GEMINI_API_KEY_2=AIza...   # opsional
GEMINI_API_KEY_3=AIza...   # opsional
GEMINI_API_KEY_4=AIza...   # opsional

# ── Groq API Keys (primary LLM, lebih cepat dari Gemini) ─────────
# Dapet dari: https://console.groq.com
GROQ_API_KEY_1=gsk_...
GROQ_API_KEY_2=gsk_...     # opsional

# ── Mode Operasi ─────────────────────────────────────────────────
# APP_MODE: normal | affiliate | trend_affiliate
APP_MODE=trend_affiliate

# ENGAGEMENT_MODE: ADVANCED (2 LLM calls, lebih akurat) | FAST (1 call, hemat token)
# Default: ADVANCED
ENGAGEMENT_MODE=ADVANCED

# ── Shopee (opsional, untuk generate link) ───────────────────────
SHOPEE_RAW_COOKIE=
```

### Cara Dapat Session Cookies

1. Buka browser → `instagram.com` atau `threads.net`
2. Login akun
3. Tekan **F12** → tab **Application** → **Storage** → **Cookies**
4. Copy nilai dari: `sessionid`, `csrftoken`, `ds_user_id`, `mid`, `ig_did`
5. Paste ke `.env`

> **Penting:** Session expires kalau kamu logout atau Instagram nge-invalidate. Kalau bot error session expired, tinggal ulangi langkah di atas.

---

## Panduan Setting Mode

Ada **dua variable mode** yang mengontrol perilaku bot. Keduanya diset di `.env`.

---

### 1. `APP_MODE` — Mode Utama Bot

Ini yang ngontrol **strategi keseluruhan** bot waktu balas komentar.

```env
APP_MODE=normal          # atau affiliate, atau trend_affiliate
```

#### `APP_MODE=normal` (default kalau nggak diset)
Bot balas semua post dengan komentar biasa tanpa link apapun. Murni engagement, nggak ada monetisasi.

```
Post masuk → Generate komentar natural → Kirim
```

**Cocok buat:** warming up akun baru, biar keliatan natural dulu sebelum sisipkan affiliate.

---

#### `APP_MODE=affiliate`
Bot cari produk yang relevan sama konten post. Kalau ada yang cocok (skor ≥ 5.0), ada kemungkinan **50% langsung sisipkan link**, 50% komentar biasa dulu.

```
Post masuk → Analisis keyword → Cari produk relevan?
  ├── YA → 50% sisipkan link, 50% komentar biasa
  └── TIDAK → komentar biasa 100%
```

**Cocok buat:** operasi normal sehari-hari.

---

#### `APP_MODE=trend_affiliate`
Mode paling agresif. Bot scan semua post di timeline, **pilih yang paling viral** (30+ likes, 3+ replies), terus **wajib** sisipkan affiliate link di komentarnya.

```
Fetch timeline → Score semua post berdasarkan viral + relevance
  → Pilih 1 post dengan skor tertinggi
  → Cari produk paling relevan → Generate komentar + wajib sisipkan link
```

Kalau nggak ada post yang masuk kriteria viral → fallback ke mode `affiliate` biasa.

**Cocok buat:** maksimalkan konversi di momentum viral.

---

**Perbandingan cepat:**

| Mode | Agresivitas | Risiko | Konversi Estimasi |
|------|-------------|--------|-------------------|
| `normal` | 🟢 Rendah | Minimal | 0% (engagement only) |
| `affiliate` | 🟡 Sedang | Sedang | ~50% dari post relevan |
| `trend_affiliate` | 🔴 Tinggi | Lebih tinggi | ~90%+ dari post yang dipilih |

---

### 2. `ENGAGEMENT_MODE` — Mode AI Engine

Ini yang ngontrol **cara AI generate komentar**. Diset terpisah dari `APP_MODE`.

```env
ENGAGEMENT_MODE=ADVANCED    # atau FAST
```

#### `ENGAGEMENT_MODE=ADVANCED` (default)
Dua LLM call per post:
1. **Call pertama** → AI score intent post (JSON: `buying_intent`, `commercial_intent`, `affiliate_probability`, dll)
2. Skor diproses → masuk tier 1/2/3
3. **Call kedua** → Generate komentar sesuai tier

```
Post → [LLM Call 1: Scoring] → Tier? → [LLM Call 2: Generate] → Safety Check → Kirim
```

Lebih akurat, lebih natural, tapi pakai 2x token.

#### `ENGAGEMENT_MODE=FAST`
Satu LLM call aja — AI langsung putuskan: pakai affiliate atau nggak, sekalian generate komentarnya.

```
Post → [LLM Call 1: Decide + Generate] → Safety Check → Kirim
```

Lebih hemat API token, cocok kalau key terbatas atau mau speed up.

---

### Kombinasi yang Direkomendasikan

| Situasi | `APP_MODE` | `ENGAGEMENT_MODE` |
|---------|-----------|-------------------|
| Akun baru, masih warming up | `normal` | `FAST` |
| Operasi harian normal | `affiliate` | `ADVANCED` |
| Mau maksimalin revenue | `trend_affiliate` | `ADVANCED` |
| API key terbatas / mau hemat | `affiliate` | `FAST` |

---



## Cara Pakai

### Mode 1: Auto Commenter (utama)

```bash
python auto_commenter.py
```

Bot bakal:
1. Load dan validasi session
2. Fetch timeline Threads via GraphQL
3. Pilih 1 post buat dibalas
4. Generate komentar (pakai Groq, fallback ke Gemini)
5. Kirim reply
6. **Tidur 14–17 menit** (biar nggak keliatan kayak bot)
7. Ulangi terus

### Mode 2: Auto Poster (opini organik)

```bash
python threads_poster.py
```

Bot bakal:
1. Pilih topik random (daily life, tech, football, dll)
2. Generate post opini pendek yang terdengar human
3. Post ke Threads
4. **Tidur 48 jam** sebelum posting berikutnya

### Mode 3: Network Discovery (riset endpoint)

```bash
python main.py
```

Bot bakal:
1. Launch browser via Playwright
2. Inject cookies
3. Capture semua network traffic selama 30 detik
4. Simpan hasil ke `network_capture.json`, `feed_candidates.json`, `graphql_candidates.json`
5. Generate `NETWORK_DISCOVERY_REPORT.md`

---

## Riwayat Development — Dari Awal Sampai Sekarang

### 🗺️ Fase 0 — Ide Awal
*"Gimana kalau kita bisa nyambungin orang yang lagi diskusi produk di Threads sama link affiliate Shopee?"*

Dari situ semua dimulai. Konsepnya simpel, eksekusinya... nggak sesimpel itu.

---

### 💥 Fase 1 — Login Otomatis (Gagal Total)

Percobaan pertama: bikin sistem yang bisa login ke Instagram/Threads via HTTP request biasa. Pakai `curl_cffi` buat bypass TLS fingerprinting.

Hasilnya?

```json
{
  "user": true,
  "authenticated": false,
  "status": "ok"
}
```

Credentials bener, tapi `sessionid` nggak pernah di-issue. Meta punya **trust-layer** yang ngedeteksi semua request otomatis sebelum sempat masuk.

**Status: ❌ Dihentikan**

---

### 🔬 Fase 2 — Diagnostik Login

Daripada buang semua kerjaan, dibangun `LoginRejectionClassifier` buat nganalisis kenapa login gagal. Berhasil ngeklasifikasi 8 kategori kegagalan:

- `INVALID_CREDENTIALS`
- `RATE_LIMITED`
- `CHECKPOINT_REQUIRED`
- `BOT_DETECTED`
- `SESSION_EXPIRED`
- `NETWORK_ERROR`
- `MAINTENANCE_MODE`
- `UNKNOWN`

Semua ini sekarang ada di `services/login_classifier.py`.

**Status: 📦 Diarsipkan (masih ada kodenya, tapi nggak dipakai)**

---

### 🏗️ Fase 3 — Arsitektur Session-First

Pelajaran dari kegagalan login: **jangan pernah coba login saat runtime**.

Solusinya radikal tapi simpel: pakai session yang udah authenticated dari browser. Bot nggak perlu tau cara login — cukup tau cara pakai session yang dikasih.

Perubahan besar:
- ❌ Hapus semua login retry logic
- ❌ Hapus CSRF handling dan session negotiation
- ✅ Masukkan `SessionManager` dengan bypass mode validator
- ✅ Multi-domain cookie injection (`.instagram.com`, `.threads.net`, `.threads.com`)
- ✅ Validasi cuma cek `sessionid` ada atau nggak — sisanya Playwright yang handle

**Status: ✅ Selesai**

---

### 🌐 Fase 4 — Network Discovery dengan Playwright

Karena Threads nggak punya public API, dibuatlah `NetworkDiscovery` — tool yang launch browser headless, inject cookies, scroll-scroll, dan capture semua network request yang lewat.

Dari sini ditemukan endpoint-endpoint GraphQL yang dipakai Threads:
- `/graphql/query` (primary)
- `BarcelonaFeedDirectQuery`
- `BarcelonaHomeTimeline`

Semua endpoint ini yang sekarang dipakai `auto_commenter.py` buat fetch timeline.

**Status: ✅ Selesai**

---

### 🤖 Fase 5 — AI Engine + LLM Router

Fase paling panjang dan paling banyak iterasinya. Di sini dibangun:

**`ai_engagement_engine.py`** — Intent scoring + tiered comment generation
**`llm_router.py`** — Router yang nyoba Groq dulu, fallback ke Gemini kalau gagal
**`gemini_manager.py`** — Key rotation, cooldown management, response cache 24 jam

Tantangan terbesar: bikin AI nulis kayak manusia Indonesia, bukan kayak bot marketing atau motivator Instagram. Akhirnya lahirlah **Anti-AI Writing Layer** — serangkaian aturan prompt yang bikin AI sadar diri buat nggak pakai frasa-frasa AI klasik.

**Status: ✅ Selesai**

---

### 🛒 Fase 6 — Affiliate Strategy Engine

Dibangun sistem matching produk yang nggak butuh LLM call tambahan:

1. Bot baca caption post
2. Cari keyword yang match sama `KEYWORD_ALIASES` (hp → smartphone, kopi → minuman, dll)
3. Score tiap produk di database Shopee berdasarkan keyword + category match
4. Kalau skor ≥ 5.0 → produk dianggap relevan, sisipkan di komentar
5. Kalau nggak ada yang relevan → komentar biasa tanpa link

Database produknya ada di `shopee_affiliate_links.json` (150KB+ data produk).

**Status: ✅ Selesai**

---

### 📈 Fase 7 — Trend Affiliate Mode (Current)

Mode paling sophisticated yang ada sekarang. Daripada random pilih post buat dibalas, bot prioritasin post yang lagi viral berdasarkan engagement score.

Post dengan skor tertinggi dipilih, dicari produk yang paling relevan, terus di-generate komentar yang wajib nyisipin link affiliate (bukan 50/50 kayak mode biasa).

Logika scoring, fallback handling, dan stats tracking semuanya sudah jalan di `auto_commenter.py`.

**Status: ✅ Selesai**

---

### 🔜 Fase 8 — Yang Masih Direncanakan

- **Multi-session / Multi-akun** — Rotate antar beberapa akun Threads
- **Dukungan media (gambar)** — Post dengan gambar, bukan cuma text
- **Dashboard stats** — Web UI buat lihat performa bot
- **Feed schema validation** — Verifikasi endpoint setelah dapat valid session

---

## Progress Keseluruhan

| Komponen | Progress |
|----------|----------|
| Session Auth & Management | ████████████████ 100% |
| Network Discovery | ████████████████ 100% |
| Timeline Fetcher | ████████████████ 100% |
| AI Comment Generation | ████████████████ 100% |
| Affiliate Product Matching | ████████████████ 100% |
| Auto Reply Pipeline | ████████████████ 100% |
| Auto Post Pipeline | ████████████████ 100% |
| Trend Mode | ████████████████ 100% |
| Stats Tracking | ████████████████ 100% |
| Multi-Session Support | ░░░░░░░░░░░░░░░░ 0% |
| Feed Schema (verified) | ████░░░░░░░░░░░░ 25% |
| Web Dashboard | ░░░░░░░░░░░░░░░░ 0% |

---

## LLM Stack

| Model | Provider | Peran |
|-------|----------|-------|
| `llama-3.3-70b-versatile` | **Groq** | Primary (lebih cepat, gratis) |
| `gemini-3.5-flash` | **Google** | Fallback kalau Groq error |

Groq dicoba duluan karena lebih cepat dan punya rate limit yang lebih longgar buat inference. Kalau semua Groq key habis atau error, otomatis fallback ke Gemini. Kalau keduanya down, bot log error dan retry di iterasi berikutnya.

Key rotation dihandle otomatis — sampai 4 key per provider bisa dikonfigurasi.

---

## File Output Bot

| File | Isi |
|------|-----|
| `stats.json` | Statistik bot (comments sent, errors, dll) |
| `network_capture.json` | Raw network requests dari Playwright |
| `feed_candidates.json` | Kandidat feed endpoint |
| `graphql_candidates.json` | GraphQL requests yang ditemukan |
| `gemini_cache.json` | Cache response AI (24 jam) |
| `data/product_theme_cache.json` | Cache kategori produk |
| `NETWORK_DISCOVERY_REPORT.md` | Laporan discovery endpoint |

---

## Disclaimer

> **Penting banget dibaca sebelum pakai:**
>
> Proyek ini dibuat untuk **keperluan riset, eksplorasi teknis, dan pendidikan** di bidang automation engineering.
>
> Dengan menggunakan tool ini, kamu acknowledge bahwa:
> - **Kamu sendiri yang bertanggung jawab** untuk comply dengan ToS [Meta/Threads](https://threads.net/terms) dan [Shopee](https://shopee.co.id/terms)
> - Aksi otomatis bisa melanggar kebijakan platform dan berpotensi kena suspend
> - Developer tidak bertanggung jawab atas konsekuensi apapun dari penggunaan tool ini
> - **Use at your own risk**

---

## Tech Stack

- **Python 3.10+**
- **curl_cffi** — HTTP client dengan TLS fingerprint bypass
- **Playwright** — Browser automation untuk network capture
- **Groq API** — Primary LLM (llama-3.3-70b)
- **Google GenAI** — Fallback LLM (Gemini)
- **python-dotenv** — Environment management

---

## Lisensi

MIT License — bebas dipakai, dimodifikasi, didistribusikan.

---

*Last updated: 2026-06-19 — Semua fitur core sudah selesai dan jalan.*
