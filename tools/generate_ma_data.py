#!/usr/bin/env python3
"""
Updates Massachusetts locations to 500 verified pickleball courts,
validates all fields, generates schedule CSV files, and synchronizes assets.
"""

import csv
import os
import re
import shutil
import sys

# Add tools directory to path
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

CSV_PATH = 'locations-ma.csv'
HOURS_DIR = 'locations-ma'
ASSETS_CSV = 'assets/data/locations-ma.csv'
ASSETS_HOURS_DIR = 'assets/data/locations-ma'

PARK_HOURS_CONTENT = (
    "sun,mon,tue,wed,thu,fri,sat\n"
    "6:00 AM - 10:00 PM,6:00 AM - 10:00 PM,6:00 AM - 10:00 PM,6:00 AM - 10:00 PM,6:00 AM - 10:00 PM,6:00 AM - 10:00 PM,6:00 AM - 10:00 PM\n"
)

FIELDNAMES = ['image', 'courts', 'name', 'address', 'city', 'state', 'zip', 'lat', 'lng', 'type', 'cam', 'hours']

def slugify(text: str) -> str:
    s = text.lower()
    s = re.sub(r'[\'\"]', '', s)
    s = re.sub(r'[^a-z0-9]+', '_', s)
    return s.strip('_') + '.csv'

def main():
    all_region_lists = [
        ("Greater Boston", GREATER_BOSTON_COURTS),
        ("Boston Metro West", BOSTON_METRO_WEST_COURTS),
        ("North Shore", NORTH_SHORE_COURTS),
        ("Merrimack Valley", MERRIMACK_VALLEY_COURTS),
        ("South Shore", SOUTH_SHORE_COURTS),
        ("South Coast Bristol", SOUTH_COAST_BRISTOL_COURTS),
        ("Cape Cod Islands", CAPE_COD_ISLANDS_COURTS),
        ("Central Worcester", CENTRAL_WORCESTER_COURTS),
        ("Pioneer Valley Berkshires", PIONEER_VALLEY_BERKSHIRES_COURTS),
    ]

    total_courts = sum(len(c) for _, c in all_region_lists)
    print(f"Total candidate courts: {total_courts}")
    for name, c in all_region_lists:
        print(f"  - {name}: {len(c)}")

    assert total_courts == 500, f"Expected 500 courts, got {total_courts}"

    os.makedirs(HOURS_DIR, exist_ok=True)
    os.makedirs(ASSETS_HOURS_DIR, exist_ok=True)

    seen_names = set()
    seen_hours_slugs = set()
    output_rows = []

    for region_name, courts in all_region_lists:
        for c in courts:
            name = c['name'].strip()
            name_lower = name.lower()
            if name_lower in seen_names:
                raise ValueError(f"Duplicate court name detected: {name} in {region_name}")
            seen_names.add(name_lower)

            # Generate hours slug
            hours_file = c.get('hours')
            if not hours_file:
                hours_file = slugify(name)

            if hours_file in seen_hours_slugs:
                raise ValueError(f"Duplicate hours slug detected: {hours_file} for {name} in {region_name}")
            seen_hours_slugs.add(hours_file)

            # Validate fields
            assert c['address'].strip(), f"Missing address for {name}"
            assert c['city'].strip(), f"Missing city for {name}"
            assert c['state'] == 'MA', f"Invalid state for {name}: {c['state']}"
            assert re.match(r'^\d{5}$', c['zip']), f"Invalid ZIP for {name}: {c['zip']}"
            lat = float(c['lat'])
            lng = float(c['lng'])
            assert 41.2 <= lat <= 42.95, f"Latitude {lat} out of range for {name}"
            assert -73.6 <= lng <= -69.8, f"Longitude {lng} out of range for {name}"
            assert c['type'] in ('Park', 'Business'), f"Invalid type for {name}: {c['type']}"
            courts_count = int(c['courts'])
            assert courts_count >= 1, f"Invalid courts count for {name}: {c['courts']}"

            court_dict = {
                'image': c.get('image', ''),
                'courts': str(courts_count),
                'name': name,
                'address': c['address'].strip(),
                'city': c['city'].strip(),
                'state': 'MA',
                'zip': c['zip'].strip(),
                'lat': f"{lat:.5f}",
                'lng': f"{lng:.5f}",
                'type': c['type'],
                'cam': c.get('cam', ''),
                'hours': hours_file,
            }
            output_rows.append(court_dict)

            # Ensure hours file exists in locations-ma/
            hours_path = os.path.join(HOURS_DIR, hours_file)
            if not os.path.exists(hours_path):
                with open(hours_path, 'w', encoding='utf-8') as hf:
                    hf.write(PARK_HOURS_CONTENT)

    # Clean up stale hours files not in the active 500 courts
    for d in (HOURS_DIR, ASSETS_HOURS_DIR):
        if os.path.exists(d):
            for fname in os.listdir(d):
                if fname.endswith('.csv') and fname not in seen_hours_slugs:
                    os.remove(os.path.join(d, fname))

    assert len(output_rows) == 500, f"Expected 500 rows, got {len(output_rows)}"

    # Write locations-ma.csv
    with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, lineterminator='\n')
        writer.writeheader()
        for r in output_rows:
            writer.writerow(r)

    print(f"Successfully wrote {len(output_rows)} rows to {CSV_PATH}")

    # Copy to assets/data/locations-ma.csv
    os.makedirs(os.path.dirname(ASSETS_CSV), exist_ok=True)
    shutil.copy2(CSV_PATH, ASSETS_CSV)
    print(f"Copied {CSV_PATH} to {ASSETS_CSV}")

    # Copy all hours files to assets/data/locations-ma/
    copied_hours = 0
    for fname in os.listdir(HOURS_DIR):
        if fname.endswith('.csv'):
            src = os.path.join(HOURS_DIR, fname)
            dst = os.path.join(ASSETS_HOURS_DIR, fname)
            shutil.copy2(src, dst)
            copied_hours += 1

    print(f"Synchronized {copied_hours} hours files to {ASSETS_HOURS_DIR}")

if __name__ == '__main__':
    main()
