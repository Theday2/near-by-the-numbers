# BUILD_LOG — NEAR by the Numbers (build lanjutan, 12 Nov 2026)

**Sesi build:** 12 Nov 2026 ~20:53–21:10 WIB. Tugas: perdalam tesis
(track #2 Investment Thesis), rapikan dashboard, verifikasi.
**Status: SELESAI — semua verifikasi PASS.** Tidak ada akun/wallet dibuat,
tidak ada push GitHub, tidak ada posting X, tidak ada form diisi, tidak ada
uang keluar (sesuai batas keras).

## Yang ditambah / diubah

### 1. Perbandingan SOL (`near_thesis/fetch.py`, `analyze.py`, `report.py`)
- `fetch.py`: CoinGecko loop sekarang mengambil 4 koin — `near, bitcoin,
  ethereum, solana` (sebelumnya 3). Tanpa key, read-only, graceful
  degradation kalau satu koin gagal.
- `analyze.py`: SOL masuk ke `assets` dengan `_series_stats` yang sama
  (return 30/90/365d, vol, drawdown — semua span-gated seperti aset lain).
- Baru: korelasi NEAR–SOL (0,61 pada run 365d), pergerakan rasio harga
  NEAR/SOL (30/90/365d), dan P(NEAR beats SOL over 1y) = **87,3%** via
  model Gaussian-spread pada selisih log-return harian (dilabeli jelas
  sebagai estimasi model + jendela estimasinya, bukan hasil Monte Carlo).
- Monte Carlo bivariate NEAR/BTC **tidak diubah** (sengaja — angka
  terverifikasi sebelumnya dipertahankan).

### 2. Tren volume (`analyze.py`, `report.py`)
- Baru `_volume_stats`: rata-rata volume harian USD 30 hari terakhir vs
  60 hari sebelumnya + rasio trennya. Span-gated (butuh sampel 90 hari+).
- Hasil live 12 Nov: volume NEAR 30d **$672 jt/hari** vs 60 hari sebelumnya
  **$745 jt/hari** → tren **0,90x (aktivitas menurun)**; SOL 30d $2,59 M/hari.
- Tesis mendapat seksi baru "Volume: is anyone actually trading it?" —
  volume sebagai lie detector pergerakan harga.

### 3. Narasi tesis lebih kuat (`report.py`, `thesis.md`)
- Seksi baru "NEAR vs the majors": tabel perbandingan NEAR/BTC/ETH/SOL
  (return 30/90/365d, vol, drawdown) + paragraf interpretasi.
- "The case" tambah poin ke-4: tesis ini adalah kasus *valuasi* (mean
  reversion + diskon), bukan kasus *momentum* — NEAR tidak unggul relatif
  secara decisif kecuali vs SOL dalam 1 tahun terakhir.
- "What would change this thesis" tambah 3 pemicu tajam: tren volume
  < 0,7x dua bulan berturut-turut saat harga naik; rasio NEAR/SOL turun
  > 20% dalam 90 hari sementara volume SOL tetap naik; larangan klaim
  return 1y dari data < 1 tahun.
- Kalimat-kalimat di mode demo dibuat kondisional (tidak ada lagi "return
  of n/a" atau "$n/a").

### 4. Dashboard dirapikan (`report.py`)
- Grafik harga: tambah ETH + SOL (rebased, garis tipis; NEAR tebal).
- Grafik baru: volume harian NEAR (bar) + rata-rata 30 hari (garis merah).
- Tabel baru "NEAR vs the majors" + angka SOL/volume/P(beats SOL) di
  tabel snapshot.
- Setiap grafik dapat caption bahasa sederhana (untuk juri non-teknis).

### 5. Bug yang ditemukan & diperbaiki selama build
- **Rasio NEAR/SOL salah jendela (1y n/a, 90d +100,3% vs cross-check
  +90,8%).** Penyebab: CoinGecko mengembalikan 1 poin/hari + 1 poin "now",
  jadi timestamp akhir antar-koin berbeda beberapa detik dan join
  milidetik membuang poin + menggeser jendela 1 hari. Perbaikan:
  alignment per tanggal kalender UTC **sambil mempertahankan struktur
  baris NEAR** (hari ini muncul 2x: close 00:00 + "now"). Setelah
  perbaikan, rasio cross-check **persis** di semua jendela
  (30d −12,0% / 90d +90,8% / 1y +151,4%).
- **Split literal bytes yang salah** (bukan di proyek ini — catatan dari
  pengalaman build lain): tidak relevan di sini; tidak ada file yang
  dipecah manual.
- **Disiplin periode dipertahankan:** return 1y hanya diklaim bila sampel
  mencakup 365 hari; demo 90 hari tetap menampilkan `n/a` untuk 1y +
  peringatan jendela pendek (diuji eksplisit di tes baru).

### 6. Tes baru (`tests/test_smoke.py`)
- `test_volume_and_sol_graceful`: sampel 90 hari → volume NEAR ada +
  tren 0,90x; SOL absen dengan anggun; `ret_365d is None` (pengaman bug
  lama); rasio 1y n/a; thesis memuat seksi baru.

### 7. README diperbarui
- Sebut SOL + tren volume di "What it does" dan "Method"; angka ekspektasi
  live diperbarui ke run 12 Nov 20:59 WIB (NEAR $3,38, 1y +33,5%, MC median
  $4,46; TPS snapshot ~5 pada run ini — bervariasi antar-fetch).

## Angka kunci (live run 365d, 12 Nov 2026 ~21:05 WIB)

- NEAR **$3,38** — −83,5% dari ATH $20,44 (2022-01-16). 1y **+33,5%**,
  90d +106,2%, 30d −32,9%.
- Pembanding 1y: BTC −28,7% / ETH −41,1% / **SOL −46,9%** — NEAR satu-satunya
  yang positif. Rasio NEAR/SOL **+151,4%** dalam 1y.
- Vol 102,2%, max drawdown −61,9%, beta vs BTC 1,22, korelasi BTC 0,52,
  korelasi SOL 0,61.
- Chain: 371 validator, ~5 TPS (snapshot), 5,48 miliar transaksi total,
  blok rata-rata 0,561 dtk.
- Monte Carlo 10.000 path: median 1y **$4,46** (P10 $1,25, P90 $16,60);
  P(NEAR beats BTC) 77,2%; P(NEAR up) 61,0%.
- Volume: tren 0,90x (menurun); P(NEAR beats SOL, 1y, Gaussian spread) 87,3%.

## Verifikasi (semua PASS)

```bash
cd ~/workspace/near-hackathon-2026

python main.py --demo --out out-demo
# NEAR $3.40  1y n/a  vol 128%  beta vs BTC 1.56
# Monte Carlo 1y median $64.17 (P10 $13.07, P90 $333.15)
# wrote out-demo/thesis.md, out-demo/dashboard.html

python main.py --fetch --days 365 --out out
# NEAR $3.38  1y +33.5%  vol 102%  beta vs BTC 1.22
# Monte Carlo 1y median $4.46 (P10 $1.25, P90 $16.60)
# wrote out/thesis.md, out/dashboard.html

python -c "import sys; sys.path.insert(0, '.'); from tests.test_smoke import
  test_demo_pipeline, test_cli_demo, test_volume_and_sol_graceful; ..."
# smoke test_demo_pipeline: PASS
# smoke test_cli_demo: PASS
# smoke test_volume_and_sol_graceful: PASS
```

Pemeriksaan tambahan:
- Rasio NEAR/SOL cross-check persis vs return masing-masing aset
  (30d −0,1199 / 90d 0,9081 / 1y 1,5137, semua sama).
- Blob/dekompresi: tidak ada (proyek ini tidak memakai payload terkompresi).
- Dashboard: 4 grafik terverifikasi isinya (price 4 garis incl. SOL;
  drawdown; volume 366 bar + garis rata-rata 30d; histogram MC 60 bin +
  garis median). Thesis memuat semua seksi baru; mode demo tidak
  mengklaim angka 1y.
- Determinisme: analisis pada data yang sama memberi hasil identik
  (dijamin tes `test_demo_pipeline`).

## Sisa sebelum submit (BUKAN bagian tugas ini — untuk Wo top-level)

1. Repo GitHub publik + push (butuh akun GitHub paman).
2. Demo video/screenshot + posting X (tag @NEARProtocol + #NEARHackathon) —
   draft dulu, posting setelah paman setuju.
3. Form submit di nearhackathon.com — butuh **alamat akun NEAR paman**
   untuk payout (Wo dilarang membuat wallet).
4. Deadline: **14 Nov 2026 23:59 UTC (15 Nov 06:59 WIB)**.
