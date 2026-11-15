# Research Lab News — GitHub Actions

Bot pengiriman berita terjadwal untuk kanal news server **Research Lab**.
Ini webhook dengan nama Research Lab News, bukan bot chat online atau bot slash-command.
Paket ini berdiri sendiri; tidak mengganti aplikasi localhost `D:\VSC`.

## Apa yang dibuat

- Cek feed Federal Reserve dan CNBC setiap 15 menit (menit UTC 7, 22, 37, 52).
- Seleksi topik saham AS/makro dengan kata kunci dan bobot yang bisa diedit.
- Hanya berita bertanggal dalam 24 jam; tidak memakai tanggal publikasi masa depan.
- Maksimal 2 berita per pemeriksaan dan 12 percobaan kirim per hari UTC.
- Hindari URL yang sudah diproses dan judul identik antarpenerbit. Ini bukan deteksi semua duplikat semantik.
- Kiriman berisi sumber, tanggal publikasi, batas bukti, dan draft caption Canva.
- Arsip berita yang dipilih, payload Discord, serta status pengiriman pada branch `research-state`.
- Mode preview tidak mengirim apa pun dan tidak menandai berita sebagai terkirim.
- Tidak memerlukan pip/dependency tambahan: Python 3.12 dan standard library.

**Status paket:** kode dan unit test tersedia. Belum di-deploy ke akun GitHub, belum memiliki webhook,
dan belum diuji mengirim ke Discord Anda. Pengujian lokal memakai fixture, bukan bukti feed saat ini aktif.

## Biaya dan AI

GitHub Actions runner standar gratis pada repository publik. Repository privat memiliki kuota;
jangan mengaktifkan biaya berlebih jika ingin tetap gratis. Jadwal tidak menjamin ketepatan 15 menit
atau SLA 24/7. Workflow publik dapat dinonaktifkan setelah 60 hari tanpa aktivitas repository.
Pantau tab Actions dan aktifkan email notifikasi kegagalan.

Tanpa API key, bot tetap bekerja sebagai **headline alert + template caption**, bukan ringkasan AI.
Dengan `GEMINI_API_KEY` dan `GEMINI_MODEL`, bot meminta draft Bahasa Indonesia dari Gemini.
Pilih model yang memiliki kuota gratis di akun AI Studio Anda; tidak ada model berbayar/default otomatis.
Jika model gagal/kuota habis, bot menurunkan keluaran menjadi headline alert yang diberi label jelas.
Teks judul/deskripsi RSS publik dikirim ke Google hanya saat key dipasang. Tidak memakai Ollama laptop.
Biaya hosting dan kuota AI adalah dua hal berbeda; paket tidak menjamin AI gratis tanpa batas.

## Pasang di GitHub

1. Buat repository baru, misalnya `research-lab-news`. Pilih Public hanya jika bersedia kode,
   arsip payload berita, dan riwayat delivery ID terlihat publik. Secret tidak masuk repository.
2. Extract ZIP. Upload seluruh isi ke root repository, termasuk folder **`.github/workflows`**.
   File workflow harus berada di `.github/workflows/news.yml`, bukan di subfolder paket.
3. Buka Settings > Actions > General. Izinkan workflow memiliki **Read and write permissions**
   untuk menyimpan arsip pada repository ini. Jika aturan organisasi melarang, jangan kirim
   sebelum ada penyimpanan persisten alternatif.

## Buat webhook kanal yang benar

1. Di server Research Lab, buka pengaturan kanal news yang dituju.
2. Integrations > Webhooks > New Webhook. Namai `Research Lab News`, pilih kanal tujuan,
   kemudian Copy Webhook URL. Anda memerlukan izin Manage Webhooks.
3. Aktifkan Developer Mode Discord, klik kanan kanal tujuan > Copy Channel ID.
4. Di GitHub: Settings > Secrets and variables > Actions:

