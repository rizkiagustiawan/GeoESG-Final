library(shiny)
library(leaflet)
library(jsonlite)
library(ggplot2)
library(sf)
library(dplyr)

# 1. Load Data
# Membaca GeoJSON untuk poligon peta
ntb_map <- st_read("../shared_data/batas_ntb.geojson", quiet = TRUE)

# ---> INI BARIS SAKTI UNTUK MENGATASI ERROR MERAH <---
ntb_map <- sf::st_collection_extract(ntb_map, "POLYGON")

# Membaca Hasil Ekstraksi A.E.C.O
raw_data <- fromJSON("../shared_data/raw_data.json")

# Join Data Satelit ke Map berdasarkan ADM2_NAME
map_data <- ntb_map %>%
  filter(ADM2_NAME == raw_data$site_id) %>%
  mutate(
    ndvi = raw_data$satellite_ndvi_90,
    carbon = raw_data$estimated_carbon,
    biomass = raw_data$estimated_biomass,
    radar_vh = raw_data$radar_vh_db,
    source = raw_data$biomass_data_source
  )

# 2. UI - Wajah Dashboard
ui <- fluidPage(
  titlePanel("A.E.C.O: Dashboard Pemantauan ESG & Karbon"),
  sidebarLayout(
    sidebarPanel(
      h3(raw_data$site_id),
      p("Status Audit: ", span("VALID", style = "color: green; font-weight: bold;")),
      hr(),
      strong("Metrik Satelit:"),
      verbatimTextOutput("metrics"),
      hr(),
      plotOutput("carbonChart", height = "200px")
    ),
    mainPanel(
      leafletOutput("map", height = "600px")
    )
  )
)

# 3. Server - Otak Dashboard
server <- function(input, output, session) {
  output$map <- renderLeaflet({
    leaflet(map_data) %>%
      addTiles() %>%
      addPolygons(
        fillColor = "green",
        weight = 2,
        opacity = 1,
        color = "white",
        dashArray = "3",
        fillOpacity = 0.7,
        label = ~ paste0(ADM2_NAME, ": NDVI ", ndvi),
        popup = ~ paste0(
          "<b>Wilayah: </b>", ADM2_NAME, "<br>",
          "<b>Estimasi Karbon: </b>", carbon, " Mg C/ha<br>",
          "<b>Sumber Data: </b>", source, "<br>",
          "<b>Radar VH: </b>", radar_vh, " dB"
        )
      ) %>%
      setView(lng = 116.85, lat = -8.75, zoom = 10) # Fokus ke Sumbawa Barat
  })

  output$metrics <- renderText({
    paste0(
      "NDVI Optik: ", raw_data$satellite_ndvi_90, "\n",
      "Radar VH  : ", raw_data$radar_vh_db, " dB\n",
      "Biomassa  : ", raw_data$estimated_biomass, " Mg/ha\n",
      "Stok Karbon: ", raw_data$estimated_carbon, " Mg C/ha"
    )
  })

  output$carbonChart <- renderPlot({
    df <- data.frame(
      Kategori = c("Target", "Aktual"),
      Nilai = c(60, raw_data$estimated_carbon)
    )
    ggplot(df, aes(x = Kategori, y = Nilai, fill = Kategori)) +
      geom_bar(stat = "identity") +
      theme_minimal() +
      labs(title = "Capaian Stok Karbon", y = "Mg C/ha") +
      scale_fill_manual(values = c("Aktual" = "darkgreen", "Target" = "grey"))
  })
}

shinyApp(ui, server)
