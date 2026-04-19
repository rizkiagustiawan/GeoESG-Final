"""
GeoESG Map Printer v1.0 — Modul Cetak Peta Kartografi Profesional
=================================================================
Menghasilkan peta cetak standar kartografi untuk setiap lokasi audit.

Elemen Wajib Peta:
  1. Judul Peta
  2. Skala Peta (Scale Bar)
  3. North Arrow (Panah Utara)
  4. Legenda
  5. Grid Koordinat (Graticule)
  6. Inset Peta (Peta Lokasi)
  7. Sumber Data dan Tahun Pembuatan
  8. Sistem Proyeksi dan Datum
  9. Nama Pembuat: Rizki Agustiawan

Output → shared_data/maps/ (PNG 300 DPI, siap cetak A3)
"""

import os
import json
import datetime
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnchoredText
import matplotlib.patheffects as pe


# ─── Config ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_DATA = os.path.join(BASE_DIR, "shared_data")
GEOJSON_PATH = os.path.join(SHARED_DATA, "batas_ntb.geojson")
RAW_DATA_PATH = os.path.join(SHARED_DATA, "raw_data.json")
MAP_OUTPUT_DIR = os.path.join(SHARED_DATA, "maps")

# Bounding box NTB keseluruhan (untuk inset map)
NTB_BOUNDS = {
    "lon_min": 115.80, "lon_max": 119.10,
    "lat_min": -9.10, "lat_max": -8.10
}

# Warna peta profesional (Publication-Quality Cartographic Palette)
COLORS = {
    "land": "#f0ece3",
    "water": "#cde4f2",
    "ocean_deep": "#a8cce0",
    "border": "#2c3e50",
    "border_light": "#7f8c8d",
    "highlight": "#c0392b",
    "highlight_glow": "#e74c3c",
    "fill_high": "#1a9850",
    "fill_mid_high": "#91cf60",
    "fill_mid": "#fee08b",
    "fill_mid_low": "#fc8d59",
    "fill_low": "#d73027",
    "grid": "#95a5a6",
    "grid_label": "#5d6d7e",
    "title_bg": "#1a1a2e",
    "title_accent": "#2980b9",
    "inset_bg": "#eef2f5",
    "inset_highlight": "#e74c3c",
    "frame": "#1a1a2e",
    "frame_outer": "#34495e",
    "info_bg": "#fafbfc",
    "annotation_bg": "#fffde7",
    "annotation_border": "#5d4e37",
}


def load_geojson():
    """Muat GeoJSON batas administrasi NTB."""
    if not os.path.exists(GEOJSON_PATH):
        print(f"⚠️ GeoJSON tidak ditemukan: {GEOJSON_PATH}")
        return None
    with open(GEOJSON_PATH, "r") as f:
        return json.load(f)


def load_raw_data():
    """Muat data audit satelit."""
    if not os.path.exists(RAW_DATA_PATH):
        return []
    with open(RAW_DATA_PATH, "r") as f:
        return json.load(f)


def extract_polygon_coords(geometry):
    """
    Ekstrak koordinat dari geometry GeoJSON.
    Mendukung Polygon, MultiPolygon, dan GeometryCollection.
    Returns list of (lons, lats) tuples per ring.
    """
    rings = []
    geom_type = geometry.get("type", "")

    if geom_type == "Polygon":
        for ring in geometry.get("coordinates", []):
            coords = np.array(ring)
            if len(coords) > 0:
                rings.append((coords[:, 0], coords[:, 1]))

    elif geom_type == "MultiPolygon":
        for polygon in geometry.get("coordinates", []):
            for ring in polygon:
                coords = np.array(ring)
                if len(coords) > 0:
                    rings.append((coords[:, 0], coords[:, 1]))

    elif geom_type == "GeometryCollection":
        for geom in geometry.get("geometries", []):
            rings.extend(extract_polygon_coords(geom))

    return rings


