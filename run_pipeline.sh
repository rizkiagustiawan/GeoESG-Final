#!/bin/bash
echo "🚀 Memulai GeoESG Pipeline: 90% Satelit / 10% Lapangan..."
echo "----------------------------------------"

# 1. Ekstraksi Python
cd python-gee-ai && python3 extractor.py
cd ..
echo "----------------------------------------"

# 2. Audit Rust (Memanggil langsung binary-nya, bukan via cargo)
cd rust-esg-engine
if [ -f "target/release/rust-esg-engine" ]; then
    ./target/release/rust-esg-engine
else
    # Fallback jika dijalankan lokal tanpa docker
    cargo run --release -q
fi
cd ..
echo "----------------------------------------"

# 3. Pelaporan R
cd r-reporting && Rscript dashboard.R
cd ..
echo "----------------------------------------"
echo "🎉 Eksekusi selesai! Laporan Markdown telah diperbarui."