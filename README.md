# 🌍 GeoESG A.E.C.O — Automated ESG Compliance Observer

> **Pipeline audit kepatuhan lingkungan (ESG) berbasis data satelit** untuk wilayah Nusa Tenggara Barat, mengintegrasikan remote sensing, machine audit, dan pelaporan otomatis.

![Python](https://img.shields.io/badge/Python-GEE%20%7C%20FastAPI-3776AB?logo=python&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-ESG%20Engine-000000?logo=rust&logoColor=white)
![R](https://img.shields.io/badge/R-Shiny%20%7C%20ggplot2-276DC3?logo=r&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Multi--Stage-2496ED?logo=docker&logoColor=white)
![CI](https://github.com/rizkiagustiawan/GeoESG-Final/actions/workflows/main.yml/badge.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## 📋 Overview

GeoESG adalah sistem **polyglot pipeline** (Python → Rust → R) yang melakukan:

1. **Ekstraksi data satelit** dari Google Earth Engine (Sentinel-2 NDVI, Sentinel-1 SAR Radar)
2. **Audit integritas data** — membandingkan estimasi satelit (80%) vs ground truth lapangan (20%) menggunakan *Exponential Decay Trust Score* untuk mendeteksi risiko *greenwashing*
3. **Pelaporan otomatis** sesuai kerangka GRI 304 (Keanekaragaman Hayati) & estimasi stok karbon

### Mengapa 3 Bahasa?

| Bahasa | Peran | Alasan |
|--------|-------|--------|
| **Python** | Ekstraksi data satelit (GEE SDK) | Satu-satunya bahasa dengan SDK resmi Earth Engine |
| **Rust** | Mesin kalkulasi compliance | Performa tinggi, type-safety untuk kalkulasi kritis |
| **R** | Pelaporan statistik & dashboard | Ekosistem terbaik untuk reporting geospasial (sf, ggplot2) |

---

## 🏗️ Arsitektur

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Python (GEE)   │────▶│   Rust Engine    │────▶│   R Reporting   │
│  Sentinel-2/1   │     │  Trust Score +   │     │  Markdown + Shiny│
│  NDVI + Radar   │     │  Greenwashing    │     │  Dashboard      │
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
                     ▼
              ┌─────────────┐
              │  Command    │
              │  Center UI  │
              └─────────────┘
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
pip install fastapi uvicorn earthengine-api pydantic

# 3. GEE Credentials (opsional — ada fallback mode)
# Letakkan service account key di credentials/gee-key.json

# 4. Build Rust engine
cd rust-esg-engine && cargo build --release && cd ..

# 5. Jalankan server
uvicorn api_server:app --host 0.0.0.0 --port 8000

# 6. Buka browser → http://localhost:8000
```

### Docker

```bash
# Gunakan docker-compose untuk deployment satu perintah
docker-compose up -d --build

# Server akan berjalan di background pada port 8000
```

---

## 📡 API Endpoints

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `GET` | `/` | Command Center UI |
| `GET` | `/api/regional-borders` | GeoJSON batas NTB (9 kabupaten) |
| `POST` | `/generate-esg-report` | Audit single site |
| `POST` | `/generate-esg-batch` | Audit multi-site (batch) |
| `GET` | `/api/audit-history` | Log audit SQLite |
| `GET` | `/api/health` | Health check |

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
```

---

## 📂 Struktur Proyek

```
GeoESG-Final/
├── api_server.py              # FastAPI orchestrator (6 endpoints)
├── index.html                 # Command Center UI (Leaflet + Chart.js)
├── test_api.py                # Pytest suite (6 tests)
├── requirements.txt           # Python dependencies
├── python-gee-ai/
│   └── extractor.py           # GEE extraction (Sentinel-2/1, fusi sensor)
├── rust-esg-engine/
│   ├── Cargo.toml
│   └── src/main.rs            # Trust score & greenwashing detection (4 unit tests)
├── r-reporting/
│   ├── app.R                  # Shiny dashboard
│   ├── dashboard.R            # Markdown report generator
│   └── ESG_Report.Rmd         # Output laporan
├── shared_data/
│   ├── batas_ntb.geojson      # Batas administratif NTB
│   ├── raw_data.json          # Output Python → Input Rust
│   ├── esg_metrics.json       # Output Rust → Input R
│   └── geoesg.db              # SQLite audit logs
├── credentials/               # GEE service account key (gitignored)
├── .github/workflows/
│   └── main.yml               # CI/CD: Rust test + Python test
├── Dockerfile                 # Multi-stage build (Rust + Ubuntu + R)
├── docker-compose.yml         # Production + testing profiles
└── run_pipeline.sh            # CLI pipeline runner
```

---

## ⚠️ Catatan Metodologi Ilmiah

> **Estimasi biomassa dan karbon** dalam proyek ini telah menggunakan pendekatan **Multivariable Exponential Fusion Model** (menggabungkan Optik/Sentinel-2 dan SAR/Sentinel-1) untuk memitigasi efek saturasi NDVI di hutan tropis. Faktor konversi karbon disesuaikan dengan **SNI 7724:2011** (0.46) untuk hutan pamah Indonesia. Meski lebih mutakhir, model regresi ini belum divalidasi dengan plot lapangan destruktif khusus NTB. Untuk laporan ESG definitif hukum, model tetap wajib dikalibrasi ulang dengan data *ground-truthing* lokal.

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+, FastAPI, Google Earth Engine API
- **Engine:** Rust (serde, serde_json)
- **Reporting:** R (Shiny, sf, leaflet, ggplot2, jsonlite)
- **Frontend:** Vanilla HTML/CSS/JS, Leaflet.js, Chart.js
- **Database:** SQLite
- **DevOps:** Docker multi-stage build, bash orchestration
- **Data:** Sentinel-2 (optik), Sentinel-1 (SAR), GeoJSON admin boundaries

---

## 📜 Lisensi

MIT License — Lihat [LICENSE](LICENSE) untuk detail.
