#!/usr/bin/env python3
"""
Pulls coordinates directly from Google Maps for all 500 Indiana courts.
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

CSV_PATH = 'locations-in.csv'
OUT_JSON = 'tools/in_google_maps_coords.json'

IN_BOUNDS = {
    'min_lat': 37.75,
    'max_lat': 41.80,
    'min_lng': -88.10,
    'max_lng': -84.75,
}

def is_in_indiana(lat: float, lng: float) -> bool:
    return (
        IN_BOUNDS['min_lat'] <= lat <= IN_BOUNDS['max_lat'] and
        IN_BOUNDS['min_lng'] <= lng <= IN_BOUNDS['max_lng']
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
        ' Pickleball', ' Courts', ' Dedicated PB Courts'
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
        f"{name}, {address}, {city}, IN",
        f"{clean_name}, {address}, {city}, IN",
        f"{clean_name}, {city}, IN",
        f"{address}, {city}, IN {zip_code}",
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
            with urllib.request.urlopen(req, timeout=8) as resp:
                content = resp.read().decode('utf-8', errors='ignore')

            # Extract [null,null,lat,lng]
            # Primary: look for exact place pin
            place_matches = re.findall(r'\[null,null,([34][0-9]\.[0-9]+),(-[89][0-9]\.[0-9]+)\]', content)
            if not place_matches:
                # Also try comma-separated lat,lng
                place_matches = re.findall(r'([34][0-9]\.[0-9]{4,}),\s*(-[89][0-9]\.[0-9]{4,})', content)

            for lat_s, lng_s in place_matches:
                lat = float(lat_s)
                lng = float(lng_s)
                if is_in_indiana(lat, lng):
                    dist = haversine_miles(orig_lat, orig_lng, lat, lng)
                    # If within 5 miles of expected city/parcel location
                    if dist < 5.0 and dist < min_dist:
                        min_dist = dist
                        best_match = (lat, lng, q)
            
            if best_match and min_dist < 1.0:
                # Close match found, no need to query more variants
                break
        except Exception:
            pass

    if best_match:
        return {
            'name': name,
            'lat': best_match[0],
            'lng': best_match[1],
            'source': 'google_maps_direct',
            'query': best_match[2],
            'dist_from_orig_mi': min_dist,
        }
    else:
        # Fallback to existing coordinates
        return {
            'name': name,
            'lat': orig_lat,
            'lng': orig_lng,
            'source': 'census_fallback',
            'query': None,
            'dist_from_orig_mi': 0.0,
        }

def main():
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        courts = list(csv.DictReader(f))

    print(f"Loaded {len(courts)} courts from {CSV_PATH}.")
    print("Pulling coordinates directly from Google Maps using concurrent workers...")

    results = {}
    completed = 0
    start_time = time.time()

    # Use 4 workers to balance speed and avoid Google rate-limiting
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_court = {executor.submit(fetch_google_maps_coords, c): c for c in courts}
        for future in concurrent.futures.as_completed(future_to_court):
            c = future_to_court[future]
            try:
                data = future.result()
                results[data['name']] = data
            except Exception as e:
                results[c['name']] = {
                    'name': c['name'],
                    'lat': float(c['lat']),
                    'lng': float(c['lng']),
                    'source': 'error_fallback',
                }
            completed += 1
            if completed % 50 == 0 or completed == len(courts):
                elapsed = time.time() - start_time
                print(f"Progress: {completed}/{len(courts)} courts processed ({elapsed:.1f}s)")

    # Stats
    gm_count = sum(1 for v in results.values() if v.get('source') == 'google_maps_direct')
    fallback_count = len(results) - gm_count
    print(f"\nCompleted: {gm_count} pulled directly from Google Maps, {fallback_count} using verified fallback.")

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"Saved results to {OUT_JSON}")

if __name__ == '__main__':
    main()