def get_ndvi_color(ndvi_val):
    """Map NDVI value to color for choropleth (5-level classification)."""
    if ndvi_val is None:
        return "#cccccc"
    if ndvi_val >= 0.7:
        return COLORS["fill_high"]
    elif ndvi_val >= 0.55:
        return COLORS["fill_mid_high"]
    elif ndvi_val >= 0.4:
        return COLORS["fill_mid"]
    elif ndvi_val >= 0.25:
        return COLORS["fill_mid_low"]
    else:
        return COLORS["fill_low"]


def get_site_metrics(site_id, raw_data_list):
    """Cari metrik audit untuk site tertentu."""
    for item in raw_data_list:
        if item.get("site_id") == site_id:
            return item
    return None


def draw_scale_bar(ax, lon_center, lat_bottom, km_length=20):
    """
    Gambar skala peta horizontal dalam kilometer.
    Menggunakan konversi derajat ke km pada lintang tertentu.
    """
    # Konversi km ke derajat longitude pada lintang tertentu
    km_per_deg_lon = 111.32 * np.cos(np.radians(lat_bottom))
    deg_length = km_length / km_per_deg_lon

    y = lat_bottom
    x_start = lon_center - deg_length / 2
    x_end = lon_center + deg_length / 2

    # Bar utama (alternating black/white)
    n_segments = 4
    seg_len = deg_length / n_segments
    for i in range(n_segments):
        color = "black" if i % 2 == 0 else "white"
        ax.plot(
            [x_start + i * seg_len, x_start + (i + 1) * seg_len],
            [y, y], color=color, linewidth=4,
            solid_capstyle='butt', zorder=20
        )
        # Border
        ax.plot(
            [x_start + i * seg_len, x_start + (i + 1) * seg_len],
            [y, y], color="black", linewidth=5,
            solid_capstyle='butt', zorder=19
        )

    # Label km
    ax.text(x_start, y - 0.015, "0", fontsize=6, ha='center', va='top',
            fontweight='bold', zorder=20)
    ax.text(x_end, y - 0.015, f"{km_length} km", fontsize=6, ha='center',
            va='top', fontweight='bold', zorder=20)
    ax.text(lon_center, y - 0.015, f"{km_length // 2}", fontsize=5,
            ha='center', va='top', color='#555', zorder=20)


def draw_north_arrow(ax, x, y, size=0.06):
    """Gambar panah utara (North Arrow) profesional."""
    # Menggunakan axes fraction coordinates
    arrow_ax = ax.inset_axes([x, y, size, size * 2.2], transform=ax.transAxes)
    arrow_ax.set_xlim(-1, 1)
    arrow_ax.set_ylim(-1, 2.5)
    arrow_ax.axis('off')

    # Panah utama
    arrow_ax.fill(
        [0, -0.4, 0, 0.4],
        [2.2, 0.3, 0.8, 0.3],
        color='black', zorder=10
    )
    # Sisi kanan (putih)
    arrow_ax.fill(
        [0, 0, 0.4],
        [2.2, 0.8, 0.3],
        color='white', edgecolor='black', linewidth=0.5, zorder=11
    )
    # Huruf N
    arrow_ax.text(0, -0.5, "N", fontsize=9, fontweight='bold',
                  ha='center', va='center', color='black')
    # Lingkaran dekoratif
    circle = plt.Circle((0, 0.8), 0.15, color='black', fill=True, zorder=12)
    arrow_ax.add_patch(circle)


def draw_coordinate_grid(ax, bounds, step=0.25):
    """Gambar grid koordinat (graticule) dengan label."""
    lon_min, lon_max = bounds[0], bounds[1]
    lat_min, lat_max = bounds[2], bounds[3]

    # Grid lines longitude
    for lon in np.arange(np.floor(lon_min * 4) / 4, lon_max + step, step):
        if lon_min <= lon <= lon_max:
            ax.axvline(x=lon, color=COLORS["grid"], linewidth=0.3,
                       alpha=0.5, linestyle='--', zorder=2)
            ax.text(lon, lat_min - 0.02, f"{lon:.2f}°E", fontsize=5,
                    ha='center', va='top', color='#555', rotation=0)

    # Grid lines latitude
    for lat in np.arange(np.floor(lat_min * 4) / 4, lat_max + step, step):
        if lat_min <= lat <= lat_max:
            ax.axhline(y=lat, color=COLORS["grid"], linewidth=0.3,
                       alpha=0.5, linestyle='--', zorder=2)
            ax.text(lon_min - 0.02, lat, f"{abs(lat):.2f}°S", fontsize=5,
                    ha='right', va='center', color='#555')


