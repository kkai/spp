#!/usr/bin/env python3
"""
DFG Projects Relevance Analyzer
Analyzes scraped projects for relevance to wearables and AI
"""

import json
import re
from pathlib import Path
import pandas as pd
from collections import defaultdict

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
PROJECTS_DIR = RAW_DIR / "projects"
REPORTS_DIR = BASE_DIR / "reports"

# Keywords for matching
WEARABLES_KEYWORDS = {
    'german': [
        'wearable', 'tragbar', 'smart watch', 'smartwatch', 'fitness tracker',
        'sensor', 'biosensor', 'tragbare elektronik', 'e-textil', 'smart textile',
        'körpersensor', 'gesundheitsmonitor', 'mobile sensoren', 'hautnahe',
        'tragbare sensoren', 'smart clothing', 'intelligente kleidung',
        'körpernah', 'am körper', 'wearable computing', 'tragbares system',
        # Robotics and soft materials
        'soft robot', 'weich', 'flexible', 'dehnbar', 'elastomer',
        'aktor', 'actuator', 'greif', 'manipulator', 'biomimetisch',
        # Medical/implantable
        'implant', 'lunge', 'lung', 'medizin', 'medical', 'biomedical',
        'patient', 'therapie', 'therapy', 'prothes', 'orthes'
    ],
    'english': [
        'wearable', 'smart watch', 'smartwatch', 'fitness tracker', 'body sensor',
        'health monitoring', 'e-textile', 'smart fabric', 'on-body', 'on body',
        'mobile health', 'mhealth', 'm-health', 'wearable device',
        'wearable sensor', 'body-worn', 'worn sensor', 'smart clothing',
        # Robotics and soft materials
        'soft robot', 'soft material', 'flexible', 'stretchable', 'elastomer',
        'actuator', 'gripper', 'manipulator', 'biomimetic',
        # Medical/implantable
        'implant', 'lung', 'medical', 'biomedical', 'patient',
        'therapy', 'prosthe', 'orthoti', 'clinical'
    ]
}

AI_KEYWORDS = {
    'german': [
        'künstliche intelligenz', 'ki', 'maschinelles lernen', 'machine learning',
        'deep learning', 'neuronale netze', 'neuronales netz', 'bilderkennung',
        'spracherkennung', 'nlp', 'computer vision', 'mustererkennung',
        'bildverarbeitung', 'datenanalyse', 'vorhersage', 'klassifikation',
        'künstliches neuronales', 'convolutional', 'lstm', 'transformer',
        'reinforcement learning', 'verstärkendes lernen',
        # Broader computational/algorithmic terms
        'computational', 'algorith', 'konnektom', 'connectom',
        'argumentation', 'argumentationslogik', 'reasoning', 'neural',
        'gehirn', 'brain', 'kognitiv', 'cognitive', 'intelligente',
        'intelligent', 'automat', 'learning', 'trained', 'model'
    ],
    'english': [
        'artificial intelligence', 'ai', 'machine learning', 'ml',
        'deep learning', 'neural network', 'pattern recognition',
        'computer vision', 'natural language processing', 'nlp',
        'image recognition', 'classification', 'prediction', 'regression',
        'convolutional', 'lstm', 'transformer', 'reinforcement learning',
        'supervised learning', 'unsupervised learning', 'data mining',
        # Broader computational/algorithmic terms
        'computational', 'algorithm', 'connectome', 'connectomic',
        'argumentation', 'reasoning', 'neural', 'brain', 'cognitive',
        'intelligent', 'automated', 'learning', 'trained', 'model'
    ]
}


def load_all_projects():
    """Load all project JSON files"""
    all_projects = []
    spp_mapping = {}

    if not PROJECTS_DIR.exists():
        print(f"ERROR: Projects directory not found: {PROJECTS_DIR}")
        return [], {}

    json_files = list(PROJECTS_DIR.glob("*.json"))
    print(f"Found {len(json_files)} SPP project files")

    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            spp_number = data.get('spp_number', '')
            spp_title = data.get('spp_title', '')
            projects = data.get('projects', [])

            spp_mapping[spp_number] = spp_title

            for project in projects:
                project['spp_number'] = spp_number
                project['spp_title'] = spp_title
                all_projects.append(project)

    print(f"Loaded {len(all_projects)} total projects from {len(json_files)} SPP programs")
    return all_projects, spp_mapping


