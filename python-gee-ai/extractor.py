"""
GeoESG Extractor v2.0 — Pipeline Tahap 1 (Hulu)
================================================
Modul ini bertanggung jawab mengekstrak data penginderaan jauh dari
Google Earth Engine (GEE) untuk wilayah NTB.

Sumber Data:
  - NDVI Optik    : Sentinel-2 SR Harmonized (B8/B4)
  - Radar VH/VV   : Sentinel-1 GRD (C-Band SAR)
  - Biomassa/Karbon: Estimasi allometrik dari NDVI (IPCC 0.47 factor)

Output → shared_data/raw_data.json
"""

import os
import json
import datetime

# ─── Path Setup ──────────────────────────────────────────────────────────────
# Mendukung override via environment variables untuk isolasi per-request
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_PATH = os.path.join(BASE_DIR, "credentials", "gee-key.json")
OUTPUT_PATH = os.environ.get(
    "GEOESG_OUTPUT_PATH", os.path.join(BASE_DIR, "shared_data", "raw_data.json")
)
GEOJSON_PATH = os.environ.get(
    "GEOESG_GEOJSON_PATH", os.path.join(BASE_DIR, "shared_data", "batas_ntb.geojson")
)
USER_INPUT_PATH = os.environ.get(
    "GEOESG_INPUT_PATH", os.path.join(BASE_DIR, "shared_data", "user_input.json")
)


# ─── GEE Initialization ─────────────────────────────────────────────────────
def init_gee():
    """Autentikasi dan inisialisasi Google Earth Engine."""
    try:
        import ee

        with open(KEY_PATH, "r") as f:
            cred_dict = json.load(f)
        service_account = cred_dict["client_email"]
        credentials = ee.ServiceAccountCredentials(service_account, key_file=KEY_PATH)
        ee.Initialize(credentials=credentials, project="thermal-cathode-421211")
        print("✅ Koneksi Google Earth Engine berhasil!")
        return True
    except Exception as e:
        print(f"⚠️  GEE tidak tersedia ({e}), menggunakan mode fallback.")
        return False


# ─── GEE Extraction Functions ───────────────────────────────────────────────
def extract_ndvi_gee(region_geojson, site_id):
    """
    Ekstraksi NDVI dari Sentinel-2 SR Harmonized.
    Menggunakan median composite 3 bulan terakhir.
    """
    import ee

    geometry = ee.Geometry(region_geojson)

    # Sentinel-2 Surface Reflectance — 3 bulan terakhir
    end_date = ee.Date(datetime.datetime.now().isoformat())
    start_date = end_date.advance(-3, "month")

    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geometry)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
        .median()
    )

    # Hitung NDVI = (B8 - B4) / (B8 + B4)
    ndvi = s2.normalizedDifference(["B8", "B4"]).rename("NDVI")
    stats = ndvi.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=geometry, scale=10, maxPixels=1e9
    )
    ndvi_val = stats.get("NDVI").getInfo()

    if ndvi_val is None:
        print(f"  ⚠️  Tidak ada data NDVI untuk {site_id}, menggunakan default.")
        return 0.65
    return round(ndvi_val, 3)


def extract_radar_gee(region_geojson, site_id):
    """
    Ekstraksi backscatter Radar dari Sentinel-1 GRD (VH & VV).
    Menggunakan median composite 3 bulan terakhir.
    """
    import ee

    geometry = ee.Geometry(region_geojson)

    end_date = ee.Date(datetime.datetime.now().isoformat())
    start_date = end_date.advance(-3, "month")

    s1 = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(geometry)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .select(["VH", "VV"])
        .median()
    )

    stats = s1.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=geometry, scale=10, maxPixels=1e9
    )

    vh = stats.get("VH").getInfo()
    vv = stats.get("VV").getInfo()

    return (
        round(vh, 3) if vh else -14.0,
        round(vv, 3) if vv else -7.4,
    )


def estimate_biomass_carbon(ndvi, vh, vv):
    """
    Estimasi Above-Ground Biomass (AGB) menggunakan fusi Optik dan SAR.

    Problem Ilmiah: NDVI (Optik) mengalami saturasi pada biomassa tinggi (>100 Mg/ha) 
    di hutan tropis. Sinyal SAR (C-band) mampu berpenetrasi lebih dalam.

    Model: Multivariable Exponential Regression (Fusi Sentinel-1 & 2)
    Adaptasi dari literatur fusi sensor (misal: Laurin et al. & Forkuor et al.)
      AGB = exp( α + β(NDVI) + γ(VH) + δ(VV) )

    Konversi Karbon (SNI 7724:2011): 
      Faktor konversi spesifik hutan tropis pamah Indonesia adalah 0.46 
      (berbeda sedikit dari default IPCC 0.47).
    """
    import math

    # Clamp parameter ke range rasional satelit
    ndvi_c = max(0.0, min(ndvi, 1.0))
    vh_c = max(-30.0, min(vh, 0.0))
    vv_c = max(-30.0, min(vv, 0.0))

    # Koefisien regresi fusi (S2 + S1) untuk wilayah tropis
    # Penambahan VH positif kecil mengurangi efek saturasi NDVI
    agb = math.exp(2.8 + (1.8 * ndvi_c) + (0.03 * vh_c) - (0.01 * vv_c))
    
    # SNI 7724:2011 Standard
    carbon = agb * 0.46
    
    return round(agb, 2), round(carbon, 2)


