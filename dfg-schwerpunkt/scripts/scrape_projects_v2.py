#!/usr/bin/env python3
"""
DFG Individual Projects Scraper v2
Uses GEPRIS search to find projects by SPP number instead of relying on project links
"""

import json
import time
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
PROJECTS_DIR = DATA_DIR / "projects"
INPUT_FILE = DATA_DIR / "spp_programs.json"
CHECKPOINT_FILE = DATA_DIR / "scraping_checkpoint.json"

# URLs
BASE_URL = "https://gepris.dfg.de"


def load_checkpoint():
    """Load checkpoint to resume scraping"""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, 'r') as f:
            return json.load(f)
    return {'completed_spps': [], 'last_index': -1}


def save_checkpoint(checkpoint):
    """Save checkpoint for resuming"""
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(checkpoint, f, indent=2)


def search_spp_projects(page, spp_number):
    """
    Search GEPRIS for all projects in a given SPP using the search function
    """
    # Extract just the number from "SPP 1234"
    spp_num = spp_number.replace('SPP ', '').strip()

    # Use GEPRIS search URL with SPP filter
    search_url = f"{BASE_URL}/gepris/OCTOPUS?task=showSearchSimple"

    try:
        print(f"  Searching for projects in {spp_number}...")
        page.goto(search_url, wait_until="networkidle", timeout=60000)
        time.sleep(2)

        # Fill in search form - search for the SPP number in "Programm" field
        # Try to find and fill the search field
        page.fill('input[name="keywords"]', spp_num)
        time.sleep(1)

        # Submit search
        page.click('button[type="submit"]')
        time.sleep(3)

        # Get results page
        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')

        projects = []

        # Find all project links in search results
        # GEPRIS typically shows project results with links to /gepris/projekt/
        project_links = soup.find_all('a', href=re.compile(r'/gepris/projekt/\d+'))

        print(f"  Found {len(project_links)} potential project links")

        for link in project_links:
            href = link['href']
            if not href.startswith('http'):
                href = BASE_URL + href if href.startswith('/') else f"{BASE_URL}/{href}"

            # Extract project ID
            project_id_match = re.search(r'projekt/(\d+)', href)
            project_id = project_id_match.group(1) if project_id_match else None

            title = link.get_text(strip=True)

            # Avoid duplicates
            if project_id and not any(p['project_id'] == project_id for p in projects):
                projects.append({
                    'project_id': project_id,
                    'title': title,
                    'url': href,
                    'spp_number': spp_number
                })

        return projects

    except Exception as e:
        print(f"  Error searching for {spp_number}: {e}")
        return []


def scrape_project_details(page, project):
    """
    Visit individual project page and extract detailed information
    """
    try:
        page.goto(project['url'], wait_until="networkidle", timeout=60000)
        time.sleep(1.5)

        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')

        # Extract title (from h1 or specific div)
        title_elem = soup.find('h1')
        if title_elem:
            project['full_title'] = title_elem.get_text(strip=True)

        # Extract project description/abstract
        # Look for description in common GEPRIS patterns
        abstract = ""

        # Try various selectors for abstract
        abstract_selectors = [
            ('div', {'class': re.compile(r'abstract|beschreibung|description', re.I)}),
            ('div', {'id': re.compile(r'abstract|zusammenfassung', re.I)}),
        ]

        for tag, attrs in abstract_selectors:
            abstract_elem = soup.find(tag, attrs)
            if abstract_elem:
                abstract = abstract_elem.get_text(strip=True)
                break

        project['abstract'] = abstract

        # Extract structured data from definition lists (dl/dt/dd)
        # GEPRIS often uses this pattern
        dls = soup.find_all('dl')
        for dl in dls:
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')

            for dt, dd in zip(dts, dds):
                label = dt.get_text(strip=True).lower()
                value = dd.get_text(strip=True)

                if any(term in label for term in ['antragsteller', 'applicant', 'principal']):
                    project['principal_investigator'] = value
                elif any(term in label for term in ['institution', 'universität', 'university']):
                    project['institution'] = value
                elif any(term in label for term in ['laufzeit', 'duration', 'period', 'förderung']):
                    project['funding_period'] = value
                elif any(term in label for term in ['fachgebiet', 'subject', 'keywords']):
                    project['keywords'] = [kw.strip() for kw in re.split(r'[,;]', value) if kw.strip()]
                elif 'dfg' in label and ('fachsystematik' in label or 'classification' in label):
                    project['dfg_classification'] = value

        # Set defaults for missing fields
        project.setdefault('principal_investigator', '')
        project.setdefault('institution', '')
        project.setdefault('funding_period', '')
        project.setdefault('keywords', [])
        project.setdefault('dfg_classification', '')

        return project

    except Exception as e:
        print(f"    Error scraping project {project['project_id']}: {e}")
        project['error'] = str(e)
        return project


def main():
    """
    Main scraping function for individual projects
    """
    print("=" * 80)
    print("DFG Individual Projects Scraper v2")
    print("Using GEPRIS search to find projects by SPP number")
    print("=" * 80)

    # Load SPP programs
    if not INPUT_FILE.exists():
        print(f"ERROR: SPP programs file not found: {INPUT_FILE}")
        print("Please run scrape_spp_programs.py first!")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        spp_programs = json.load(f)

    print(f"Loaded {len(spp_programs)} SPP programs")

    # Ensure output directory exists
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load checkpoint
    checkpoint = load_checkpoint()
    start_index = checkpoint['last_index'] + 1

    if start_index > 0:
        print(f"Resuming from checkpoint (starting at index {start_index})")

    with sync_playwright() as p:
        # Launch browser
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Process each SPP program
            for i, spp in enumerate(spp_programs):
                if i < start_index:
                    continue

                spp_number = spp.get('spp_number', f'SPP_{i}')
                print(f"\n[{i+1}/{len(spp_programs)}] Processing {spp_number}")

                # Skip if already completed
                if spp_number in checkpoint['completed_spps']:
                    print(f"  Already completed, skipping")
                    continue

                # Search for projects
                projects = search_spp_projects(page, spp_number)

                # Scrape details for each project
                if projects:
                    print(f"  Scraping details for {len(projects)} projects...")
                    for j, project in enumerate(projects, 1):
                        print(f"    [{j}/{len(projects)}] {project['project_id']}", end=" ")
                        scrape_project_details(page, project)
                        print("✓")
                        time.sleep(1)  # Rate limiting
                else:
                    print(f"  No projects found for {spp_number}")

                # Save projects for this SPP
                output_file = PROJECTS_DIR / f"{spp_number.replace(' ', '_')}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'spp_number': spp_number,
                        'spp_title': spp.get('title', ''),
                        'projects_count': len(projects),
                        'projects': projects
                    }, f, ensure_ascii=False, indent=2)

                print(f"  Saved {len(projects)} projects to {output_file.name}")

                # Update checkpoint
                checkpoint['completed_spps'].append(spp_number)
                checkpoint['last_index'] = i
                save_checkpoint(checkpoint)

            print("\n" + "=" * 80)
            print("✓ Scraping complete!")
            print(f"✓ Processed {len(checkpoint['completed_spps'])} SPP programs")
            print(f"✓ Output directory: {PROJECTS_DIR}")
            print("=" * 80)

        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Progress saved to checkpoint.")
            print(f"Resume by running this script again.")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
