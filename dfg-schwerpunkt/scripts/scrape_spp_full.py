#!/usr/bin/env python3
"""
Full DFG Schwerpunktprogramme scraper — gets ALL SPPs from GEPRIS.

The previous scraper only got 20 SPPs because Tabulator.js uses virtual DOM
and scrolling didn't load all rows. This version:
1. Accesses Tabulator's in-memory data via JS (bypasses virtual rendering)
2. Falls back to paginated GEPRIS search if the table approach fails
3. Scrapes detail pages for each program
"""

import json
import time
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
OUTPUT_FILE = DATA_DIR / "spp_programs_full.json"

BASE_URL = "https://gepris.dfg.de"
LIST_URL = f"{BASE_URL}/gepris/programmlisten?language=de#PROGRAMM=Schwerpunktprogramme"


def extract_tabulator_data(page):
    """Try to extract all data directly from the Tabulator instance in JS."""
    print("Attempting to extract Tabulator data via JS...")

    data = page.evaluate("""
    () => {
        // Find all Tabulator instances on the page
        const tables = document.querySelectorAll('.tabulator');
        const results = [];

        for (const table of tables) {
            // Tabulator stores instance on the DOM element
            const instance = table.tabulator || table._tabulator;
            if (instance && typeof instance.getData === 'function') {
                const rows = instance.getData();
                results.push(...rows);
            }
        }

        // Alternative: check for global references
        if (results.length === 0) {
            // Try window-level Tabulator references
            for (const key of Object.keys(window)) {
                try {
                    const obj = window[key];
                    if (obj && typeof obj.getData === 'function' && typeof obj.getRows === 'function') {
                        const rows = obj.getData();
                        if (rows.length > 0) {
                            results.push(...rows);
                        }
                    }
                } catch(e) {}
            }
        }

        return results;
    }
    """)

    if data:
        print(f"  Got {len(data)} rows from Tabulator JS API")
    else:
        print("  Tabulator JS API returned no data")

    return data


def scrape_via_search(page):
    """
    Use GEPRIS search to find all Schwerpunktprogramme.
    This is the fallback approach using paginated search results.
    """
    print("\nUsing GEPRIS search to find all SPPs...")

    # GEPRIS search for coordinated programs (eintragsart=4 = koordinierte Programme)
    # bewilligungStatus: empty=all, 2=laufend (running), 3=abgeschlossen (completed)
    search_url = (
        f"{BASE_URL}/gepris/OCTOPUS?"
        "task=doSearchSimple&context=projekt"
        "&eintragsart=4"  # koordinierte Programme
        "&hitsPerPage=100"
        "&index=0"
        "&nurProjekteMitAB=false"
        "&teilprojekte=false"
        "&phrase=true"
    )

    programs = []
    page_index = 0

    while True:
        url = search_url.replace("index=0", f"index={page_index}")
        print(f"  Fetching search results page (index={page_index})...")
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(2)

        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')

        # Find result entries
        results = soup.find_all('div', class_='result_entry')
        if not results:
            # Try alternative selectors
            results = soup.find_all('div', class_='ergebnis_eintrag')

        if not results:
            print(f"  No results found on page index={page_index}, stopping.")
            break

        for entry in results:
            link = entry.find('a', href=True)
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link['href']
            if not href.startswith('http'):
                href = BASE_URL + (href if href.startswith('/') else f"/{href}")

            # Only keep Schwerpunktprogramme
            if 'Schwerpunktprogramm' in title or 'SPP' in entry.get_text():
                programs.append({
                    'title': title,
                    'url': href,
                })

        # Check for next page
        next_link = soup.find('a', text=re.compile(r'weiter|next|›', re.I))
        if next_link:
            page_index += len(results)
        else:
            break

    print(f"  Found {len(programs)} programs via search")
    return programs


