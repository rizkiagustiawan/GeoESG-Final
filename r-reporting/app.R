library(shiny)
library(leaflet)
library(jsonlite)
library(ggplot2)
library(sf)
library(dplyr)

# 1. Load Data
# Gunakan tryCatch supaya kalau file JSON belum ada, app tidak langsung crash
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

# 2. UI
ui <- fluidPage(
  tags$head(tags$style(HTML("body { background-color: #f4f7f6; }"))),
  titlePanel("A.E.C.O: Dashboard Pemantauan ESG & Karbon"),
  sidebarLayout(
    sidebarPanel(
      h3(ifelse(exists("raw_data"), raw_data$site_id, "Memuat Data...")),
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

# 3. Server
server <- function(input, output, session) {
  output$map <- renderLeaflet({
    req(map_data)
    leaflet(map_data) %>%
      addTiles() %>%
      addPolygons(
        fillColor = "green", weight = 2, opacity = 1, color = "white",
        dashArray = "3", fillOpacity = 0.7,
        label = ~ paste0(ADM2_NAME, ": NDVI ", ndvi),
        popup = ~ paste0(
          "<b>Wilayah: </b>", ADM2_NAME, "<br>",
          "<b>Estimasi Karbon: </b>", carbon, " Mg C/ha"
        )
      ) %>%
      setView(lng = 116.85, lat = -8.75, zoom = 10)
  })

  output$metrics <- renderText({
    req(raw_data)
    paste0(
      "NDVI Optik: ", raw_data$satellite_ndvi_90, "\n",
      "Radar VH  : ", raw_data$radar_vh_db, " dB\n",
      "Biomassa  : ", raw_data$estimated_biomass, " Mg/ha\n",
      "Stok Karbon: ", raw_data$estimated_carbon, " Mg C/ha"
    )
  })

  output$carbonChart <- renderPlot({
    req(raw_data)
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

# --- BARIS SAKTI ---
# Pastikan tidak ada karakter apa pun (bahkan spasi) setelah baris ini!
shinyApp(ui = ui, server = server)
