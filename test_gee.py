import ee
import json

# Pastikan path ini menunjuk ke file JSON yang baru Anda pindahkan
GEE_KEY_PATH = "credentials/gee-key.json"

try:
    # 1. Baca Kredensial
    with open(GEE_KEY_PATH, "r") as f:
        credentials_dict = json.load(f)

    # 2. Ekstraksi Email dan Inisialisasi Kunci
    service_account = credentials_dict["client_email"]
    credentials = ee.ServiceAccountCredentials(service_account, GEE_KEY_PATH)

    # 3. Lakukan Koneksi ke Server Google
    print("Mencoba menghubungi satelit Google Earth Engine...")
    ee.Initialize(credentials)

    print("✅ SUKSES! Robot geoesg-worker berhasil menembus sistem Earth Engine.")

    # 4. Tes komputasi ringan (Mengambil metadata elevasi bumi)
    image = ee.Image("CGIAR/SRTM90_V4")
    print("Merespons dengan data Band:", image.bandNames().getInfo())

except Exception as e:
    print(f"❌ GAGAL TERHUBUNG: {e}")
