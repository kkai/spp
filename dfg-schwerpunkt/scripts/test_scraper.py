#!/usr/bin/env python3
"""Test script to debug GEPRIS scraping issues"""

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"

def test_load_spp_page():
    """Test 1: Can we load a single SPP page?"""
    print("TEST 1: Loading SPP page...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Try loading SPP 2100 (Soft Robotics)
        url = "https://gepris.dfg.de/gepris/projekt/359715917"
        print(f"Loading: {url}")

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            print("✓ Page loaded successfully")

            # Save HTML to inspect
            content = page.content()
            with open('/tmp/test_spp_page.html', 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ Saved HTML to /tmp/test_spp_page.html ({len(content)} chars)")

            # Try to find project links
            soup = BeautifulSoup(content, 'html.parser')

            # Find project links that are NOT the current page
            current_id = "359715917"
            projects = []

            for link in soup.find_all('a', href=lambda x: x and '/gepris/projekt/' in x):
                href = link.get('href')

                # Skip if it's the current page or special links
                if current_id in href or 'language=' in href or 'displayMode=' in href:
                    continue

                # Extract project ID
                import re
                match = re.search(r'/gepris/projekt/(\d+)', href)
                if match:
                    project_id = match.group(1)
                    title = link.get_text(strip=True)

                    if project_id not in [p['id'] for p in projects]:
                        projects.append({
                            'id': project_id,
                            'title': title,
                            'url': f"https://gepris.dfg.de{href}"
                        })

            print(f"✓ Found {len(projects)} unique project links")
            for i, p in enumerate(projects[:10]):
                print(f"  {i+1}. [{p['id']}] {p['title'][:60]}")

            browser.close()
            return len(projects) > 0

        except Exception as e:
            print(f"✗ Error: {e}")
            browser.close()
            return False

def test_load_project_details():
    """Test 2: Can we extract details from a project page?"""
    print("\nTEST 2: Loading individual project page...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Try loading one project from SPP 2100
        url = "https://gepris.dfg.de/gepris/projekt/498342743"
        print(f"Loading: {url}")

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            print("✓ Project page loaded successfully")

            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Extract project details
            project_data = {
                'project_id': '498342743',
                'url': url
            }

            # Get title from <title> tag
            title_tag = soup.find('title')
            if title_tag:
                full_title = title_tag.get_text()
                clean_title = full_title.replace('DFG - GEPRIS - ', '').strip()
                project_data['title'] = clean_title
                print(f"✓ Title: {clean_title}")

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

            if 'Antragstellerinnen / Antragsteller' in metadata:
                project_data['investigators'] = metadata['Antragstellerinnen / Antragsteller']
                print(f"✓ PIs: {project_data['investigators'][:60]}...")

            if 'Fachliche Zuordnung' in metadata:
                project_data['subject_area'] = metadata['Fachliche Zuordnung']
                print(f"✓ Subject: {project_data['subject_area'][:60]}...")

            # Get description from second content_frame div
            content_frames = soup.find_all('div', class_='content_frame')
            if len(content_frames) >= 2:
                description = content_frames[1].get_text(strip=True)
                project_data['description'] = description
                print(f"✓ Description: {len(description)} chars")
                print(f"  {description[:150]}...")

            browser.close()

            # Success if we have title, PIs, and description
            has_essentials = 'title' in project_data and 'investigators' in project_data and 'description' in project_data
            if has_essentials:
                print(f"✓ Successfully extracted all essential fields")
            return has_essentials

        except Exception as e:
            print(f"✗ Error: {e}")
            browser.close()
            return False

if __name__ == "__main__":
    test1 = test_load_spp_page()
    test2 = test_load_project_details()
    exit(0 if (test1 and test2) else 1)
