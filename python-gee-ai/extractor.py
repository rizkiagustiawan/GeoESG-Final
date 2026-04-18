import ee
import json
import os
import datetime

# --- KONFIGURASI PATH ABSOLUT ---
GEE_KEY_PATH = "/app/credentials/gee-key.json"
USER_INPUT_PATH = "/app/shared_data/user_input.json"
GEOJSON_PATH = "/app/shared_data/batas_ntb.geojson"
OUTPUT_PATH = "/app/shared_data/raw_data.json"


def initialize_gee():
    """Inisialisasi koneksi ke Google Earth Engine menggunakan Service Account."""
    try:
        if not os.path.exists(GEE_KEY_PATH):
            print(f"❌ Kunci GEE tidak ditemukan di: {GEE_KEY_PATH}")
            return False

        with open(GEE_KEY_PATH, "r") as f:
            credentials_dict = json.load(f)

        credentials = ee.ServiceAccountCredentials(
            credentials_dict["client_email"], GEE_KEY_PATH
        )
        ee.Initialize(credentials)
        print("✅ Terhubung ke Google Earth Engine.")
        return True
    except Exception as e:
        print(f"❌ GEE Error: {e}")
        return False


def get_real_satellite_ndvi(geometry):
    """Mengekstrak nilai rata-rata NDVI dari Sentinel-2 (Satelit Optik)."""
    print("🛰️  Menarik citra Sentinel-2 (Optik)...")
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geometry)
        .filterDate("2024-01-01", "2026-12-31")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
    )

    def calculate_ndvi(image):
        ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
        return image.addBands(ndvi)

    median_ndvi = collection.map(calculate_ndvi).select("NDVI").median()
    stats = median_ndvi.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=geometry, scale=100, maxPixels=1e13
    )

    val = stats.get("NDVI").getInfo()
    return val if val is not None else 0.0


def get_radar_metrics(geometry):
    """Mengekstrak data SAR dari Sentinel-1 (Satelit Radar Tembus Awan)."""
    print("🦇  Menarik citra Sentinel-1 (Radar SAR)...")
    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(geometry)
        .filterDate("2024-01-01", "2026-12-31")
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
    )

    # Menggunakan median untuk mengurangi efek speckle (noise bintik pada citra radar)
    median_sar = collection.median()
    stats = median_sar.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=geometry, scale=100, maxPixels=1e13
    )

    vh_val = stats.get("VH").getInfo()
    vv_val = stats.get("VV").getInfo()

    return (
        vh_val if vh_val is not None else -99.0,
        vv_val if vv_val is not None else -99.0,
    )


def get_carbon_metrics(ndvi_val, vh_val):
    """Estimasi Karbon dengan Logika All-Weather (Optik + Radar)."""
    print("🧠  Mengkalkulasi Biomassa (Smart Fallback Logic)...")

    # Logika: Jika NDVI valid, gunakan Optik. Jika gagal/terlalu kecil, cek VH Radar.
    # Nilai VH (Volume Scattering) sangat berkorelasi dengan kerapatan ranting dan batang.

    if ndvi_val > 0.1:
        biomass_val = ndvi_val * 150.0
        source_used = "Optik (Sentinel-2)"
    elif vh_val > -20.0 and vh_val < 0.0:
        # Fallback ke Radar: Persamaan regresi empiris kasar untuk mengubah dB ke Biomassa
        biomass_val = (vh_val + 25) * 12.0
        source_used = "Radar SAR (Sentinel-1)"
    else:
        biomass_val = 0.0
        source_used = "Tidak terdeteksi vegetasi"

    carbon_val = biomass_val * 0.47
    return round(biomass_val, 2), round(carbon_val, 2), source_used


def find_feature_by_site_id(geojson_data, site_id):
    """Mencari poligon wilayah berdasarkan Nama di GeoJSON."""
    for feature in geojson_data["features"]:
        props = feature.get("properties", {})
        # Fitur kacamata ADM2_NAME tetap dipertahankan
        region_name = (
            props.get("NAMOBJ")
            or props.get("WADMKC")
            or props.get("WADMKK")
            or props.get("ADM2_NAME")
        )

        if region_name == site_id:
            return feature
    return None


def build_dataset():
    """Orkestrator Utama Ekstraksi Data Sentinel Multi-Sensor."""
    if not initialize_gee():
        return

    if not os.path.exists(USER_INPUT_PATH):
        print("❌ Menunggu input dari Dashboard...")
        return

    with open(USER_INPUT_PATH, "r") as f:
        user_req = json.load(f)[0]

    site_id = user_req["site_id"]
    gt_val = float(user_req["ground_truth_ndvi"])

    with open(GEOJSON_PATH, "r") as f:
        geo_data = json.load(f)

    target_feature = find_feature_by_site_id(geo_data, site_id)
    if not target_feature:
        print(f"❌ Wilayah {site_id} tidak ditemukan di GeoJSON!")
        return

    roi_geometry = ee.Geometry(target_feature["geometry"])

    # Tarik Data Multi-Sensor
    sat_val = get_real_satellite_ndvi(roi_geometry)
    vh_val, vv_val = get_radar_metrics(roi_geometry)

    # Kalkulasi dengan Smart Logic
    biomass, carbon, source = get_carbon_metrics(sat_val, vh_val)

    # Simpan hasil dengan data radar tambahan
    raw_data = [
        {
            "site_id": site_id,
            "satellite_ndvi_90": round(sat_val, 3),
            "radar_vh_db": round(vh_val, 3),
            "radar_vv_db": round(vv_val, 3),
            "biomass_data_source": source,
            "ground_truth_10": gt_val,
            "error_margin": round(abs(sat_val - gt_val), 3),
            "estimated_biomass": biomass,
            "estimated_carbon": carbon,
            "timestamp": datetime.datetime.now().isoformat(),
        }
    ]

    with open(OUTPUT_PATH, "w") as f:
        json.dump(raw_data, f, indent=4)

    print(f"✅ Data {site_id} (Optik & Radar) berhasil disimpan untuk Audit Rust!")


if __name__ == "__main__":
    build_dataset()
