#!/usr/bin/env python3
"""
DFG Individual Projects Scraper
Scrapes individual research projects within each SPP program
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


def scrape_project_list(page, projects_url, spp_number):
    """
    Scrape the list of projects for a given SPP program
    """
    if not projects_url:
        print(f"  No projects URL found for {spp_number}")
        return []

    try:
        print(f"  Loading projects page: {projects_url}")
        page.goto(projects_url, wait_until="networkidle", timeout=60000)
        time.sleep(2)

        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')

        projects = []

        # Look for project entries
        # GEPRIS typically shows projects in a list or table format

        # Strategy 1: Find all project links
        # Projects usually have URLs like /gepris/projekt/XXXXXX
        project_links = soup.find_all('a', href=re.compile(r'/gepris/projekt/\d+'))

        for link in project_links:
            href = link['href']
            if not href.startswith('http'):
                href = BASE_URL + href if href.startswith('/') else f"{BASE_URL}/{href}"

            # Extract project ID from URL
            project_id_match = re.search(r'projekt/(\d+)', href)
            project_id = project_id_match.group(1) if project_id_match else None

            # Get project title from link text
            title = link.get_text(strip=True)

            # Avoid duplicates
            if not any(p['project_id'] == project_id for p in projects):
                projects.append({
                    'project_id': project_id,
                    'title': title,
                    'url': href,
                    'spp_number': spp_number
                })

        print(f"  Found {len(projects)} projects")
        return projects

    except Exception as e:
        print(f"  Error loading projects list: {e}")
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

        # Extract various project details
        # GEPRIS typically has structured data in divs or tables

        # Title (might be in h1 or specific div)
        title_elem = soup.find('h1')
        if title_elem:
            project['full_title'] = title_elem.get_text(strip=True)

        # Abstract/Description
        abstract = ""
        abstract_elem = soup.find('div', {'id': re.compile(r'abstract|zusammenfassung', re.I)})
        if not abstract_elem:
            abstract_elem = soup.find('div', class_=re.compile(r'abstract|beschreibung|description', re.I))
        if abstract_elem:
            abstract = abstract_elem.get_text(strip=True)
        project['abstract'] = abstract

        # Principal Investigator (PI)
        pi = ""
        pi_elem = soup.find(text=re.compile(r'Antragsteller|Applicant|Principal Investigator', re.I))
        if pi_elem:
            parent = pi_elem.find_parent()
            if parent:
                # Get the next sibling or within the same parent
                pi_text = parent.get_text(strip=True)
                pi = pi_text.replace('Antragsteller', '').replace('Applicant', '').strip()
        project['principal_investigator'] = pi

        # Institution
        institution = ""
        inst_elem = soup.find(text=re.compile(r'Institution|Universität|University', re.I))
        if inst_elem:
            parent = inst_elem.find_parent()
            if parent:
                institution = parent.get_text(strip=True)
        project['institution'] = institution

        # Funding period
        period = ""
        period_elem = soup.find(text=re.compile(r'Laufzeit|Duration|Period|Förderung', re.I))
        if period_elem:
            parent = period_elem.find_parent()
            if parent:
                period = parent.get_text(strip=True)
        project['funding_period'] = period

        # Keywords/Subject areas
        keywords = []
        keywords_elem = soup.find(text=re.compile(r'Fachgebiet|Subject|Keywords|Schlagwörter', re.I))
        if keywords_elem:
            parent = keywords_elem.find_parent()
            if parent:
                # Get all text, split by common separators
                kw_text = parent.get_text(strip=True)
                keywords = [kw.strip() for kw in re.split(r'[,;]', kw_text) if kw.strip()]
        project['keywords'] = keywords

        # DFG classification
        dfg_class = ""
        dfg_elem = soup.find(text=re.compile(r'DFG-Fachsystematik|DFG Classification', re.I))
        if dfg_elem:
            parent = dfg_elem.find_parent()
            if parent:
                dfg_class = parent.get_text(strip=True)
        project['dfg_classification'] = dfg_class

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
    print("DFG Individual Projects Scraper")
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

                # Get projects list
                projects_url = spp.get('projects_url', '')
                if not projects_url:
                    # Try to construct projects URL from main URL
                    detail_url = spp.get('detail_page_url', spp.get('url', ''))
                    # Some SPP pages might have projects listed directly
                    projects_url = detail_url

                projects = scrape_project_list(page, projects_url, spp_number)

                # Scrape details for each project
                if projects:
                    print(f"  Scraping details for {len(projects)} projects...")
                    for j, project in enumerate(projects, 1):
                        print(f"    [{j}/{len(projects)}] {project['project_id']}", end=" ")
                        scrape_project_details(page, project)
                        print("✓")
                        time.sleep(1)  # Rate limiting

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
