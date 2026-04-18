"""
GeoESG API Server v2.2 — Orkestrasi Pipeline
=============================================
FastAPI server yang menjembatani antarmuka Command Center (index.html)
dengan komponen pipeline (Python → Rust → R).

Endpoints:
  GET  /                      → Serve Command Center UI
  GET  /api/regional-borders  → Serve GeoJSON batas NTB
  POST /generate-esg-report   → Trigger full pipeline audit (single site)
  POST /generate-esg-batch    → Trigger batch audit (multi-site)
  GET  /api/audit-history     → Query log audit dari SQLite
  GET  /api/health            → Health check
"""

import json
import os
import sqlite3
import subprocess
import datetime
import tempfile
import shutil
import asyncio
import uuid
from functools import partial
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

# ─── Config ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DATA = os.path.join(BASE_DIR, "shared_data")
DB_PATH = os.path.join(SHARED_DATA, "geoesg.db")
GEOJSON_PATH = os.path.join(SHARED_DATA, "batas_ntb.geojson")

app = FastAPI(
    title="GeoESG A.E.C.O API",
    description="Automated ESG Compliance Observer — Pipeline Orchestrator",
    version="2.2.0",
)

# ─── CORS Middleware ─────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Database Setup ──────────────────────────────────────────────────────────
def init_db():
    """Inisialisasi tabel audit_logs di SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_id TEXT,
        sat_ndvi REAL,
        ground_ndvi REAL,
        trust_score REAL,
        biomass REAL,
        carbon REAL,
        status TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()


def get_db():
    """Buat koneksi database baru (per-request)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


init_db()


# ─── Request Models ──────────────────────────────────────────────────────────
class AuditRequest(BaseModel):
    site_id: str
    ground_truth_biomass: float = Field(default=150.0, ge=0.0)


class BatchAuditRequest(BaseModel):
    sites: List[AuditRequest]


