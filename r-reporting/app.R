# =============================================================================
# GeoESG A.E.C.O — R Spatial Dashboard v2.0
# Automated ESG Compliance Observer — Cartographic Map Viewer
# =============================================================================
# Elemen Kartografi Wajib:
#   1. Scale Bar (Metric)        5. North Arrow
#   2. Legend / Color Ramp       6. Mini Map / Locator Map
#   3. Graticule Grid            7. Custom Attribution
#   4. Map Title Overlay
# =============================================================================

library(shiny)
library(leaflet)
library(jsonlite)
library(ggplot2)
library(sf)
library(dplyr)
library(htmltools)
library(htmlwidgets)


# ─── 1. Load Data ───────────────────────────────────────────────────────────
# (UNCHANGED — logic data asli dipertahankan sepenuhnya)
tryCatch(
  {
    ntb_map <- st_read("../shared_data/batas_ntb.geojson", quiet = TRUE)
    ntb_map <- sf::st_collection_extract(ntb_map, "POLYGON")
    raw_data <- fromJSON("../shared_data/raw_data.json")

    map_data <- ntb_map %>%
      filter(ADM2_NAME == raw_data$site_id) %>%
      mutate(
        ndvi = raw_data$satellite_ndvi_90,
        carbon = raw_data$estimated_carbon,
        biomass = raw_data$estimated_biomass,
        radar_vh = raw_data$radar_vh_db,
        source = raw_data$biomass_data_source
      )
  },
  error = function(e) {
    message("Menunggu data dari pipeline...")
  }
)


# ─── NDVI Color Palette ─────────────────────────────────────────────────────
ndvi_colors <- c("#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#91cf60", "#1a9850")
ndvi_pal <- colorNumeric(palette = ndvi_colors, domain = c(0, 1), na.color = "#cccccc")


