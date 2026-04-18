from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import sqlite3, subprocess, json, os, geopandas as gpd
from pydantic import BaseModel

app = FastAPI()


def init_db():
    conn = sqlite3.connect("shared_data/geoesg.db")
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, site_id TEXT, sat_ndvi REAL, 
        ground_ndvi REAL, trust_score REAL, biomass REAL, carbon REAL, 
        status TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    conn.close()


init_db()

# ... (lanjutkan route POST /generate-esg-report dan API history)
