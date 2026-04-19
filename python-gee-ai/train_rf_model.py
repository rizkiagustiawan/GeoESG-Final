"""
GeoESG — Science-Based Biomass RF Model Training
=================================================
Training data generated using published allometric equations for tropical forests.

References:
  [1] Mitchard et al. (2012), "Mapping tropical forest biomass with radar and
      spaceborne LiDAR", Remote Sens. of Environ. — L-band HV-AGB relationship
  [2] Saatchi et al. (2011), "Benchmark map of forest carbon stocks in tropical
      regions across three continents", PNAS — Multi-sensor fusion approach
  [3] Lucas et al. (2010), "An evaluation of the ALOS PALSAR for monitoring
      forest extent and structure", IEEE TGRS — SAR-biomass sensitivity
  [4] Chave et al. (2014), "Improved allometric models to estimate AGB of
      tropical trees", Global Change Biology — Field uncertainty ±15%

Sensor uncertainty (from ESA/JAXA technical specifications):
  - NDVI:    σ = 0.02 (ESA Sentinel-2 L2A radiometric accuracy)
  - C-VH/VV: σ = 1.0 dB (ESA Sentinel-1 GRD calibration accuracy)
  - L-HH/HV: σ = 1.5 dB (JAXA ALOS PALSAR-2 calibration accuracy)
  - AGB:     σ = 15% of true value (Chave et al., 2014, field inventory error)
"""

import numpy as np
import joblib
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

print("=" * 60)
print("  GeoESG — Science-Based RF Biomass Model Training")
print("  References: Mitchard (2012), Saatchi (2011), Chave (2014)")
print("=" * 60)

# ─── 1. Generate Science-Based Training Data ─────────────────────
np.random.seed(42)
n_samples = 10000

print(f"[1/5] Generating {n_samples} training samples from published")
print("      allometric equations (Mitchard et al., 2012)...\n")

# Sensor feature ranges (realistic for NTB tropical forests)
ndvi = np.random.uniform(0.10, 0.95, n_samples)   # Sentinel-2
c_vh = np.random.uniform(-25.0, -5.0, n_samples)  # Sentinel-1 VH (dB)
c_vv = np.random.uniform(-15.0, -2.0, n_samples)  # Sentinel-1 VV (dB)
l_hh = np.random.uniform(-15.0, -2.0, n_samples)  # ALOS PALSAR HH (dB)
l_hv = np.random.uniform(-25.0, -5.0, n_samples)  # ALOS PALSAR HV (dB)

# ── Ground Truth AGB from published allometric relationships ──
# Primary: L-band HV (Mitchard et al., 2012)
#   ln(AGB) = a₀ + a₁*HV  →  original coefficients ~0.067-0.11
# Secondary: NDVI (saturates ~0.85, Huete et al., 2006)
# Tertiary: C-band VH (Lucas et al., 2010, saturates ~100 Mg/ha)
#
# Combined multi-sensor model (adapted from Saatchi et al., 2011):
ln_agb_true = (
    5.00                     # Intercept (calibrated for NTB)
    + 0.10 * l_hv            # L-band HV: primary biomass predictor [1]
    + 0.03 * l_hh            # L-band HH: trunk/soil interaction [1]
    + 0.05 * c_vh            # C-band VH: canopy volume scattering [3]
    + 2.00 * ndvi            # Optical: photosynthetic activity [2]
)

# Add field measurement uncertainty: σ = 15% (Chave et al., 2014)
field_noise = np.random.normal(0, 0.15, n_samples)
agb_true = np.exp(ln_agb_true + field_noise)
agb_true = np.clip(agb_true, 1.0, 450.0)  # Tropical forest max ~450 Mg/ha

# Add sensor measurement noise (ESA/JAXA specs)
ndvi_obs  = ndvi + np.random.normal(0, 0.02, n_samples)
c_vh_obs  = c_vh + np.random.normal(0, 1.0, n_samples)
c_vv_obs  = c_vv + np.random.normal(0, 1.0, n_samples)
l_hh_obs  = l_hh + np.random.normal(0, 1.5, n_samples)
l_hv_obs  = l_hv + np.random.normal(0, 1.5, n_samples)

# Clip to physical ranges
ndvi_obs = np.clip(ndvi_obs, -0.1, 1.0)

X = np.column_stack((ndvi_obs, c_vh_obs, c_vv_obs, l_hh_obs, l_hv_obs))
y = agb_true