def scrape_programmlisten(page):
    """
    Scrape the programmlisten page — improved approach.
    Clicks the SPP tab, waits for table, then extracts via JS or DOM.
    """
    print(f"Navigating to {LIST_URL}")
    page.goto(LIST_URL, wait_until="networkidle", timeout=60000)
    time.sleep(3)

    # Click the Schwerpunktprogramme tab if it exists
    try:
        spp_tab = page.locator('text=Schwerpunktprogramme').first
        if spp_tab.is_visible():
            spp_tab.click()
            time.sleep(3)
            print("Clicked Schwerpunktprogramme tab")
    except Exception as e:
        print(f"  No tab to click: {e}")

    # Save debug screenshot
    debug_dir = DATA_DIR / "debug"
    debug_dir.mkdir(exist_ok=True)
    page.screenshot(path=str(debug_dir / "programmlisten.png"), full_page=True)

    # Approach 1: Try Tabulator JS API
    tabulator_data = extract_tabulator_data(page)
    if tabulator_data and len(tabulator_data) > 20:
        return parse_tabulator_data(tabulator_data)

    # Approach 2: Aggressive scrolling + DOM extraction
    print("\nFalling back to aggressive scroll + DOM extraction...")
    return scrape_with_aggressive_scroll(page)


def parse_tabulator_data(data):
    """Parse raw Tabulator row data into our program format."""
    programs = []
    for row in data:
        typ = row.get('TYP', '')
        if typ != 'SPP':
            continue

        nummer = str(row.get('NUMMER', ''))
        title = row.get('PRJ_TITEL', '')
        # PRJ_TITEL might contain HTML — strip tags
        if '<' in title:
            title = BeautifulSoup(title, 'html.parser').get_text(strip=True)

        # Extract URL from title HTML
        url = ''
        raw_title = row.get('PRJ_TITEL', '')
        if 'href=' in raw_title:
            match = re.search(r'href="([^"]+)"', raw_title)
            if match:
                href = match.group(1)
                url = href if href.startswith('http') else BASE_URL + href

        # Also try DETAIL_URL or similar fields
        if not url:
            url = row.get('URL', row.get('DETAIL_URL', ''))
            if url and not url.startswith('http'):
                url = BASE_URL + url

        programs.append({
            'spp_number': f'SPP {nummer}' if nummer and not nummer.startswith('SPP') else nummer,
            'title': title,
            'url': url,
            'beginn': str(row.get('PRJ_BEGINN', '')),
            'bundesland': row.get('BUNDESLAND', ''),
            'int_bezug': row.get('INT_BEZUG', ''),
            'variante': row.get('VARIANTE', ''),
            'wissenschaftsbereich': row.get('WSB', ''),
        })

    print(f"Parsed {len(programs)} SPP programs from Tabulator data")
    return programs


