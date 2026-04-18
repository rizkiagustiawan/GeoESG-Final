library(jsonlite)

# Membaca data metrik hasil olahan mesin Rust
esg_data <- fromJSON("../shared_data/esg_metrics.json")
file_path <- "ESG_Report_Output.md"
sink(file_path)

cat("# GeoESG: Laporan Kepatuhan Otomatis & Analisis Karbon 🌍\n\n")
cat("> **Metodologi:** 90% AI Satelit (GEE) + 10% Validasi In-Situ\n")
cat("> **Standar:** GRI 304 (Keanekaragaman Hayati) & Estimasi Stok Karbon\n\n")

cat("## 📊 Ringkasan Audit Integritas & Biomassa\n\n")

# Membuat tabel untuk tampilan yang lebih profesional
cat("| Lokasi | Bio-Index (NDVI) | Estimasi Biomassa (Mg/ha) | Estimasi Karbon (Mg C/ha) | Status Integritas |\n")
cat("| :--- | :--- | :--- | :--- | :--- |\n")

for (i in 1:nrow(esg_data)) {
  # Mengasumsikan field baru akan ditambahkan oleh mesin Rust nanti
  # Jika field belum ada, kita berikan nilai default atau placeholder
  biomass <- if (!is.null(esg_data$estimated_biomass)) esg_data$estimated_biomass[i] else "Pending"
  carbon <- if (!is.null(esg_data$estimated_carbon)) esg_data$estimated_carbon[i] else "Pending"

  cat(sprintf(
    "| **%s** | %s | %s | %s | `%s` |\n",
    esg_data$site_id[i],
    esg_data$gri_304_biodiversity_score[i],
    biomass,
    carbon,
    esg_data$data_integrity_flag[i]
  ))
}

cat("\n---\n")
cat("## 🔬 Catatan Teknis Ekstraksi\n")
cat("- **Dataset Biomassa:** Menggunakan integrasi GEDI L4A / ALOS PALSAR.\n")
cat("- **Faktor Konversi:** Carbon = Aboveground Biomass (AGB) × 0.47 (IPCC Standard).\n")
cat("- **Waktu Audit:** ", format(Sys.time(), "%d %B %Y %H:%M:%S"), "\n")

sink()
cat("✅ Format laporan R-Markdown telah diperbarui dengan kolom Karbon/Biomassa!\n")
