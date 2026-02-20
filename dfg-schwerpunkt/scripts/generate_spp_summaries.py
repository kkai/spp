#!/usr/bin/env python3
"""
Generate comprehensive SPP summaries in Markdown and CSV formats for proposal writing.
Creates individual SPP summary files and a master CSV/guide.
"""

import json
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SUMMARIES_DIR = DATA_DIR / "spp_summaries"
REPORTS_DIR = BASE_DIR / "reports"

# Create directories
SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def load_spp_data():
    """Load all SPP data"""
    # Load detailed SPP program data
    with open(RAW_DIR / "spp_programs_detailed.json", 'r', encoding='utf-8') as f:
        detailed_spps = json.load(f)

    # Load project counts from institutional analysis
    inst_file = RAW_DIR / "spp_institutional_analysis.json"
    project_counts = {}
    if inst_file.exists():
        with open(inst_file, 'r', encoding='utf-8') as f:
            inst_data = json.load(f)
            for item in inst_data:
                project_counts[item['spp_number']] = item['num_projects']

    # Merge project counts into detailed data
    for spp in detailed_spps:
        spp_num = spp.get('spp_number', '')
        spp['num_projects'] = project_counts.get(spp_num, 0)

    return detailed_spps

def generate_individual_summary(spp):
    """Generate markdown summary for individual SPP"""
    spp_num = spp.get('spp_number', 'Unknown')
    safe_filename = spp_num.replace(' ', '_').replace('/', '-')

    content = f"""# {spp_num}: {spp.get('title', 'Unknown')}

## Program Overview

{spp.get('full_description', 'No description available.')}

## Key Information

- **SPP Number**: {spp_num}
- **Scientific Area**: {spp.get('wissenschaftsbereich', 'N/A')}
- **Start Year**: {spp.get('beginn', spp.get('funding_start', 'N/A'))}
- **Funding Period**: {spp.get('funding_period', 'N/A')}
- **Current Projects**: {spp.get('num_projects', 'N/A')}

## Program Coordinator

- **Name**: {spp.get('coordinator_name', 'Information not available')}
- **Contact Email**: {spp.get('contact_email', 'N/A')}
- **Contact Phone**: {spp.get('contact_phone', 'N/A')}
- **General Contact**: {spp.get('contact_general', 'N/A')}

## Geographic & International Information

- **Federal State (Bundesland)**: {spp.get('bundesland', 'N/A')}
- **International Collaborations**: {spp.get('int_bezug', 'N/A')}

## Application Information

### Program Type
- **Variant**: {spp.get('variante', 'N/A')}
- **DFG Procedure**: {spp.get('dfg_procedure', 'Schwerpunktprogramme')}

### Important Links
- **Program Page**: {spp.get('url', 'N/A')}

## Funding Details

{f"- **Funding Start**: {spp.get('funding_start', 'N/A')}" if spp.get('funding_start') else ''}
{f"- **Funding End**: {spp.get('funding_end', 'Ongoing')}" if spp.get('funding_end') else ''}
- **Subject Area**: {spp.get('subject_area', 'N/A')}

## For Proposal Writers

### Key Questions to Address
1. How does your research align with the program's objectives?
2. What unique contribution can you make to this SPP?
3. Which existing projects could you collaborate with?
4. What gap in the current research landscape does your proposal fill?

### Next Steps
1. Review the full program description above
2. Visit the program page: {spp.get('url', 'N/A')}
3. Contact the coordinator if you have questions
4. Review existing funded projects in this SPP

---

*Generated: {pd.Timestamp.now().strftime('%Y-%m-%d')}*
*Source: DFG GEPRIS Database*
"""

    # Save individual summary
    output_file = SUMMARIES_DIR / f"{safe_filename}_summary.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    return output_file

def generate_master_csv(spps):
    """Generate comprehensive CSV with all SPP data"""
    # Prepare data for CSV
    csv_data = []

    for spp in spps:
        row = {
            'spp_number': spp.get('spp_number', ''),
            'title': spp.get('title', ''),
            'start_year': spp.get('beginn', spp.get('funding_start', '')),
            'funding_period': spp.get('funding_period', ''),
            'coordinator_name': spp.get('coordinator_name', ''),
            'contact_email': spp.get('contact_email', ''),
            'contact_phone': spp.get('contact_phone', ''),
            'num_projects': spp.get('num_projects', 0),
            'scientific_area': spp.get('wissenschaftsbereich', ''),
            'bundesland': spp.get('bundesland', ''),
            'international_collaborations': spp.get('int_bezug', ''),
            'program_type': spp.get('variante', ''),
            'subject_area': spp.get('subject_area', ''),
            'description': spp.get('full_description', ''),
            'url': spp.get('url', '')
        }
        csv_data.append(row)

    # Create DataFrame
    df = pd.DataFrame(csv_data)

    # Save to CSV
    output_file = PROCESSED_DIR / "spp_programs_comprehensive.csv"
    df.to_csv(output_file, index=False, encoding='utf-8-sig')  # UTF-8 with BOM for Excel

    return output_file, df

