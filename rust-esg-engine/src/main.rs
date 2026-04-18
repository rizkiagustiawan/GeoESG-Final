use serde::{Deserialize, Serialize};
use std::fs;

// Struct untuk membaca output dari Python (Hulu)
#[derive(Deserialize, Debug)]
struct SiteData {
    site_id: String,
    satellite_ndvi_90: f64,
    ground_truth_10: f64,
    error_margin: f64,
    estimated_biomass: f64, // [BARU] Menangkap data Biomassa dari GEE
    estimated_carbon: f64,  // [BARU] Menangkap data Karbon dari GEE
}

// Struct untuk menulis input bagi R-Markdown (Hilir)
#[derive(Serialize, Debug)]
struct ESGReport {
    site_id: String,
    gri_304_biodiversity_score: String,
    data_integrity_flag: String,
    final_trust_score: f64,
    estimated_biomass: f64, // [BARU] Meneruskan data ke R
    estimated_carbon: f64,  // [BARU] Meneruskan data ke R
}

fn calculate_trust_score(sat: f64, gt: f64, error: f64) -> f64 {
    let base_score = (0.9 * sat) + (0.1 * gt);
    // Penalti jika deviasi antara satelit dan lapangan > 15%
    let penalty = if error > 0.15 { 0.2 } else { 0.0 };
    base_score - penalty
}

fn main() {
    let data_str = fs::read_to_string("../shared_data/raw_data.json").expect("Gagal membaca JSON");
    let sites: Vec<SiteData> = serde_json::from_str(&data_str).expect("Gagal parsing JSON");
    let mut reports: Vec<ESGReport> = Vec::new();

    for site in sites {
        let trust_score = calculate_trust_score(
            site.satellite_ndvi_90,
            site.ground_truth_10,
            site.error_margin,
        );

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
            estimated_biomass: site.estimated_biomass, // Eksekusi pemindahan data
            estimated_carbon: site.estimated_carbon,   // Eksekusi pemindahan data
        });
    }

    let out_str = serde_json::to_string_pretty(&reports).unwrap();
    fs::write("../shared_data/esg_metrics.json", out_str).expect("Gagal menulis output ESG");
    println!("✅ Tahap 2: Rust ESG Engine selesai memproses metrik kepatuhan (Termasuk Kalkulasi Karbon)!");
}