def scrape_with_aggressive_scroll(page):
    """
    Scroll the Tabulator table aggressively and collect ALL rendered rows.
    Uses a Set to deduplicate rows that appear multiple times.
    """
    programs = {}  # keyed by spp_number to deduplicate

    # Find the table holder
    holder = page.query_selector('.tabulator-tableholder')
    if not holder:
        print("  No .tabulator-tableholder found!")
        return []

    # Get total scroll height
    scroll_info = page.evaluate("""
    () => {
        const holder = document.querySelector('.tabulator-tableholder');
        return {
            scrollHeight: holder.scrollHeight,
            clientHeight: holder.clientHeight,
            scrollTop: holder.scrollTop
        };
    }
    """)
    print(f"  Table: scrollHeight={scroll_info['scrollHeight']}, clientHeight={scroll_info['clientHeight']}")

    # Scroll in small increments and collect rows at each position
    scroll_step = max(50, scroll_info['clientHeight'] // 3)
    max_scroll = scroll_info['scrollHeight']
    current = 0

    while current <= max_scroll + scroll_step:
        page.evaluate(f"""
            const holder = document.querySelector('.tabulator-tableholder');
            if (holder) holder.scrollTop = {current};
        """)
        time.sleep(0.15)

        # Extract visible rows
        rows_data = page.evaluate("""
        () => {
            const rows = document.querySelectorAll('.tabulator-row');
            return Array.from(rows).map(row => {
                const cells = {};
                row.querySelectorAll('.tabulator-cell').forEach(cell => {
                    const field = cell.getAttribute('tabulator-field');
                    if (field) {
                        cells[field] = cell.innerHTML;
                        cells[field + '_text'] = cell.innerText;
                    }
                });
                return cells;
            });
        }
        """)

        for row in rows_data:
            typ = row.get('TYP_text', '').strip()
            if typ != 'SPP':
                continue

            nummer = row.get('NUMMER_text', '').strip()
            if not nummer:
                continue

            spp_key = f"SPP {nummer}"

            # Extract title and URL from HTML
            title_html = row.get('PRJ_TITEL', '')
            title_text = row.get('PRJ_TITEL_text', '').strip()
            url = ''
            match = re.search(r'href="([^"]+)"', title_html)
            if match:
                href = match.group(1)
                url = href if href.startswith('http') else BASE_URL + href

            if spp_key not in programs:
                programs[spp_key] = {
                    'spp_number': spp_key,
                    'title': title_text,
                    'url': url,
                    'beginn': row.get('PRJ_BEGINN_text', '').strip(),
                    'bundesland': row.get('BUNDESLAND_text', '').strip(),
                    'int_bezug': row.get('INT_BEZUG_text', '').strip(),
                    'variante': row.get('VARIANTE_text', '').strip(),
                    'wissenschaftsbereich': row.get('WSB_text', '').strip(),
                }

        current += scroll_step

    result = sorted(programs.values(), key=lambda x: x.get('spp_number', ''))
    print(f"  Collected {len(result)} unique SPP programs via scrolling")
    return result


def scrape_program_detail(page, program):
    """Visit individual program page and extract detailed info."""
    url = program.get('url', '')
    if not url:
        return program

    spp = program['spp_number']
    print(f"  [{spp}] Scraping detail page...")

    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(1.5)

        # Use JS to extract structured data from GEPRIS detail page
        details = page.evaluate("""
        () => {
            const result = {};

            // Extract <span class="name"> + sibling value pairs
            document.querySelectorAll('span.name').forEach(span => {
                const label = span.textContent.trim().replace(/:$/, '');
                const parent = span.parentElement;
                if (parent) {
                    // Value is all text in parent minus the label
                    let value = '';
                    const siblings = Array.from(parent.childNodes);
                    const spanIndex = siblings.indexOf(span);
                    for (let i = spanIndex + 1; i < siblings.length; i++) {
                        value += siblings[i].textContent || '';
                    }
                    value = value.trim();
                    if (value) result[label] = value;
                }
            });

            // Extract description: look for #projekttext or similar
            const projekttext = document.querySelector('#projekttext');
            if (projekttext) {
                result['_projekttext'] = projekttext.textContent.trim();
            }

            // Also try the main content area for description text
            const detailContent = document.querySelector('.detail_content, .detailseite');
            if (detailContent) {
                // Find paragraphs that look like descriptions (not metadata)
                const paras = detailContent.querySelectorAll('p');
                const descParts = [];
                for (const p of paras) {
                    const text = p.textContent.trim();
                    // Skip short metadata-like lines
                    if (text.length > 100 && !text.startsWith('Projekt') && !text.includes('Förderung')) {
                        descParts.push(text);
                    }
                }
                if (descParts.length > 0) {
                    result['_description_paras'] = descParts.join('\\n\\n');
                }
            }

            // Extract project list link
            const links = document.querySelectorAll('a[href*="ergebnisse"], a[href*="Ergebnisse"]');
            if (links.length > 0) {
                result['_projects_url'] = links[0].href;
            }

            // Extract website link — multiple strategies
            // Strategy 1: Look for "Webseite" or "Homepage" label with sibling link
            document.querySelectorAll('span.name').forEach(span => {
                if (span.textContent.includes('Webseite') || span.textContent.includes('Homepage')) {
                    const link = span.parentElement?.querySelector('a[href]');
                    if (link && link.href && !link.href.includes('gepris.dfg.de')) {
                        result['_website'] = link.href;
                    }
                }
            });

            // Strategy 2: Look for a.extern or a[target="_blank"] links outside GEPRIS
            if (!result['_website']) {
                const externLinks = document.querySelectorAll('a.extern, .detail_content a[target="_blank"], .detail__content a[target="_blank"]');
                for (const link of externLinks) {
                    const href = link.href;
                    if (href && !href.includes('gepris.dfg.de') && !href.includes('dfg.de/gepris') && href.startsWith('http')) {
                        result['_website'] = href;
                        break;
                    }
                }
            }

            // Strategy 3: Any external link in the detail content area
            if (!result['_website']) {
                const contentArea = document.querySelector('.detail_content, .detail__content, .detailseite');
                if (contentArea) {
                    const links = contentArea.querySelectorAll('a[href^="http"]');
                    for (const link of links) {
                        const href = link.href;
                        if (href && !href.includes('gepris.dfg.de') && !href.includes('dfg.de/gepris') && !href.includes('dfg.de/foerderung')) {
                            result['_website'] = href;
                            break;
                        }
                    }
                }
            }

            return result;
        }
        """)

        # Map German field names
        field_map = {
            'Sprecher/in': 'coordinator_name',
            'Sprecher / Sprecherin': 'coordinator_name',
            'Sprecherin / Sprecher': 'coordinator_name',
            'Sprecherin': 'coordinator_name',
            'Sprecher': 'coordinator_name',
            'DFG-Verfahren': 'funding_type',
            'Förderung': 'funding_period',
            'Fachliche Zuordnung': 'subject_area',
            'Webseite': 'website',
            'Internationaler Bezug': 'international_partners',
        }

        for german, english in field_map.items():
            if german in details:
                program[english] = details[german]

        # Use best description source
        description = details.get('_projekttext', '') or details.get('_description_paras', '')
        program['description'] = description[:500] if description else ''
        program['full_description'] = description
        program['projects_url'] = details.get('_projects_url', '')
        program['detail_page_url'] = url
        if details.get('_website'):
            program['website'] = details['_website']

    except Exception as e:
        print(f"  [{spp}] Error: {e}")
        program['_error'] = str(e)

    return program


def main():
    print("=" * 70)
    print("DFG Schwerpunktprogramme — Full Scraper")
    print("=" * 70)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # visible for debugging
        context = browser.new_context(
            viewport={'width': 1280, 'height': 900},
            locale='de-DE',
        )
        page = context.new_page()

        # Step 1: Get program list from programmlisten page
        programs = scrape_programmlisten(page)

        if len(programs) < 25:
            print(f"\nOnly found {len(programs)} programs — trying GEPRIS search as fallback...")
            search_programs = scrape_via_search(page)
            if len(search_programs) > len(programs):
                programs = search_programs

        if not programs:
            print("ERROR: No programs found! Saving debug info.")
            page.screenshot(path=str(DATA_DIR / "debug" / "error.png"), full_page=True)
            with open(DATA_DIR / "debug" / "error.html", 'w') as f:
                f.write(page.content())
            browser.close()
            return

        print(f"\n{'=' * 70}")
        print(f"Found {len(programs)} SPP programs total")
        print(f"{'=' * 70}")

        # Filter: currently running + back to 2020
        filtered = []
        for prog in programs:
            beginn = prog.get('beginn', '')
            try:
                year = int(beginn) if beginn else 0
            except ValueError:
                year = 0

            # Keep if started 2020+ or if no year info (likely current)
            if year >= 2020 or year == 0:
                filtered.append(prog)
                prog['_filter'] = 'start>=2020'
            else:
                # Also keep older ones that are likely still running (SPPs run ~6 years)
                # So anything starting 2017+ could still be active
                if year >= 2017:
                    filtered.append(prog)
                    prog['_filter'] = 'likely_still_running'

        print(f"After filtering (2020+ and likely still running): {len(filtered)} programs")
        print(f"Dropped {len(programs) - len(filtered)} older/completed programs")

        # Step 2: Scrape details for each program
        print(f"\nScraping detail pages for {len(filtered)} programs...")
        for i, prog in enumerate(filtered, 1):
            print(f"[{i}/{len(filtered)}]", end="")
            scrape_program_detail(page, prog)
            time.sleep(1)  # rate limiting

        # Also save ALL programs (unfiltered) for reference
        all_output = DATA_DIR / "spp_programs_all.json"
        with open(all_output, 'w', encoding='utf-8') as f:
            # Strip internal fields
            clean = [{k: v for k, v in p.items() if not k.startswith('_')} for p in programs]
            json.dump(clean, f, ensure_ascii=False, indent=2)
        print(f"\nSaved ALL {len(programs)} programs to {all_output}")

        # Save filtered programs
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            clean = [{k: v for k, v in p.items() if not k.startswith('_')} for p in filtered]
            json.dump(clean, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(filtered)} filtered programs to {OUTPUT_FILE}")

        # Print summary
        print(f"\n{'=' * 70}")
        print("SUMMARY")
        print(f"{'=' * 70}")
        by_year = {}
        for prog in filtered:
            y = prog.get('beginn', '?')
            by_year.setdefault(y, []).append(prog['spp_number'])
        for year in sorted(by_year.keys()):
            print(f"  {year}: {len(by_year[year])} programs — {', '.join(by_year[year][:5])}")
        print(f"{'=' * 70}")

        browser.close()


if __name__ == "__main__":
    main()
