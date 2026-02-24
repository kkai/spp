/** A DFG Priority Programme (Schwerpunktprogramm) */
export interface SPPProgram {
  spp_number: string;
  title: string;
  url: string;
  beginn: string;
  bundesland: string;
  int_bezug: string;
  variante: string;
  wissenschaftsbereich: string;
  description: string;
  full_description: string;
  period: string;
  projects_url: string;
  detail_page_url: string;
  coordinator_name: string;
  contact_email: string;
  funding_period: string;
  funding_start: string;
  funding_end: string;
  subject_area: string;
  website: string;
  estimated_ai_relevance: number;
  estimated_wearables_relevance: number;
  projects_count: number;
  projects: Project[];
  slug: string;
}

/** A research project within an SPP */
export interface Project {
  project_id: string;
  spp_number: string;
  spp_title: string;
  title: string;
  full_title: string;
  principal_investigator: string;
  institution: string;
  funding_period: string;
  abstract: string;
  description: string;
  keywords: string;
  dfg_classification: string;
  subject_area: string;
  url: string;
  wearables_score: number;
  ai_score: number;
  combined_score: number;
  matched_wearables_keywords: string;
  matched_ai_keywords: string;
}

/** A node in the topic graph */
export interface TopicNode {
  id: string;
  label: string;
  type: 'spp' | 'topic' | 'keyword';
  size: number;
  color: string;
  metadata?: Record<string, unknown>;
}

/** An edge in the topic graph */
export interface TopicEdge {
  source: string;
  target: string;
  weight: number;
}

/** Tier classification for relevance */
export type RelevanceTier = 'high' | 'medium' | 'low' | 'none';

export function getRelevanceTier(score: number): RelevanceTier {
  if (score >= 3) return 'high';
  if (score >= 1) return 'medium';
  if (score > 0) return 'low';
  return 'none';
}

export function tierColor(tier: RelevanceTier): string {
  switch (tier) {
    case 'high': return 'text-emerald-600 dark:text-emerald-400';
    case 'medium': return 'text-amber-600 dark:text-amber-400';
    case 'low': return 'text-slate-500 dark:text-slate-400';
    case 'none': return 'text-slate-400 dark:text-slate-600';
  }
}

export function tierBg(tier: RelevanceTier): string {
  switch (tier) {
    case 'high': return 'bg-emerald-500/10 border-emerald-500/30';
    case 'medium': return 'bg-amber-500/10 border-amber-500/30';
    case 'low': return 'bg-slate-500/10 border-slate-500/30';
    case 'none': return 'bg-slate-400/10 border-slate-400/30';
  }
}
