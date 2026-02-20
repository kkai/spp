#!/usr/bin/env python3
"""
DFG Schwerpunktprogramme (SPP) Scraper
Scrapes all SPP programs from GEPRIS database using Playwright
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
OUTPUT_FILE = DATA_DIR / "spp_programs.json"

# URLs
BASE_URL = "https://gepris.dfg.de"
START_URL = f"{BASE_URL}/gepris/programmlisten?language=de#PROGRAMM=Schwerpunktprogramme"


def scrape_spp_list(page):
    """
    Scrape the list of all SPP programs from the main page
    """
    print(f"Navigating to {START_URL}")
    page.goto(START_URL, wait_until="networkidle", timeout=60000)

    # Wait for the dynamic table to load
    time.sleep(5)

    # Scroll the table to load all virtual rows
    print("Scrolling table to load all rows...")
    table_holder = page.query_selector('.tabulator-tableholder')
    if table_holder:
        # Scroll to bottom multiple times to load all virtual rows
        for i in range(50):  # Adjust if needed
            page.evaluate("""
                const holder = document.querySelector('.tabulator-tableholder');
                if (holder) {
                    holder.scrollTop = holder.scrollHeight;
                }
            """)
            time.sleep(0.3)  # Brief pause to let rows render

        # Scroll back to top
        page.evaluate("""
            const holder = document.querySelector('.tabulator-tableholder');
            if (holder) {
                holder.scrollTop = 0;
            }
        """)
        time.sleep(2)
        print("Finished scrolling")

    # Get the page content
    content = page.content()
    soup = BeautifulSoup(content, 'html.parser')

    # Save raw HTML for debugging
    debug_file = DATA_DIR / "debug_spp_page.html"
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Saved debug HTML to {debug_file}")

    # The page uses Tab ulator.js which renders rows dynamically
    # We need to find all rows with TYP="SPP"
    spp_programs = []

    # Find all tabulator rows
    rows = soup.find_all('div', class_='tabulator-row')
    print(f"Found {len(rows)} total program rows")

    for row in rows:
        # Find the TYP cell
        typ_cell = row.find('div', {'tabulator-field': 'TYP'})
        if not typ_cell:
            continue

        typ_text = typ_cell.get_text(strip=True)

        # Only process SPP type programs
        if typ_text != 'SPP':
            continue

        # Extract program number
        nummer_cell = row.find('div', {'tabulator-field': 'NUMMER'})
        spp_number = nummer_cell.get_text(strip=True) if nummer_cell else ''

        # Extract title and URL
        titel_cell = row.find('div', {'tabulator-field': 'PRJ_TITEL'})
        title = ''
        url = ''
        if titel_cell:
            link = titel_cell.find('a', href=True)
            if link:
                title = link.get_text(strip=True)
                href = link['href']
                if not href.startswith('http'):
                    url = BASE_URL + href if href.startswith('/') else f"{BASE_URL}/{href}"
                else:
                    url = href

        # Extract other metadata
        beginn_cell = row.find('div', {'tabulator-field': 'PRJ_BEGINN'})
        beginn = beginn_cell.get_text(strip=True) if beginn_cell else ''

        bundesland_cell = row.find('div', {'tabulator-field': 'BUNDESLAND'})
        bundesland = bundesland_cell.get_text(strip=True) if bundesland_cell else ''

        int_bezug_cell = row.find('div', {'tabulator-field': 'INT_BEZUG'})
        int_bezug = int_bezug_cell.get_text(strip=True) if int_bezug_cell else ''

        # Get hidden fields too
        variante_cell = row.find('div', {'tabulator-field': 'VARIANTE'})
        variante = variante_cell.get_text(strip=True) if variante_cell else ''

        wsb_cell = row.find('div', {'tabulator-field': 'WSB'})
        wsb = wsb_cell.get_text(strip=True) if wsb_cell else ''

        if spp_number and title and url:
            spp_programs.append({
                'spp_number': f'SPP {spp_number}',
                'title': title,
                'url': url,
                'beginn': beginn,
                'bundesland': bundesland,
                'int_bezug': int_bezug,
                'variante': variante,
                'wissenschaftsbereich': wsb
            })

    print(f"Found {len(spp_programs)} SPP programs")
    return spp_programs


def scrape_program_details(page, spp_program):
    """
    Visit individual SPP program page and extract detailed information
    """
    print(f"Scraping details for {spp_program['spp_number']}")

    try:
        page.goto(spp_program['url'], wait_until="networkidle", timeout=60000)
        time.sleep(2)

        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')

        # Extract program details
        # This will vary based on GEPRIS page structure

        # Try to find description
        description = ""
        description_div = soup.find('div', class_=re.compile(r'beschreibung|description', re.I))
        if description_div:
            description = description_div.get_text(strip=True)

        # Try to find period/duration
        period = ""
        period_elem = soup.find(text=re.compile(r'Laufzeit|Duration|Period', re.I))
        if period_elem:
            parent = period_elem.find_parent()
            if parent:
                period = parent.get_text(strip=True)

        # Look for project list URL
        projects_url = ""
        projects_link = soup.find('a', text=re.compile(r'Projekte|Projects', re.I))
        if projects_link and projects_link.get('href'):
            href = projects_link['href']
            if not href.startswith('http'):
                projects_url = BASE_URL + href if href.startswith('/') else f"{BASE_URL}/{href}"
            else:
                projects_url = href

        # Update program info
        spp_program.update({
            'description': description,
            'period': period,
            'projects_url': projects_url,
            'detail_page_url': spp_program['url']
        })

        print(f"  - Extracted details for {spp_program['spp_number']}")

    except Exception as e:
        print(f"  - Error scraping {spp_program['spp_number']}: {e}")
        spp_program['error'] = str(e)

    return spp_program


def main():
    """
    Main scraping function
    """
    print("=" * 80)
    print("DFG Schwerpunktprogramme Scraper")
    print("=" * 80)

    # Ensure output directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # Launch browser
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Step 1: Get list of all SPP programs
            spp_programs = scrape_spp_list(page)

            if not spp_programs:
                print("WARNING: No SPP programs found! Check the debug HTML file.")
                print("The page structure might have changed or JavaScript rendering might be different.")
                return

            # Step 2: Visit each program page for detailed info
            print(f"\nScraping details for {len(spp_programs)} programs...")
            for i, spp in enumerate(spp_programs, 1):
                print(f"[{i}/{len(spp_programs)}] ", end="")
                scrape_program_details(page, spp)
                time.sleep(1)  # Rate limiting

            # Step 3: Save to JSON
            print(f"\nSaving {len(spp_programs)} programs to {OUTPUT_FILE}")
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(spp_programs, f, ensure_ascii=False, indent=2)

            print("=" * 80)
            print(f"✓ Scraping complete!")
            print(f"✓ Saved {len(spp_programs)} SPP programs")
            print(f"✓ Output: {OUTPUT_FILE}")
            print("=" * 80)

        finally:
            browser.close()


if __name__ == "__main__":
    main()
