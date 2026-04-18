import os
import json
import shutil
import tempfile
import subprocess
import uuid
import threading
from celery import Celery

# Konfigurasi Celery
broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery("geoesg_tasks", broker=broker_url, backend=result_backend)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DATA = os.path.join(BASE_DIR, "shared_data")

# Lock untuk race condition file Rust jika banyak worker berjalan di mesin yang sama
_rust_lock = threading.Lock()

@celery_app.task(bind=True)
def run_pipeline_task(self, user_inputs: list):
    """
    Menjalankan pipeline secara asinkron di belakang layar.
    Fungsi ini diambil dari api_server.py dan dijadikan Celery Task.
    """
    request_id = str(uuid.uuid4())[:8]
    work_dir = tempfile.mkdtemp(prefix=f"geoesg_batch_{request_id}_")

    # Path I/O
    input_path = os.path.join(work_dir, "user_inputs.json")
    raw_data_path = os.path.join(work_dir, "raw_data.json")
    esg_metrics_path = os.path.join(work_dir, "esg_metrics.json")

    standard_raw = os.path.join(SHARED_DATA, "raw_data.json")
    standard_esg = os.path.join(SHARED_DATA, "esg_metrics.json")
    standard_in = os.path.join(SHARED_DATA, "user_inputs.json")

    try:
        # Update progress ke 10%
        self.update_state(state='PROGRESS', meta={'status': 'Menyiapkan Input...'})
        
        with open(input_path, "w") as f:
            json.dump(user_inputs, f)

        with _rust_lock:
            # ── Step 1: Python GEE Extractor ─────────────────────────
            self.update_state(state='PROGRESS', meta={'status': 'Ekstraksi GEE (Satelit)...'})
            shutil.copy2(input_path, standard_in)
            
            # Gunakan python3 yang ada di venv atau environment
            python_exec = "python3"
            if os.path.exists(os.path.join(BASE_DIR, "venv", "bin", "python3")):
                python_exec = os.path.join(BASE_DIR, "venv", "bin", "python3")

            result_py = subprocess.run(
                [python_exec, "extractor.py"],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=os.path.join(BASE_DIR, "python-gee-ai"),
            )

            if result_py.returncode != 0:
                raise RuntimeError(f"Python GEE Error: {result_py.stderr}")

            if os.path.exists(standard_raw):
                shutil.copy2(standard_raw, raw_data_path)
            else:
                raise FileNotFoundError("raw_data.json gagal dibuat oleh extractor.")

            # ── Step 2: Rust ESG Engine ──────────────────────────────
            self.update_state(state='PROGRESS', meta={'status': 'Analisis Integritas (Rust Engine)...'})
            
            cargo_exec = "cargo"
            if os.path.exists(os.path.join(BASE_DIR, "rust-esg-engine", "target", "release", "rust-esg-engine")):
                cargo_exec = os.path.join(BASE_DIR, "rust-esg-engine", "target", "release", "rust-esg-engine")
                result_rs = subprocess.run(
                    [cargo_exec],
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
                raise RuntimeError(f"Rust Engine Error: {result_rs.stderr}")

            if os.path.exists(standard_esg):
                shutil.copy2(standard_esg, esg_metrics_path)
            else:
                raise FileNotFoundError("esg_metrics.json gagal dibuat oleh Rust.")

        # ── Step 3: Baca Hasil ───────────────────────────────────────
        self.update_state(state='PROGRESS', meta={'status': 'Membaca Hasil Akhir...'})
        with open(raw_data_path, "r") as f:
            raw_data = json.load(f)
        with open(esg_metrics_path, "r") as f:
            esg_metrics = json.load(f)

        return {"raw_data": raw_data, "esg_metrics": esg_metrics}

    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)