| Jenis | Nama | Isi |
|---|---|---|
| Secret | `DISCORD_WEBHOOK_URL` | URL webhook kanal Research Lab |
| Variable | `DISCORD_CHANNEL_ID` | ID kanal yang sama; bot memverifikasinya sebelum mengirim |
| Secret, opsional | `GEMINI_API_KEY` | Key dari akun Google AI Studio Anda |
| Variable, untuk AI | `GEMINI_MODEL` | Kode model yang tersedia dan sesuai kuota gratis akun Anda |
| Variable | `NEWS_ENABLED` | Awalnya `false`; ubah menjadi `true` setelah pengujian |

Jangan menaruh webhook/key di config.json, README, issue, screenshot, atau chat.
Undangan `discord.gg` tidak dapat digunakan sebagai webhook.

## Uji lalu aktifkan

1. Actions > Research Lab News > Run workflow. Biarkan **send = false**.
2. Setelah selesai, unduh artifact `research-lab-preview-...`. Buka JSON berita:
   `payload.embeds[0].description` berisi tampilan teks; `run-report.json` menunjukkan feed gagal/berhasil.
3. Periksa sumber, waktu, format caption, dan apakah feed memberi hasil relevan. Jika selected = 0,
   itu bisa berarti tidak ada berita yang lolos, bukan berarti bot rusak.
4. Jalankan manual lagi dengan **send = true** untuk menguji kanal (maksimum 2 kiriman).
5. Pastikan kiriman benar-benar masuk kanal news Research Lab. Baru set **NEWS_ENABLED = true**.
6. Untuk berhenti, set NEWS_ENABLED = false atau Disable workflow. Workflow manual send=true tetap dapat mengirim.

## Factual bukan berarti dijamin benar

Bot memakai **judul/deskripsi RSS**, bukan pembacaan penuh artikel dan bukan fact-checker independen.
Pemilihan 'penting' memakai skor kata kunci; tidak otomatis mengetahui semua hot news.
Setiap draft AI ditandai untuk diperiksa sebelum dipublikasikan. Satu penerbit tidak dianggap sebagai
konfirmasi independen. Tautan sumber ditambahkan program, bukan dihasilkan AI.
Jangan langsung menerbitkan klaim besar atau angka tanpa membuka sumber aslinya.
Caption sudah berada pada kiriman yang sama untuk disalin ke Canva; desain Canva tidak dibuat otomatis.

## Arsip dan pengiriman yang tidak pasti

Branch `research-state` menyimpan `state.json` dan `archive/<id>.json`.
Sebelum POST ke Discord, status `pending` disimpan dan di-push; setelah ada receipt menjadi `sent`.
Jika timeout/crash terjadi, pending tidak dikirim ulang otomatis. Cek kanal dulu. Jika pesan sudah ada,
ubah status pending menjadi sent di state.json. Jika benar-benar belum terkirim, hapus hanya entri
tersebut dari `items` untuk mengizinkan percobaan baru (selama berita masih dalam rentang 24 jam).
Ini mengutamakan pencegahan duplikasi; bukan jaminan exactly-once. Git push yang gagal akan
menghentikan proses. Baca Actions log, bukan sekadar mengulang run berkali-kali.

Arsip hanya untuk berita terpilih, bukan seluruh internet. Artifact preview disimpan 7 hari;
arsip pengiriman bertahan pada branch sampai Anda menghapusnya. Jangan menulis data privat di repo publik.

## Kustomisasi

Edit config.json: feed RSS (HTTPS), keywords, min_score, max_age_hours, batas kiriman.
Ketersediaan feed dapat berubah dan akses dari GitHub bisa berbeda dengan laptop. Kegagalan sebagian
feed dicatat; jika semua gagal, workflow gagal tanpa membuat berita pengganti.
Paket ini khusus news/Discord; dashboard SEC/PDF/FRED tetap ada pada paket aplikasi lokal sebelumnya.

## Tes lokal

```powershell
python -m unittest discover -s tests -v
python bot.py
```

Perintah kedua hanya preview. Jangan menuliskan secret langsung dalam command yang akan disimpan di history.

## Dokumentasi resmi

- https://docs.github.com/en/actions/concepts/billing-and-usage
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- https://docs.discord.com/developers/resources/webhook
- https://www.federalreserve.gov/feeds/feeds.htm
- https://www.cnbc.com/rss-feeds/
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://ai.google.dev/gemini-api/docs/models