def calculate_keyword_score(text, keywords_dict, field_weight=1.0):
    """
    Calculate relevance score based on keyword matching

    Args:
        text: Text to search in
        keywords_dict: Dictionary with 'german' and 'english' keyword lists
        field_weight: Multiplier for this field (title gets higher weight)

    Returns:
        tuple: (score, matched_keywords_set)
    """
    if not text:
        return 0.0, set()

    text_lower = text.lower()
    matches = 0
    matched_keywords = set()

    # Combine all keywords
    all_keywords = keywords_dict.get('german', []) + keywords_dict.get('english', [])

    for keyword in all_keywords:
        keyword_lower = keyword.lower()
        # Count occurrences
        count = len(re.findall(r'\b' + re.escape(keyword_lower) + r'\b', text_lower))
        if count > 0:
            matches += count
            matched_keywords.add(keyword)

    # Score calculation
    # Base: number of unique keywords matched (max 5 points)
    # Bonus: total matches (max 5 points, capped at 10 total)
    unique_score = min(len(matched_keywords) * 2, 5)  # 2 points per unique keyword
    frequency_score = min(matches * 0.5, 5)  # 0.5 points per match

    total_score = (unique_score + frequency_score) * field_weight

    return total_score, matched_keywords


def analyze_project_relevance(project):
    """
    Analyze a single project for wearables and AI relevance

    Returns:
        wearables_score, ai_score, matched_wearables_keywords, matched_ai_keywords
    """
    # Collect text fields
    title = project.get('title', '') + ' ' + project.get('full_title', '')
    abstract = project.get('abstract', '')
    keywords = ' '.join(project.get('keywords', []))
    dfg_class = project.get('dfg_classification', '')

    # Calculate scores for different fields
    # Title gets highest weight (3x)
    wearables_title_score, wearables_title_kw = calculate_keyword_score(title, WEARABLES_KEYWORDS, field_weight=3.0)
    wearables_abstract_score, wearables_abstract_kw = calculate_keyword_score(abstract, WEARABLES_KEYWORDS, field_weight=1.5)
    wearables_keywords_score, wearables_keywords_kw = calculate_keyword_score(keywords, WEARABLES_KEYWORDS, field_weight=2.0)
    wearables_class_score, wearables_class_kw = calculate_keyword_score(dfg_class, WEARABLES_KEYWORDS, field_weight=1.0)

    ai_title_score, ai_title_kw = calculate_keyword_score(title, AI_KEYWORDS, field_weight=3.0)
    ai_abstract_score, ai_abstract_kw = calculate_keyword_score(abstract, AI_KEYWORDS, field_weight=1.5)
    ai_keywords_score, ai_keywords_kw = calculate_keyword_score(keywords, AI_KEYWORDS, field_weight=2.0)
    ai_class_score, ai_class_kw = calculate_keyword_score(dfg_class, AI_KEYWORDS, field_weight=1.0)

    # Total scores (normalized to 0-10 scale)
    wearables_score = min(
        (wearables_title_score + wearables_abstract_score +
         wearables_keywords_score + wearables_class_score) / 3,
        10.0
    )

    ai_score = min(
        (ai_title_score + ai_abstract_score +
         ai_keywords_score + ai_class_score) / 3,
        10.0
    )

    # Combine matched keywords
    matched_wearables = wearables_title_kw | wearables_abstract_kw | wearables_keywords_kw | wearables_class_kw
    matched_ai = ai_title_kw | ai_abstract_kw | ai_keywords_kw | ai_class_kw

    return wearables_score, ai_score, matched_wearables, matched_ai