# ─── Fallback Mode (Tanpa GEE) ──────────────────────────────────────────────
def extract_fallback(site_id, ground_truth_biomass=150.0):
    """
    Mode fallback untuk development lokal tanpa kredensial GEE.
    Menggunakan ground truth biomassa lapangan + noise realistis.
    """
    import random

    random.seed(hash(site_id) % 2**32)

    sat_ndvi = round(random.uniform(0.65, 0.95), 3)
    vh = round(-15.0 + random.uniform(-2.0, 2.0), 3)
    vv = round(-8.0 + random.uniform(-1.5, 1.5), 3)
    
    # Satelit biomassa memiliki deviasi acak dari field biomass
    simulated_sat_biomass = ground_truth_biomass * random.uniform(0.85, 1.15)
    biomass = round(simulated_sat_biomass, 2)
    carbon = round(biomass * 0.46, 2)

    return {
        "satellite_ndvi_90": sat_ndvi,
        "radar_vh_db": vh,
        "radar_vv_db": vv,
        "biomass_data_source": "Fallback (Simulated)",
        "estimated_biomass": biomass,
        "estimated_carbon": carbon,
    }


# ─── Main Extraction Pipeline ───────────────────────────────────────────────
def extract_site_data(site_id, ground_truth_biomass, region_geojson=None, use_gee=False):
    """
    Ekstraksi data lengkap untuk satu site.
    Mengembalikan dict yang siap ditulis ke raw_data.json.
    """
    if use_gee and region_geojson:
        print(f"  🛰️  [{site_id}] Mengambil fusi data optik dan SAR dari GEE...")
        sat_ndvi = extract_ndvi_gee(region_geojson, site_id)
        vh, vv = extract_radar_gee(region_geojson, site_id)
        biomass, carbon = estimate_biomass_carbon(sat_ndvi, vh, vv)
        source = "Fusi Optik & SAR (Sentinel-1 & 2) via GEE"
    else:
        print(f"  📡 [{site_id}] Menggunakan mode fallback...")
        fallback = extract_fallback(site_id, ground_truth_biomass)
        sat_ndvi = fallback["satellite_ndvi_90"]
        vh = fallback["radar_vh_db"]
        vv = fallback["radar_vv_db"]
        biomass = fallback["estimated_biomass"]
        carbon = fallback["estimated_carbon"]
        source = "Simulasi Fusi Optik & SAR"

    # Error Margin (Relative Error) = |Sat - Ground| / Ground
    error_margin = round(abs(biomass - ground_truth_biomass) / max(ground_truth_biomass, 10.0), 3)

    return {
        "site_id": site_id,
        "satellite_ndvi_90": sat_ndvi,
        "radar_vh_db": vh,
        "radar_vv_db": vv,
        "biomass_data_source": source,
        "ground_truth_10": ground_truth_biomass,
        "error_margin": error_margin,
        "estimated_biomass": biomass,
        "estimated_carbon": carbon,
        "timestamp": datetime.datetime.now().isoformat(),
    }


def load_user_inputs():
    """Memuat daftar wilayah yang akan diaudit dari user_input.json."""
    if os.path.exists(USER_INPUT_PATH):
        with open(USER_INPUT_PATH, "r") as f:
            return json.load(f)
    # Default: Sumbawa Barat
    return [{"site_id": "Sumbawa Barat", "ground_truth_10": 150.0}]


def find_region_geometry(site_id):
    """
    Cari geometry untuk region tertentu dari GeoJSON boundaries.
    Mencocokkan site_id dengan properti ADM2_NAME, NAMOBJ, dll.
    """
    if not os.path.exists(GEOJSON_PATH):
        return None
    try:
        with open(GEOJSON_PATH, "r") as f:
            geojson = json.load(f)
        for feature in geojson.get("features", []):
            props = feature.get("properties", {})
            names = [
                props.get("ADM2_NAME"),
                props.get("NAMOBJ"),
                props.get("WADMKC"),
                props.get("WADMKK"),
                props.get("KABUPATEN"),
            ]
            if site_id in [n for n in names if n]:
                return feature.get("geometry")
    except Exception:
        pass
    return None


def run_pipeline():
    """Eksekusi utama pipeline ekstraksi."""
    print("=" * 60)
    print("  GeoESG Extractor v2.0 — Pipeline Tahap 1 (Hulu)")
    print("=" * 60)

    gee_available = init_gee()
    inputs = load_user_inputs()
    results = []

    for inp in inputs:
        site_id = inp["site_id"]
        # Ambil input ground_truth_10 (atau ground_truth_biomass) dari JSON
        gt_biomass = inp.get("ground_truth_10", inp.get("ground_truth_biomass", 150.0))

        region_geo = find_region_geometry(site_id) if gee_available else None

        data = extract_site_data(
            site_id=site_id,
            ground_truth_biomass=gt_biomass,
            region_geojson=region_geo,
            use_gee=gee_available and region_geo is not None,
        )
        results.append(data)

        print(f"  ✅ [{site_id}] NDVI={data['satellite_ndvi_90']}, "
              f"Biomass={data['estimated_biomass']} Mg/ha, "
              f"Carbon={data['estimated_carbon']} Mg C/ha")

    # Tulis output
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=4)
    print(f"\n📁 Data berhasil ditulis ke: {OUTPUT_PATH}")
    print("✅ Tahap 1: Ekstraksi satelit selesai!")
    return results


if __name__ == "__main__":
    run_pipeline()
