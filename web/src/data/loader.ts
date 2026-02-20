import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { parse } from 'csv-parse/sync';
import type { SPPProgram, Project } from './types';

const DATA_DIR = resolve(process.cwd(), '../dfg-schwerpunkt/data');

function readJSON<T>(relPath: string): T {
  return JSON.parse(readFileSync(resolve(DATA_DIR, relPath), 'utf-8'));
}

function readCSV(relPath: string): Record<string, string>[] {
  const content = readFileSync(resolve(DATA_DIR, relPath), 'utf-8');
  return parse(content, { columns: true, skip_empty_lines: true });
}

// ── Raw data types ──────────────────────────────────────────────

interface RawSPPAnalyzed {
  spp_number: string;
  title: string;
  url: string;
  beginn: string;
  bundesland: string;
  int_bezug: string;
  variante: string;
  wissenschaftsbereich: string;
  description: string;
  period: string;
  projects_url: string;
  detail_page_url: string;
  website?: string;
  estimated_wearables_relevance: number;
  estimated_ai_relevance: number;
}

interface RawSPPDetailed {
  spp_number: string;
  title: string;
  full_description: string;
  coordinator_name: string;
  contact_email: string;
  funding_period: string;
  funding_start: string;
  funding_end: string;
  subject_area: string;
  [key: string]: unknown;
}

interface RawProjectFile {
  spp_number: string;
  spp_title: string;
  spp_url: string;
  projects_count: number;
  projects: Array<{
    project_id: string;
    url: string;
    title: string;
    subject_area?: string;
    funding_period?: string;
    description?: string;
    investigators?: string;
  }>;
}

// ── Helpers ─────────────────────────────────────────────────────

function parseInvestigators(raw: RawProjectFile['projects'][number]): string {
  // Use investigators field if present (best source)
  if (raw.investigators?.trim()) return raw.investigators.trim();

  // Parse from description metadata (labels are fused into text with no delimiters)
  const desc = raw.description || '';
  const names: string[] = [];

  const endDelim =
    '(?=Ehemalige|Kooperationspartner|Mitverantwortlich|DFG-Verfahren|Beteiligte|Internationale|Teilprojekt|$)';

  const patterns: [RegExp, boolean][] = [
    [new RegExp(`Mitverantwortliche?([\\s\\S]*?)${endDelim}`), false],
    [new RegExp(`Kooperationspartner(?:innen\\s*/\\s*Kooperationspartner|in(?:nen)?|n)?([\\s\\S]*?)${endDelim}`), false],
    [new RegExp(`Ehemalige[rs]?\\s*Antragsteller(?:in(?:nen)?)?([\\s\\S]*?)${endDelim}`), true],
  ];

  for (const [pat, stripDate] of patterns) {
    const m = desc.match(pat);
    if (m?.[1]) {
      const extracted = m[1]
        .split(';')
        .map((s) => {
          let name = s.replace(/\s+/g, ' ').trim();
          if (stripDate) name = name.replace(/,\s*bis\s+\d{1,2}\/\d{4}$/, '').trim();
          return name;
        })
        .filter(Boolean);
      names.push(...extracted);
    }
  }

  return names.join('; ');
}

function cleanDescription(desc: string): string {
  // Strip GEPRIS metadata appended to the end of descriptions
  const cutoff = desc.search(
    /DFG-Verfahren|Mitverantwortlich|Ehemalige[rs]?\s*Antragsteller|Kooperationspartner|Teilprojektleiter/,
  );
  return cutoff > 0 ? desc.slice(0, cutoff).trim() : desc;
}

// ── Cached data ─────────────────────────────────────────────────

let _programs: SPPProgram[] | null = null;
let _allProjects: Project[] | null = null;

// ── Loaders ─────────────────────────────────────────────────────

