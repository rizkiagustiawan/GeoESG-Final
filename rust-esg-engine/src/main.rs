use serde::{Deserialize, Serialize};
use std::fs;

/// ═══════════════════════════════════════════════════════════════════════════
/// GeoESG — ESG Data Quality Assessment Engine (Rust)
///
/// Validasi integritas data satelit vs ground truth menggunakan metrik
/// statistik standar yang peer-reviewed:
///
/// Referensi:
///   [1] IPCC 2006 Guidelines Vol 4, Ch 2 — Uncertainty classification
///   [2] Chave et al. (2014), Global Change Biol. — Field measurement ±15%
///   [3] Willmott (1982), Physical Geography — Validation metrics
///   [4] GRI 304 (2021), Global Reporting Initiative — Biodiversity disclosure
///
/// Metrik yang dihitung:
///   - Relative Error (RE)       — |predicted - observed| / observed
///   - Bias                      — predicted - observed (Mg/ha)
///   - Accuracy Index            — max(0, 1 - RE) × 100%
///   - IPCC Accuracy Tier        — Berdasarkan IPCC 2006 uncertainty tiers
/// ═══════════════════════════════════════════════════════════════════════════

// Struct input dari Python (Hulu)
#[derive(Deserialize, Debug)]
struct SiteData {
    site_id: String,
    satellite_ndvi_90: f64,
    ground_truth_10: f64,
    error_margin: f64,
    estimated_biomass: f64,
    estimated_carbon: f64,
}

// Struct output untuk R-Markdown dan Frontend (Hilir)
#[derive(Serialize, Debug)]
struct ESGReport {
    site_id: String,
    // ── Standard statistical metrics ──
    relative_error_pct: f64,
    bias_mg_ha: f64,
    accuracy_pct: f64,
    ipcc_tier: String,
    // ── Backward-compatible fields ──
    data_integrity_flag: String,
    gri_304_biodiversity_score: String,
    final_trust_score: f64,
    // ── Pass-through data ──
    estimated_biomass: f64,
    estimated_carbon: f64,
}

/// Menghitung metrik validasi data menggunakan standar statistik.
///
/// Metrik:
///   - RE (Relative Error) = |predicted - observed| / max(observed, 1.0)
///   - Bias = predicted - observed (positif = overestimate)
///   - Accuracy = max(0, (1 - RE) × 100)
///
/// Klasifikasi akurasi berdasarkan IPCC 2006 Guidelines Vol 4, Ch 2:
///   - Tier 3: RE ≤ 10% — Akurasi tinggi (spatially explicit, field-validated)
///   - Tier 2: RE ≤ 20% — Akurasi moderat (country-specific factors)
///   - Tier 1: RE ≤ 30% — Akurasi minimum (default IPCC factors)
///   - Unacceptable: RE > 30% — Melebihi toleransi IPCC
///
/// Referensi threshold:
///   Chave et al. (2014): Field measurement uncertainty ±10-20% untuk AGB
///   GOFC-GOLD (2016): RE ≤ 20% direkomendasikan untuk MRV REDD+
fn validate_data_quality(
    predicted_biomass: f64,
    observed_biomass: f64,
) -> (f64, f64, f64, String, String) {
    let gt = observed_biomass.max(1.0); // Prevent division by zero

    // Standard statistical metrics
    let relative_error = (predicted_biomass - gt).abs() / gt;
    let bias = predicted_biomass - gt;
    let accuracy_pct = ((1.0 - relative_error) * 100.0).max(0.0);
    let re_pct = relative_error * 100.0;

    // IPCC-aligned accuracy tier classification
    // Based on: IPCC 2006 Vol 4 Ch 2 + GOFC-GOLD (2016) MRV guidelines
    let (tier, integrity) = if relative_error <= 0.10 {
        (
            "Tier_3".to_string(),
            format!(
                "AUDIT_PASS: Akurasi Tinggi — RE={:.1}% ≤ 10% (IPCC Tier 3, Chave et al. 2014)",
                re_pct
            ),
        )
    } else if relative_error <= 0.20 {
        (
            "Tier_2".to_string(),
            format!(
                "AUDIT_PASS: Akurasi Moderat — RE={:.1}% ≤ 20% (IPCC Tier 2, GOFC-GOLD 2016)",
                re_pct
            ),
        )
    } else if relative_error <= 0.30 {
        (
            "Tier_1".to_string(),
            format!(
                "AUDIT_WARN: Akurasi Rendah — RE={:.1}% ≤ 30% (batas minimum IPCC Tier 1)",
                re_pct
            ),
        )
    } else {
        (
            "Unacceptable".to_string(),
            format!(
                "AUDIT_FAIL: RE={:.1}% > 30% — Melebihi batas toleransi IPCC. Kalibrasi ulang diperlukan.",
                re_pct
            ),
        )
    };

    (re_pct, bias, accuracy_pct, tier, integrity)
}

