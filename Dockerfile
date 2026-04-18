# ==========================================
# STAGE 1: Kompilasi Mesin Rust (Builder)
# ==========================================
FROM rust:1.80-slim-bookworm AS rust-builder
WORKDIR /usr/src/app
COPY rust-esg-engine/ .
RUN cargo build --release

# ==========================================
# STAGE 2: Produksi (Ubuntu 22.04)
# ==========================================
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 1. Instal Dependensi Sistem + R Base + Library Sistem untuk paket R
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common curl gnupg2 \
    python3 python3-pip \
    r-base \
    libcurl4-openssl-dev libssl-dev libxml2-dev \
    libudunits2-dev libgdal-dev libgeos-dev libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Instal R Packages dari CRAN
RUN R -e "install.packages(c('shiny','sf','leaflet','dplyr','ggplot2','jsonlite'), repos='https://cloud.r-project.org/', Ncpus=4)"

WORKDIR /app

# 3. Instal Library Python GEE & API
RUN pip3 install --no-cache-dir \
    fastapi uvicorn earthengine-api \
    pandas geopandas shapely pydantic

# 4. Salin File Proyek & Binary Rust
COPY . /app
RUN mkdir -p /app/rust-esg-engine/target/release
COPY --from=rust-builder /usr/src/app/target/release/rust-esg-engine /app/rust-esg-engine/target/release/rust-esg-engine

# 5. Beri Hak Akses Eksekusi
RUN chmod +x /app/run_pipeline.sh && chmod +x /app/rust-esg-engine/target/release/rust-esg-engine

# 6. Inisialisasi Database
RUN python3 /app/init_db.py

# 7. Health Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000 3838
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]