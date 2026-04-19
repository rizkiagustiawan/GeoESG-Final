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
import psycopg2
from psycopg2.extras import RealDictCursor
import subprocess
import datetime
import tempfile
import shutil
import asyncio
import time
import uuid
import threading
from functools import partial
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, Depends, status, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

# PDF Generator
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "python-gee-ai"))
try:
    from pdf_generator import generate_pdf_report
except ImportError:
    generate_pdf_report = None

# ─── Config ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DATA = os.path.join(BASE_DIR, "shared_data")
GEOJSON_PATH = os.path.join(SHARED_DATA, "batas_ntb.geojson")

# Konfigurasi PostgreSQL / PostGIS
# Fallback ke localhost jika dijalankan di luar docker
DB_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://geoesg_user:geoesg_password@localhost:5432/geoesg_spatial"
)

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
    """Inisialisasi tabel audit_logs di PostgreSQL + PostGIS."""
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Aktifkan ekstensi spasial
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        
        # Buat tabel enterprise dengan kolom GEOMETRY
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                site_id TEXT,
                sat_ndvi REAL,
                ground_biomass REAL,
                trust_score REAL,
                biomass REAL,
                carbon REAL,
                status TEXT,
                geom GEOMETRY(Polygon, 4326),  -- [BARU] Kolom Spasial PostGIS
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.close()
        conn.close()
        print("✅ PostgreSQL + PostGIS berhasil diinisialisasi.")
    except Exception as e:
        print(f"⚠️ Gagal koneksi ke PostgreSQL: {e}. Pastikan docker-compose up db sudah jalan.")


def get_db():
    """Buat koneksi database baru (per-request)."""
    return psycopg2.connect(DB_URL)


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
API_KEY_SECRET = os.getenv("GEOESG_API_KEY", "geoesg-secret-key-2026")

def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verifikasi API Key untuk endpoint sensitif/batch."""
    if api_key != API_KEY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )

RATE_LIMIT_DB = {}

def rate_limit(request: Request):
    """Rate limiter sederhana berbasis IP (Maks 5 request / menit)."""
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    # Cleanup: hapus entries lama (>60s) untuk mencegah memory leak
    stale_ips = [ip for ip, times in RATE_LIMIT_DB.items()
                 if all(current_time - t > 60 for t in times)]
    for ip in stale_ips:
        del RATE_LIMIT_DB[ip]
    
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
_rust_lock = threading.Lock()  # Serialisasi akses ke Rust binary (shared I/O)

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
        venv_python = os.path.join(BASE_DIR, "venv", "bin", "python3")
        python_exe = venv_python if os.path.exists(venv_python) else "python3"
        result_py = subprocess.run(
            [python_exe, extractor_path],
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

        # Rust binary membaca ../shared_data/raw_data.json secara hardcoded.
        # Kita gunakan threading Lock untuk memastikan hanya satu request
        # yang menulis + menjalankan Rust pada satu waktu.
        standard_raw = os.path.join(SHARED_DATA, "raw_data.json")
        standard_esg = os.path.join(SHARED_DATA, "esg_metrics.json")

        with _rust_lock:
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

            # Copy esg_metrics back to isolated work dir
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
        else "AUDIT GAGAL — Akurasi Tidak Memenuhi Standar IPCC"
    )

    return f"""# GeoESG Audit Report: {site_id}

> **Waktu Audit:** {datetime.datetime.now().strftime('%d %B %Y %H:%M:%S')}
> **Metodologi:** Random Forest Sensor Fusion (Optik + SAR) — Mitchard et al. (2012)
> **Standar:** IPCC 2006 Vol 4 Ch 2 & SNI 7724:2011 (Carbon Accounting)

---

## {status_emoji} Status: {status_text}

### 📊 Metrik Satelit (Fusi Sensor)
| Parameter | Nilai | Referensi |
|-----------|-------|-----------|
| **NDVI Optik (Sentinel-2)** | {site_raw.get('satellite_ndvi_90', 'N/A')} | Rouse et al. (1974) |
| **Radar VH (Sentinel-1)** | {site_raw.get('radar_vh_db', 'N/A')} dB | ESA Copernicus |
| **Radar VV (Sentinel-1)** | {site_raw.get('radar_vv_db', 'N/A')} dB | ESA Copernicus |
| **Metode Estimasi** | Random Forest (Optik + SAR Fusion) | Saatchi et al. (2011) |

### 🌱 Estimasi Karbon & Biomassa
| Parameter | Nilai | Referensi |
|-----------|-------|-----------|
| **Above-Ground Biomass (AGB)** | {site_raw.get('estimated_biomass', 'N/A')} Mg/ha | RF Model |
| **Stok Karbon** | {site_raw.get('estimated_carbon', 'N/A')} Mg C/ha | AGB × 0.46 |
| **Faktor Konversi Karbon** | 0.46 | SNI 7724:2011 |

