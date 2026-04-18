import os
import ee

# 1. CARA PALING AMAN: Cari folder root berdasarkan lokasi file ini
# os.path.abspath(__file__) -> ambil lokasi file extractor.py
# os.path.dirname -> naik satu tingkat ke folder python-gee-ai
# os.path.dirname lagi -> naik satu tingkat lagi ke folder GeoESG-Final (Root)
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_PATH = os.path.join(base_dir, "credentials", "gee-key.json")

# 2. Inisialisasi GEE
try:
    # Gunakan parameter key_file= secara eksplisit
    credentials = ee.ServiceAccountCredentials(
        "geoesg-worker@thermal-cathode-421211.iam.gserviceaccount.com",
        key_file=KEY_PATH,
    )

    # Tambahkan project ID-mu
    ee.Initialize(credentials=credentials, project="thermal-cathode-421211")

    print("✅ Koneksi Google Earth Engine Berhasil!")

    # Tambahkan ini untuk tes kalau beneran narik data
    print("🛰️  Sedang mengambil data NDVI Sumbawa Barat...")

except Exception as e:
    print(f"❌ Gagal koneksi GEE: {e}")