def draw_inset_map(fig, ax_main, geojson_data, highlight_site, position):
    """
    Gambar peta inset (locator map) yang menunjukkan posisi
    wilayah target dalam konteks Pulau Lombok-Sumbawa.
    """
    ax_inset = fig.add_axes(position)
    ax_inset.set_facecolor(COLORS["water"])

    # Gambar semua kabupaten
    for feature in geojson_data.get("features", []):
        name = feature["properties"].get("ADM2_NAME", "")
        geometry = feature.get("geometry", {})
        rings = extract_polygon_coords(geometry)

        for lons, lats in rings:
            color = COLORS["highlight"] if name == highlight_site else COLORS["land"]
            edge = "red" if name == highlight_site else "#666"
            lw = 1.5 if name == highlight_site else 0.3
            ax_inset.fill(lons, lats, color=color, alpha=0.7,
                         edgecolor=edge, linewidth=lw)

    ax_inset.set_xlim(NTB_BOUNDS["lon_min"], NTB_BOUNDS["lon_max"])
    ax_inset.set_ylim(NTB_BOUNDS["lat_min"], NTB_BOUNDS["lat_max"])
    ax_inset.set_aspect('equal')

    # Label
    ax_inset.set_title("PETA LOKASI", fontsize=6, fontweight='bold',
                       pad=2, color='#333')
    ax_inset.tick_params(labelsize=4, length=2)

    # Border inset
    for spine in ax_inset.spines.values():
        spine.set_edgecolor('#333')
        spine.set_linewidth(1.5)

    return ax_inset


def draw_legend(ax, has_audit_data=True):
    """Gambar legenda peta (5-level NDVI classification)."""
    legend_elements = [
        mpatches.Patch(facecolor=COLORS["fill_high"], edgecolor='#333',
                       linewidth=0.5, label='NDVI Tinggi (≥ 0.70)'),
        mpatches.Patch(facecolor=COLORS["fill_mid_high"], edgecolor='#333',
                       linewidth=0.5, label='NDVI Sedang-Tinggi (0.55–0.69)'),
        mpatches.Patch(facecolor=COLORS["fill_mid"], edgecolor='#333',
                       linewidth=0.5, label='NDVI Sedang (0.40–0.54)'),
        mpatches.Patch(facecolor=COLORS["fill_mid_low"], edgecolor='#333',
                       linewidth=0.5, label='NDVI Sedang-Rendah (0.25–0.39)'),
        mpatches.Patch(facecolor=COLORS["fill_low"], edgecolor='#333',
                       linewidth=0.5, label='NDVI Rendah (< 0.25)'),
        mpatches.Patch(facecolor=COLORS["land"], edgecolor='#999',
                       linewidth=0.5, label='Belum Diaudit'),
        Line2D([0], [0], color=COLORS["border"], linewidth=1.2,
               linestyle='-', label='Batas Administrasi'),
        Line2D([0], [0], color=COLORS["grid"], linewidth=0.5,
               linestyle='--', label='Grid Koordinat'),
    ]

    if has_audit_data:
        legend_elements.append(
            Line2D([0], [0], marker='o', color='w', markerfacecolor='red',
                   markersize=6, label='Titik Audit')
        )

    leg = ax.legend(
        handles=legend_elements,
        loc='lower left',
        fontsize=5,
        title='LEGENDA',
        title_fontsize=6,
        frameon=True,
        fancybox=True,
        shadow=True,
        framealpha=0.96,
        edgecolor='#333',
        borderpad=0.8,
        labelspacing=0.4,
        handlelength=1.5,
    )
    leg.get_title().set_fontweight('bold')
    return leg