### 🔬 Validasi Integritas Data (Standar IPCC)
| Parameter | Nilai | Referensi |
|-----------|-------|-----------|
| **Ground Truth Biomass** | {ground_truth_biomass} Mg/ha | Field inventory |
| **Relative Error (RE)** | {site_esg.get('relative_error_pct', 'N/A')}% | IPCC 2006 Vol 4 |
| **Bias** | {site_esg.get('bias_mg_ha', 'N/A')} Mg/ha | Willmott (1982) |
| **Akurasi** | {site_esg.get('accuracy_pct', 'N/A')}% | 1 - RE |
| **IPCC Tier** | {site_esg.get('ipcc_tier', 'N/A')} | IPCC 2006 |
| **Status** | `{site_esg.get('data_integrity_flag', 'N/A')}` | |

> ℹ️ **Catatan Metodologi:**
> Estimasi biomassa menggunakan Random Forest dengan fusi 5 fitur sensor
> (Mitchard et al., 2012; Saatchi et al., 2011). Validasi menggunakan
> Relative Error terhadap data lapangan dengan threshold IPCC 2006:
> Tier 3 (≤10%), Tier 2 (≤20%), Tier 1 (≤30%).

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
        "relative_error_pct": site_esg.get("relative_error_pct"),
        "bias_mg_ha": site_esg.get("bias_mg_ha"),
        "accuracy_pct": site_esg.get("accuracy_pct"),
        "ipcc_tier": site_esg.get("ipcc_tier"),
        "estimated_biomass": site_raw.get("estimated_biomass"),
        "estimated_carbon": site_raw.get("estimated_carbon"),
        "data_integrity_flag": site_esg.get("data_integrity_flag"),
        "historical_ndvi_series": site_raw.get("historical_ndvi_series"),
        "historical_trend_slope": site_raw.get("historical_trend_slope"),
        "ecological_status": site_raw.get("ecological_status"),
    }



def log_audit(conn, site_id, site_raw, site_esg, ground_truth_biomass):
    """Insert audit log ke PostgreSQL."""
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO audit_logs
           (site_id, sat_ndvi, ground_biomass, trust_score, biomass, carbon, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
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
    cursor.close()


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

        # Log ke PostgreSQL
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


# 4. Generate PDF Report (Export via Backend)
@app.post("/api/export-pdf")
async def export_pdf(payload: dict = Body(...)):
    """Menghasilkan PDF laporan audit menggunakan reportlab."""
    if not generate_pdf_report:
        raise HTTPException(status_code=500, detail="PDF Generator (reportlab) belum terpasang.")
    
    site_id = payload.get("site_id", "Unknown")
    filename = f"Laporan_Audit_ESG_{site_id.replace(' ', '_')}.pdf"
    
    # Simpan di shared_data
    output_path = os.path.join(BASE_DIR, "shared_data", filename)
    
    try:
        # Panggil generator sinkron
        generate_pdf_report(payload, output_path)
        return FileResponse(output_path, filename=filename, media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal generate PDF: {str(e)}")


# 4. Audit History
@app.get("/api/audit-history")
async def get_audit_history():
    """Mengembalikan 50 log audit terakhir dari PostgreSQL."""
    try:
        conn = get_db()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT id, site_id, sat_ndvi, ground_biomass, trust_score, biomass, carbon, status, timestamp FROM audit_logs ORDER BY timestamp DESC LIMIT 50"
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Konversi datetime menjadi string (ISO format) untuk JSON
        for row in rows:
            if isinstance(row["timestamp"], datetime.datetime):
                row["timestamp"] = row["timestamp"].isoformat()

        return JSONResponse(content=rows)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal membaca history: {str(e)}",
        )


# 5. Cek Status Task Asinkron (Engineering Max)
@app.get("/api/task-status/{task_id}")
async def get_task_status(task_id: str):
    """Mengecek status proses background Celery."""
    try:
        from celery.result import AsyncResult
        from worker import celery_app
        task_result = AsyncResult(task_id, app=celery_app)
        
        response = {
            "task_id": task_id,
            "status": task_result.status,
        }
        
        if task_result.status == 'SUCCESS':
            response["result"] = task_result.result
        elif task_result.status == 'PROGRESS':
            response["meta"] = task_result.info
        elif task_result.status == 'FAILURE':
            response["error"] = str(task_result.result)
            
        return JSONResponse(content=response)
    except ImportError:
        raise HTTPException(status_code=503, detail="Celery/Redis tidak tersedia. Jalankan docker-compose up.")


# 6. Batch Multi-Site Audit (ASYNCHRONOUS MAX)
@app.post("/generate-esg-batch", dependencies=[Depends(verify_api_key)])
async def generate_esg_batch(req: BatchAuditRequest):
    """
    Menjalankan audit ESG untuk ribuan wilayah sekaligus secara ASINKRON.
    Server akan langsung merespons dengan Task ID (0.1 detik).
    """
    try:
        from worker import run_pipeline_task

        user_inputs = [
            {"site_id": s.site_id, "ground_truth_10": s.ground_truth_biomass}
            for s in req.sites
        ]

        # 🚀 Kirim ke Message Broker (Redis) -> Celery Worker
        task = run_pipeline_task.delay(user_inputs)

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": "accepted",
                "message": f"Permintaan audit {len(user_inputs)} titik diterima. Memproses di background.",
                "task_id": task.id,
                "check_status_url": f"/api/task-status/{task.id}"
            }
        )

    except ImportError:
        raise HTTPException(status_code=503, detail="Celery/Redis tidak tersedia. Jalankan docker-compose up.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch error: {str(e)}")


