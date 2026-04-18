# ==========================================
# STAGE 1: Kompilasi Mesin Rust (Builder)
# ==========================================
FROM rust:1.80-slim-bookworm AS rust-builder
WORKDIR /usr/src/app
COPY rust-esg-engine/ .
RUN cargo build --release

# ==========================================
# STAGE 2: Produksi (Ubuntu 22.04 + Pre-compiled R)
# ==========================================
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 1. Instal Dependensi Sistem & Tambahkan PPA c2d4u (Kunci Kecepatan!)
RUN apt-get update && apt-get install -y \
    software-properties-common curl gnupg2 \
    python3 python3-pip \
    && add-apt-repository ppa:c2d4u.4.0+ -y \
    && apt-get update \
    && apt-get install -y \
    r-cran-shiny \
    r-cran-sf \
    r-cran-leaflet \
    r-cran-dplyr \
    r-cran-ggplot2 \
    r-cran-jsonlite \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Instal Library Python GEE
RUN pip3 install fastapi uvicorn earthengine-api pandas geopandas shapely

# 3. Salin File Proyek & Binary Rust
COPY . /app
RUN mkdir -p /app/rust-esg-engine/target/release
COPY --from=rust-builder /usr/src/app/target/release/rust-esg-engine /app/rust-esg-engine/target/release/rust-esg-engine

# 4. Beri Hak Akses Eksekusi
RUN chmod +x /app/run_pipeline.sh && chmod +x /app/rust-esg-engine/target/release/rust-esg-engine

EXPOSE 8000 3838
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]