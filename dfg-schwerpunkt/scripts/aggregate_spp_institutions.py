#!/usr/bin/env python3
"""
Aggregate institutional participation data from scraped projects.
Analyzes which institutions are involved in each SPP program.
"""

import json
from pathlib import Path
from collections import defaultdict, Counter

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
PROJECTS_DIR = DATA_DIR / "projects"
OUTPUT_FILE = DATA_DIR / "spp_institutional_analysis.json"

def extract_institution_from_investigators(investigators_str):
    """
    Extract institution names from investigators string.
    Format: "Dr. Name1;Prof. Name2" or similar
    Institutions are often in parentheses or after commas
    """
    if not investigators_str:
        return []

    institutions = []

    # Split by semicolon for multiple investigators
    parts = investigators_str.split(';')

    for part in parts:
        # Look for institution in parentheses
        if '(' in part and ')' in part:
            start = part.index('(')
            end = part.index(')')
            institution = part[start+1:end].strip()
            if institution and len(institution) > 2:
                institutions.append(institution)

    return institutions

def analyze_spp_institutions():
    """Analyze institutional participation for each SPP"""
    print("="*70)
    print("SPP Institutional Participation Analysis")
    print("="*70)

    if not PROJECTS_DIR.exists():
        print(f"✗ Projects directory not found: {PROJECTS_DIR}")
        return

    project_files = list(PROJECTS_DIR.glob("*.json"))
    print(f"✓ Found {len(project_files)} SPP project files")

    all_spp_analysis = []

    for project_file in sorted(project_files):
        with open(project_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        spp_number = data.get('spp_number', 'Unknown')
        spp_title = data.get('spp_title', 'Unknown')
        projects = data.get('projects', [])

        print(f"\n{spp_number}: {spp_title}")
        print(f"  Total projects: {len(projects)}")

        # Count institutions
        institution_counter = Counter()
        all_institutions = []

        for project in projects:
            investigators = project.get('investigators', '')

            # Try to extract institutions (this is basic - might need refinement)
            # Since GEPRIS doesn't always separate institution cleanly,
            # we'll just count unique investigator strings as proxies

            if investigators:
                # Split by semicolon and comma to get individual names
                names = investigators.replace(';', ',').split(',')
                for name in names:
                    name = name.strip()
                    if name and len(name) > 5:  # Filter out very short strings
                        # Extract institution if in format "Name (Institution)"
                        insts = extract_institution_from_investigators(name)
                        for inst in insts:
                            institution_counter[inst] += 1
                            all_institutions.append(inst)

        # Get top institutions
        top_institutions = institution_counter.most_common(10)

        if top_institutions:
            print(f"  Top institutions:")
            for inst, count in top_institutions[:5]:
                print(f"    {count:2d} projects - {inst[:50]}")
        else:
            print(f"  No clear institutional data extracted")

        # Create analysis summary
        analysis = {
            'spp_number': spp_number,
            'spp_title': spp_title,
            'num_projects': len(projects),
            'num_institutions': len(set(all_institutions)),
            'top_institutions': [
                {'name': inst, 'project_count': count}
                for inst, count in top_institutions
            ],
            'all_institutions': sorted(set(all_institutions))
        }

        all_spp_analysis.append(analysis)

    # Save analysis
    print(f"\n{'='*70}")
    print("Saving institutional analysis...")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_spp_analysis, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved to {OUTPUT_FILE}")
    print(f"✓ Analyzed {len(all_spp_analysis)} SPP programs")
    print("="*70)

    return all_spp_analysis

if __name__ == "__main__":
    analyze_spp_institutions()