def draw_info_box(fig, site_id, site_metrics, projection_text):
    """
    Gambar kotak informasi di bagian bawah peta berisi:
    - Sumber Data dan Tahun Pembuatan
    - Sistem Proyeksi dan Datum
    - Nama Pembuat
    """
    now = datetime.datetime.now()
    year = now.strftime("%Y")
    date_str = now.strftime("%d %B %Y")

    source = "Sentinel-2 MSI (ESA/Copernicus), Sentinel-1 SAR (ESA/Copernicus)"
    if site_metrics:
        src = site_metrics.get("biomass_data_source", "")
        if "REAL" in src:
            source = "Google Earth Engine — " + source
        else:
            source = "Mode Simulasi — " + source

    info_lines = [
        f"Sumber Data  : {source}",
        f"Tahun Pembuatan  : {year}  |  Tanggal Cetak: {date_str}",
        f"Sistem Proyeksi  : {projection_text}",
        f"Nama Pembuat : Rizki Agustiawan",
    ]

    info_text = "\n".join(info_lines)
    fig.text(
        0.5, 0.025, info_text,
        fontsize=6, ha='center', va='bottom',
        fontfamily='monospace',
        bbox=dict(
            boxstyle='round,pad=0.6',
            facecolor='white',
            edgecolor='#333',
            linewidth=1,
            alpha=0.95
        )
    )