fn main() {
    let data_str =
        fs::read_to_string("../shared_data/raw_data.json").expect("Gagal membaca JSON");
    let sites: Vec<SiteData> = serde_json::from_str(&data_str).expect("Gagal parsing JSON");
    let mut reports: Vec<ESGReport> = Vec::new();

    for site in sites {
        let (re_pct, bias, accuracy_pct, tier, integrity) =
            validate_data_quality(site.estimated_biomass, site.ground_truth_10);

        // GRI 304 disclosure text (factual, not a score)
        let gri_text = format!(
            "Akurasi biomassa {:.1}% (RE={:.1}%, Bias={:+.1} Mg/ha) — Tier: {}",
            accuracy_pct, re_pct, bias, tier
        );

        // Backward-compatible trust score = accuracy as fraction (0-1)
        let trust = accuracy_pct / 100.0;

        reports.push(ESGReport {
            site_id: site.site_id,
            relative_error_pct: (re_pct * 10.0).round() / 10.0,
            bias_mg_ha: (bias * 100.0).round() / 100.0,
            accuracy_pct: (accuracy_pct * 10.0).round() / 10.0,
            ipcc_tier: tier,
            data_integrity_flag: integrity,
            gri_304_biodiversity_score: gri_text,
            final_trust_score: (trust * 1000.0).round() / 1000.0,
            estimated_biomass: site.estimated_biomass,
            estimated_carbon: site.estimated_carbon,
        });
    }

    let out_str = serde_json::to_string_pretty(&reports).unwrap();
    if fs::write("../shared_data/esg_metrics.json", out_str).is_ok() {
        println!("✅ ESG Metrics (IPCC-validated) ditulis ke: ../shared_data/esg_metrics.json");
    } else {
        eprintln!("❌ Gagal menulis file.");
    }
    println!("✅ Tahap 2: Rust ESG Engine — Data Quality Assessment selesai!");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_perfect_match() {
        // RE = 0% → Tier 3
        let (re, bias, acc, tier, status) = validate_data_quality(150.0, 150.0);
        assert_eq!(re, 0.0);
        assert_eq!(bias, 0.0);
        assert_eq!(acc, 100.0);
        assert_eq!(tier, "Tier_3");
        assert!(status.contains("AUDIT_PASS"));
    }

    #[test]
    fn test_tier_2_accuracy() {
        // RE = 15% → Tier 2 (between 10-20%)
        let (re, _bias, acc, tier, status) = validate_data_quality(127.5, 150.0);
        assert!((re - 15.0).abs() < 0.1);
        assert!((acc - 85.0).abs() < 0.1);
        assert_eq!(tier, "Tier_2");
        assert!(status.contains("AUDIT_PASS"));
    }

    #[test]
    fn test_tier_1_warning() {
        // RE = 25% → Tier 1 (between 20-30%)
        let (re, _bias, _acc, tier, status) = validate_data_quality(112.5, 150.0);
        assert!((re - 25.0).abs() < 0.1);
        assert_eq!(tier, "Tier_1");
        assert!(status.contains("AUDIT_WARN"));
    }

    #[test]
    fn test_unacceptable() {
        // RE = 167% → Unacceptable
        let (re, bias, _acc, tier, status) = validate_data_quality(400.0, 150.0);
        assert!(re > 30.0);
        assert!(bias > 0.0); // Overestimate
        assert_eq!(tier, "Unacceptable");
        assert!(status.contains("AUDIT_FAIL"));
    }

    #[test]
    fn test_zero_ground_truth() {
        // Division by zero protection
        let (re, _bias, _acc, tier, _status) = validate_data_quality(50.0, 0.0);
        // gt clamped to 1.0, so RE = |50-1|/1 = 49 → 4900%
        assert!(re > 100.0);
        assert_eq!(tier, "Unacceptable");
    }

    #[test]
    fn test_overestimate_bias() {
        // Satellite overestimates → positive bias
        let (_re, bias, _acc, _tier, _status) = validate_data_quality(200.0, 150.0);
        assert_eq!(bias, 50.0);
    }

    #[test]
    fn test_underestimate_bias() {
        // Satellite underestimates → negative bias
        let (_re, bias, _acc, _tier, _status) = validate_data_quality(100.0, 150.0);
        assert_eq!(bias, -50.0);
    }
}
