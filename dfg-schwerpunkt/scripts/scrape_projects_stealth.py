#!/usr/bin/env python3
"""
DFG Individual Projects Scraper - Stealth Version
Uses anti-bot detection measures and human-like behavior
"""

import json
import time
import re
import random
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# Try to import stealth, but continue if not available
try:
    from playwright_stealth import stealth_sync
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False

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


def human_delay(min_sec=1.5, max_sec=4.0):
    """Add random human-like delay"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def scrape_spp_projects_direct(page, spp):
    """
    Try to scrape projects by visiting the SPP detail page directly
    and looking for project listings
    """
    spp_number = spp.get('spp_number', '')
    spp_url = spp.get('url', '')

    if not spp_url:
        return []

    try:
        print(f"  Visiting {spp_number} detail page...")
        page.goto(spp_url, wait_until="domcontentloaded", timeout=60000)
        human_delay(2, 4)

        # Scroll to simulate reading
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        human_delay(1, 2)

        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')

        projects = []

        # Strategy: Look for project links on the SPP page
        # GEPRIS might list related projects, teilprojekte, etc.

        # Find all links that look like projects
        all_links = soup.find_all('a', href=re.compile(r'/gepris/projekt/\d+'))

        seen_ids = set()
        for link in all_links:
            href = link['href']
            if not href.startswith('http'):
                href = BASE_URL + href if href.startswith('/') else f"{BASE_URL}/{href}"

            # Extract project ID
            project_id_match = re.search(r'projekt/(\d+)', href)
            if not project_id_match:
                continue

            project_id = project_id_match.group(1)

            # Skip if we've seen this ID (avoid duplicates)
            if project_id in seen_ids:
                continue
            seen_ids.add(project_id)

            # Skip if it's the SPP coordinator project itself
            if href == spp_url:
                continue

            title = link.get_text(strip=True)

            projects.append({
                'project_id': project_id,
                'title': title,
                'url': href,
                'spp_number': spp_number
            })

        # If we found projects, great! Otherwise try to find a "show all projects" link
        if not projects:
            # Look for links that might lead to project lists
            list_indicators = ['projekt', 'teilprojekt', 'projekte', 'projects', 'liste', 'list']
            for link in soup.find_all('a', href=True):
                link_text = link.get_text(strip=True).lower()
                if any(indicator in link_text for indicator in list_indicators):
                    # Try following this link
                    list_url = link['href']
                    if not list_url.startswith('http'):
                        list_url = BASE_URL + list_url if list_url.startswith('/') else f"{BASE_URL}/{list_url}"

                    print(f"  Following potential project list: {link_text[:50]}")
                    page.goto(list_url, wait_until="domcontentloaded", timeout=60000)
                    human_delay(2, 3)

                    # Now look for projects again
                    content2 = page.content()
                    soup2 = BeautifulSoup(content2, 'html.parser')

                    project_links = soup2.find_all('a', href=re.compile(r'/gepris/projekt/\d+'))
                    for plink in project_links:
                        href = plink['href']
                        if not href.startswith('http'):
                            href = BASE_URL + href if href.startswith('/') else f"{BASE_URL}/{href}"

                        project_id_match = re.search(r'projekt/(\d+)', href)
                        if not project_id_match:
                            continue
                        project_id = project_id_match.group(1)

                        if project_id in seen_ids or href == spp_url:
                            continue
                        seen_ids.add(project_id)

                        title = plink.get_text(strip=True)
                        projects.append({
                            'project_id': project_id,
                            'title': title,
                            'url': href,
                            'spp_number': spp_number
                        })

                    # Found projects, stop looking
                    if projects:
                        break

        print(f"  Found {len(projects)} projects")
        return projects

    except Exception as e:
        print(f"  Error: {e}")
        return []


def scrape_project_details(page, project):
    """Visit individual project page and extract details with human-like behavior"""
    try:
        print(f"    Visiting project {project['project_id']}...")
        page.goto(project['url'], wait_until="domcontentloaded", timeout=60000)
        human_delay(1.5, 3.0)

        # Scroll to simulate reading
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
        human_delay(0.5, 1.0)

        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')

        # Extract title
        title_elem = soup.find('h1')
        if title_elem:
            project['full_title'] = title_elem.get_text(strip=True)

        # Extract abstract/description
        abstract = ""
        # Try multiple selectors
        for selector in [
            ('div', {'class': re.compile(r'abstract|beschreibung', re.I)}),
            ('div', {'id': re.compile(r'abstract|zusammenfassung', re.I)}),
            ('p', {'class': re.compile(r'abstract|beschreibung', re.I)})
        ]:
            elem = soup.find(*selector)
            if elem:
                abstract = elem.get_text(strip=True)
                break

        # If still no abstract, try to find any substantial paragraph
        if not abstract:
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 100:  # Substantial text
                    abstract = text
                    break

        project['abstract'] = abstract

        # Extract from definition lists (common GEPRIS pattern)
        for dl in soup.find_all('dl'):
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')

            for dt, dd in zip(dts, dds):
                label = dt.get_text(strip=True).lower()
                value = dd.get_text(strip=True)

                if any(x in label for x in ['antragsteller', 'applicant', 'principal']):
                    project['principal_investigator'] = value
                elif any(x in label for x in ['institution', 'universität', 'university', 'hochschule']):
                    project['institution'] = value
                elif any(x in label for x in ['laufzeit', 'duration', 'period', 'förderung']):
                    project['funding_period'] = value
                elif any(x in label for x in ['fachgebiet', 'subject', 'keywords', 'schlagwort']):
                    keywords = [kw.strip() for kw in re.split(r'[,;]', value) if kw.strip()]
                    project['keywords'] = keywords
                elif 'dfg' in label and ('systematik' in label or 'classification' in label):
                    project['dfg_classification'] = value

        # Set defaults
        project.setdefault('principal_investigator', '')
        project.setdefault('institution', '')
        project.setdefault('funding_period', '')
        project.setdefault('keywords', [])
        project.setdefault('dfg_classification', '')

        return project

    except Exception as e:
        print(f"    Error scraping project {project.get('project_id')}: {e}")
        project['error'] = str(e)
        return project


def main():
    """Main scraping function with stealth mode"""
    print("=" * 80)
    print("DFG Individual Projects Scraper - STEALTH MODE")
    print("Using anti-bot detection and human-like behavior")
    print("=" * 80)

    # Load SPP programs
    if not INPUT_FILE.exists():
        print(f"ERROR: {INPUT_FILE} not found. Run scrape_spp_programs.py first!")
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
        print(f"Resuming from checkpoint (index {start_index})")

    with sync_playwright() as p:
        print("Launching browser in stealth mode...")

        # Launch with realistic browser settings
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        # Create context with realistic settings
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='de-DE',
            timezone_id='Europe/Berlin',
        )

        page = context.new_page()

        # Apply stealth mode if available
        if STEALTH_AVAILABLE:
            try:
                stealth_sync(page)
                print("Stealth mode enabled")
            except Exception as e:
                print(f"Note: Stealth mode failed ({e}), continuing without it")
        else:
            print("Note: playwright-stealth not available, using basic anti-detection")

        try:
            # Process each SPP
            for i, spp in enumerate(spp_programs):
                if i < start_index:
                    continue

                spp_number = spp.get('spp_number', f'SPP_{i}')
                print(f"\n[{i+1}/{len(spp_programs)}] Processing {spp_number}")
                print(f"  {spp.get('title', '')[:70]}...")

                # Skip if already completed
                if spp_number in checkpoint['completed_spps']:
                    print(f"  Already completed, skipping")
                    continue

                # Try to find projects
                projects = scrape_spp_projects_direct(page, spp)

                # Scrape details for each project
                if projects:
                    print(f"  Scraping details for {len(projects)} projects...")
                    for j, project in enumerate(projects, 1):
                        print(f"    [{j}/{len(projects)}] {project['project_id']}", end=" ")
                        scrape_project_details(page, project)
                        print("✓")

                        # Human-like delay between projects
                        if j < len(projects):
                            human_delay(2, 4)
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

                # Longer delay between SPP programs
                if i < len(spp_programs) - 1:
                    delay = random.uniform(3, 7)
                    print(f"  Waiting {delay:.1f}s before next SPP...")
                    time.sleep(delay)

            print("\n" + "=" * 80)
            print("✓ Scraping complete!")
            print(f"✓ Processed {len(checkpoint['completed_spps'])} SPP programs")

            # Count total projects
            total_projects = 0
            for f in PROJECTS_DIR.glob("*.json"):
                with open(f) as jf:
                    data = json.load(jf)
                    total_projects += data.get('projects_count', 0)

            print(f"✓ Total projects collected: {total_projects}")
            print(f"✓ Output directory: {PROJECTS_DIR}")
            print("=" * 80)

        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Progress saved to checkpoint.")
            print("Resume by running this script again.")
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
