# 📚 Referensi Akademik & Standar Pendukung GeoESG

Proyek GeoESG A.E.C.O dibangun di atas fondasi literatur sains yang solid. Dokumen ini merangkum seluruh paper, jurnal, dan standar pelaporan yang relevan dengan metode yang digunakan di dalam *pipeline* ini.

Beberapa jurnal yang tersedia *open-access* (seperti penelitian Deep Learning & Fusi Sensor) telah diunduh otomatis dalam format PDF di direktori `/references/` ini.

---

## 1. Standar Regulasi & ESG Reporting

### 🍃 GRI 304: Biodiversity (2016)
*   **Relevansi dalam Proyek:** Modul Rust `rust-esg-engine` menghitung skor `gri_304_biodiversity_score`. Standar ini mewajibkan pelaporan dampak organisasi terhadap kawasan lindung dan area bernilai keanekaragaman hayati tinggi.
*   **Akses Dokumen Resmi:** Dapat diunduh secara gratis melalui portal resmi [Global Reporting Initiative (GRI) Standards Download Center](https://www.globalreporting.org/how-to-use-the-gri-standards/gri-standards-english-language/).

### 🌳 SNI 7724:2011 (Pengukuran dan Penghitungan Cadangan Karbon)
*   **Relevansi dalam Proyek:** Dalam fungsi `estimate_biomass_carbon` di `extractor.py`, nilai konstanta `0.46` digunakan untuk mengubah nilai *Above-Ground Biomass* (AGB) menjadi stok karbon. Konstanta ini adalah ketetapan SNI untuk hutan tropis Indonesia.
*   **Akses Dokumen Resmi:** Dokumen fisik/digital SNI ini diterbitkan oleh Badan Standardisasi Nasional (BSN) dan Kementerian Lingkungan Hidup dan Kehutanan (KLHK) Indonesia. Referensi metodologi IPCC Tier 1 & Tier 2 terkait bisa diakses di portal [IPCC Task Force on National Greenhouse Gas Inventories (TFI)](https://www.ipcc-nggip.iges.or.jp/).

---

## 2. Literatur Remote Sensing & Machine Learning
*(File PDF telah diunduh otomatis ke dalam folder ini)*

### 🛰️ Estimasi Biomassa melalui Fusi Sensor (Sentinel-1, Sentinel-2, ALOS)
*   **File Unduhan:** `Biomass_Fusion_Sentinel_ALOS.pdf`
*   **Relevansi dalam Proyek:** Menggabungkan NDVI dari optik (Sentinel-2) dengan struktur dahan/kayu dari gelombang mikro (Radar C-Band Sentinel-1 dan L-Band ALOS PALSAR-2) untuk mengatasi kelemahan "saturasi NDVI" pada hutan yang sangat lebat.
*   **Abstrak Ringkas:** Kombinasi indeks vegetasi optik seringkali mengalami saturasi saat densitas biomassa tinggi. Jurnal ini mendemonstrasikan bagaimana integrasi *backscatter* Radar mampu menembus tajuk awan dan memberikan informasi struktural 3D dari pepohonan, sehingga meningkatkan akurasi *Random Forest Regressor* secara signifikan.

### 🤖 Computer Vision & U-Net untuk Tree Crown Detection
*   **File Unduhan:** `UNet_Tree_Crown_Detection_ArXiv.pdf`
*   **Relevansi dalam Proyek:** Modul `vision_unet_model.py` dalam proyek ini mendemonstrasikan kapabilitas arsitektur *Deep Learning U-Net* untuk menghitung (*instance segmentation*) jumlah pohon secara individual dari citra resolusi super tinggi 0.5 meter.
*   **Abstrak Ringkas:** Ekstraksi kanopi pohon secara manual dari citra satelit memakan waktu lama. Literatur ini menggunakan Convolutional Neural Networks (CNN) berbasis U-Net yang dimodifikasi untuk mendeteksi kanopi dalam hutan yang rapat, memberikan fondasi algoritmik untuk estimasi ekologis otomatis.

---

## 3. Data Pendukung & Pustaka Terbuka

Sistem GeoESG menggunakan teknologi dari penyedia data global berikut:
1.  **Google Earth Engine (GEE):** *Petabyte-scale geospatial analysis platform* yang menaungi data Copernicus (ESA) dan JAXA.
2.  **Dataset Copernicus Sentinel:** Menyediakan citra resolusi 10m dengan *revisit time* 5 hari.
3.  **PostGIS Spatial Data:** Standar de-facto dari *Open Geospatial Consortium* (OGC) untuk analisis titik poligon *in-database*.

> **Tips Auditor:** Saat mempresentasikan sistem ini, referensikan jurnal fusi sensor dan standar SNI 7724:2011 untuk membuktikan bahwa metode yang digunakan dalam kalkulasi backend memiliki *scientific validation* yang kuat.
