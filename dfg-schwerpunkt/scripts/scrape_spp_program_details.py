#!/usr/bin/env python3
"""
Scrape comprehensive details from DFG SPP program pages for proposal preparation.
Extracts: descriptions, coordinators, funding info, research themes, application requirements.
"""

import json
import time
import random
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
OUTPUT_FILE = DATA_DIR / "spp_programs_detailed.json"
CHECKPOINT_FILE = DATA_DIR / "spp_detail_checkpoint.json"

# Field mapping: German → English
FIELD_MAPPING = {
    'Antragstellende': 'applicants',
    'Sprecher / Sprecherin': 'spokesperson',
    'Sprecherin / Sprecher': 'spokesperson',
    'Koordinatorin / Koordinator': 'coordinator',
    'Koordinator / Koordinatorin': 'coordinator',
    'Fachliche Zuordnung': 'subject_area',
    'Förderung': 'funding_period',
    'Laufzeit': 'duration',
    'Projektkennung': 'project_identifier',
    'Kontakt': 'contact',
    'E-Mail': 'email',
    'Telefon': 'phone',
    'Bewilligungsausschuss': 'approval_committee',
    'DFG-Verfahren': 'dfg_procedure',
    'Antragstellende Institution': 'applicant_institution',
    'Teilprojekt zu': 'subproject_of',
}

def load_checkpoint():
    """Load scraping progress checkpoint"""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'completed_spps': [], 'failed_spps': []}

def save_checkpoint(checkpoint):
    """Save scraping progress checkpoint"""
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(checkpoint, f, indent=2, ensure_ascii=False)

