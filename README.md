# 🌍 GeoESG A.E.C.O — Automated ESG Compliance Observer

> **Pipeline audit kepatuhan lingkungan (ESG) berbasis data satelit** untuk wilayah Nusa Tenggara Barat, mengintegrasikan remote sensing, machine audit, computer vision, dan pelaporan otomatis.

![Python](https://img.shields.io/badge/Python-GEE%20%7C%20FastAPI-3776AB?logo=python&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-ESG%20Engine-000000?logo=rust&logoColor=white)
![R](https://img.shields.io/badge/R-Shiny%20%7C%20ggplot2-276DC3?logo=r&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Multi--Stage-2496ED?logo=docker&logoColor=white)
![CI](https://github.com/rizkiagustiawan/GeoESG-Final/actions/workflows/main.yml/badge.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## 📋 Overview

GeoESG adalah sistem **polyglot pipeline** (Python → Rust → R) yang melakukan:

1. **Ekstraksi data satelit** dari Google Earth Engine (Sentinel-2 NDVI, Sentinel-1 SAR, ALOS PALSAR L-Band)
2. **Computer Vision** — Tree Crown Segmentation menggunakan arsitektur U-Net untuk menghitung pohon individu dari citra resolusi tinggi (0.5m)
3. **Machine Learning** — Estimasi biomassa menggunakan Random Forest yang dilatih dengan fusi data multi-sensor
4. **Audit integritas data** — membandingkan estimasi satelit vs ground truth lapangan menggunakan *Exponential Decay Trust Score* untuk mendeteksi risiko *greenwashing*
5. **Cetak peta kartografi otomatis** — 300 DPI, A3 landscape, 9 elemen wajib (judul, skala, north arrow, legenda, grid, inset, sumber data, proyeksi, pembuat)
6. **Pelaporan otomatis** sesuai kerangka GRI 304 (Keanekaragaman Hayati) & estimasi stok karbon SNI 7724:2011

### Mengapa 3 Bahasa?

| Bahasa | Peran | Alasan |
|--------|-------|--------|
| **Python** | Ekstraksi data satelit (GEE SDK), ML, CV, Kartografi | SDK resmi Earth Engine + ekosistem ML terlengkap |
| **Rust** | Mesin kalkulasi compliance | Performa tinggi, type-safety untuk kalkulasi kritis |
| **R** | Pelaporan statistik & dashboard | Ekosistem terbaik untuk reporting geospasial (sf, ggplot2) |

---

## 🏗️ Arsitektur

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Python (GEE)   │────▶│   Rust Engine    │────▶│   R Reporting   │
│  Sentinel-2/1   │     │  Trust Score +   │     │  Markdown + Shiny│
│  ALOS PALSAR    │     │  Greenwashing    │     │  Dashboard      │
│  U-Net Vision   │     │  Detection       │     │                 │
│  ML Biomass     │     │                  │     │                 │
└────────┬────────┘     └────────┬─────────┘     └────────┬────────┘
         │                       │                         │
         ▼                       ▼                         ▼
    raw_data.json          esg_metrics.json         ESG_Report.md
         │                       │                         │
         └───────────┬───────────┘                         │
                     ▼                                     │
              ┌─────────────┐                              │
              │  FastAPI     │◀─────────────────────────────┘
              │  Orchestrator│
              └──────┬──────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
    ┌──────────┐ ┌────────┐ ┌──────────┐
    │ Command  │ │  Map   │ │ Celery   │
    │ Center   │ │ Printer│ │ Workers  │
    │ (UI)     │ │ (300DPI)│ │ (Async)  │
    └──────────┘ └────────┘ └──────────┘
```

---

## 🚀 Quick Start

### Lokal (Development)

```bash
# 1. Clone & setup
git clone https://github.com/rizkiagustiawan/GeoESG-Final.git
cd GeoESG-Final

# 2. Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. GEE Credentials (opsional — ada fallback mode)
# Letakkan service account key di credentials/gee-key.json

# 4. Build Rust engine
cd rust-esg-engine && cargo build --release && cd ..

# 5. Start PostgreSQL + Redis (untuk fitur lengkap)
docker-compose up -d db redis

# 6. Jalankan server
uvicorn api_server:app --host 0.0.0.0 --port 8000

# 7. Buka browser → http://localhost:8000
```

### Docker (Production)

```bash
# Gunakan docker-compose untuk deployment satu perintah
docker-compose up -d --build

# Server akan berjalan di background pada port 8000
```

---

## 📡 API Endpoints

| Method | Endpoint | Deskripsi | Auth |
|--------|----------|-----------|------|
| `GET` | `/` | Command Center UI | — |
| `GET` | `/api/regional-borders` | GeoJSON batas NTB (9 kabupaten) | — |
| `POST` | `/generate-esg-report` | Audit single site | Rate limited |
| `POST` | `/generate-esg-batch` | Audit multi-site async (Celery) | API Key |
| `GET` | `/api/task-status/{id}` | Cek status batch task | — |
| `GET` | `/api/audit-history` | Log audit PostgreSQL | — |
| `POST` | `/api/generate-map/{site_id}` | Generate peta kartografi (single) | — |
| `POST` | `/api/generate-all-maps` | Batch generate 9 peta NTB | — |
| `GET` | `/api/maps` | List peta yang tersedia | — |
| `GET` | `/api/maps/{filename}` | Download peta PNG | — |
| `GET` | `/api/health` | Health check | — |

### Contoh Request

```bash
# Single audit
curl -X POST http://localhost:8000/generate-esg-report \
  -H "Content-Type: application/json" \
  -d '{"site_id": "Sumbawa Barat", "ground_truth_biomass": 120.5}'

# Batch audit (Dilindungi API Key)
curl -X POST http://localhost:8000/generate-esg-batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: geoesg-secret-key-2026" \
  -d '{
    "sites": [
      {"site_id": "Sumbawa Barat", "ground_truth_biomass": 120.5},
      {"site_id": "Lombok Tengah", "ground_truth_biomass": 210.0},
      {"site_id": "Dompu", "ground_truth_biomass": 95.5}
    ]
  }'

# Generate peta satu lokasi
curl -X POST http://localhost:8000/api/generate-map/Lombok%20Barat -o peta.png
```

---

## 📂 Struktur Proyek

```
GeoESG-Final/
├── api_server.py              # FastAPI orchestrator (11 endpoints)
├── worker.py                  # Celery async worker (batch processing)
├── index.html                 # Command Center UI (Leaflet + Chart.js + Map Gallery)
├── test_api.py                # Pytest suite
├── requirements.txt           # Python dependencies
├── python-gee-ai/
│   ├── extractor.py           # GEE extraction (Sentinel-2/1, ALOS, fusi sensor)
│   ├── map_printer.py         # Cetak peta kartografi 300 DPI (matplotlib)
│   ├── vision_unet_model.py   # Computer Vision tree crown segmentation
│   └── ml_models/             # Trained Random Forest model (.joblib)
├── rust-esg-engine/
│   ├── Cargo.toml
│   └── src/main.rs            # Trust score & greenwashing detection (4 unit tests)
├── r-reporting/
│   └── app.R                  # Shiny dashboard (sf, leaflet, ggplot2)
├── shared_data/
│   ├── batas_ntb.geojson      # Batas administratif NTB
│   ├── raw_data.json          # Output Python → Input Rust
│   ├── esg_metrics.json       # Output Rust → Input R
│   └── maps/                  # Generated kartografi maps (PNG)
├── credentials/               # GEE service account key (gitignored)
├── .github/workflows/
│   └── main.yml               # CI/CD: Rust test + Python test
├── Dockerfile                 # Multi-stage build (Rust + Ubuntu + R)
├── docker-compose.yml         # Production: API + Worker + PostgreSQL + Redis
└── run_pipeline.sh            # CLI pipeline runner
```

---

## ⚠️ Catatan Metodologi Ilmiah

> **Estimasi biomassa dan karbon** dalam proyek ini menggunakan pendekatan **Multivariable Fusion Model** yang menggabungkan data Optik (Sentinel-2), C-Band SAR (Sentinel-1), dan L-Band SAR (ALOS PALSAR-2) untuk memitigasi efek saturasi NDVI di hutan tropis. Model Machine Learning (Random Forest) dilatih dengan 10,000 titik sampel simulasi NASA GEDI L4A. Faktor konversi karbon disesuaikan dengan **SNI 7724:2011** (0.46) untuk hutan pamah Indonesia. Untuk laporan ESG definitif hukum, model tetap wajib dikalibrasi ulang dengan data *ground-truthing* lokal.

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+, FastAPI, Google Earth Engine API
- **Async Processing:** Celery + Redis (message broker)
- **Engine:** Rust (serde, serde_json)
- **Reporting:** R (Shiny, sf, leaflet, ggplot2, jsonlite)
- **Frontend:** Vanilla HTML/CSS/JS, Leaflet.js, Chart.js
- **Database:** PostgreSQL + PostGIS
- **Kartografi:** matplotlib (300 DPI, A3 landscape)
- **Computer Vision:** OpenCV (tree crown segmentation)
- **ML:** scikit-learn (Random Forest biomass estimation)
- **DevOps:** Docker multi-stage build, GitHub Actions CI/CD
- **Data:** Sentinel-2 (optik), Sentinel-1 (SAR), ALOS PALSAR (L-Band), GeoJSON admin boundaries

---

## 📜 Lisensi

MIT License — Lihat [LICENSE](LICENSE) untuk detail.