def generate_site_map(site_id, geojson_data, raw_data_list, output_dir=None):
    """
    Generate peta cetak profesional untuk satu lokasi.

    Parameters:
        site_id: Nama kabupaten/kota (e.g. "Sumbawa Barat")
        geojson_data: Dict GeoJSON lengkap NTB
        raw_data_list: List dict hasil audit dari raw_data.json
        output_dir: Direktori output (default: shared_data/maps/)

    Returns:
        str: Path file PNG yang dihasilkan
    """
    if output_dir is None:
        output_dir = MAP_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    site_metrics = get_site_metrics(site_id, raw_data_list)

    # ─── Setup Figure (A3 landscape, 300 DPI) ────────────────────────
    fig = plt.figure(figsize=(16.54, 11.69), dpi=300, facecolor='white')

    # Margin untuk info box di bawah
    ax = fig.add_axes([0.08, 0.10, 0.82, 0.78])
    ax.set_facecolor(COLORS["water"])

    # ─── Cari geometry target ────────────────────────────────────────
    target_feature = None
    all_features = geojson_data.get("features", [])

    for feat in all_features:
        name = feat["properties"].get("ADM2_NAME", "")
        if name == site_id:
            target_feature = feat
            break

    if not target_feature:
        print(f"⚠️ Site '{site_id}' tidak ditemukan dalam GeoJSON!")
        plt.close(fig)
        return None

    # ─── Hitung bounds untuk target site ─────────────────────────────
    target_rings = extract_polygon_coords(target_feature["geometry"])
    all_lons = np.concatenate([r[0] for r in target_rings])
    all_lats = np.concatenate([r[1] for r in target_rings])

    lon_min, lon_max = all_lons.min(), all_lons.max()
    lat_min, lat_max = all_lats.min(), all_lats.max()

    # Padding 15%
    pad_lon = (lon_max - lon_min) * 0.15
    pad_lat = (lat_max - lat_min) * 0.15
    bounds = [
        lon_min - pad_lon, lon_max + pad_lon,
        lat_min - pad_lat, lat_max + pad_lat
    ]

    # ─── Gambar semua kabupaten (background) ─────────────────────────
    for feat in all_features:
        name = feat["properties"].get("ADM2_NAME", "")
        geometry = feat.get("geometry", {})
        rings = extract_polygon_coords(geometry)

        for lons, lats in rings:
            if name == site_id:
                # Warnai berdasarkan NDVI jika ada data audit
                ndvi = site_metrics.get("satellite_ndvi_90") if site_metrics else None
                color = get_ndvi_color(ndvi) if ndvi else "#90EE90"
                ax.fill(lons, lats, color=color, alpha=0.6,
                       edgecolor=COLORS["border"], linewidth=1.5, zorder=5)
                # Border tebal untuk target
                ax.plot(lons, lats, color=COLORS["highlight"],
                       linewidth=2.0, zorder=6)
            else:
                ax.fill(lons, lats, color=COLORS["land"], alpha=0.4,
                       edgecolor='#999', linewidth=0.5, zorder=3)

    # ─── Label kabupaten target ──────────────────────────────────────
    centroid_lon = (lon_min + lon_max) / 2
    centroid_lat = (lat_min + lat_max) / 2

    ax.text(centroid_lon, centroid_lat, site_id.upper(),
            fontsize=9, fontweight='bold', ha='center', va='center',
            color='#1a1a2e', zorder=15,
            path_effects=[pe.withStroke(linewidth=3, foreground='white')])

    # ─── Marker audit point ──────────────────────────────────────────
    if site_metrics:
        ax.plot(centroid_lon, centroid_lat + 0.02, 'o',
                color='red', markersize=8, markeredgecolor='white',
                markeredgewidth=1.5, zorder=16)

        # Annotasi metrik (Clean professional annotation box)
        ndvi = site_metrics.get("satellite_ndvi_90", "N/A")
        biomass = site_metrics.get("estimated_biomass", "N/A")
        carbon = site_metrics.get("estimated_carbon", "N/A")
        trees = site_metrics.get("vision_tree_count", "N/A")
        status = site_metrics.get("ecological_status", "N/A")

        ann_text = (
            f"━━ HASIL AUDIT SATELIT ━━\n"
            f"  NDVI         : {ndvi}\n"
            f"  Biomassa  : {biomass} Mg/ha\n"
            f"  Karbon      : {carbon} Mg C/ha\n"
            f"  Pohon        : {trees}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"  Status: {status}"
        )
        ax.annotate(
            ann_text,
            xy=(centroid_lon, centroid_lat + 0.02),
            xytext=(centroid_lon + (lon_max - lon_min) * 0.3,
                    centroid_lat + (lat_max - lat_min) * 0.3),
            fontsize=5, fontweight='normal',
            fontfamily='monospace',
            bbox=dict(boxstyle='round,pad=0.6',
                     facecolor=COLORS["annotation_bg"],
                     edgecolor=COLORS["annotation_border"],
                     alpha=0.94, linewidth=0.8),
            arrowprops=dict(arrowstyle='->', color='#555',
                          lw=0.8, connectionstyle='arc3,rad=0.15'),
            zorder=17
        )

    # ─── Set map bounds ──────────────────────────────────────────────
    ax.set_xlim(bounds[0], bounds[1])
    ax.set_ylim(bounds[2], bounds[3])
    ax.set_aspect('equal')

    # ─── 1. JUDUL PETA (Professional Title Block) ────────────────────
    title_main = "PETA MONITORING LINGKUNGAN & ESG"
    title_sub = f"Kabupaten/Kota {site_id} — Provinsi Nusa Tenggara Barat"

    fig.text(0.5, 0.955, title_main, fontsize=16, fontweight='bold',
             ha='center', va='center', color=COLORS["title_bg"],
             fontfamily='sans-serif',
             path_effects=[pe.withStroke(linewidth=0.5, foreground='#888')])

    # Accent line under title
    fig.patches.append(plt.Rectangle(
        (0.25, 0.941), 0.50, 0.002,
        transform=fig.transFigure, facecolor=COLORS["title_accent"],
        edgecolor='none', zorder=50
    ))

    fig.text(0.5, 0.928, title_sub, fontsize=9.5, ha='center', va='center',
             color='#4a5568', style='italic', fontfamily='sans-serif')

    # ─── 2. SKALA PETA ───────────────────────────────────────────────
    scale_lon = (bounds[0] + bounds[1]) / 2
    scale_lat = bounds[2] + (bounds[3] - bounds[2]) * 0.05
    map_width_km = (bounds[1] - bounds[0]) * 111.32 * np.cos(np.radians(centroid_lat))
    if map_width_km > 80:
        bar_km = 20
    elif map_width_km > 40:
        bar_km = 10
    else:
        bar_km = 5
    draw_scale_bar(ax, scale_lon, scale_lat, km_length=bar_km)

    # ─── 3. NORTH ARROW ─────────────────────────────────────────────
    draw_north_arrow(ax, 0.90, 0.78, size=0.06)

    # ─── 4. LEGENDA ──────────────────────────────────────────────────
    draw_legend(ax, has_audit_data=(site_metrics is not None))

    # ─── 5. GRID KOORDINAT ───────────────────────────────────────────
    grid_step = 0.25
    map_span = max(bounds[1] - bounds[0], bounds[3] - bounds[2])
    if map_span < 0.5:
        grid_step = 0.1
    elif map_span < 1.0:
        grid_step = 0.15
    draw_coordinate_grid(ax, bounds, step=grid_step)

    # ─── 6. INSET PETA ──────────────────────────────────────────────
    draw_inset_map(fig, ax, geojson_data, site_id,
                   position=[0.72, 0.12, 0.20, 0.22])

    # ─── 7, 8, 9. INFO BOX (Sumber, Proyeksi, Pembuat) ──────────────
    projection_text = "WGS 1984 (EPSG:4326) — Geographic Coordinate System, Datum: WGS84"
    draw_info_box(fig, site_id, site_metrics, projection_text)

    # ─── Axis labels (refined styling) ───────────────────────────────
    ax.set_xlabel("Bujur (Longitude)", fontsize=7, labelpad=8,
                  color=COLORS["grid_label"], fontweight='medium')
    ax.set_ylabel("Lintang (Latitude)", fontsize=7, labelpad=8,
                  color=COLORS["grid_label"], fontweight='medium')
    ax.tick_params(labelsize=6, colors=COLORS["grid_label"],
                   direction='out', length=3, width=0.6)

    # ─── Double Neatline Frame ───────────────────────────────────────
    for spine in ax.spines.values():
        spine.set_edgecolor(COLORS["frame"])
        spine.set_linewidth(1.8)

    # Outer frame (decorative border)
    outer = plt.Rectangle(
        (0.06, 0.08), 0.86, 0.82,
        transform=fig.transFigure, fill=False,
        edgecolor=COLORS["frame_outer"], linewidth=0.8,
        linestyle='-', zorder=40
    )
    fig.patches.append(outer)

    # ─── Save (High Quality) ─────────────────────────────────────────
    safe_name = site_id.replace(" ", "_").lower()
    filename = f"peta_{safe_name}_{datetime.datetime.now().strftime('%Y%m%d')}.png"
    filepath = os.path.join(output_dir, filename)
    fig.savefig(filepath, dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none',
                pad_inches=0.15)
    plt.close(fig)

    print(f"  🗺️  [{site_id}] Peta berhasil dicetak: {filepath}")
    return filepath