def generate_proposal_guide(spps):
    """Generate master proposal reference guide"""

    # Group by scientific area
    by_area = {}
    for spp in spps:
        area = spp.get('wissenschaftsbereich', 'Other')
        if area not in by_area:
            by_area[area] = []
        by_area[area].append(spp)

    content = f"""# DFG Schwerpunktprogramme - Proposal Reference Guide

**Generated**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}
**Total Programs**: {len(spps)}
**Source**: DFG GEPRIS Database

---

## Quick Reference Table

| SPP Number | Title | Start | Projects | Coordinator | Contact |
|------------|-------|-------|----------|-------------|---------|
"""

    for spp in sorted(spps, key=lambda x: x.get('spp_number', '')):
        spp_num = spp.get('spp_number', 'N/A')
        title = spp.get('title', 'Unknown')[:50]
        start = spp.get('beginn', spp.get('funding_start', 'N/A'))
        projects = spp.get('num_projects', 'N/A')
        coordinator = spp.get('coordinator_name', 'N/A')[:30]
        email = spp.get('contact_email', 'N/A')

        content += f"| {spp_num} | {title}... | {start} | {projects} | {coordinator}... | {email} |\n"

    content += "\n---\n\n## Programs by Scientific Area\n\n"

    for area, area_spps in sorted(by_area.items()):
        content += f"### {area}\n\n"
        for spp in sorted(area_spps, key=lambda x: x.get('spp_number', '')):
            spp_num = spp.get('spp_number', '')
            title = spp.get('title', '')
            content += f"- **{spp_num}**: {title}\n"
        content += "\n"

    content += """---

## How to Use This Guide

### For Proposal Preparation

1. **Find Relevant SPPs**:
   - Review the quick reference table above
   - Check programs in your scientific area
   - Read individual SPP summaries in `data/spp_summaries/`

2. **Contact Program Coordinators**:
   - All coordinator contact information is in the table above
   - Reach out early to discuss your proposal idea
   - Ask about upcoming calls and deadlines

3. **Review Existing Projects**:
   - Check what's already funded in your target SPP
   - Identify collaboration opportunities
   - Find gaps in current research

4. **Prepare Your Proposal**:
   - Align with program objectives (see individual summaries)
   - Address program-specific research questions
   - Demonstrate awareness of funded projects
   - Highlight unique contributions

### Individual SPP Summaries

Detailed summaries for each program are available in:
`data/spp_summaries/SPP_XXXX_summary.md`

Each summary includes:
- Full program description
- Coordinator contact information
- Funding details and timeline
- Links to program resources
- Guidance for proposal writers

### Data Files

- **Comprehensive CSV**: `data/processed/spp_programs_comprehensive.csv`
  Contains all SPP data in spreadsheet format for analysis

- **Detailed JSON**: `data/raw/spp_programs_detailed.json`
  Raw structured data with all fields

- **Individual Summaries**: `data/spp_summaries/*.md`
  One markdown file per SPP program

---

## Application Tips

### General Requirements (Common Across SPPs)

While each SPP has specific requirements, most DFG Schwerpunktprogramme expect:

- **Research Proposal**: Detailed scientific plan (typically 5-15 pages)
- **CV and Publications**: For all principal investigators
- **Work Plan**: Timeline and milestones
- **Budget Justification**: Detailed cost breakdown
- **Collaboration Statement**: How you'll integrate with existing projects
- **Innovation Statement**: What's new and unique about your approach

### Timeline Planning

1. **6-12 months before deadline**: Contact coordinator, explore collaboration
2. **3-6 months before**: Draft proposal, get feedback
3. **2-3 months before**: Finalize budget, letters of support
4. **1 month before**: Final revisions, submission preparation

### Success Factors

- **Alignment**: Clearly demonstrate fit with SPP objectives
- **Collaboration**: Show how you'll work with existing projects
- **Innovation**: Highlight unique contributions
- **Feasibility**: Realistic timeline and resource planning
- **Impact**: Potential for significant scientific advancement

---

## Contact Directory

For questions about specific programs, contact the coordinators listed in the quick reference table above.

For general DFG questions:
- DFG Website: https://www.dfg.de/
- GEPRIS Database: https://gepris.dfg.de/

---

*This guide was automatically generated from the DFG GEPRIS database.*
*For the most current information, always check the official DFG website.*
"""

    # Save proposal guide
    output_file = REPORTS_DIR / "spp_proposal_guide.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    return output_file

def main():
    """Main function to generate all summaries"""
    print("="*70)
    print("SPP Summary Generator")
    print("="*70)

    # Load data
    print("\n1. Loading SPP data...")
    spps = load_spp_data()
    print(f"   ✓ Loaded {len(spps)} SPP programs")

    # Generate individual summaries
    print("\n2. Generating individual SPP summaries...")
    for i, spp in enumerate(spps, 1):
        spp_num = spp.get('spp_number', f'SPP_{i}')
        output_file = generate_individual_summary(spp)
        print(f"   [{i}/{len(spps)}] ✓ {spp_num} → {output_file.name}")

    print(f"   ✓ All summaries saved to {SUMMARIES_DIR}/")

    # Generate master CSV
    print("\n3. Generating comprehensive CSV...")
    csv_file, df = generate_master_csv(spps)
    print(f"   ✓ Saved to {csv_file}")
    print(f"   ✓ {len(df)} rows x {len(df.columns)} columns")

    # Generate proposal guide
    print("\n4. Generating proposal reference guide...")
    guide_file = generate_proposal_guide(spps)
    print(f"   ✓ Saved to {guide_file}")

    # Summary
    print(f"\n{'='*70}")
    print("✓ Summary Generation Complete!")
    print(f"{'='*70}")
    print(f"\nGenerated files:")
    print(f"  - {len(spps)} individual SPP markdown summaries")
    print(f"  - 1 comprehensive CSV: {csv_file.name}")
    print(f"  - 1 proposal guide: {guide_file.name}")
    print(f"\nLocations:")
    print(f"  - Summaries: {SUMMARIES_DIR}/")
    print(f"  - CSV: {PROCESSED_DIR}/")
    print(f"  - Guide: {REPORTS_DIR}/")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
