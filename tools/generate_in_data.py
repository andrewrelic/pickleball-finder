#!/usr/bin/env python3
"""
Updates Indiana locations to 500 verified pickleball courts,
validates all fields, generates schedule CSV files, and synchronizes assets.
"""

import csv
import os
import re
import shutil
import sys

# Add tools directory to path
sys.path.insert(0, os.path.dirname(__file__))

from in_regions.indy_metro import INDY_METRO_COURTS
from in_regions.hamilton_boone import HAMILTON_BOONE_COURTS
from in_regions.central_suburbs import CENTRAL_SUBURBS_COURTS
from in_regions.fort_wayne_northeast import FORT_WAYNE_NORTHEAST_COURTS
from in_regions.northwest_indiana import NORTHWEST_INDIANA_COURTS
from in_regions.michiana_north import MICHIANA_NORTH_COURTS
from in_regions.evansville_southwest import EVANSVILLE_SOUTHWEST_COURTS
from in_regions.bloomington_south_central import BLOOMINGTON_SOUTH_CENTRAL_COURTS
from in_regions.mid_indiana_wabash import MID_INDIANA_WABASH_COURTS

CSV_PATH = 'locations-in.csv'
HOURS_DIR = 'locations-in'
ASSETS_CSV = 'assets/data/locations-in.csv'
ASSETS_HOURS_DIR = 'assets/data/locations-in'

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
        ("Indy Metro", INDY_METRO_COURTS),
        ("Hamilton & Boone", HAMILTON_BOONE_COURTS),
        ("Central Suburbs", CENTRAL_SUBURBS_COURTS),
        ("Fort Wayne Northeast", FORT_WAYNE_NORTHEAST_COURTS),
        ("Northwest Indiana", NORTHWEST_INDIANA_COURTS),
        ("Michiana North", MICHIANA_NORTH_COURTS),
        ("Evansville Southwest", EVANSVILLE_SOUTHWEST_COURTS),
        ("Bloomington South Central", BLOOMINGTON_SOUTH_CENTRAL_COURTS),
        ("Mid-Indiana Wabash", MID_INDIANA_WABASH_COURTS),
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
            assert c['state'] == 'IN', f"Invalid state for {name}: {c['state']}"
            assert re.match(r'^\d{5}$', c['zip']), f"Invalid ZIP for {name}: {c['zip']}"
            lat = float(c['lat'])
            lng = float(c['lng'])
            assert 37.7 <= lat <= 41.8, f"Latitude {lat} out of range for {name}"
            assert -88.1 <= lng <= -84.7, f"Longitude {lng} out of range for {name}"
            assert c['type'] in ('Park', 'Business'), f"Invalid type for {name}: {c['type']}"
            courts_count = int(c['courts'])
            assert courts_count >= 1, f"Invalid courts count for {name}: {c['courts']}"

            court_dict = {
                'image': c.get('image', ''),
                'courts': str(courts_count),
                'name': name,
                'address': c['address'].strip(),
                'city': c['city'].strip(),
                'state': 'IN',
                'zip': c['zip'].strip(),
                'lat': f"{lat:.5f}",
                'lng': f"{lng:.5f}",
                'type': c['type'],
                'cam': c.get('cam', ''),
                'hours': hours_file,
            }
            output_rows.append(court_dict)

            # Ensure hours file exists in locations-in/
            hours_path = os.path.join(HOURS_DIR, hours_file)
            if not os.path.exists(hours_path):
                with open(hours_path, 'w', encoding='utf-8') as hf:
                    hf.write(PARK_HOURS_CONTENT)

    assert len(output_rows) == 500, f"Expected 500 rows, got {len(output_rows)}"

    # Write locations-in.csv
    with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, lineterminator='\n')
        writer.writeheader()
        for r in output_rows:
            writer.writerow(r)

    print(f"Successfully wrote {len(output_rows)} rows to {CSV_PATH}")

    # Copy to assets/data/locations-in.csv
    os.makedirs(os.path.dirname(ASSETS_CSV), exist_ok=True)
    shutil.copy2(CSV_PATH, ASSETS_CSV)
    print(f"Copied {CSV_PATH} to {ASSETS_CSV}")

    # Copy all hours files to assets/data/locations-in/
    for fname in os.listdir(HOURS_DIR):
        if fname.endswith('.csv'):
            src = os.path.join(HOURS_DIR, fname)
            dst = os.path.join(ASSETS_HOURS_DIR, fname)
            shutil.copy2(src, dst)

    hours_count = len([f for f in os.listdir(HOURS_DIR) if f.endswith('.csv')])
    assets_hours_count = len([f for f in os.listdir(ASSETS_HOURS_DIR) if f.endswith('.csv')])
    print(f"Hours files: {hours_count} in {HOURS_DIR}, {assets_hours_count} in {ASSETS_HOURS_DIR}")
    assert hours_count == 500, f"Expected 500 hours files in {HOURS_DIR}, got {hours_count}"
    assert assets_hours_count == 500, f"Expected 500 hours files in {ASSETS_HOURS_DIR}, got {assets_hours_count}"
    print("All tasks completed successfully!")

if __name__ == '__main__':
    main()
