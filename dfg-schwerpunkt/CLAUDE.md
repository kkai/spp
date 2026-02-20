# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DFG Schwerpunktprogramme (SPP) scraper and analyzer. Scrapes research projects from the GEPRIS database and identifies wearables/AI-related projects using keyword matching.

**Data source**: https://gepris.dfg.de/gepris/programmlisten?language=de#PROGRAMM=Schwerpunktprogramme

## Commands

```bash
# Install dependencies
pip install -r scripts/requirements.txt
python3 -m playwright install chromium

# Core pipeline (run in order)
python3 scripts/scrape_spp_programs.py          # Step 1: Get SPP program list
python3 scripts/scrape_projects_working.py      # Step 2: Scrape individual projects (hours)
python3 scripts/analyze_relevance.py            # Step 3: Score and filter projects

# Optional: Extended data collection
python3 scripts/scrape_spp_program_details.py   # Scrape coordinator info, descriptions
python3 scripts/aggregate_spp_institutions.py   # Analyze institutional participation
python3 scripts/generate_spp_summaries.py       # Generate markdown summaries per SPP

# Priority scraping (wearables/AI SPPs first)
python3 scripts/scrape_priority_spps.py

# Testing
python3 scripts/test_one_spp.py                 # Test scraper on single SPP
```

## Architecture

```
scripts/
├── scrape_spp_programs.py        # Scrapes main SPP listing → data/raw/spp_programs.json
├── scrape_projects_working.py    # Scrapes projects per SPP → data/raw/projects/SPP_*.json
├── scrape_spp_program_details.py # Scrapes coordinator/description → data/raw/spp_programs_detailed.json
├── analyze_relevance.py          # Keyword scoring → data/processed/*.csv
├── aggregate_spp_institutions.py # Institution analysis → data/raw/spp_institutional_analysis.json
├── generate_spp_summaries.py     # Per-SPP markdown → data/spp_summaries/
└── scrape_priority_spps.py       # High-value SPPs first (imports from scrape_projects_working)

data/
├── raw/
│   ├── spp_programs.json           # Basic SPP program list
│   ├── spp_programs_detailed.json  # Detailed SPP data with coordinators
│   ├── projects/                   # One JSON per SPP with all projects
│   └── scraping_checkpoint.json    # Resume support
├── processed/                      # CSV outputs from analyzer
└── spp_summaries/                  # Markdown summaries per SPP
```

## Environment

Python 3.11 via `pyenv-virtualenv` (virtualenv `venv-data-311`). All scripts use `Path(__file__).parent.parent` as `BASE_DIR`, so they work when invoked from any directory.

## Key Implementation Details

**Virtual scrolling**: GEPRIS uses Tabulator.js with virtual DOM. Scrapers must scroll the table container to load all rows - see `scrape_spp_programs.py:39-55`.

**Checkpointing**: Project scrapers save progress to `scraping_checkpoint.json`. Delete this file to restart from scratch. The detail scraper uses `spp_detail_checkpoint.json`.

**Relevance scoring**: Projects scored 0-10 based on keyword matches with field weights:
- Title: 3x weight
- Abstract: 1.5x weight
- Keywords: 2x weight
- DFG classification: 1x weight

Threshold currently ≥1.0 for relevance in output files (configurable in `analyze_relevance.py:232-241`).

**Rate limiting**: 1.5-2 second random delays between requests. Full scrape takes several hours.

**German field mapping**: `scrape_spp_program_details.py` contains `FIELD_MAPPING` dict translating German metadata labels (e.g., "Sprecher / Sprecherin" → "spokesperson").

**GEPRIS page structure**: Project metadata is in `<span class="name">` elements paired with sibling text. Descriptions are in the second `<div class="content_frame">`. This pattern is used by both `scrape_projects_working.py` and `scrape_spp_program_details.py`.

**Module imports**: `scrape_priority_spps.py` imports `scrape_spp_projects`, `load_checkpoint`, and `save_checkpoint` from `scrape_projects_working`. Renaming or restructuring that module will break the priority scraper.

## Multiple Scraper Variants

Several scraper versions exist from iterative development:
- `scrape_projects_working.py` - **Current production version**
- `scrape_projects_stealth.py` - Uses playwright-stealth for anti-detection
- `scrape_projects_v2.py`, `scrape_projects.py` - Earlier versions, not used

Use `scrape_projects_working.py` for production scraping.