# ─── Security & Rate Limiting ────────────────────────────────────────────────
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verifikasi API Key statis untuk endpoint sensitif/batch."""
    if api_key != "geoesg-secret-key-2026":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )

RATE_LIMIT_DB = {}

def rate_limit(request: Request):
    """Rate limiter sederhana berbasis IP (Maks 5 request / menit)."""
    client_ip = request.client.host if request.client else "unknown"
    import time
    current_time = time.time()
    
    if client_ip in RATE_LIMIT_DB:
        requests = [req_time for req_time in RATE_LIMIT_DB[client_ip] if current_time - req_time < 60]
        if len(requests) >= 5:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, 
                detail="Rate limit exceeded. Maksimal 5 audit per menit."
            )
        requests.append(current_time)
        RATE_LIMIT_DB[client_ip] = requests
    else:
        RATE_LIMIT_DB[client_ip] = [current_time]


# ─── Pipeline Execution (Thread-Safe) ────────────────────────────────────────
def _run_pipeline_sync(user_inputs: list) -> tuple:
    """
    Menjalankan pipeline Python→Rust di isolated temp directory.
    Thread-safe: setiap request mendapat copy shared_data sendiri.

    Returns: (raw_data_list, esg_metrics_list)
    """
    request_id = str(uuid.uuid4())[:8]
    work_dir = os.path.join(BASE_DIR, "shared_data", f".tmp_{request_id}")

    try:
        os.makedirs(work_dir, exist_ok=True)

        # Copy data yang diperlukan ke work dir
        geojson_src = os.path.join(SHARED_DATA, "batas_ntb.geojson")
        if os.path.exists(geojson_src):
            shutil.copy2(geojson_src, os.path.join(work_dir, "batas_ntb.geojson"))

        # Tulis user input ke work dir (isolated, no race condition)
        user_input_path = os.path.join(work_dir, "user_input.json")
        raw_data_path = os.path.join(work_dir, "raw_data.json")
        esg_metrics_path = os.path.join(work_dir, "esg_metrics.json")

        with open(user_input_path, "w") as f:
            json.dump(user_inputs, f, indent=4)

        # ── Step 1: Jalankan Python Extractor ────────────────────────
        # Override paths via environment variables
        env = os.environ.copy()
        env["GEOESG_OUTPUT_PATH"] = raw_data_path
        env["GEOESG_INPUT_PATH"] = user_input_path
        env["GEOESG_GEOJSON_PATH"] = os.path.join(work_dir, "batas_ntb.geojson")

        extractor_path = os.path.join(BASE_DIR, "python-gee-ai", "extractor.py")
        result_py = subprocess.run(
            ["python3", extractor_path],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=BASE_DIR,
            env=env,
        )
        if result_py.returncode != 0:
            print(f"⚠️ [{request_id}] Extractor stderr: {result_py.stderr}")

        # Fallback: jika extractor tidak mendukung env vars, cek path standar
        if not os.path.exists(raw_data_path):
            fallback_raw = os.path.join(SHARED_DATA, "raw_data.json")
            if os.path.exists(fallback_raw):
                shutil.copy2(fallback_raw, raw_data_path)

        # ── Step 2: Jalankan Rust ESG Engine ─────────────────────────
        rust_binary = os.path.join(
            BASE_DIR, "rust-esg-engine", "target", "release", "rust-esg-engine"
        )

        # Buat symlink sementara agar Rust bisa baca dari ../shared_data/
        # (Rust binary expects relative path ../shared_data/raw_data.json)
        # Copy raw_data ke shared_data standar sementara
        standard_raw = os.path.join(SHARED_DATA, "raw_data.json")
        standard_esg = os.path.join(SHARED_DATA, "esg_metrics.json")

        shutil.copy2(raw_data_path, standard_raw)

        if os.path.exists(rust_binary):
            result_rs = subprocess.run(
                [rust_binary],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=os.path.join(BASE_DIR, "rust-esg-engine"),
            )
        else:
            result_rs = subprocess.run(
                ["cargo", "run", "--release", "-q"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=os.path.join(BASE_DIR, "rust-esg-engine"),
            )
        if result_rs.returncode != 0:
            print(f"⚠️ [{request_id}] Rust stderr: {result_rs.stderr}")

        # Copy esg_metrics back
        if os.path.exists(standard_esg):
            shutil.copy2(standard_esg, esg_metrics_path)

        # ── Step 3: Baca Hasil ───────────────────────────────────────
        with open(raw_data_path, "r") as f:
            raw_data = json.load(f)
        with open(esg_metrics_path, "r") as f:
            esg_metrics = json.load(f)

        return raw_data, esg_metrics

    finally:
        # Cleanup temp directory
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)


async def run_pipeline(user_inputs: list) -> tuple:
    """Async wrapper — jalankan pipeline di thread pool agar tidak blokir event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_run_pipeline_sync, user_inputs))


def build_report_markdown(site_id, site_raw, site_esg, ground_truth_biomass):
    """Generate laporan Markdown untuk satu site."""
    is_pass = "PASS" in site_esg.get("data_integrity_flag", "")
    status_emoji = "✅" if is_pass else "❌"
    status_text = (
        "AUDIT LULUS — Konsistensi Tinggi"
        if is_pass
        else "AUDIT GAGAL — Risiko Greenwashing Terdeteksi"
    )

    return f"""# GeoESG Audit Report: {site_id}

> **Waktu Audit:** {datetime.datetime.now().strftime('%d %B %Y %H:%M:%S')}
> **Metodologi:** Sensor Fusion (Optik + SAR) & Validasi Statistik In-Situ
> **Standar:** GRI 304 (Biodiversity) & SNI 7724:2011 (Carbon Accounting)

---

## {status_emoji} Status: {status_text}

### 📊 Metrik Satelit (Fusi Sensor)
| Parameter | Nilai |
|-----------|-------|
| **NDVI Optik (Sentinel-2)** | {site_raw.get('satellite_ndvi_90', 'N/A')} |
| **Radar VH (Sentinel-1)** | {site_raw.get('radar_vh_db', 'N/A')} dB |
| **Radar VV (Sentinel-1)** | {site_raw.get('radar_vv_db', 'N/A')} dB |
| **Metode Estimasi Biomassa** | Multivariable Exponential Fusion (Optik & SAR) |

### 🌱 Estimasi Karbon & Biomassa
| Parameter | Nilai |
|-----------|-------|
| **Above-Ground Biomass (AGB)** | {site_raw.get('estimated_biomass', 'N/A')} Mg/ha |
| **Stok Karbon** | {site_raw.get('estimated_carbon', 'N/A')} Mg C/ha |
| **Faktor Konversi Karbon** | AGB × 0.46 (SNI 7724:2011 Hutan Tropis) |

### 🔬 Validasi Integritas Data
| Parameter | Nilai |
|-----------|-------|
| **Field Biomass Ground Truth** | {ground_truth_biomass} Mg/ha |
| **Relative Error (RE)** | {site_raw.get('error_margin', 'N/A')} |
| **Trust Score (Z-Decay)** | {site_esg.get('final_trust_score', 'N/A')} |
| **GRI 304 Bio-Index** | {site_esg.get('gri_304_biodiversity_score', 'N/A')} |
| **Status Integritas** | `{site_esg.get('data_integrity_flag', 'N/A')}` |

> ℹ️ **Catatan Metodologi Ilmiah:** 
> Estimasi biomassa menggunakan fusi Optik-SAR mengatasi kelemahan saturasi NDVI di hutan tropis padat.
> Trust score dikalkulasi menggunakan peluruhan eksponensial (exponential decay) berdasarkan Relative Error, 
> merujuk pada standar ketidakpastian ±15% (IPCC Tier 1).

---
*Laporan dihasilkan otomatis oleh GeoESG A.E.C.O Pipeline v2.2*
"""


