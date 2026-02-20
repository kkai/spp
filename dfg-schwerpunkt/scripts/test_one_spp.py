#!/usr/bin/env python3
"""Test scraper on a single SPP to verify it works"""

import json
from pathlib import Path
import sys

# Add parent directory to path to import the scraper
sys.path.insert(0, str(Path(__file__).parent))

from scrape_projects_working import scrape_spp_projects

# Test on SPP 2100 (Soft Robotics) which we know has 18 projects
spp_number = "SPP 2100"
spp_title = "Soft Material Robotic Systems"
spp_url = "https://gepris.dfg.de/gepris/projekt/359715917"

print("Testing scraper on SPP 2100 (Soft Robotics)...")
print("This SPP should have ~18 projects based on our tests.\n")

result = scrape_spp_projects(spp_number, spp_title, spp_url)

if result:
    print(f"\n✓ Test successful!")
    print(f"  SPP: {result['spp_number']}")
    print(f"  Projects: {result['projects_count']}")
    print(f"\nFirst project sample:")
    if result['projects']:
        proj = result['projects'][0]
        print(f"  Title: {proj.get('title', 'N/A')}")
        print(f"  ID: {proj.get('project_id', 'N/A')}")
        print(f"  PIs: {proj.get('investigators', 'N/A')[:80]}...")
        print(f"  Description: {len(proj.get('description', ''))} chars")
else:
    print("\n✗ Test failed")
    sys.exit(1)
