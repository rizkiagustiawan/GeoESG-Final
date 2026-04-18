from mcp.server.fastmcp import FastMCP
import httpx

# Inisialisasi server MCP
mcp = FastMCP("GeoESG_Agent")


@mcp.tool()
async def trigger_esg_audit(site_id: str, ground_truth_ndvi: float) -> str:
    """
    Memicu pipeline audit GeoESG untuk suatu wilayah di NTB.
    Gunakan tool ini HANYA ketika pengguna meminta untuk menjalankan audit ESG,
    mengecek risiko greenwashing, atau memicu pipeline.

    Args:
        site_id: Nama wilayah (contoh: "Wilayah_1", "Lombok Utara", atau sesuaikan dengan permintaan).
        ground_truth_ndvi: Nilai NDVI aktual di lapangan (antara 0.0 hingga 1.0).
    """
    url = "http://localhost:8000/generate-esg-report"
    payload = {"site_id": site_id, "ground_truth_ndvi": ground_truth_ndvi}

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
