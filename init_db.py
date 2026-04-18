import sqlite3


def init_db():
    conn = sqlite3.connect("shared_data/geoesg.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id TEXT,
            sat_ndvi REAL,
            ground_ndvi REAL,
            trust_score REAL,
            biomass REAL,
            carbon REAL,
            status TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Database SQLite berhasil diinisialisasi di shared_data/geoesg.db")


if __name__ == "__main__":
    init_db()