# Matplotlib lock — matplotlib is NOT thread-safe; serialize map generation
_map_lock = threading.Lock()


def _generate_map_sync(site_id: str, maps_dir: str) -> str:
    """Thread-safe map generation wrapper. Holds lock during matplotlib rendering."""
    import sys
    sys.path.insert(0, os.path.join(BASE_DIR, "python-gee-ai"))
    from map_printer import generate_site_map, load_geojson, load_raw_data

    geojson_data = load_geojson()
    raw_data_list = load_raw_data()

    if not geojson_data:
        raise FileNotFoundError("GeoJSON tidak ditemukan")

    with _map_lock:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        try:
            path = generate_site_map(site_id, geojson_data, raw_data_list, maps_dir)
        finally:
            plt.close('all')  # Bersihkan semua figure untuk mencegah memory leak & I/O error

    return path


# 7. Generate Map Print (Kartografi) — Simpan ke galeri
@app.post("/api/generate-map/{site_id}")
async def generate_map(site_id: str):
    """Generate peta cetak kartografi profesional untuk satu lokasi dan simpan ke galeri."""
    try:
        maps_dir = os.path.join(SHARED_DATA, "maps")
        os.makedirs(maps_dir, exist_ok=True)

        loop = asyncio.get_event_loop()
        path = await loop.run_in_executor(
            None, partial(_generate_map_sync, site_id, maps_dir)
        )
        if not path:
            raise HTTPException(status_code=404, detail=f"Site '{site_id}' tidak ditemukan")

        return JSONResponse(content={
            "status": "success",
            "site_id": site_id,
            "filename": os.path.basename(path),
            "message": f"Peta {site_id} berhasil dicetak dan disimpan ke galeri."
        })
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Map generation error: {str(e)}")


# 8. (Dihapus) Generate All Maps — fitur batch generate dihapus


# 9. List Available Maps
@app.get("/api/maps")
async def list_maps():
    """List semua peta yang sudah digenerate."""
    maps_dir = os.path.join(SHARED_DATA, "maps")
    if not os.path.exists(maps_dir):
        return JSONResponse(content={"maps": [], "count": 0})

    files = [f for f in os.listdir(maps_dir) if f.endswith(".png")]
    return JSONResponse(content={"maps": sorted(files), "count": len(files)})


# 10. Download Specific Map
@app.get("/api/maps/{filename:path}")
async def get_map(filename: str):
    """Download peta spesifik berdasarkan nama file."""
    # Validasi path traversal: hanya izinkan nama file PNG sederhana
    if '/' in filename or '\\' in filename or '..' in filename or not filename.endswith('.png'):
        raise HTTPException(status_code=400, detail="Nama file tidak valid")
    filepath = os.path.join(SHARED_DATA, "maps", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Peta tidak ditemukan")
    return FileResponse(
        filepath, media_type="image/png", filename=filename,
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )


# 11. Delete All Maps (Clear Gallery)
@app.delete("/api/maps")
async def delete_all_maps():
    """Hapus semua peta dari galeri."""
    maps_dir = os.path.join(SHARED_DATA, "maps")
    if not os.path.exists(maps_dir):
        return JSONResponse(content={"status": "success", "deleted": 0})

    files = [f for f in os.listdir(maps_dir) if f.endswith(".png")]
    deleted = 0
    for f in files:
        try:
            os.remove(os.path.join(maps_dir, f))
            deleted += 1
        except OSError:
            pass
    return JSONResponse(content={"status": "success", "deleted": deleted})


# 11. Health Check
@app.get("/api/health")
async def health_check():
    """Cek status kesehatan sistem."""
    db_ok = False
    try:
        conn = get_db()
        conn.close()
        db_ok = True
    except Exception:
        pass
        
    checks = {
        "api": True,
        "database": db_ok,
        "geojson": os.path.exists(GEOJSON_PATH),
        "raw_data": os.path.exists(os.path.join(SHARED_DATA, "raw_data.json")),
        "esg_metrics": os.path.exists(os.path.join(SHARED_DATA, "esg_metrics.json")),
        "rust_binary": os.path.exists(
            os.path.join(BASE_DIR, "rust-esg-engine", "target", "release", "rust-esg-engine")
        ) or os.path.exists(os.path.join(BASE_DIR, "rust-esg-engine", "Cargo.toml")),
        "maps_dir": os.path.exists(os.path.join(SHARED_DATA, "maps")),
    }
    return JSONResponse(
        content={
            "status": "healthy" if all(checks.values()) else "degraded",
            "checks": checks,
            "timestamp": datetime.datetime.now().isoformat(),
        }
    )