export function loadPrograms(): SPPProgram[] {
  if (_programs) return _programs;

  const analyzed = readJSON<RawSPPAnalyzed[]>('raw/spp_programs_analyzed.json');
  const detailed = readJSON<RawSPPDetailed[]>('raw/spp_programs_detailed.json');
  const csvRows = readCSV('processed/all_projects.csv');

  // Index detailed by spp_number
  const detailedMap = new Map<string, RawSPPDetailed>();
  for (const d of detailed) {
    detailedMap.set(d.spp_number, d);
  }

  // Index CSV rows by spp_number for project counts
  const projectsBySPP = new Map<string, Record<string, string>[]>();
  for (const row of csvRows) {
    const spp = row.spp_number;
    if (!projectsBySPP.has(spp)) projectsBySPP.set(spp, []);
    projectsBySPP.get(spp)!.push(row);
  }

  // Load raw project files for descriptions
  const rawProjectsBySPP = new Map<string, RawProjectFile>();
  const projectFiles = readdirSync(resolve(DATA_DIR, 'raw/projects'));
  for (const file of projectFiles) {
    if (!file.endsWith('.json')) continue;
    const raw = readJSON<RawProjectFile>(`raw/projects/${file}`);
    rawProjectsBySPP.set(raw.spp_number, raw);
  }

  _programs = analyzed.map((a) => {
    const d = detailedMap.get(a.spp_number);
    const rawFile = rawProjectsBySPP.get(a.spp_number);
    const csvProjects = projectsBySPP.get(a.spp_number) || [];
    const slug = a.spp_number.replace(/\s+/g, '-').toLowerCase();

    // Build project list by joining CSV (scores) with raw JSON (descriptions)
    const rawProjectMap = new Map<string, RawProjectFile['projects'][number]>();
    if (rawFile) {
      for (const rp of rawFile.projects) {
        rawProjectMap.set(rp.project_id, rp);
      }
    }

    const projects: Project[] = csvProjects.map((csv) => {
      const raw = rawProjectMap.get(csv.project_id);
      return {
        project_id: csv.project_id,
        spp_number: csv.spp_number,
        spp_title: csv.spp_title,
        title: csv.title || raw?.title || '',
        full_title: csv.full_title || '',
        principal_investigator: raw ? parseInvestigators(raw) : '',
        institution: csv.institution || '',
        funding_period: csv.funding_period || raw?.funding_period || '',
        abstract: csv.abstract || '',
        description: cleanDescription(raw?.description || ''),
        keywords: csv.keywords || '',
        dfg_classification: csv.dfg_classification || '',
        subject_area: raw?.subject_area || '',
        url: csv.url || raw?.url || '',
        wearables_score: parseFloat(csv.wearables_score) || 0,
        ai_score: parseFloat(csv.ai_score) || 0,
        combined_score: parseFloat(csv.combined_score) || 0,
        matched_wearables_keywords: csv.matched_wearables_keywords || '',
        matched_ai_keywords: csv.matched_ai_keywords || '',
      };
    });

    return {
      spp_number: a.spp_number,
      title: d?.title || a.title,
      url: a.url,
      beginn: a.beginn,
      bundesland: a.bundesland,
      int_bezug: a.int_bezug,
      variante: a.variante,
      wissenschaftsbereich: a.wissenschaftsbereich,
      description: a.description,
      full_description: d?.full_description || '',
      period: a.period,
      projects_url: a.projects_url,
      detail_page_url: a.detail_page_url,
      website: a.website || (d as any)?.website || '',
      coordinator_name: d?.coordinator_name || '',
      contact_email: d?.contact_email || '',
      funding_period: d?.funding_period || '',
      funding_start: d?.funding_start || '',
      funding_end: d?.funding_end || '',
      subject_area: d?.subject_area || '',
      estimated_ai_relevance: a.estimated_ai_relevance,
      estimated_wearables_relevance: a.estimated_wearables_relevance,
      projects_count: projects.length || rawFile?.projects_count || 0,
      projects,
      slug,
    } satisfies SPPProgram;
  });

  return _programs;
}

export function loadAllProjects(): Project[] {
  if (_allProjects) return _allProjects;
  const programs = loadPrograms();
  _allProjects = programs.flatMap((p) => p.projects);
  return _allProjects;
}

export function loadAIProjects(): Project[] {
  return loadAllProjects().filter((p) => p.ai_score >= 1.0);
}

export function loadWearablesProjects(): Project[] {
  return loadAllProjects().filter((p) => p.wearables_score >= 1.0);
}

export function loadSummaryMarkdown(sppNumber: string): string {
  const filename = sppNumber.replace(/\s+/g, '_') + '_summary.md';
  try {
    return readFileSync(resolve(DATA_DIR, 'spp_summaries', filename), 'utf-8');
  } catch {
    return '';
  }
}

/** Stats for the landing page */
export function loadStats() {
  const programs = loadPrograms();
  const allProjects = loadAllProjects();
  return {
    totalPrograms: programs.length,
    totalProjects: allProjects.length,
    aiRelevant: loadAIProjects().length,
    wearablesRelevant: loadWearablesProjects().length,
    wissenschaftsbereiche: [...new Set(programs.map((p) => p.wissenschaftsbereich))],
  };
}