def create_dataframes(projects):
    """Convert projects to pandas DataFrames with relevance scores"""

    print("\nAnalyzing project relevance...")

    analyzed_projects = []
    for i, project in enumerate(projects, 1):
        if i % 100 == 0:
            print(f"  Analyzed {i}/{len(projects)} projects...")

        wearables_score, ai_score, matched_wearables, matched_ai = analyze_project_relevance(project)

        analyzed_projects.append({
            'project_id': project.get('project_id', ''),
            'spp_number': project.get('spp_number', ''),
            'spp_title': project.get('spp_title', ''),
            'title': project.get('title', ''),
            'full_title': project.get('full_title', ''),
            'principal_investigator': project.get('principal_investigator', ''),
            'institution': project.get('institution', ''),
            'funding_period': project.get('funding_period', ''),
            'abstract': project.get('abstract', ''),
            'keywords': ', '.join(project.get('keywords', [])),
            'dfg_classification': project.get('dfg_classification', ''),
            'url': project.get('url', ''),
            'wearables_score': round(wearables_score, 2),
            'ai_score': round(ai_score, 2),
            'combined_score': round(wearables_score + ai_score, 2),
            'matched_wearables_keywords': ', '.join(sorted(matched_wearables)),
            'matched_ai_keywords': ', '.join(sorted(matched_ai))
        })

    print(f"  Analyzed all {len(projects)} projects ✓")

    # Create DataFrames
    all_df = pd.DataFrame(analyzed_projects)

    # Filter relevant projects (score >= 1.0)
    # Lower threshold captures broader relevance, higher threshold (>=3) gives only high-confidence matches
    wearables_df = all_df[all_df['wearables_score'] >= 1.0].copy()
    wearables_df = wearables_df.sort_values('wearables_score', ascending=False)

    ai_df = all_df[all_df['ai_score'] >= 1.0].copy()
    ai_df = ai_df.sort_values('ai_score', ascending=False)

    # Combined (both wearables AND AI)
    combined_df = all_df[(all_df['wearables_score'] >= 1.0) & (all_df['ai_score'] >= 1.0)].copy()
    combined_df = combined_df.sort_values('combined_score', ascending=False)

    return all_df, wearables_df, ai_df, combined_df


def save_csvs(all_df, wearables_df, ai_df, combined_df):
    """Save DataFrames to CSV files"""

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("\nSaving CSV files...")

    all_df.to_csv(PROCESSED_DIR / 'all_projects.csv', index=False, encoding='utf-8')
    print(f"  Saved all_projects.csv ({len(all_df)} rows)")

    wearables_df.to_csv(PROCESSED_DIR / 'wearables_relevant.csv', index=False, encoding='utf-8')
    print(f"  Saved wearables_relevant.csv ({len(wearables_df)} rows)")

    ai_df.to_csv(PROCESSED_DIR / 'ai_relevant.csv', index=False, encoding='utf-8')
    print(f"  Saved ai_relevant.csv ({len(ai_df)} rows)")

    combined_df.to_csv(PROCESSED_DIR / 'wearables_ai_combined.csv', index=False, encoding='utf-8')
    print(f"  Saved wearables_ai_combined.csv ({len(combined_df)} rows)")


