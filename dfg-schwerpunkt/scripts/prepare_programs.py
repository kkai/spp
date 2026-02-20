#!/usr/bin/env python3
"""
Prepare scraped SPP data for the website.

Takes spp_programs_full.json (from scrape_spp_full.py), cleans descriptions,
estimates program-level AI/wearables relevance, and writes the files the
web loader expects:
  - raw/spp_programs_analyzed.json
  - raw/spp_programs_detailed.json
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
INPUT_FILE = DATA_DIR / "spp_programs_full.json"

# Program-level relevance keywords.
# All matched with word boundaries (\b) to avoid substring false positives
# (e.g. "lung" in "Forschungsleistung", "greif" in "begreifen").
# More selective than the project-level keywords in analyze_relevance.py.

AI_KEYWORDS = [
    r'künstliche\s+intelligenz', r'\bKI\b', r'maschinelles\s+lernen',
    r'machine\s+learning', r'deep\s+learning',
    r'neuronale[sn]?\s+netz', r'neural\s+network',
    r'computer\s+vision', r'\bNLP\b', r'natural\s+language',
    r'sprachmodell', r'language\s+model',
    r'reinforcement\s+learning', r'data[\s-]driven', r'datengetrieben',
    r'\bconnectom', r'\bkonnektom',
    r'artificial\s+intelligence',
    r'entscheidungsunterstützung', r'decision\s+support',
    r'\brobotik\b', r'\brobotic\b', r'\broboter\b',
    r'klassifikation', r'classification',
    r'quantum\s+software', r'quantum\s+algorithm',
    r'disinformation', r'desinformation',
]

WEARABLES_KEYWORDS = [
    r'\bwearable', r'\btragbare?\b', r'\bsensor(?:en|ik)?\b', r'\bbiosensor',
    r'e-textil', r'smart\s+textile', r'smart\s+clothing',
    r'körpersensor', r'gesundheitsmonitor', r'mobile\s+sensor',
    r'soft\s+robot', r'\belastomer', r'\baktuator', r'\bactuator',
    r'\bimplant(?:at|ierbar)', r'\bimplantable\b',
    r'\blunge\b', r'implantierbare\s+lunge',
    r'\bbiomedizin', r'\bbiomedical\b',
    r'\bprothes', r'\borthes', r'\borthoti',
    r'\bbiomimetisch', r'\bbiomimetic',
    r'\bmanipulator', r'\bgripper\b', r'\bgreifer\b',
    r'\bgaze\b', r'eye\s+track', r'blickbewegung',
    r'\bhapti[ck]', r'\baugmented\s+(reality|human)',
]


def clean_field(value: str) -> str:
    """Normalize whitespace and strip trailing junk from any metadata field."""
    if not value:
        return ''
    # Normalize whitespace
    value = re.sub(r'\s+', ' ', value).strip()
    # Remove trailing "value" artifact from JS extraction
    value = re.sub(r'\s*value$', '', value).strip()
    return value


def clean_description(desc: str, title: str) -> str:
    """Remove GEPRIS page artifacts from description text."""
    if not desc:
        return ''

    # Remove "ProjektSPP NNNN:" prefix
    desc = re.sub(r'^Projekt\s*SPP\s*\d+\s*:\s*', '', desc)

    # Remove the title if it's duplicated at the start
    if title and desc.startswith(title):
        desc = desc[len(title):].strip()

    # Remove trailing metadata labels that got concatenated
    metadata_labels = [
        'Fachliche Zuordnung', 'DFG-Verfahren', 'Förderung',
        'Internationaler Bezug', 'Sprecher', 'Sprecherin',
        'Webseite', 'Teilprojekt', 'Kooperationspartner',
        'Ehemalige', 'Mitverantwortlich', 'Beteiligte',
        'Gastgeber', 'Antragsteller', 'Projektkennung',
        'Keine Zusammenfassung',
    ]
    for label in metadata_labels:
        idx = desc.find(label)
        if idx >= 0:
            desc = desc[:idx].strip()

    # Normalize whitespace
    desc = re.sub(r'\s+', ' ', desc).strip()

    # Drop if it's just "Keine Zusammenfassung vorhanden" or empty
    if desc.lower().startswith('keine zusammenfassung'):
        return ''

    return desc


def estimate_relevance(title: str, description: str, patterns: list[str]) -> float:
    """Score 0-10 based on regex keyword matches in title+description."""
    text = f"{title} {description}"
    matches = 0
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            matches += 1
    # Scale: 0 matches=0, 1=2, 2=4, 3+=6-10
    if matches == 0:
        return 0
    if matches == 1:
        return 2
    if matches == 2:
        return 4
    return min(2 * matches, 10)


def main():
    print("=" * 70)
    print("Preparing SPP data for website")
    print("=" * 70)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        programs = json.load(f)

    print(f"Loaded {len(programs)} programs from {INPUT_FILE.name}")

    analyzed = []
    detailed = []

    for prog in programs:
        title = prog.get('title', '')
        raw_desc = prog.get('description', '')
        full_desc = prog.get('full_description', '')

        desc = clean_description(raw_desc, title)
        full_desc_clean = clean_description(full_desc, title)

        ai_score = estimate_relevance(title, desc + ' ' + full_desc_clean, AI_KEYWORDS)
        wear_score = estimate_relevance(title, desc + ' ' + full_desc_clean, WEARABLES_KEYWORDS)

        spp_number = prog['spp_number']

        # analyzed.json format (matches RawSPPAnalyzed in loader.ts)
        analyzed.append({
            'spp_number': spp_number,
            'title': title,
            'url': prog.get('url', ''),
            'beginn': prog.get('beginn', ''),
            'bundesland': prog.get('bundesland', ''),
            'int_bezug': prog.get('int_bezug', ''),
            'variante': prog.get('variante', ''),
            'wissenschaftsbereich': prog.get('wissenschaftsbereich', ''),
            'description': desc,
            'period': clean_field(prog.get('funding_period', '')),
            'projects_url': prog.get('projects_url', ''),
            'detail_page_url': prog.get('detail_page_url', prog.get('url', '')),
            'website': prog.get('website', ''),
            'estimated_wearables_relevance': wear_score,
            'estimated_ai_relevance': ai_score,
        })

        # Clean metadata fields
        coordinator = clean_field(prog.get('coordinator_name', ''))
        funding_period = clean_field(prog.get('funding_period', ''))
        subject_area = clean_field(prog.get('subject_area', ''))

        # detailed.json format (matches RawSPPDetailed in loader.ts)
        detailed.append({
            'spp_number': spp_number,
            'title': title,
            'full_description': full_desc_clean,
            'coordinator_name': coordinator,
            'contact_email': clean_field(prog.get('contact_email', '')),
            'funding_period': funding_period,
            'funding_start': clean_field(prog.get('funding_start', '')),
            'funding_end': clean_field(prog.get('funding_end', '')),
            'subject_area': subject_area,
            'website': prog.get('website', ''),
        })

    # Sort by SPP number
    analyzed.sort(key=lambda x: x['spp_number'])
    detailed.sort(key=lambda x: x['spp_number'])

    # Stats
    ai_relevant = [p for p in analyzed if p['estimated_ai_relevance'] > 0]
    wear_relevant = [p for p in analyzed if p['estimated_wearables_relevance'] > 0]
    print(f"\nRelevance estimates:")
    print(f"  AI-relevant programs:        {len(ai_relevant)}/{len(analyzed)}")
    print(f"  Wearables-relevant programs:  {len(wear_relevant)}/{len(analyzed)}")

    # Back up old files
    for fname in ['spp_programs_analyzed.json', 'spp_programs_detailed.json']:
        old = DATA_DIR / fname
        if old.exists():
            backup = DATA_DIR / fname.replace('.json', '_old20.json')
            if not backup.exists():
                old.rename(backup)
                print(f"  Backed up {fname} → {backup.name}")

    # Write outputs
    out_analyzed = DATA_DIR / 'spp_programs_analyzed.json'
    with open(out_analyzed, 'w', encoding='utf-8') as f:
        json.dump(analyzed, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(analyzed)} programs to {out_analyzed.name}")

    out_detailed = DATA_DIR / 'spp_programs_detailed.json'
    with open(out_detailed, 'w', encoding='utf-8') as f:
        json.dump(detailed, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(detailed)} programs to {out_detailed.name}")

    # Show a few examples
    print(f"\n{'=' * 70}")
    print("Sample cleaned descriptions:")
    print(f"{'=' * 70}")
    for p in analyzed[:5]:
        desc = p['description'][:120] + '...' if len(p['description']) > 120 else p['description']
        print(f"  {p['spp_number']:12s} AI={p['estimated_ai_relevance']:.0f} W={p['estimated_wearables_relevance']:.0f}")
        print(f"  {' ':12s} {p['title'][:70]}")
        print(f"  {' ':12s} {desc}")
        print()


if __name__ == "__main__":
    main()
