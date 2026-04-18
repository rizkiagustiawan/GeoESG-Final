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

/// Menghitung Trust Score berdasarkan deviasi statistik (Relative Error).
///
/// Pendekatan Ilmiah:
///   1. Relative Error (RE) = |sat - gt| / max(gt, 0.1)
///   2. Jika RE ≤ 15% -> Sangat Konsisten (Standar ketidakpastian IPCC Tier 1)
///   3. Reliability Decay = exp(-5.0 * RE)
///      Alih-alih memberikan penalti linier yang arbitrer, fungsi peluruhan
///      eksponensial mensimulasikan hilangnya kepercayaan secara drastis
///      ketika diskrepansi data lapangan dan satelit membesar.
fn calculate_trust_score(sat: f64, gt: f64) -> (f64, f64, String) {
    let re = (sat - gt).abs() / gt.max(0.1);
    
    // Base score gabungan (Satelit dan Ground Truth)
    let base_score = (0.8 * sat) + (0.2 * gt);
    
    // Faktor peluruhan (Exponential Decay)
    let reliability_factor = (-5.0 * re).exp();
    let trust_score = base_score * reliability_factor;
    
    let integrity = if re <= 0.15 {
        "AUDIT_PASS: High Consistency (RE ≤ 15%)".to_string()
    } else if re <= 0.25 {
        "AUDIT_WARN: Moderate Deviation (15% < RE ≤ 25%)".to_string()
    } else {
        "AUDIT_FAIL: High Deviation (Greenwashing Risk, RE > 25%)".to_string()
    };
    
    (trust_score, re, integrity)
}

fn main() {
    let data_str = fs::read_to_string("../shared_data/raw_data.json").expect("Gagal membaca JSON");
    let sites: Vec<SiteData> = serde_json::from_str(&data_str).expect("Gagal parsing JSON");
    let mut reports: Vec<ESGReport> = Vec::new();

    for site in sites {
        let (trust_score, _re, integrity) = calculate_trust_score(
            site.estimated_biomass,
            site.ground_truth_10,
        );

        reports.push(ESGReport {
            site_id: site.site_id,
            gri_304_biodiversity_score: format!("{:.2} (Biomass-Validated)", trust_score),
            data_integrity_flag: integrity,
            final_trust_score: trust_score,
            estimated_biomass: site.estimated_biomass, // Eksekusi pemindahan data
            estimated_carbon: site.estimated_carbon,   // Eksekusi pemindahan data
        });
    }

    let out_str = serde_json::to_string_pretty(&reports).unwrap();
    if fs::write("../shared_data/esg_metrics.json", out_str).is_ok() {
        println!("✅ ESG Metrics berhasil ditulis ke: ../shared_data/esg_metrics.json");
    } else {
        eprintln!("❌ Gagal membuka file untuk menulis.");
    }
    println!("✅ Tahap 2: Rust ESG Engine selesai memproses metrik kepatuhan (Termasuk Kalkulasi Karbon)!");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_perfect_consistency() {
        // Satelit dan lapangan sama persis
        let (score, re, status) = calculate_trust_score(150.0, 150.0);
        assert_eq!(re, 0.0);
        assert!(score > 149.0); // Karena decay factor = 1.0, score harus dekat dengan 150
        assert!(status.contains("AUDIT_PASS"));
    }

    #[test]
    fn test_moderate_deviation() {
        // Deviasi 20% (RE = 0.20)
        let (score, re, status) = calculate_trust_score(180.0, 150.0);
        assert!((re - 0.20).abs() < 0.001);
        assert!(status.contains("AUDIT_WARN"));
        // Decay factor: exp(-5 * 0.2) = exp(-1) = ~0.367
        // Base score: 0.8*180 + 0.2*150 = 144 + 30 = 174
        // Trust score: 174 * 0.367 = ~64
        assert!(score > 60.0 && score < 70.0);
    }

    #[test]
    fn test_greenwashing_risk() {
        // Satelit overestimates biomassa (400 vs 150 -> RE = 1.66)
        let (score, re, status) = calculate_trust_score(400.0, 150.0);
        assert!(re > 0.25);
        assert!(status.contains("AUDIT_FAIL"));
        assert!(status.contains("Greenwashing Risk"));
        // Score harus hancur (sangat rendah) karena exponential decay
        assert!(score < 10.0);
    }

    #[test]
    fn test_zero_ground_truth() {
        // Pastikan tidak ada division by zero
        let (score, re, _status) = calculate_trust_score(50.0, 0.0);
        assert_eq!(re, 50.0 / 0.1); // dibagi dengan gt.max(0.1)
        assert!(score < 1.0); // Decay factor membunuh skor
    }
}
