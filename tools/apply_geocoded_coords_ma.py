#!/usr/bin/env python3
"""
Applies Google Maps coordinates from tools/ma_google_maps_coords.json
back into the 9 regional files under tools/ma_regions/.
"""

import json
import os
import re
import sys

REGIONS_DIR = 'tools/ma_regions'

def update_region_file(filepath: str, coords_map: dict):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current_name = None
    updated_courts = set()
    new_lines = []

    for line in lines:
        name_match = re.search(r"['\"]name['\"]:\s*['\"]([^'\"]+)['\"]", line)
        if name_match:
            current_name = name_match.group(1)

        if current_name and current_name in coords_map:
            entry = coords_map[current_name]
            new_lat = float(entry.get('new_lat', entry.get('lat', 0)))
            new_lng = float(entry.get('new_lng', entry.get('lng', 0)))

            if new_lat != 0 and new_lng != 0:
                lat_match = re.search(r"(['\"]lat['\"]:\s*)([-0-9.]+)(,?)", line)
                if lat_match:
                    line = re.sub(r"(['\"]lat['\"]:\s*)([-0-9.]+)(,?)", rf"\g<1>{new_lat:.5f}\g<3>", line)
                    updated_courts.add(current_name)

                lng_match = re.search(r"(['\"]lng['\"]:\s*)([-0-9.]+)(,?)", line)
                if lng_match:
                    line = re.sub(r"(['\"]lng['\"]:\s*)([-0-9.]+)(,?)", rf"\g<1>{new_lng:.5f}\g<3>", line)
                    updated_courts.add(current_name)

        if re.search(r'^\s*\},?\s*$', line):
            current_name = None

        new_lines.append(line)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"Updated {len(updated_courts)} courts in {filepath}")
    return len(updated_courts)

def main():
    json_path = sys.argv[1] if len(sys.argv) > 1 else 'tools/ma_google_maps_coords.json'
    if not os.path.exists(json_path):
        print(f"File {json_path} does not exist.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        coords_map = json.load(f)

    print(f"Loaded {len(coords_map)} geocoded coordinates.")

    total_updated = 0
    for filename in sorted(os.listdir(REGIONS_DIR)):
        if filename.endswith('.py') and not filename.startswith('__'):
            filepath = os.path.join(REGIONS_DIR, filename)
            total_updated += update_region_file(filepath, coords_map)

    print(f"\nTotal courts updated across all region files: {total_updated}")

if __name__ == '__main__':
    main()
