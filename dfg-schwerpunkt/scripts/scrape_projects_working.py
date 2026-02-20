#!/usr/bin/env python3
"""
Working scraper for DFG SPP projects based on iterative testing.
Uses proven approach: visit each SPP page, extract project links, then scrape each project.
"""

import json
import time
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
PROJECTS_DIR = DATA_DIR / "projects"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_FILE = DATA_DIR / "scraping_checkpoint.json"

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

def extract_project_links(soup, current_spp_id):
    """Extract all project links from an SPP page"""
    projects = []

    for link in soup.find_all('a', href=lambda x: x and '/gepris/projekt/' in x):
        href = link.get('href')

        # Skip if it's the current SPP page or special links
        if current_spp_id in href or 'language=' in href or 'displayMode=' in href:
            continue

        # Extract project ID
        match = re.search(r'/gepris/projekt/(\d+)', href)
        if match:
            project_id = match.group(1)
            title = link.get_text(strip=True)

            # Avoid duplicates
            if project_id not in [p['id'] for p in projects]:
                projects.append({
                    'id': project_id,
                    'title': title,
                    'url': f"https://gepris.dfg.de/gepris/projekt/{project_id}"
                })

    return projects

def scrape_project_details(page, project_id, project_url):
    """Scrape detailed information from a project page"""
    try:
        page.goto(project_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(0.5)  # Small delay to be polite

        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')

        project_data = {
            'project_id': project_id,
            'url': project_url
        }

        # Get title from <title> tag
        title_tag = soup.find('title')
        if title_tag:
            full_title = title_tag.get_text()
            clean_title = full_title.replace('DFG - GEPRIS - ', '').strip()
            project_data['title'] = clean_title

        # Extract metadata from name/value spans
        metadata = {}
        name_spans = soup.find_all('span', class_='name')
        for name_span in name_spans:
            label = name_span.get_text(strip=True)
            parent = name_span.parent
            if parent:
                all_text = parent.get_text(strip=True)
                value = all_text.replace(label, '', 1).strip()
                metadata[label] = value

        # Map German field names to English keys
        field_mapping = {
            'Antragstellerinnen / Antragsteller': 'investigators',
            'Fachliche Zuordnung': 'subject_area',
            'Förderung': 'funding_period',
            'Projektkennung': 'project_identifier',
            'DFG-Verfahren': 'dfg_procedure',
            'Teilprojekt zu': 'parent_program'
        }

        for german_label, english_key in field_mapping.items():
            if german_label in metadata:
                project_data[english_key] = metadata[german_label]

        # Get description from second content_frame div
        content_frames = soup.find_all('div', class_='content_frame')
        if len(content_frames) >= 2:
            description = content_frames[1].get_text(strip=True)
            project_data['description'] = description
        else:
            project_data['description'] = ''

        return project_data

    except Exception as e:
        print(f"  ✗ Error scraping project {project_id}: {e}")
        return None

def scrape_spp_projects(spp_number, spp_title, spp_url):
    """Scrape all projects for a single SPP"""
    print(f"\n{'='*70}")
    print(f"Processing: {spp_number} - {spp_title}")
    print(f"URL: {spp_url}")
    print(f"{'='*70}")

    # Extract SPP ID from URL
    spp_id_match = re.search(r'/gepris/projekt/(\d+)', spp_url)
    if not spp_id_match:
        print(f"✗ Could not extract SPP ID from URL: {spp_url}")
        return None

    spp_id = spp_id_match.group(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Step 1: Load SPP page and extract project links
            print(f"Step 1: Loading SPP page...")
            page.goto(spp_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(1)

            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')

            project_links = extract_project_links(soup, spp_id)
            print(f"✓ Found {len(project_links)} project links")

            if len(project_links) == 0:
                print(f"⚠ No projects found for {spp_number}")
                browser.close()
                return {
                    'spp_number': spp_number,
                    'spp_title': spp_title,
                    'spp_url': spp_url,
                    'projects_count': 0,
                    'projects': []
                }

            # Step 2: Scrape details for each project
            print(f"Step 2: Scraping project details...")
            projects = []

            for i, proj_link in enumerate(project_links, 1):
                print(f"  [{i}/{len(project_links)}] Scraping {proj_link['id']}: {proj_link['title'][:60]}...")

                project_data = scrape_project_details(page, proj_link['id'], proj_link['url'])

                if project_data:
                    projects.append(project_data)
                    print(f"    ✓ Success")
                else:
                    print(f"    ✗ Failed")

                # Polite delay between requests (1-2 seconds)
                time.sleep(1.5)

            browser.close()

            # Step 3: Save results
            result = {
                'spp_number': spp_number,
                'spp_title': spp_title,
                'spp_url': spp_url,
                'projects_count': len(projects),
                'projects': projects
            }

            output_file = PROJECTS_DIR / f"{spp_number.replace(' ', '_')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            print(f"\n✓ Successfully scraped {len(projects)}/{len(project_links)} projects")
            print(f"✓ Saved to {output_file}")

            return result

        except Exception as e:
            print(f"✗ Error processing {spp_number}: {e}")
            browser.close()
            return None

def main():
    """Main scraping loop"""
    print("="*70)
    print("DFG SPP Projects Scraper - Working Version")
    print("="*70)

    # Load SPP programs list
    spp_file = DATA_DIR / "spp_programs.json"
    if not spp_file.exists():
        print(f"✗ SPP programs file not found: {spp_file}")
        print("  Please run scrape_spp_programs.py first")
        return

    with open(spp_file, 'r', encoding='utf-8') as f:
        spp_programs = json.load(f)

    print(f"✓ Loaded {len(spp_programs)} SPP programs")

    # Load checkpoint
    checkpoint = load_checkpoint()
    completed = set(checkpoint.get('completed_spps', []))
    failed = set(checkpoint.get('failed_spps', []))

    if completed:
        print(f"✓ Resuming from checkpoint: {len(completed)} completed, {len(failed)} failed")

    # Process each SPP
    total_projects = 0

    for i, spp in enumerate(spp_programs, 1):
        spp_number = spp.get('spp_number', f"SPP_{i}")

        # Skip if already completed
        if spp_number in completed:
            print(f"\n[{i}/{len(spp_programs)}] Skipping {spp_number} (already completed)")
            continue

        # Skip if previously failed (will retry at end)
        if spp_number in failed:
            print(f"\n[{i}/{len(spp_programs)}] Skipping {spp_number} (previously failed, will retry)")
            continue

        print(f"\n[{i}/{len(spp_programs)}] Processing {spp_number}")

        result = scrape_spp_projects(
            spp_number=spp_number,
            spp_title=spp.get('title', 'Unknown'),
            spp_url=spp.get('url', '')
        )

        if result and result['projects_count'] > 0:
            completed.add(spp_number)
            total_projects += result['projects_count']
            print(f"✓ {spp_number}: {result['projects_count']} projects")
        elif result and result['projects_count'] == 0:
            completed.add(spp_number)
            print(f"⚠ {spp_number}: No projects found")
        else:
            failed.add(spp_number)
            print(f"✗ {spp_number}: Failed")

        # Save checkpoint after each SPP
        checkpoint['completed_spps'] = list(completed)
        checkpoint['failed_spps'] = list(failed)
        save_checkpoint(checkpoint)

    # Retry failed SPPs
    if failed:
        print(f"\n{'='*70}")
        print(f"Retrying {len(failed)} failed SPPs...")
        print(f"{'='*70}")

        for spp_number in list(failed):
            spp = next((s for s in spp_programs if s.get('spp_number') == spp_number), None)
            if not spp:
                continue

            print(f"\nRetrying {spp_number}")
            result = scrape_spp_projects(
                spp_number=spp_number,
                spp_title=spp.get('title', 'Unknown'),
                spp_url=spp.get('url', '')
            )

            if result:
                failed.remove(spp_number)
                completed.add(spp_number)
                total_projects += result.get('projects_count', 0)

                checkpoint['completed_spps'] = list(completed)
                checkpoint['failed_spps'] = list(failed)
                save_checkpoint(checkpoint)

    # Final summary
    print(f"\n{'='*70}")
    print("SCRAPING COMPLETE")
    print(f"{'='*70}")
    print(f"✓ Completed: {len(completed)}/{len(spp_programs)} SPPs")
    print(f"✓ Total projects scraped: {total_projects}")
    if failed:
        print(f"✗ Failed: {len(failed)} SPPs - {', '.join(failed)}")
    print(f"\nProject data saved to: {PROJECTS_DIR}")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
