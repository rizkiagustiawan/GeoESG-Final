#!/bin/bash

echo "🚀 Inisialisasi Arsitektur GeoESG Polyglot (Arch Linux Ready)..."

# 1. Buat Struktur Folder
mkdir -p python-gee-ai
mkdir -p rust-esg-engine/src
mkdir -p r-reporting
mkdir -p shared_data

# 2. Tulis File Cargo.toml (ROOT WORKSPACE)
cat << 'EOF' > Cargo.toml
[workspace]
members = ["rust-esg-engine"]
EOF

# 3. Tulis File Cargo.toml (RUST APP)
cat << 'EOF' > rust-esg-engine/Cargo.toml
[package]
name = "rust-esg-engine"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
EOF

# 4. Tulis File main.rs (RUST LOGIC)
cat << 'EOF' > rust-esg-engine/src/main.rs
use serde::{Deserialize, Serialize};
use std::fs;

#[derive(Deserialize, Debug)]
struct SiteData {
    site_id: String,
    satellite_ndvi_90: f64,
    ground_truth_10: f64,
    error_margin: f64,
}

#[derive(Serialize, Debug)]
struct ESGReport {
    site_id: String,
    gri_304_biodiversity_score: String,
    data_integrity_flag: String,
    final_trust_score: f64,
}

fn calculate_trust_score(sat: f64, gt: f64, error: f64) -> f64 {
    let base_score = (0.9 * sat) + (0.1 * gt);
    let penalty = if error > 0.15 { 0.2 } else { 0.0 };
    base_score - penalty
}

fn main() {
    let data_str = fs::read_to_string("../shared_data/raw_data.json").expect("Gagal membaca JSON");
    let sites: Vec<SiteData> = serde_json::from_str(&data_str).expect("Gagal parsing JSON");
    let mut reports: Vec<ESGReport> = Vec::new();

    for site in sites {
        let trust_score = calculate_trust_score(site.satellite_ndvi_90, site.ground_truth_10, site.error_margin);
        let integrity = if site.error_margin <= 0.15 {
            "AUDIT_PASS: High Consistency".to_string()
        } else {
            "AUDIT_FAIL: High Deviation (Greenwashing Risk)".to_string()
        };

        reports.push(ESGReport {
            site_id: site.site_id,
            gri_304_biodiversity_score: format!("{:.2} (Adjusted NDVI)", trust_score),
            data_integrity_flag: integrity,
            final_trust_score: trust_score,
        });
    }

    let out_str = serde_json::to_string_pretty(&reports).unwrap();
    fs::write("../shared_data/esg_metrics.json", out_str).expect("Gagal menulis output ESG");
    println!("✅ Tahap 2: Rust ESG Engine selesai memproses metrik kepatuhan!");
}
EOF

# 5. Tulis File extractor.py (PYTHON LOGIC)
cat << 'EOF' > python-gee-ai/extractor.py
import json
import random

def get_satellite_ndvi(lat, lon):
    base_ndvi = 0.65 
    noise = random.uniform(-0.05, 0.05)
    return round(base_ndvi + noise, 3)

def get_ground_truth(lat, lon):
    return 0.68

def build_dataset():
    locations = [{"id": "Site_A_NTB", "lat": -8.5, "lon": 116.5}]
    raw_data = []
    for loc in locations:
        sat_val = get_satellite_ndvi(loc["lat"], loc["lon"])
        gt_val = get_ground_truth(loc["lat"], loc["lon"])
        error_margin = abs(sat_val - gt_val)
        raw_data.append({
            "site_id": loc["id"],
            "satellite_ndvi_90": sat_val,
            "ground_truth_10": gt_val,
            "error_margin": round(error_margin, 3)
        })
        
    with open('../shared_data/raw_data.json', 'w') as f:
        json.dump(raw_data, f, indent=4)
    print("✅ Tahap 1: Data fusi satelit & lapangan berhasil di-generate!")

if __name__ == "__main__":
    build_dataset()
EOF

# 6. Tulis File dashboard.R (R LOGIC)
cat << 'EOF' > r-reporting/dashboard.R
library(jsonlite)

esg_data <- fromJSON("../shared_data/esg_metrics.json")
file_path <- "ESG_Report_Output.md"
sink(file_path)

cat("# GeoESG: Laporan Kepatuhan Otomatis 🌍\n\n")
cat("> **Metodologi:** 90% AI Satelit (GEE) + 10% Validasi In-Situ\n")
cat("> **Standar:** Sesuai dengan parameter GRI 304 (Keanekaragaman Hayati)\n\n")
cat("## Hasil Audit Integritas Data\n\n")

for (i in 1:nrow(esg_data)) {
  cat(sprintf("### Lokasi Observasi: %s\n", esg_data$site_id[i]))
  cat(sprintf("- **Skor Bio-Index (GRI 304):** %s\n", esg_data$gri_304_biodiversity_score[i]))
  cat(sprintf("- **Status Integritas:** `%s`\n", esg_data$data_integrity_flag[i]))
  cat("---\n")
}

sink()
cat("✅ Tahap 3: Laporan R Markdown 'ESG_Report_Output.md' berhasil dicetak!\n")
EOF

# 7. Tulis File run_pipeline.sh (MASTER SCRIPT)
cat << 'EOF' > run_pipeline.sh
#!/bin/bash
echo "🚀 Memulai GeoESG Pipeline: 90% Satelit / 10% Lapangan..."
echo "----------------------------------------"
cd python-gee-ai && python3 extractor.py
cd ..
echo "----------------------------------------"
cd rust-esg-engine && cargo run --release -q
cd ..
echo "----------------------------------------"
cd r-reporting && Rscript dashboard.R
cd ..
echo "----------------------------------------"
echo "🎉 Eksekusi selesai! Silakan periksa r-reporting/ESG_Report_Output.md"
EOF

# 8. Eksekusi Otomatis!
chmod +x run_pipeline.sh
echo "✅ Struktur berhasil di-deploy. Menjalankan pipeline sekarang..."
./run_pipeline.sh