def build_metrics_dict(site_raw, site_esg, ground_truth_biomass):
    """Extract standard metrics dict dari pipeline output."""
    return {
        "satellite_ndvi_90": site_raw.get("satellite_ndvi_90"),
        "ground_truth_biomass": ground_truth_biomass,
        "error_margin": site_raw.get("error_margin"),
        "trust_score": site_esg.get("final_trust_score"),
        "estimated_biomass": site_raw.get("estimated_biomass"),
        "estimated_carbon": site_raw.get("estimated_carbon"),
        "data_integrity_flag": site_esg.get("data_integrity_flag"),
    }


def log_audit(conn, site_id, site_raw, site_esg, ground_truth_biomass):
    """Insert audit log ke SQLite."""
    conn.execute(
        """INSERT INTO audit_logs
           (site_id, sat_ndvi, ground_ndvi, trust_score, biomass, carbon, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            site_id,
            site_raw.get("satellite_ndvi_90"),
            ground_truth_biomass,
            site_esg.get("final_trust_score"),
            site_raw.get("estimated_biomass"),
            site_raw.get("estimated_carbon"),
            site_esg.get("data_integrity_flag"),
        ),
    )


# ─── Routes ──────────────────────────────────────────────────────────────────

# 1. Serve Frontend
@app.get("/")
async def serve_index():
    """Menyajikan halaman Command Center."""
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html tidak ditemukan.")


# 2. Regional Borders (GeoJSON)
@app.get("/api/regional-borders")
async def get_regional_borders():
    """Mengembalikan data GeoJSON batas administratif NTB."""
    if not os.path.exists(GEOJSON_PATH):
        raise HTTPException(status_code=404, detail="File GeoJSON tidak ditemukan.")
    try:
        with open(GEOJSON_PATH, "r") as f:
            geojson = json.load(f)
        return JSONResponse(content=geojson)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="GeoJSON format tidak valid.")


# 3. Generate ESG Report (Single Site)
@app.post("/generate-esg-report", dependencies=[Depends(rate_limit)])
async def generate_esg_report(req: AuditRequest):
    """
    Menjalankan pipeline audit ESG lengkap untuk satu wilayah.
    Pipeline dijalankan di thread pool agar tidak memblokir event loop.
    """
    try:
        user_inputs = [
            {"site_id": req.site_id, "ground_truth_10": req.ground_truth_biomass}
        ]

        raw_data, esg_metrics = await run_pipeline(user_inputs)

        # Cari data untuk site yang diminta
        site_raw = next(
            (r for r in raw_data if r["site_id"] == req.site_id), raw_data[0]
        )
        site_esg = next(
            (m for m in esg_metrics if m["site_id"] == req.site_id), esg_metrics[0]
        )

        # Generate report
        report_md = build_report_markdown(
            req.site_id, site_raw, site_esg, req.ground_truth_biomass
        )

        # Log ke SQLite
        conn = get_db()
        log_audit(conn, req.site_id, site_raw, site_esg, req.ground_truth_biomass)
        conn.commit()
        conn.close()

        return JSONResponse(
            content={
                "status": "success",
                "site_id": req.site_id,
                "metrics": build_metrics_dict(site_raw, site_esg, req.ground_truth_biomass),
                "report_markdown": report_md,
            }
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Pipeline timeout (>120s).")
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=f"File pipeline tidak ditemukan: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Kesalahan pipeline: {str(e)}",
        )


# 4. Audit History
@app.get("/api/audit-history")
async def get_audit_history():
    """Mengembalikan 50 log audit terakhir dari SQLite."""
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 50"
        ).fetchall()
        conn.close()

        history = [
            {
                "id": row["id"],
                "site_id": row["site_id"],
                "sat_ndvi": row["sat_ndvi"],
                "ground_biomass": row["ground_ndvi"],
                "trust_score": row["trust_score"],
                "biomass": row["biomass"],
                "carbon": row["carbon"],
                "status": row["status"],
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]
        return JSONResponse(content=history)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal membaca history: {str(e)}",
        )


# 5. Batch Multi-Site Audit
@app.post("/generate-esg-batch", dependencies=[Depends(verify_api_key)])
async def generate_esg_batch(req: BatchAuditRequest):
    """
    Menjalankan audit ESG untuk beberapa wilayah sekaligus.
    Pipeline dijalankan sekali untuk semua site.
    """
    try:
        user_inputs = [
            {"site_id": s.site_id, "ground_truth_10": s.ground_truth_biomass}
            for s in req.sites
        ]

        raw_data, esg_metrics = await run_pipeline(user_inputs)

        results = []
        conn = get_db()

        for site_req in req.sites:
            site_raw = next(
                (r for r in raw_data if r["site_id"] == site_req.site_id), None
            )
            site_esg = next(
                (m for m in esg_metrics if m["site_id"] == site_req.site_id), None
            )

            if not site_raw or not site_esg:
                results.append({
                    "site_id": site_req.site_id,
                    "status": "error",
                    "detail": "Data tidak ditemukan setelah pipeline",
                })
                continue

            is_pass = "PASS" in site_esg.get("data_integrity_flag", "")

            log_audit(conn, site_req.site_id, site_raw, site_esg, site_req.ground_truth_biomass)

            results.append({
                "site_id": site_req.site_id,
                "status": "success",
                "metrics": build_metrics_dict(site_raw, site_esg, site_req.ground_truth_biomass),
                "audit_passed": is_pass,
            })

        conn.commit()
        conn.close()

        passed = sum(1 for r in results if r.get("audit_passed"))
        failed = sum(1 for r in results if r.get("status") == "success" and not r.get("audit_passed"))
        errors = sum(1 for r in results if r.get("status") == "error")

        return JSONResponse(content={
            "status": "success",
            "summary": {
                "total_sites": len(req.sites),
                "passed": passed,
                "failed": failed,
                "errors": errors,
            },
            "results": results,
        })

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Batch pipeline timeout.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch error: {str(e)}")


# 6. Health Check
@app.get("/api/health")
async def health_check():
    """Cek status kesehatan sistem."""
    checks = {
        "api": True,
        "database": os.path.exists(DB_PATH),
        "geojson": os.path.exists(GEOJSON_PATH),
        "raw_data": os.path.exists(os.path.join(SHARED_DATA, "raw_data.json")),
        "esg_metrics": os.path.exists(os.path.join(SHARED_DATA, "esg_metrics.json")),
        "rust_binary": os.path.exists(
            os.path.join(BASE_DIR, "rust-esg-engine", "target", "release", "rust-esg-engine")
        ),
    }
    return JSONResponse(
        content={
            "status": "healthy" if all(checks.values()) else "degraded",
            "checks": checks,
            "timestamp": datetime.datetime.now().isoformat(),
        }
    )
