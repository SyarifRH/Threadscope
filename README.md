# 🚀 ThreadScope — Threads × Shopee Affiliate Automation Bot

ThreadScope adalah bot otomatisasi berbasis AI yang membaca timeline Threads, memahami konteks postingan, dan memberikan komentar yang relevan. Jika memungkinkan, bot ini akan menyisipkan link afiliasi Shopee secara natural.

Bot ini menggunakan pendekatan **Session-First** (menggunakan cookie browser) untuk menghindari pemblokiran *trust-layer* dari Meta.

## ✨ Fitur Utama

- **Session Injection:** Menghindari blokir login menggunakan cookie browser.
- **LLM Combo:** Menggunakan Groq (Llama 3) untuk kecepatan dan Gemini sebagai cadangan (fallback).
- **Anti-AI Writing:** Komentar dihasilkan se-natural mungkin seperti manusia, menghindari bahasa kaku.
- **Trend Affiliate Mode:** Menargetkan postingan viral (30+ likes) untuk memaksimalkan eksposur link afiliasi.
- **Auto Post:** Dapat melakukan *organic post* secara otomatis agar akun tetap terlihat aktif.

## 🛠️ Instalasi & Persiapan

1. **Clone repositori dan masuk ke direktori proyek:**
   ```bash
   git clone <repo-url>
   cd Threadscope
   ```

2. **Buat dan aktifkan virtual environment:**
   - **Windows:**
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   - **Mac/Linux:**
     ```bash
     python -m venv venv
     source venv/bin/activate
     ```

3. **Install semua dependensi:**
   ```bash
   pip install -r requirements.txt
   pip install playwright
   python -m playwright install chromium
   ```

4. **Siapkan konfigurasi `.env`:**
   Salin file `.env.example` menjadi `.env`.
   ```bash
   cp .env.example .env
   ```

## ⚙️ Konfigurasi

### 1. Pengaturan `.env`
Buka file `.env` dan lengkapi data berikut:

```env
# Session Cookies Threads (Ambil dari F12 > Application > Cookies di threads.net)
THREADS_SESSION_ID=
THREADS_CSRF_TOKEN=
THREADS_DS_USER_ID=
THREADS_MID=
THREADS_IG_DID=

# API Keys (Bisa diisi lebih dari satu)
GEMINI_API_KEY_1=
GROQ_API_KEY_1=

# Mode Aplikasi
APP_MODE=trend_affiliate      # Pilihan: normal | affiliate | trend_affiliate
ENGAGEMENT_MODE=ADVANCED      # Pilihan: ADVANCED (analisis 2 tahap) | FAST (analisis 1 tahap)
```
*(Catatan: Jika session expired, silakan login ulang di browser dan perbarui cookie di `.env`)*

## 🛒 Ganti Link Shopee Punya Lu Sendiri

Biar cuannya masuk ke kantong lu (bukan ke kantong *developer*), lu **wajib** ganti data produk di file `shopee_affiliate_links.json`. 

Buka file-nya, terus ganti *link-link* yang ada di situ pake *custom link affiliate* Shopee lu sendiri. Formatnya JSON biasa, lu tinggal sesuaikan nama produk, *keyword*, sama URL-nya. Kalo ngga diganti, ntar yang dapet komisi orang lain dong! 💸

## 🚀 Cara Menjalankan

Pilih skrip yang ingin Anda jalankan sesuai kebutuhan:

1. **Bot Komentar & Afiliasi Utama:**
   Bot akan membalas postingan di timeline dengan jeda waktu natural.
   ```bash
   python auto_commenter.py
   ```

2. **Bot Posting Otomatis:**
   Untuk membuat akun terlihat hidup dengan postingan organik.
   ```bash
   python threads_poster.py
   ```

3. **Network & Endpoint Discovery (Riset):**
   ```bash
   python main.py
   ```

## ⚠️ Disclaimer

Bot ini dibuat murni untuk keperluan **riset dan edukasi**. Penggunaan bot ini untuk melakukan spamming hingga menyebabkan penangguhan akun (suspend) sepenuhnya merupakan **tanggung jawab pengguna**. Harap patuhi Ketentuan Layanan (ToS) dari Meta dan Shopee.
