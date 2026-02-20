#!/usr/bin/env python3
"""
Priority scraper for high-value SPPs related to wearables and AI.
Scrapes these first, then continues with remaining SPPs.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from scrape_projects_working import scrape_spp_projects, load_checkpoint, save_checkpoint

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"

# High-priority SPPs for wearables and AI research
HIGH_PRIORITY = [
    "SPP 1999",  # Robust Argumentation Machines (RATIO) - AI
    "SPP 2041",  # Computational Connectomics - AI + Neuroscience
    "SPP 2100",  # Soft Material Robotic Systems - Wearables
]

MEDIUM_PRIORITY = [
    "SPP 2014",  # Implantable Lung - Medical devices/wearables
]

def main():
    print("="*70)
    print("DFG SPP Priority Scraper - High-Value Programs First")
    print("="*70)

    # Load SPP programs
    spp_file = DATA_DIR / "spp_programs.json"
    with open(spp_file, 'r', encoding='utf-8') as f:
        spp_programs = json.load(f)

    print(f"✓ Loaded {len(spp_programs)} SPP programs")

    # Load checkpoint
    checkpoint = load_checkpoint()
    completed = set(checkpoint.get('completed_spps', []))

    # Separate into priority groups
    high_priority_spps = []
    medium_priority_spps = []
    other_spps = []

    for spp in spp_programs:
        spp_num = spp.get('spp_number', '')
        if spp_num in HIGH_PRIORITY:
            high_priority_spps.append(spp)
        elif spp_num in MEDIUM_PRIORITY:
            medium_priority_spps.append(spp)
        else:
            other_spps.append(spp)

    print(f"\n✓ Priority breakdown:")
    print(f"  HIGH priority (wearables/AI): {len(high_priority_spps)} SPPs")
    print(f"  MEDIUM priority: {len(medium_priority_spps)} SPPs")
    print(f"  OTHER (infrastructure/etc): {len(other_spps)} SPPs")

    # Process in priority order
    all_spps_ordered = high_priority_spps + medium_priority_spps + other_spps

    total_projects = 0
    failed = []

    for i, spp in enumerate(all_spps_ordered, 1):
        spp_number = spp.get('spp_number', f"SPP_{i}")

        # Skip if already completed
        if spp_number in completed:
            print(f"\n[{i}/{len(all_spps_ordered)}] ✓ {spp_number} (already completed)")
            continue

        # Indicate priority level
        priority = "HIGH" if spp_number in HIGH_PRIORITY else ("MEDIUM" if spp_number in MEDIUM_PRIORITY else "LOW")
        print(f"\n[{i}/{len(all_spps_ordered)}] [{priority}] Processing {spp_number}")

        result = scrape_spp_projects(
            spp_number=spp_number,
            spp_title=spp.get('title', 'Unknown'),
            spp_url=spp.get('url', '')
        )

        if result:
            completed.add(spp_number)
            total_projects += result.get('projects_count', 0)
            print(f"✓ {spp_number}: {result.get('projects_count', 0)} projects")
        else:
            failed.append(spp_number)
            print(f"✗ {spp_number}: Failed")

        # Save checkpoint
        checkpoint['completed_spps'] = list(completed)
        checkpoint['failed_spps'] = failed
        save_checkpoint(checkpoint)

    # Summary
    print(f"\n{'='*70}")
    print("SCRAPING COMPLETE")
    print(f"{'='*70}")
    print(f"✓ Completed: {len(completed)}/{len(all_spps_ordered)} SPPs")
    print(f"✓ Total projects: {total_projects}")
    if failed:
        print(f"✗ Failed: {len(failed)} SPPs - {', '.join(failed)}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