def generate_report(all_df, wearables_df, ai_df, combined_df, spp_mapping):
    """Generate markdown summary report"""

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report_file = REPORTS_DIR / 'summary_report.md'

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# DFG Schwerpunktprogramme Analysis Report\n\n")
        f.write("Analysis of wearables and AI-related research projects\n\n")

        # Overview Statistics
        f.write("## Overview Statistics\n\n")
        f.write(f"- **Total SPP Programs**: {len(spp_mapping)}\n")
        f.write(f"- **Total Projects**: {len(all_df)}\n")
        f.write(f"- **Wearables-Related Projects**: {len(wearables_df)} ({len(wearables_df)/len(all_df)*100:.1f}%)\n")
        f.write(f"- **AI-Related Projects**: {len(ai_df)} ({len(ai_df)/len(all_df)*100:.1f}%)\n")
        f.write(f"- **Combined (Wearables + AI)**: {len(combined_df)} ({len(combined_df)/len(all_df)*100:.1f}%)\n\n")

        # Top Combined Projects (most relevant)
        f.write("## Top 20 Combined Wearables + AI Projects\n\n")
        f.write("Projects that are relevant to both wearables AND artificial intelligence:\n\n")

        if len(combined_df) > 0:
            f.write("| Rank | SPP | Project Title | PI | Institution | Wearables Score | AI Score |\n")
            f.write("|------|-----|---------------|----|--------------|-----------------|-----------|\n")

            for idx, row in combined_df.head(20).iterrows():
                title = row['full_title'] if row['full_title'] else row['title']
                title = title[:80] + '...' if len(title) > 80 else title
                rank = list(combined_df.index).index(idx) + 1
                f.write(f"| {rank} | {row['spp_number']} | {title} | {row['principal_investigator'][:30]} | ")
                f.write(f"{row['institution'][:40]} | {row['wearables_score']:.1f} | {row['ai_score']:.1f} |\n")
        else:
            f.write("*No projects found with both wearables and AI relevance.*\n")

        f.write("\n")

        # Top Wearables Projects
        f.write("## Top 20 Wearables-Related Projects\n\n")

        if len(wearables_df) > 0:
            f.write("| Rank | SPP | Project Title | PI | Institution | Score |\n")
            f.write("|------|-----|---------------|----|--------------|---------|\n")

            for idx, row in wearables_df.head(20).iterrows():
                title = row['full_title'] if row['full_title'] else row['title']
                title = title[:80] + '...' if len(title) > 80 else title
                rank = list(wearables_df.index).index(idx) + 1
                f.write(f"| {rank} | {row['spp_number']} | {title} | {row['principal_investigator'][:30]} | ")
                f.write(f"{row['institution'][:40]} | {row['wearables_score']:.1f} |\n")

        f.write("\n")

        # Top AI Projects
        f.write("## Top 20 AI-Related Projects\n\n")

        if len(ai_df) > 0:
            f.write("| Rank | SPP | Project Title | PI | Institution | Score |\n")
            f.write("|------|-----|---------------|----|--------------|---------|\n")

            for idx, row in ai_df.head(20).iterrows():
                title = row['full_title'] if row['full_title'] else row['title']
                title = title[:80] + '...' if len(title) > 80 else title
                rank = list(ai_df.index).index(idx) + 1
                f.write(f"| {rank} | {row['spp_number']} | {title} | {row['principal_investigator'][:30]} | ")
                f.write(f"{row['institution'][:40]} | {row['ai_score']:.1f} |\n")

        f.write("\n")

        # By SPP Program
        f.write("## Relevance by SPP Program\n\n")
        f.write("SPP programs with the most wearables/AI relevant projects:\n\n")

        # Group by SPP
        spp_stats = all_df.groupby('spp_number').agg({
            'wearables_score': lambda x: (x >= 3).sum(),
            'ai_score': lambda x: (x >= 3).sum(),
            'project_id': 'count'
        }).rename(columns={
            'wearables_score': 'wearables_count',
            'ai_score': 'ai_count',
            'project_id': 'total_projects'
        })

        spp_stats['combined_count'] = all_df.groupby('spp_number').apply(
            lambda x: ((x['wearables_score'] >= 3) & (x['ai_score'] >= 3)).sum()
        )

        # Sort by combined relevance
        spp_stats = spp_stats.sort_values('combined_count', ascending=False)

        f.write("| SPP Number | Total Projects | Wearables | AI | Combined |\n")
        f.write("|------------|----------------|-----------|----|-----------|\n")

        for spp_num, row in spp_stats.head(30).iterrows():
            f.write(f"| {spp_num} | {row['total_projects']} | {row['wearables_count']} | ")
            f.write(f"{row['ai_count']} | {row['combined_count']} |\n")

        f.write("\n")
        f.write("---\n\n")
        f.write("*Generated by analyze_relevance.py*\n")

    print(f"\nGenerated report: {report_file}")


def main():
    """Main analysis function"""
    print("=" * 80)
    print("DFG Projects Relevance Analyzer")
    print("=" * 80)

    # Load all projects
    projects, spp_mapping = load_all_projects()

    if not projects:
        print("ERROR: No projects found. Please run scraping scripts first.")
        return

    # Analyze and create DataFrames
    all_df, wearables_df, ai_df, combined_df = create_dataframes(projects)

    # Save CSVs
    save_csvs(all_df, wearables_df, ai_df, combined_df)

    # Generate report
    generate_report(all_df, wearables_df, ai_df, combined_df, spp_mapping)

    print("\n" + "=" * 80)
    print("✓ Analysis complete!")
    print(f"✓ Results: {PROCESSED_DIR}")
    print(f"✓ Report: {REPORTS_DIR / 'summary_report.md'}")
    print("=" * 80)


if __name__ == "__main__":
    main()
