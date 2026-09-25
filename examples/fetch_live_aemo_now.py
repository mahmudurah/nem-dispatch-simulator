"""
Live AEMO Real-Time Market Monitor (Updated Every 5 Minutes)
=============================================================
Fetches the absolute latest live 5-minute dispatch interval directly
from AEMO NEMWEB (Reports/CURRENT/DispatchIS_Reports/).
"""

import requests
import zipfile
import io
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

NEMWEB_CURRENT_URL = "http://nemweb.com.au/Reports/CURRENT/DispatchIS_Reports/"

def get_latest_live_aemo_dispatch():
    """
    Download and parse the latest 5-minute dispatch interval from AEMO.
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connecting to AEMO NEMWEB live dispatch feed...")
    
    # 1. Scrape listing to find the newest 5-minute ZIP file
    resp = requests.get(NEMWEB_CURRENT_URL, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to access AEMO live feed (HTTP {resp.status_code})")
        
    soup = BeautifulSoup(resp.text, 'html.parser')
    zip_links = [a['href'] for a in soup.find_all('a') if a.get('href', '').endswith('.zip')]
    if not zip_links:
        raise RuntimeError("No live dispatch files found on NEMWEB.")
        
    latest_file_url = "http://nemweb.com.au" + zip_links[-1]
    filename = zip_links[-1].split('/')[-1]
    print(f" -> Found latest live file: {filename}")

    # 2. Download in-memory and parse CSV
    r = requests.get(latest_file_url, timeout=15)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    csv_filename = z.namelist()[0]
    
    lines = z.open(csv_filename).read().decode('utf-8').splitlines()

    # Parse Prices and Regional Demand
    prices = {}
    demand = {}
    timestamp = None

    for line in lines:
        parts = [p.strip().strip('"') for p in line.split(',')]
        if len(parts) < 10 or parts[0] != 'D':
            continue
            
        # Parse DISPATCH, PRICE
        if parts[1] == 'DISPATCH' and parts[2] == 'PRICE':
            timestamp = parts[4]
            region = parts[6]
            try:
                rrp = float(parts[9])
                prices[region] = rrp
            except ValueError:
                pass

        # Parse DISPATCH, REGIONSUM
        elif parts[1] == 'DISPATCH' and parts[2] == 'REGIONSUM':
            timestamp = parts[4]
            region = parts[6]
            try:
                tot_demand = float(parts[9])
                demand[region] = tot_demand
            except ValueError:
                pass

    df_live = pd.DataFrame({
        'Region': list(prices.keys()),
        'Demand_MW': [demand.get(r, 0.0) for r in prices.keys()],
        'Spot_Price_AUD_per_MWh': list(prices.values())
    })

    print(f"\n=======================================================")
    print(f" LIVE AEMO NEM DISPATCH AT {timestamp}")
    print(f"=======================================================")
    print(df_live.to_string(index=False))
    
    nsw_price = prices.get('NSW1', 0.0)
    nsw_demand = demand.get('NSW1', 0.0)
    print(f"\n NSW Highlights Right Now:")
    print(f" - Operational Demand: {nsw_demand:,.1f} MW")
    print(f" - Wholesale Spot Price: ${nsw_price:.2f} / MWh")
    print("=======================================================\n")
    return df_live

if __name__ == "__main__":
    get_latest_live_aemo_dispatch()
