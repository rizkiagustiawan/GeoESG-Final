import os
import urllib.request
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

# List paper & standar publik yang open-access dan bebas bot-block
DOWNLOADS = {
    "SNI_7724_2011_Carbon_Estimation_Summary.pdf": "https://www.fao.org/forestry/35032-0c9f1fc78dff5d3c82e666fbd6df1e15.pdf", # Referensi FAO terkait Forestry
    "GRI_304_Biodiversity_Standards.pdf": "https://www.globalreporting.org/media/0bxjf2w1/gri-304-biodiversity-2016.pdf",
    "UNet_Tree_Crown_Detection_ArXiv.pdf": "https://arxiv.org/pdf/2006.12450.pdf", # Deep Learning for Tree Counting
    "Biomass_Fusion_Sentinel_ALOS.pdf": "https://arxiv.org/pdf/1908.08383.pdf" # Remote Sensing Fusion
}

ref_dir = os.path.dirname(os.path.abspath(__file__))

print("==================================================")
print(" Mengunduh Referensi & Data Pendukung GeoESG...")
print("==================================================")

for filename, url in DOWNLOADS.items():
    filepath = os.path.join(ref_dir, filename)
    print(f"📥 Mengunduh: {filename}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(filepath, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
        print(f"✅ Selesai ({len(data)/1024/1024:.2f} MB)")
    except Exception as e:
        print(f"❌ Gagal mengunduh {filename}: {e}")

print("\n🎉 Proses unduhan referensi selesai.")
