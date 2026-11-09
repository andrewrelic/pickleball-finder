#!/usr/bin/env python3
"""
Expands California locations from 73 to 500 courts, validates all fields,
generates schedule CSV files, and synchronizes assets.
"""

import csv
import os
import re
import shutil
import sys

# Add tools directory to path
sys.path.insert(0, os.path.dirname(__file__))

from ca_regions.la_county import LA_COUNTY_COURTS
from ca_regions.orange_county import ORANGE_COUNTY_COURTS
from ca_regions.san_diego import SAN_DIEGO_COURTS
from ca_regions.san_francisco_peninsula import SF_PENINSULA_COURTS
from ca_regions.silicon_valley import SILICON_VALLEY_COURTS
from ca_regions.east_bay import EAST_BAY_COURTS
from ca_regions.sacramento_north import SACRAMENTO_NORTH_COURTS
from ca_regions.inland_empire import INLAND_EMPIRE_COURTS
from ca_regions.central_coast_valley import CENTRAL_COAST_VALLEY_COURTS

EXISTING_CSV = 'locations-ca.csv'
HOURS_DIR = 'locations-ca'
ASSETS_CSV = 'assets/data/locations-ca.csv'
ASSETS_HOURS_DIR = 'assets/data/locations-ca'

PARK_HOURS_CONTENT = (
    "sun,mon,tue,wed,thu,fri,sat\n"
    "6:00 AM - 10:00 PM,6:00 AM - 10:00 PM,6:00 AM - 10:00 PM,6:00 AM - 10:00 PM,6:00 AM - 10:00 PM,6:00 AM - 10:00 PM,6:00 AM - 10:00 PM\n"
)

def slugify(text: str) -> str:
    s = text.lower()
    s = re.sub(r'[\'\"]', '', s)
    s = re.sub(r'[^a-z0-9]+', '_', s)
    return s.strip('_') + '.csv'

def main():
    # 1. Read existing rows
    with open(EXISTING_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        existing_rows = list(reader)

    print(f"Existing rows in {EXISTING_CSV}: {len(existing_rows)}")
    assert len(existing_rows) == 73, f"Expected 73 existing rows, found {len(existing_rows)}"

    existing_names = {r['name'].strip().lower() for r in existing_rows}

    # 2. Collect all new rows
    all_new_lists = [
        ("LA County", LA_COUNTY_COURTS),
        ("Orange County", ORANGE_COUNTY_COURTS),
        ("San Diego", SAN_DIEGO_COURTS),
        ("SF Peninsula", SF_PENINSULA_COURTS),
        ("Silicon Valley", SILICON_VALLEY_COURTS),
        ("East Bay", EAST_BAY_COURTS),
        ("Sacramento North", SACRAMENTO_NORTH_COURTS),
        ("Inland Empire", INLAND_EMPIRE_COURTS),
        ("Central Coast & Valley", CENTRAL_COAST_VALLEY_COURTS),
    ]

    total_new = sum(len(c) for _, c in all_new_lists)
    print(f"Total new candidate courts: {total_new}")
    for name, c in all_new_lists:
        print(f"  - {name}: {len(c)}")

    assert total_new == 427, f"Expected 427 new courts, got {total_new}"

    new_rows = []
    seen_names = set(existing_names)
    seen_hours_slugs = set(os.listdir(HOURS_DIR))

    for region_name, courts in all_new_lists:
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

            # Validate fields
            assert c['address'].strip(), f"Missing address for {name}"
            assert c['city'].strip(), f"Missing city for {name}"
            assert c['state'] == 'CA', f"Invalid state for {name}: {c['state']}"
            assert re.match(r'^\d{5}$', c['zip']), f"Invalid ZIP for {name}: {c['zip']}"
            lat = float(c['lat'])
            lng = float(c['lng'])
            assert 32.5 <= lat <= 42.0, f"Latitude {lat} out of range for {name}"
            assert -124.5 <= lng <= -114.1, f"Longitude {lng} out of range for {name}"
            assert c['type'] in ('Park', 'Business'), f"Invalid type for {name}: {c['type']}"

            court_dict = {
                'image': c.get('image', ''),
                'courts': str(c['courts']),
                'name': name,
                'address': c['address'].strip(),
                'city': c['city'].strip(),
                'state': 'CA',
                'zip': c['zip'].strip(),
                'lat': f"{lat:.5f}",
                'lng': f"{lng:.5f}",
                'type': c['type'],
                'cam': c.get('cam', ''),
                'hours': hours_file,
            }
            new_rows.append(court_dict)

            # Ensure hours file exists in locations-ca/
            hours_path = os.path.join(HOURS_DIR, hours_file)
            if not os.path.exists(hours_path):
                with open(hours_path, 'w', encoding='utf-8') as hf:
                    hf.write(PARK_HOURS_CONTENT)

    total_combined = len(existing_rows) + len(new_rows)
    print(f"Total combined courts: {total_combined}")
    assert total_combined == 500, f"Expected 500 combined courts, got {total_combined}"

    # 3. Write combined rows to locations-ca.csv
    with open(EXISTING_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator='\n')
        writer.writeheader()
        for r in existing_rows:
            writer.writerow(r)
        for r in new_rows:
            writer.writerow(r)

    print(f"Successfully wrote {total_combined} rows to {EXISTING_CSV}")

    # 4. Copy to assets/data/locations-ca.csv
    os.makedirs(os.path.dirname(ASSETS_CSV), exist_ok=True)
    shutil.copy2(EXISTING_CSV, ASSETS_CSV)
    print(f"Copied {EXISTING_CSV} to {ASSETS_CSV}")

    # 5. Copy all hours files to assets/data/locations-ca/
    os.makedirs(ASSETS_HOURS_DIR, exist_ok=True)
    for fname in os.listdir(HOURS_DIR):
        if fname.endswith('.csv'):
            src = os.path.join(HOURS_DIR, fname)
            dst = os.path.join(ASSETS_HOURS_DIR, fname)
            shutil.copy2(src, dst)

    hours_count = len([f for f in os.listdir(HOURS_DIR) if f.endswith('.csv')])
    assets_hours_count = len([f for f in os.listdir(ASSETS_HOURS_DIR) if f.endswith('.csv')])
    print(f"Hours files: {hours_count} in {HOURS_DIR}, {assets_hours_count} in {ASSETS_HOURS_DIR}")

if __name__ == '__main__':
    main()
