#!/usr/bin/env python3
"""
Pulls coordinates directly from Google Maps for all 500 Massachusetts courts.
Uses Google Maps search endpoint to resolve the exact venue/park entrance
or athletic complex pin, matching the exact Google Maps user experience.
"""

import concurrent.futures
import csv
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))

from ma_regions.greater_boston import GREATER_BOSTON_COURTS
from ma_regions.boston_metro_west import BOSTON_METRO_WEST_COURTS
from ma_regions.north_shore import NORTH_SHORE_COURTS
from ma_regions.merrimack_valley import MERRIMACK_VALLEY_COURTS
from ma_regions.south_shore import SOUTH_SHORE_COURTS
from ma_regions.south_coast_bristol import SOUTH_COAST_BRISTOL_COURTS
from ma_regions.cape_cod_islands import CAPE_COD_ISLANDS_COURTS
from ma_regions.central_worcester import CENTRAL_WORCESTER_COURTS
from ma_regions.pioneer_valley_berkshires import PIONEER_VALLEY_BERKSHIRES_COURTS

OUT_JSON = 'tools/ma_google_maps_coords.json'

MA_BOUNDS = {
    'min_lat': 41.20,
    'max_lat': 42.95,
    'min_lng': -73.60,
    'max_lng': -69.80,
}

def is_in_massachusetts(lat: float, lng: float) -> bool:
    return (
        MA_BOUNDS['min_lat'] <= lat <= MA_BOUNDS['max_lat'] and
        MA_BOUNDS['min_lng'] <= lng <= MA_BOUNDS['max_lng']
    )

def haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def clean_venue_name(name: str) -> str:
    cleaned = name
    for s in [
        ' Pickleball Courts', ' PB Courts', ' Pickleball Complex',
        ' Pickleball Club', ' Pickleball Hub', ' PB Plaza', ' PB',
        ' Pickleball', ' Courts', ' Dedicated PB Courts', ' Dedicated PB'
    ]:
        cleaned = cleaned.replace(s, '')
    return cleaned.strip()

def fetch_google_maps_coords(court: dict):
    name = court['name']
    address = court['address']
    city = court['city']
    zip_code = court['zip']
    orig_lat = float(court['lat'])
    orig_lng = float(court['lng'])
    
    clean_name = clean_venue_name(name)

    queries = [
        f"{name}, {address}, {city}, MA",
        f"{clean_name}, {address}, {city}, MA",
        f"{clean_name}, {city}, MA",
        f"{address}, {city}, MA {zip_code}",
    ]

    best_match = None
    min_dist = float('inf')

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    for q in queries:
        url = 'https://www.google.com/search?tbm=map&authuser=0&hl=en&gl=us&q=' + urllib.parse.quote(q)
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                content = resp.read().decode('utf-8', errors='ignore')

            # Extract [null,null,lat,lng]
            place_matches = re.findall(r'\[null,null,([4][12]\.[0-9]+),(-[67][0-9]\.[0-9]+)\]', content)
            if not place_matches:
                place_matches = re.findall(r'([4][12]\.[0-9]{4,}),\s*(-[67][0-9]\.[0-9]{4,})', content)

            for lat_s, lng_s in place_matches:
                lat = float(lat_s)
                lng = float(lng_s)
                if is_in_massachusetts(lat, lng):
                    dist = haversine_miles(orig_lat, orig_lng, lat, lng)
                    if dist < 6.0 and dist < min_dist:
                        min_dist = dist
                        best_match = (lat, lng, q)
            if best_match and min_dist < 0.2:
                # Close enough match found
                break
        except Exception:
            pass

    if best_match:
        return {
            'name': name,
            'city': city,
            'orig_lat': orig_lat,
            'orig_lng': orig_lng,
            'new_lat': best_match[0],
            'new_lng': best_match[1],
            'dist_miles': round(min_dist, 3),
            'matched_query': best_match[2],
            'status': 'updated' if min_dist > 0.005 else 'verified',
        }
    else:
        return {
            'name': name,
            'city': city,
            'orig_lat': orig_lat,
            'orig_lng': orig_lng,
            'new_lat': orig_lat,
            'new_lng': orig_lng,
            'dist_miles': 0.0,
            'matched_query': 'fallback_to_original',
            'status': 'unmodified',
        }

def main():
    all_courts = (
        GREATER_BOSTON_COURTS + BOSTON_METRO_WEST_COURTS + NORTH_SHORE_COURTS +
        MERRIMACK_VALLEY_COURTS + SOUTH_SHORE_COURTS + SOUTH_COAST_BRISTOL_COURTS +
        CAPE_COD_ISLANDS_COURTS + CENTRAL_WORCESTER_COURTS + PIONEER_VALLEY_BERKSHIRES_COURTS
    )
    print(f"Loaded {len(all_courts)} Massachusetts courts.")

    results = {}
    updated_count = 0
    verified_count = 0
    unmodified_count = 0

    print("Querying Google Maps for exact venue place coordinates (workers=10)...")
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_court = {executor.submit(fetch_google_maps_coords, c): c for c in all_courts}
        done_count = 0
        for future in concurrent.futures.as_completed(future_to_court):
            done_count += 1
            res = future.result()
            results[res['name']] = res
            if res['status'] == 'updated':
                updated_count += 1
            elif res['status'] == 'verified':
                verified_count += 1
            else:
                unmodified_count += 1

            if done_count % 50 == 0 or done_count == len(all_courts):
                elapsed = time.time() - start_time
                print(f"  [{done_count}/{len(all_courts)}] done in {elapsed:.1f}s (Updated: {updated_count}, Verified: {verified_count}, Fallback: {unmodified_count})")

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    print(f"\nFinished in {time.time() - start_time:.1f}s.")
    print(f"Results saved to {OUT_JSON}.")
    print(f"Updated coordinates: {updated_count}")
    print(f"Verified coordinates: {verified_count}")
    print(f"Unmodified (fallback): {unmodified_count}")

if __name__ == '__main__':
    main()
