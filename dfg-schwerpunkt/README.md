# DFG Schwerpunktprogramme - Wearables & AI Analysis

Web scraping and analysis tool to identify wearables and AI-related research projects in DFG Schwerpunktprogramme (SPP).

## Quick Start

```bash
# 1. Install dependencies
pip install -r scripts/requirements.txt
python3 -m playwright install chromium

# 2. Scrape SPP programs
python3 scripts/scrape_spp_programs.py

# 3. Scrape individual projects (may take hours)
python3 scripts/scrape_projects.py

# 4. Analyze for wearables/AI relevance
python3 scripts/analyze_relevance.py

# 5. View results
cat reports/summary_report.md
open data/processed/wearables_ai_combined.csv
```

## Project Structure

```
dfg-schwerpunkt/
├── scripts/
│   ├── scrape_spp_programs.py      # Step 1: Scrape SPP programs
│   ├── scrape_projects.py          # Step 2: Scrape individual projects
│   ├── analyze_relevance.py        # Step 3: Analyze & filter
│   └── requirements.txt            # Python dependencies
├── data/
│   ├── raw/
│   │   ├── spp_programs.json       # All SPP programs
│   │   └── projects/               # Individual project JSONs
│   │       └── SPP_XXXX.json       # One file per SPP
│   └── processed/
│       ├── all_projects.csv        # All projects with scores
│       ├── wearables_relevant.csv  # Wearables projects (score ≥3)
│       ├── ai_relevant.csv         # AI projects (score ≥3)
│       └── wearables_ai_combined.csv  # Both wearables AND AI
├── reports/
│   └── summary_report.md           # Human-readable summary
├── CLAUDE.md                       # Technical documentation
└── README.md                       # This file
```

## Usage Guide

### Step 1: Scrape SPP Programs

```bash
python3 scripts/scrape_spp_programs.py
```

**What it does**:
- Navigates to GEPRIS Schwerpunktprogramme page
- Extracts all SPP program listings
- Saves program metadata to `data/raw/spp_programs.json`

**Expected output**:
```
Found X SPP programs
Saved to data/raw/spp_programs.json
```

**Time**: ~2-5 minutes

### Step 2: Scrape Individual Projects

```bash
python3 scripts/scrape_projects.py
```

**What it does**:
- Reads the SPP programs list
- For each SPP, visits its project list page
- Extracts all individual research projects
- Saves one JSON file per SPP to `data/raw/projects/`

**Features**:
- ✅ **Checkpointing**: Can resume if interrupted (Ctrl+C)
- ✅ **Rate limiting**: 1-2 sec delays between requests
- ✅ **Error handling**: Logs failed URLs

**Expected output**:
```
[1/X] Processing SPP 2000
  Found 15 projects
  Scraping details for 15 projects...
  Saved to data/raw/projects/SPP_2000.json
```

**Time**: 2-4 hours (depending on number of SPP programs and projects)

### Step 3: Analyze Relevance

```bash
python3 scripts/analyze_relevance.py
```

**What it does**:
- Loads all scraped projects
- Scores each project for wearables and AI relevance
- Generates filtered CSV files
- Creates markdown summary report

**Output files**:
- `data/processed/all_projects.csv` - All projects with relevance scores
- `data/processed/wearables_relevant.csv` - Wearables projects (score ≥ 3)
- `data/processed/ai_relevant.csv` - AI projects (score ≥ 3)
- `data/processed/wearables_ai_combined.csv` - Projects relevant to BOTH
- `reports/summary_report.md` - Summary with top 20 lists and statistics

**Time**: < 1 minute

## Relevance Scoring

Projects are automatically scored based on keyword matching:

### Wearables Keywords (German/English)
- wearable, tragbar, smart watch, fitness tracker
- sensor, biosensor, körpersensor
- e-textil, smart textile, smart fabric
- gesundheitsmonitor, health monitoring
- mobile sensoren, body-worn

### AI Keywords (German/English)
- künstliche intelligenz, AI, KI
- maschinelles lernen, machine learning
- deep learning, neural network
- computer vision, bildverarbeitung
- natural language processing, NLP
- mustererkennung, pattern recognition

### Scoring Logic

- **Title match**: 3x weight (most important)
- **Abstract match**: 1.5x weight
- **Keywords match**: 2x weight
- **DFG classification match**: 1x weight

**Threshold**: Projects with score ≥ 3.0 are considered relevant.

## Configuration

### Adjust Keywords

Edit `scripts/analyze_relevance.py` to customize keyword lists:

```python
WEARABLES_KEYWORDS = {
    'german': ['your', 'keywords'],
    'english': ['your', 'keywords']
}

AI_KEYWORDS = {
    'german': ['your', 'keywords'],
    'english': ['your', 'keywords']
}
```

### Adjust Relevance Threshold

Change the threshold in `analyze_relevance.py`:

```python
# Line ~240
wearables_df = all_df[all_df['wearables_score'] >= 3].copy()  # Change 3 to your threshold
```

### Adjust Scraping Speed

Modify delays in scraper scripts:

```python
# In scrape_spp_programs.py or scrape_projects.py
time.sleep(2)  # Change delay between requests (in seconds)
```

## Troubleshooting

### Playwright browser crashes

```bash
# Reinstall browser binaries
python3 -m playwright install --force chromium
```

### "No SPP programs found"

The GEPRIS page may have changed structure. Check:
1. Visit the URL manually in a browser
2. Check `data/raw/debug_spp_page.html` for page structure
3. Update selectors in `scrape_spp_programs.py` if needed

### Resume interrupted scraping

The project scraper automatically saves checkpoints. Just run it again:

```bash
python3 scripts/scrape_projects.py  # Resumes from last checkpoint
```

To start fresh:

```bash
rm data/raw/scraping_checkpoint.json
python3 scripts/scrape_projects.py
```

### Rate limiting / blocking

If you get blocked:
1. Increase delays in scrapers (change `time.sleep(1)` to `time.sleep(3)`)
2. Run overnight to avoid peak hours
3. Use `headless=False` in Playwright to debug manually

## Data Fields

### SPP Programs
- `spp_number`: Program ID (e.g., "SPP 2000")
- `title`: Program title
- `beginn`: Start year
- `bundesland`: German state(s)
- `wissenschaftsbereich`: Science domain
- `description`: Full description
- `projects_url`: URL to project list

### Individual Projects
- `project_id`: Unique project ID
- `title`: Short title
- `full_title`: Complete title
- `principal_investigator`: PI name
- `institution`: Host institution
- `funding_period`: Active period
- `abstract`: Project description
- `keywords`: Subject keywords
- `dfg_classification`: DFG subject classification
- `wearables_score`: 0-10 relevance score
- `ai_score`: 0-10 relevance score
- `combined_score`: Sum of both scores
- `matched_wearables_keywords`: Which keywords matched
- `matched_ai_keywords`: Which keywords matched

## Requirements

- Python 3.11+
- Playwright 1.55+
- BeautifulSoup4 4.12+
- Pandas 2.0+
- ~5 GB disk space (for full dataset)
- Stable internet connection

## License

This is a research tool for academic purposes. Please respect GEPRIS terms of service:
- Don't overload their servers (use rate limiting)
- Cache data locally (don't re-scrape unnecessarily)
- Attribute data source appropriately in publications

## Support

For issues or questions:
- Check `CLAUDE.md` for technical details
- Review scraper code comments
- Inspect debug HTML files in `data/raw/`

---

**Last Updated**: 2026-01-01