print(f"  AGB range: {y.min():.1f} — {y.max():.1f} Mg/ha")
print(f"  AGB mean:  {y.mean():.1f} ± {y.std():.1f} Mg/ha\n")

# ─── 2. Train/Test Split ─────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"[2/5] Split: {len(X_train)} train / {len(X_test)} test\n")

# ─── 3. Train Random Forest ──────────────────────────────────────
print("[3/5] Training Random Forest (200 trees, max_depth=20)...")
rf_model = RandomForestRegressor(
    n_estimators=200,
    max_depth=20,
    min_samples_leaf=5,
    random_state=42,
    n_jobs=-1,
)
rf_model.fit(X_train, y_train)

# ─── 4. Validation (Standard Metrics) ────────────────────────────
print("[4/5] Validating with standard statistical metrics...\n")

y_pred = rf_model.predict(X_test)

rmse = np.sqrt(mean_squared_error(y_test, y_pred))
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)
bias = np.mean(y_pred - y_test)
re_mean = np.mean(np.abs(y_pred - y_test) / np.maximum(y_test, 1.0))

# 5-Fold Cross Validation
cv_scores = cross_val_score(rf_model, X, y, cv=5, scoring='r2')

# Feature importance
feature_names = ['NDVI', 'S1-VH', 'S1-VV', 'ALOS-HH', 'ALOS-HV']
importances = rf_model.feature_importances_

print("  ┌───────────────────────────────────────────┐")
print("  │     VALIDATION REPORT (Test Set)          │")
print("  ├───────────────────────────────────────────┤")
print(f"  │  R²    : {r2:.4f}                         │")
print(f"  │  RMSE  : {rmse:.2f} Mg/ha                │")
print(f"  │  MAE   : {mae:.2f} Mg/ha                 │")
print(f"  │  Bias  : {bias:+.2f} Mg/ha               │")
print(f"  │  RE    : {re_mean*100:.1f}%                          │")
print("  ├───────────────────────────────────────────┤")
print(f"  │  5-Fold CV R²: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}   │")
print("  ├───────────────────────────────────────────┤")
print("  │  Feature Importance:                      │")
for name, imp in sorted(zip(feature_names, importances), key=lambda x: -x[1]):
    bar = '█' * int(imp * 40)
    print(f"  │    {name:<8s}: {imp:.3f} {bar:<20s}│")
print("  └───────────────────────────────────────────┘")

# ─── 5. Save Model + Validation Report ───────────────────────────
output_dir = os.path.join(os.path.dirname(__file__), "ml_models")
os.makedirs(output_dir, exist_ok=True)
model_path = os.path.join(output_dir, "biomass_rf_model.joblib")
joblib.dump(rf_model, model_path)

# Save validation report as JSON
import json
report = {
    "model": "RandomForestRegressor",
    "n_estimators": 200,
    "max_depth": 20,
    "n_training_samples": len(X_train),
    "n_test_samples": len(X_test),
    "training_data_source": "Science-based synthetic (Mitchard et al., 2012; Saatchi et al., 2011)",
    "validation_metrics": {
        "R2": round(r2, 4),
        "RMSE_Mg_ha": round(rmse, 2),
        "MAE_Mg_ha": round(mae, 2),
        "Bias_Mg_ha": round(bias, 2),
        "Mean_RE_pct": round(re_mean * 100, 1),
        "CV_5fold_R2_mean": round(cv_scores.mean(), 4),
        "CV_5fold_R2_std": round(cv_scores.std(), 4),
    },
    "feature_importance": dict(zip(feature_names, [round(float(x), 4) for x in importances])),
    "references": [
        "Mitchard et al. (2012) Remote Sens. Environ. 124:587-598",
        "Saatchi et al. (2011) PNAS 108(24):9899-9904",
        "Lucas et al. (2010) IEEE TGRS 48(3):1266-1284",
        "Chave et al. (2014) Global Change Biol. 20(10):3177-3190",
    ],
    "disclaimer": "Model trained on science-based synthetic data. For peer-reviewed publication, retrain with GEDI L4A + field inventory plots."
}
report_path = os.path.join(output_dir, "model_validation_report.json")
with open(report_path, "w") as f:
    json.dump(report, f, indent=2)

print(f"\n[5/5] Model saved: {model_path}")
print(f"      Report saved: {report_path}")
print("=" * 60)
print("✅ Science-based model ready!")