def extract_spp_program_details(page, spp_url):
    """
    Extract comprehensive details from an SPP program detail page.
    Based on proven patterns from scrape_projects_working.py
    """
    try:
        page.goto(spp_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(0.5)  # Small delay for dynamic content

        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')

        spp_data = {'url': spp_url}

        # 1. Extract title from <title> tag
        title_tag = soup.find('title')
        if title_tag:
            full_title = title_tag.get_text()
            clean_title = full_title.replace('DFG - GEPRIS - ', '').strip()
            spp_data['title'] = clean_title

        # 2. Extract metadata from <span class="name"> fields
        metadata = {}
        name_spans = soup.find_all('span', class_='name')
        for name_span in name_spans:
            label = name_span.get_text(strip=True)
            parent = name_span.parent
            if parent:
                all_text = parent.get_text(strip=True)
                value = all_text.replace(label, '', 1).strip()

                # Map to English field name if known
                english_key = FIELD_MAPPING.get(label, label.lower().replace(' / ', '_').replace(' ', '_'))
                metadata[english_key] = value

        # 3. Extract description from <div class="content_frame">
        content_frames = soup.find_all('div', class_='content_frame')

        # Usually first content_frame has metadata, second has description
        if len(content_frames) >= 2:
            description = content_frames[1].get_text(strip=True)
            spp_data['full_description'] = description
        elif len(content_frames) == 1:
            description = content_frames[0].get_text(strip=True)
            spp_data['full_description'] = description
        else:
            spp_data['full_description'] = ''

        # 4. Extract coordinator information
        if 'spokesperson' in metadata:
            spp_data['coordinator_name'] = metadata['spokesperson']
        elif 'coordinator' in metadata:
            spp_data['coordinator_name'] = metadata['coordinator']
        else:
            spp_data['coordinator_name'] = ''

        # 5. Extract contact information
        spp_data['contact_email'] = metadata.get('email', '')
        spp_data['contact_phone'] = metadata.get('phone', '')
        spp_data['contact_general'] = metadata.get('contact', '')

        # 6. Extract funding period information
        funding_period = metadata.get('funding_period', '')
        spp_data['funding_period'] = funding_period

        # Try to parse funding years
        if 'seit' in funding_period.lower():
            # Extract year after "seit"
            match = re.search(r'seit\s+(\d{4})', funding_period)
            if match:
                spp_data['funding_start'] = match.group(1)
                spp_data['funding_end'] = ''  # Ongoing
        elif 'von' in funding_period.lower() and 'bis' in funding_period.lower():
            # Extract years from "von YYYY bis YYYY"
            match = re.search(r'von\s+(\d{4})\s+bis\s+(\d{4})', funding_period)
            if match:
                spp_data['funding_start'] = match.group(1)
                spp_data['funding_end'] = match.group(2)
        else:
            spp_data['funding_start'] = ''
            spp_data['funding_end'] = ''

        # 7. Extract subject area
        spp_data['subject_area'] = metadata.get('subject_area', '')
        spp_data['approval_committee'] = metadata.get('approval_committee', '')

        # 8. Extract institution information
        spp_data['applicant_institution'] = metadata.get('applicant_institution', '')

        # 9. Store all metadata for reference
        spp_data['metadata'] = metadata

        return spp_data

    except Exception as e:
        print(f"  ✗ Error extracting details: {e}")
        return None

def scrape_all_spp_programs():
    """Main scraping function"""
    print("="*70)
    print("DFG SPP Program Details Scraper")
    print("="*70)

    # Load existing basic SPP data
    spp_basic_file = DATA_DIR / "spp_programs.json"
    if not spp_basic_file.exists():
        print(f"✗ SPP programs file not found: {spp_basic_file}")
        print("  Please run scrape_spp_programs.py first")
        return

    with open(spp_basic_file, 'r', encoding='utf-8') as f:
        spp_programs = json.load(f)

    print(f"✓ Loaded {len(spp_programs)} SPP programs")

    # Load checkpoint
    checkpoint = load_checkpoint()
    completed = set(checkpoint.get('completed_spps', []))
    failed = set(checkpoint.get('failed_spps', []))

    if completed:
        print(f"✓ Resuming from checkpoint: {len(completed)} completed, {len(failed)} failed")

    # Scrape details for each SPP
    all_detailed_spps = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for i, spp in enumerate(spp_programs, 1):
            spp_number = spp.get('spp_number', f"SPP_{i}")
            spp_url = spp.get('detail_page_url') or spp.get('url', '')

            # Skip if already completed
            if spp_number in completed:
                print(f"\n[{i}/{len(spp_programs)}] ✓ {spp_number} (already completed)")
                # Still load from checkpoint if needed
                continue

            print(f"\n[{i}/{len(spp_programs)}] Processing {spp_number}")
            print(f"  Title: {spp.get('title', 'Unknown')[:60]}...")
            print(f"  URL: {spp_url}")

            if not spp_url:
                print(f"  ⚠ No URL available, using basic data only")
                detailed_data = {**spp, 'full_description': '', 'coordinator_name': ''}
                all_detailed_spps.append(detailed_data)
                completed.add(spp_number)
                continue

            # Scrape detailed information
            detailed_data = extract_spp_program_details(page, spp_url)

            if detailed_data:
                # Combine basic metadata with detailed scraping
                combined_data = {**spp, **detailed_data}
                all_detailed_spps.append(combined_data)
                completed.add(spp_number)
                print(f"  ✓ Extracted detailed information")

                # Show key findings
                if detailed_data.get('coordinator_name'):
                    print(f"    Coordinator: {detailed_data['coordinator_name'][:50]}...")
                if detailed_data.get('full_description'):
                    desc_len = len(detailed_data['full_description'])
                    print(f"    Description: {desc_len} characters")
            else:
                failed.add(spp_number)
                # Still save basic data
                all_detailed_spps.append({**spp, 'full_description': '', 'coordinator_name': ''})
                print(f"  ✗ Failed to extract details")

            # Save checkpoint after each SPP
            checkpoint['completed_spps'] = list(completed)
            checkpoint['failed_spps'] = list(failed)
            save_checkpoint(checkpoint)

            # Polite delay between requests
            time.sleep(random.uniform(1.5, 2.0))

        browser.close()

    # Save detailed SPP data
    print(f"\n{'='*70}")
    print("Saving detailed SPP data...")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_detailed_spps, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved to {OUTPUT_FILE}")
    print(f"✓ Total SPPs: {len(all_detailed_spps)}")
    print(f"✓ Successfully scraped: {len(completed)}")
    if failed:
        print(f"✗ Failed: {len(failed)} - {', '.join(failed)}")

    print("="*70)
    print("✓ Scraping complete!")
    print("="*70)

    return all_detailed_spps

if __name__ == "__main__":
    scrape_all_spp_programs()
