#!/usr/bin/env python3
"""
Batch geocode all 500 Indiana courts using:
1. US Census Bureau Batch Geocoder (official US parcel & street centerline GIS data)
2. Photon / Nominatim OpenStreetMap geocoding fallback for any park/non-standard parcel addresses
3. Outputs verified coordinates dictionary to tools/in_geocoded_coords.json
"""

import csv
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

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

def query_census_batch(records):
    """
    records: list of dicts with id, name, address, city, state, zip
    """
    lines = []
    for r in records:
        # ID, street, city, state, zip
        lines.append(f'{r["id"]},{r["address"]},{r["city"]},{r["state"]},{r["zip"]}')
    csv_payload = "\n".join(lines) + "\n"

    boundary = '----CensusBatchBoundary7MA4YWxkTrZu0gW'
    body = []
    body.append(f'--{boundary}'.encode())
    body.append(b'Content-Disposition: form-data; name="benchmark"')
    body.append(b'')
    body.append(b'Public_AR_Current')
    
    body.append(f'--{boundary}'.encode())
    body.append(b'Content-Disposition: form-data; name="addressFile"; filename="in_addresses.csv"')
    body.append(b'Content-Type: text/csv')
    body.append(b'')
    body.append(csv_payload.encode('utf-8'))
    body.append(f'--{boundary}--'.encode())
    body.append(b'')

    payload = b'\r\n'.join(body)
    req = urllib.request.Request(
        'https://geocoding.geo.census.gov/geocoder/locations/addressbatch',
        data=payload,
        headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'User-Agent': 'PickleballFinder/1.0'
        }
    )

    print(f"Submitting {len(records)} records to US Census Batch Geocoder...")
    with urllib.request.urlopen(req, timeout=90) as resp:
        content = resp.read().decode('utf-8')

    results = {}
    reader = csv.reader(io.StringIO(content))
    for row in reader:
        if not row:
            continue
        rec_id = int(row[0].strip('"'))
        status = row[2].strip('"') if len(row) > 2 else 'No_Match'
        if status == 'Match' and len(row) >= 6:
            coords = row[5].strip('"').split(',')
            lng = float(coords[0])
            lat = float(coords[1])
            matched_addr = row[4].strip('"')
            results[rec_id] = {
                'lat': lat,
                'lng': lng,
                'source': 'census',
                'matched': matched_addr
            }
        else:
            results[rec_id] = None
    return results

def query_photon(query: str):
    url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(query)}&limit=1"
    req = urllib.request.Request(url, headers={'User-Agent': 'PickleballFinder/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            features = data.get('features', [])
            if features:
                coords = features[0]['geometry']['coordinates']
                lng, lat = coords[0], coords[1]
                if is_in_indiana(lat, lng):
                    props = features[0].get('properties', {})
                    return {'lat': lat, 'lng': lng, 'source': 'photon', 'matched': props.get('name', query)}
    except Exception as e:
        pass
    return None

def query_nominatim(query: str):
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1&countrycodes=us"
    req = urllib.request.Request(url, headers={'User-Agent': 'PickleballFinderApp/1.0 (contact@pickleballfinder.com)'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data:
                lat = float(data[0]['lat'])
                lng = float(data[0]['lon'])
                if is_in_indiana(lat, lng):
                    return {'lat': lat, 'lng': lng, 'source': 'nominatim', 'matched': data[0].get('display_name', '')}
    except Exception as e:
        pass
    return None

def main():
    csv_path = 'locations-in.csv'
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))

    records = []
    for idx, row in enumerate(reader, 1):
        records.append({
            'id': idx,
            'name': row['name'],
            'address': row['address'],
            'city': row['city'],
            'state': row['state'],
            'zip': row['zip'],
            'orig_lat': float(row['lat']),
            'orig_lng': float(row['lng']),
        })

    print(f"Loaded {len(records)} Indiana records.")
    census_results = query_census_batch(records)
    print(f"Census batch geocoder returned matches for {sum(1 for v in census_results.values() if v)} / {len(records)} records.")

    final_results = {}
    unresolved = []

    for r in records:
        rec_id = r['id']
        name = r['name']
        c_res = census_results.get(rec_id)
        if c_res and is_in_indiana(c_res['lat'], c_res['lng']):
            final_results[name] = c_res
        else:
            unresolved.append(r)

    print(f"Need fallback geocoding for {len(unresolved)} records...")
    for idx, r in enumerate(unresolved, 1):
        query_str = f"{r['address']}, {r['city']}, IN {r['zip']}"
        res = query_photon(query_str)
        if not res:
            # Try with park name + city
            clean_name = r['name'].replace(' Pickleball Courts', '').replace(' PB Courts', '').replace(' Pickleball Complex', '').replace(' Pickleball Club', '').replace(' Pickleball', '')
            res = query_photon(f"{clean_name}, {r['city']}, IN")
        if not res:
            # Try nominatim
            time.sleep(1.0)
            res = query_nominatim(f"{r['address']}, {r['city']}, IN {r['zip']}")
        if not res:
            res = query_nominatim(f"{clean_name}, {r['city']}, IN")

        if res:
            final_results[r['name']] = res
            print(f"[{idx}/{len(unresolved)}] Matched {r['name']} via {res['source']}: ({res['lat']:.5f}, {res['lng']:.5f})")
        else:
            print(f"[{idx}/{len(unresolved)}] FAILED to resolve: {r['name']} ({r['address']}, {r['city']}, {r['zip']})")

    out_file = 'tools/in_geocoded_coords.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, indent=2)

    print(f"\nFinal geocoding complete: {len(final_results)} / {len(records)} resolved.")
    print(f"Results saved to {out_file}")

if __name__ == '__main__':
    main()