# ─── 2. UI ──────────────────────────────────────────────────────────────────
ui <- fluidPage(
  tags$head(
    tags$link(
      rel = "stylesheet",
      href = "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"
    ),
    tags$style(HTML("
      body {
        background-color: #0f172a; color: #e2e8f0;
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
      }
      .well {
        background-color: #1e293b; border: 1px solid #334155;
        border-radius: 14px; box-shadow: 0 4px 16px rgba(0,0,0,0.3);
      }
      h2 { color: #38bdf8; font-weight: 700; }
      h3 { color: #e2e8f0; font-weight: 600; }
      pre {
        background-color: #0f172a; color: #38bdf8;
        border: 1px solid #334155; border-radius: 10px;
        padding: 12px; font-family: 'JetBrains Mono', monospace;
      }
      hr { border-color: #334155; }

      /* ── Leaflet Overrides ── */
      .leaflet-container {
        border-radius: 14px; border: 1px solid #334155;
        box-shadow: 0 6px 20px rgba(0,0,0,0.4);
      }
      .info.legend {
        background: rgba(15,23,42,0.92) !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
        border-radius: 10px !important;
        padding: 10px 14px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
        font-family: 'Inter', sans-serif !important;
      }
      .info.legend i { border-radius: 2px; }
      .leaflet-control-scale-line {
        background: rgba(15,23,42,0.88) !important;
        color: #e2e8f0 !important; border-color: #38bdf8 !important;
        font-weight: 600 !important; border-radius: 4px !important;
        font-size: 11px !important;
      }
      .leaflet-control-minimap {
        border: 2px solid #38bdf8 !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.5) !important;
      }
      .leaflet-control-attribution {
        background: rgba(15,23,42,0.88) !important;
        color: #94a3b8 !important; font-size: 10px !important;
        border-radius: 6px 0 0 0 !important;
      }
      .leaflet-control-attribution a { color: #38bdf8 !important; }

      /* ── Map Title Control ── */
      .map-title-box {
        background: linear-gradient(135deg, rgba(15,23,42,0.96), rgba(30,41,59,0.96));
        padding: 12px 22px; border-radius: 12px;
        border: 1px solid rgba(56,189,248,0.3);
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        text-align: center; backdrop-filter: blur(10px);
        pointer-events: none;
      }
      .map-title-box h3 {
        margin: 0; font-size: 14px; font-weight: 700;
        color: #38bdf8; letter-spacing: 0.8px;
      }
      .map-title-box .sub {
        margin: 4px 0 0; font-size: 10.5px;
        color: #94a3b8; font-style: italic;
      }

      /* ── North Arrow Control ── */
      .north-arrow-box {
        background: rgba(15,23,42,0.92); border: 1px solid #334155;
        border-radius: 10px; padding: 8px 6px 4px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.4); text-align: center;
      }
    "))
  ),

  titlePanel(
    div(
      style = "display:flex; align-items:center; gap:12px; padding:6px 0;",
      span("\U0001F30D", style = "font-size:28px;"),
      div(
        h2("GeoESG A.E.C.O", style = "margin:0; font-size:1.4rem;"),
        p("Automated ESG Compliance Observer \u2014 R Spatial Dashboard",
          style = "margin:0; font-size:0.78rem; color:#64748b;")
      )
    )
  ),

  sidebarLayout(
    sidebarPanel(
      width = 3,
      h3(ifelse(exists("raw_data"), raw_data$site_id, "Memuat Data...")),
      p("Status Audit: ", span("VALID", style = "color: #10b981; font-weight: bold;")),
      hr(),
      strong("\U0001F4CA Metrik Satelit:"),
      verbatimTextOutput("metrics"),
      hr(),
      strong("\U0001F4C8 Capaian Karbon:"),
      plotOutput("carbonChart", height = "200px")
    ),
    mainPanel(
      width = 9,
      leafletOutput("map", height = "650px")
    )
  )
)


# ─── 3. Server ──────────────────────────────────────────────────────────────
server <- function(input, output, session) {

  output$map <- renderLeaflet({
    req(map_data)

    # ── Nilai NDVI untuk pewarnaan dinamis ──
    current_ndvi <- map_data$ndvi[1]
    fill_color <- ndvi_pal(current_ndvi)
    site_name <- map_data$ADM2_NAME[1]

    # ── Centroid untuk setView (plain numeric, no names) ──
    ctr_pt <- st_centroid(st_union(map_data))
    ctr_xy <- st_coordinates(ctr_pt)
    ctr_lng <- as.numeric(ctr_xy[1, 1])
    ctr_lat <- as.numeric(ctr_xy[1, 2])

    # ── Bounding box untuk graticule (plain numeric) ──
    bb <- as.numeric(st_bbox(map_data))  # c(xmin, ymin, xmax, ymax)
    names(bb) <- c("xmin", "ymin", "xmax", "ymax")
    pad <- 0.15
    lon_span <- bb["xmax"] - bb["xmin"]
    lat_span <- bb["ymax"] - bb["ymin"]

    # ── 3. GRATICULE: buat grid lines sebagai sf ──
    step <- ifelse(max(lon_span, lat_span) < 0.5, 0.1,
            ifelse(max(lon_span, lat_span) < 1.0, 0.15, 0.25))

    lat_seq <- seq(floor(bb["ymin"] / step) * step,
                   ceiling(bb["ymax"] / step) * step, by = step)
    lon_seq <- seq(floor(bb["xmin"] / step) * step,
                   ceiling(bb["xmax"] / step) * step, by = step)

    glines <- list()
    for (lat in lat_seq) {
      glines <- c(glines, list(st_linestring(matrix(
        c(bb["xmin"] - pad, lat, bb["xmax"] + pad, lat), ncol = 2, byrow = TRUE
      ))))
    }
    for (lng in lon_seq) {
      glines <- c(glines, list(st_linestring(matrix(
        c(lng, bb["ymin"] - pad, lng, bb["ymax"] + pad), ncol = 2, byrow = TRUE
      ))))
    }
    grat_sf <- st_sfc(glines, crs = 4326)

    # Label data frames untuk graticule ticks (unname to avoid jsonlite warnings)
    lat_labels <- data.frame(
      lng = unname(rep(bb["xmin"] - 0.01, length(lat_seq))),
      lat = unname(lat_seq),
      lab = sprintf("%.2f\u00B0S", abs(lat_seq)),
      stringsAsFactors = FALSE, row.names = NULL
    )
    lon_labels <- data.frame(
      lng = unname(lon_seq),
      lat = unname(rep(bb["ymin"] - 0.01, length(lon_seq))),
      lab = sprintf("%.2f\u00B0E", lon_seq),
      stringsAsFactors = FALSE, row.names = NULL
    )

    # ── 4. MAP TITLE overlay HTML ──
    title_html <- as.character(tags$div(
      class = "map-title-box",
      tags$h3("PETA MONITORING LINGKUNGAN & ESG"),
      tags$p(class = "sub",
        paste0("Kab/Kota ", site_name,
               " \u2014 Provinsi Nusa Tenggara Barat"))
    ))

    # ── 5. NORTH ARROW overlay HTML (SVG) ──
    north_html <- as.character(tags$div(
      class = "north-arrow-box",
      HTML(paste0(
        '<svg width="32" height="48" viewBox="0 0 32 48">',
        '<polygon points="16,2 8,28 16,22 24,28" ',
        'fill="#38bdf8" stroke="#0f172a" stroke-width="1.5"/>',
        '<polygon points="16,2 24,28 16,22" ',
        'fill="#1e40af" stroke="#0f172a" stroke-width="1.5"/>',
        '<text x="16" y="43" text-anchor="middle" fill="#e2e8f0" ',
        'font-size="12" font-weight="bold" font-family="Inter,sans-serif">',
        'N</text></svg>'
      ))
    ))

    # ── 7. CUSTOM ATTRIBUTION ──
    custom_attr <- paste0(
      "Data: Sentinel-2/1 (ESA/Copernicus) via GEE | ",
      "Batas: BIG Indonesia | ",
      "Akuisisi: ", format(Sys.Date(), "%Y"), " | ",
      "Pembuat: <b>Rizki Agustiawan</b> | ",
      "EPSG:4326 (WGS84)"
    )

    # ── NTB background (semua kabupaten, abu-abu tipis) ──
    bg_data <- ntb_map %>% filter(ADM2_NAME != site_name)

    # ═══════════════════════════════════════════════════════════════
    #  BUILD LEAFLET MAP
    # ═══════════════════════════════════════════════════════════════
    m <- leaflet(map_data) %>%

      # Base Tile + Attribution
      addProviderTiles(
        providers$Esri.WorldImagery,
        options = providerTileOptions(attribution = custom_attr)
      ) %>%

      # Background NTB polygons (konteks regional)
      addPolygons(
        data = bg_data,
        fillColor = "#64748b", weight = 0.8, opacity = 0.5,
        color = "#475569", fillOpacity = 0.15,
        group = "Background"
      ) %>%

      # ── DATA POLYGON (logic asli — TIDAK DIUBAH) ──
      addPolygons(
        fillColor = fill_color,
        weight = 2, opacity = 1, color = "white",
        dashArray = "3", fillOpacity = 0.7,
        label = ~ paste0(ADM2_NAME, ": NDVI ", ndvi),
        popup = ~ paste0(
          "<b>Wilayah: </b>", ADM2_NAME, "<br>",
          "<b>Estimasi Karbon: </b>", carbon, " Mg C/ha"
        )
      ) %>%

      # View
      setView(lng = ctr_lng, lat = ctr_lat, zoom = 10) %>%

      # ── 1. SCALE BAR (Metric) ──
      addScaleBar(
        position = "bottomleft",
        options = scaleBarOptions(
          metric = TRUE, imperial = FALSE, maxWidth = 200
        )
      ) %>%

      # ── 2. LEGEND / NDVI COLOR RAMP ──
      addLegend(
        position = "bottomright",
        pal = ndvi_pal,
        values = seq(0, 1, by = 0.1),
        title = "Indeks NDVI",
        labFormat = labelFormat(digits = 1),
        opacity = 0.9
      ) %>%

      # ── 3. GRATICULE LINES ──
      addPolylines(
        data = grat_sf,
        color = "#94a3b8", weight = 0.5, opacity = 0.35,
        dashArray = "6,4", group = "Graticule"
      ) %>%

      # Graticule tick labels (latitude)
      addLabelOnlyMarkers(
        data = lat_labels, lng = ~lng, lat = ~lat,
        label = ~lab,
        labelOptions = labelOptions(
          noHide = TRUE, textOnly = TRUE, direction = "left",
          style = list(
            "color" = "#94a3b8", "font-size" = "9px",
            "font-weight" = "600", "font-family" = "monospace"
          )
        ),
        group = "Graticule"
      ) %>%

      # Graticule tick labels (longitude)
      addLabelOnlyMarkers(
        data = lon_labels, lng = ~lng, lat = ~lat,
        label = ~lab,
        labelOptions = labelOptions(
          noHide = TRUE, textOnly = TRUE, direction = "bottom",
          style = list(
            "color" = "#94a3b8", "font-size" = "9px",
            "font-weight" = "600", "font-family" = "monospace"
          )
        ),
        group = "Graticule"
      ) %>%

      # ── 4. MAP TITLE OVERLAY ──
      addControl(html = title_html, position = "topleft") %>%

      # ── 5. NORTH ARROW ──
      addControl(html = north_html, position = "topright") %>%

      # ── 6. MINI MAP / LOCATOR MAP ──
      addMiniMap(
        tiles = providers$Esri.WorldStreetMap,
        position = "bottomright",
        toggleDisplay = TRUE, minimized = FALSE,
        width = 150, height = 150,
        zoomLevelOffset = -5
      )

    m
  })

  # ── Metrics (UNCHANGED) ──
  output$metrics <- renderText({
    req(raw_data)
    paste0(
      "NDVI Optik: ", raw_data$satellite_ndvi_90, "\n",
      "Radar VH  : ", raw_data$radar_vh_db, " dB\n",
      "Biomassa  : ", raw_data$estimated_biomass, " Mg/ha\n",
      "Stok Karbon: ", raw_data$estimated_carbon, " Mg C/ha"
    )
  })

  # ── Carbon Chart (logic UNCHANGED, style enhanced) ──
  output$carbonChart <- renderPlot({
    req(raw_data)
    df <- data.frame(
      Kategori = c("Target", "Aktual"),
      Nilai = c(60, raw_data$estimated_carbon)
    )
    ggplot(df, aes(x = Kategori, y = Nilai, fill = Kategori)) +
      geom_bar(stat = "identity", width = 0.6) +
      theme_minimal(base_size = 12) +
      theme(
        plot.background = element_rect(fill = "#1e293b", color = NA),
        panel.background = element_rect(fill = "#1e293b", color = NA),
        text = element_text(color = "#e2e8f0", family = "sans"),
        axis.text = element_text(color = "#94a3b8"),
        panel.grid.major = element_line(color = "#334155"),
        panel.grid.minor = element_blank(),
        legend.position = "none",
        plot.title = element_text(color = "#38bdf8", face = "bold", size = 13)
      ) +
      labs(title = "Capaian Stok Karbon", y = "Mg C/ha", x = NULL) +
      scale_fill_manual(values = c("Aktual" = "#10b981", "Target" = "#475569"))
  })
}

# ─── BARIS SAKTI ─────────────────────────────────────────────────────────────
# Pastikan tidak ada karakter apa pun (bahkan spasi) setelah baris ini!
shinyApp(ui = ui, server = server)
