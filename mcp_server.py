from mcp.server.fastmcp import FastMCP
import httpx

# Inisialisasi server MCP
mcp = FastMCP("GeoESG_Agent")


@mcp.tool()
async def trigger_esg_audit(site_id: str, ground_truth_biomass: float) -> str:
    """
    Memicu pipeline audit GeoESG untuk suatu wilayah di NTB.
    Gunakan tool ini HANYA ketika pengguna meminta untuk menjalankan audit ESG,
    mengecek risiko greenwashing, atau memicu pipeline.

    Args:
        site_id: Nama wilayah (contoh: "Sumbawa Barat", "Lombok Utara").
        ground_truth_biomass: Biomassa lapangan hasil pengukuran DBH (Mg/ha), misalnya 120.5.
    """
    url = "http://localhost:8000/generate-esg-report"
    payload = {"site_id": site_id, "ground_truth_biomass": ground_truth_biomass}

    try:
        async with httpx.AsyncClient() as client:
            # Mengirim perintah ke Docker FastAPI Anda
            response = await client.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                # Mengembalikan Markdown langsung ke Claude agar bisa dibaca dan diringkas
                return f"Audit berhasil dijalankan! Berikut adalah data laporannya:\n\n{data.get('report_markdown')}"
            else:
                return f"Gagal menjalankan audit dari server: {data}"
    except Exception as e:
        return f"Terjadi kesalahan saat menghubungi backend GeoESG: {str(e)}\nPastikan Docker container 'geoesg-server' sedang menyala."


if __name__ == "__main__":
    mcp.run()
