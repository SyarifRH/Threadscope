# Changelog

Semua perubahan dan update penting pada project Threadscope akan dicatat pada file ini.

## [Unreleased] / [Terbaru]

### 🚀 Fitur Baru & Peningkatan (Enhancements)
- **[auto_commenter.py] Konfigurasi Fallback Otomatis**: Menambahkan konfigurasi *GraphQL (Default Fallback)* bawaan. Sekarang, jika pengguna tidak memiliki file `graphql_dump.json` atau gagal melakukan *capture*, bot tidak akan *crash*, melainkan otomatis menggunakan konfigurasi *default* yang sudah teruji.
- **[auto_commenter.py] Sistem Log Debug Transparan**: Menambahkan pesan `[DEBUG]` pada tahapan `process_timeline`, `fetch_timeline`, dan `extract_posts`. Sebelumnya, jika bot gagal mengambil timeline (karena token kadaluarsa atau koneksi diblokir), bot akan seakan-akan *hang* (diam dan *sleep* 60 detik tanpa pesan). Sekarang, bot akan mencetak alasan pasti kenapa gagal.
- **[main.py] Pembersihan Kode (Code Cleanup)**: Menghapus fungsionalitas *testing* khusus Shopee Affiliate dari `main.py`. Skrip `main.py` kini lebih ringan dan 100% difokuskan hanya untuk validasi *Session Threads* dan *Network Discovery*.

### 🐛 Perbaikan Bug (Bug Fixes)
- **[services/network_discovery.py] Perbaikan Parsing Payload URL-Encoded**: Memperbaiki masalah fatal di mana skrip `main.py` sering kali menghasilkan file `graphql_dump.json` yang kosong. Hal ini disebabkan karena sebelumnya skrip tidak bisa membaca payload GraphQL dari Threads yang menggunakan format *URL-encoded*. Skrip kini sudah ditambal agar bisa melakukan parsing pada format JSON murni maupun *URL-encoded* dengan sempurna.
- **[auto_commenter.py] Pencegahan Crash pada Format JSON**: Meningkatkan keandalan fungsi `load_latest_query_config()`. Script kini kebal terhadap berbagai variasi format isi dari `graphql_dump.json` (seperti perubahan struktur tipe data) sehingga tidak akan terjadi error *Type Error* atau *JSONDecodeError*.