def generate_all_maps(geojson_data=None, raw_data_list=None):
    """
    Generate peta cetak untuk SEMUA lokasi dalam GeoJSON.
    Ini adalah fungsi utama yang dipanggil oleh pipeline.

    Returns:
        list: Daftar path file PNG yang dihasilkan
    """
    if geojson_data is None:
        geojson_data = load_geojson()
    if raw_data_list is None:
        raw_data_list = load_raw_data()

    if geojson_data is None:
        print("❌ Gagal memuat GeoJSON, tidak dapat mencetak peta.")
        return []

    output_paths = []
    features = geojson_data.get("features", [])

    print("\n" + "=" * 60)
    print("  GeoESG Map Printer v1.0 — Cetak Peta Kartografi")
    print("=" * 60)
    print(f"  📍 Total lokasi: {len(features)}")
    print(f"  📊 Data audit tersedia: {len(raw_data_list)} site")
    print()

    for feat in features:
        site_id = feat["properties"].get("ADM2_NAME", "Unknown")
        try:
            path = generate_site_map(site_id, geojson_data, raw_data_list)
            if path:
                output_paths.append(path)
        except Exception as e:
            print(f"  ❌ [{site_id}] Gagal mencetak peta: {e}")

    print(f"\n📁 {len(output_paths)} peta berhasil dicetak ke: {MAP_OUTPUT_DIR}")
    print("✅ Proses cetak peta selesai!")
    return output_paths


# ─── Eksekusi Mandiri ────────────────────────────────────────────────────────
if __name__ == "__main__":
    paths = generate_all_maps()
    if paths:
        print(f"\n🗺️  Total {len(paths)} peta berhasil di-generate:")
        for p in paths:
            print(f"   → {p}")
