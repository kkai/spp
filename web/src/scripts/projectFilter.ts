/**
 * Client-side project filtering, pagination, and URL state management.
 * Used by [spp].astro and focus/index.astro.
 * Pure vanilla JS — no framework dependencies.
 */

// ── Types ────────────────────────────────────────────────────────

export interface ProjectData {
  id: string;
  title: string;
  pi: string;
  keywords: string;
  funding: string;
  url: string;
  ai: number;
  wear: number;
  combined: number;
  aiKw: string;
  wearKw: string;
  abstract: string;
  subjectArea: string;
  dfgClass: string;
  spp: string;
  sppSlug: string;
}

export interface FilterState {
  q: string;
  score: number;
  sort: string;
  page: number;
  spp: string;
  tab: string;
}

// ── Filtering ────────────────────────────────────────────────────

const DEFAULT_STATE: FilterState = { q: '', score: 0, sort: 'score', page: 1, spp: '', tab: '' };

export function filterProjects(data: ProjectData[], state: FilterState): ProjectData[] {
  let results = [...data];

  // Text search (title + PI + keywords + abstract)
  if (state.q) {
    const terms = state.q.toLowerCase().split(/\s+/).filter(Boolean);
    results = results.filter((p) => {
      const haystack = `${p.title} ${p.pi} ${p.keywords} ${p.aiKw} ${p.wearKw}`.toLowerCase();
      return terms.every((t) => haystack.includes(t));
    });
  }

  // Min score threshold
  if (state.score > 0) {
    results = results.filter((p) => p.combined >= state.score);
  }

  // SPP filter
  if (state.spp) {
    results = results.filter((p) => p.spp === state.spp);
  }

  // Sort
  if (state.sort === 'score') {
    results.sort((a, b) => b.combined - a.combined);
  } else if (state.sort === 'title') {
    results.sort((a, b) => a.title.localeCompare(b.title));
  } else if (state.sort === 'pi') {
    results.sort((a, b) => a.pi.localeCompare(b.pi));
  }

  return results;
}

// ── Pagination ───────────────────────────────────────────────────

export const PAGE_SIZE = 25;

export function paginate<T>(items: T[], page: number): T[] {
  const start = (page - 1) * PAGE_SIZE;
  return items.slice(start, start + PAGE_SIZE);
}

export function renderPagination(total: number, currentPage: number): string {
  const totalPages = Math.ceil(total / PAGE_SIZE);
  if (totalPages <= 1) return '';

  const pages: (number | string)[] = [];
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== '...') {
      pages.push('...');
    }
  }

  const btnBase = `px-3 py-1.5 text-sm rounded-lg border transition-colors`;
  const btnActive = `border-[var(--color-primary-500)] bg-[var(--color-primary-500)]/10 text-[var(--color-primary-500)] font-medium`;
  const btnInactive = `border-[var(--border)] text-[var(--text-secondary)] hover:border-[var(--color-primary-500)]/50`;
  const btnDisabled = `border-transparent text-[var(--text-muted)] cursor-default`;

  return `<nav class="flex flex-wrap items-center justify-center gap-1.5 mt-8" aria-label="Pagination">
    <button class="${btnBase} ${currentPage === 1 ? btnDisabled : btnInactive}" data-page="${currentPage - 1}" ${currentPage === 1 ? 'disabled' : ''} aria-label="Previous">&lsaquo;</button>
    ${pages.map((p) =>
      p === '...'
        ? `<span class="px-2 text-sm" style="color: var(--text-muted);">&hellip;</span>`
        : `<button class="${btnBase} ${p === currentPage ? btnActive : btnInactive}" data-page="${p}" ${p === currentPage ? 'aria-current="page"' : ''}>${p}</button>`
    ).join('')}
    <button class="${btnBase} ${currentPage === totalPages ? btnDisabled : btnInactive}" data-page="${currentPage + 1}" ${currentPage === totalPages ? 'disabled' : ''} aria-label="Next">&rsaquo;</button>
  </nav>`;
}

// ── URL state ────────────────────────────────────────────────────

export function readUrlState(): Partial<FilterState> {
  const params = new URLSearchParams(window.location.search);
  const state: Partial<FilterState> = {};
  if (params.get('q')) state.q = params.get('q')!;
  if (params.get('score')) state.score = parseFloat(params.get('score')!);
  if (params.get('sort')) state.sort = params.get('sort')!;
  if (params.get('page')) state.page = parseInt(params.get('page')!, 10);
  if (params.get('spp')) state.spp = params.get('spp')!;
  if (params.get('tab')) state.tab = params.get('tab')!;
  return state;
}

export function writeUrlState(state: Partial<FilterState>): void {
  const params = new URLSearchParams();
  if (state.q) params.set('q', state.q);
  if (state.score && state.score > 0) params.set('score', String(state.score));
  if (state.sort && state.sort !== 'score') params.set('sort', state.sort);
  if (state.page && state.page > 1) params.set('page', String(state.page));
  if (state.spp) params.set('spp', state.spp);
  if (state.tab && state.tab !== 'ai') params.set('tab', state.tab);
  const qs = params.toString();
  const url = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
  history.replaceState(null, '', url);
}

// ── Card HTML rendering ──────────────────────────────────────────

function escHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function renderTags(kwString: string, variant: 'ai' | 'wearables'): string {
  if (!kwString) return '';
  const colors = {
    ai: 'bg-[#3b82f620] text-[#3b82f6] border border-[#3b82f6]/20',
    wearables: 'bg-[#f59e0b20] text-[#f59e0b] border border-[#f59e0b]/20',
  };
  return kwString.split(',').map((kw) =>
    `<span class="inline-block px-2 py-0.5 rounded text-xs font-mono ${colors[variant]}">${escHtml(kw.trim())}</span>`
  ).join('');
}

function renderKeywordTags(keywords: string, limit = 5): string {
  if (!keywords) return '';
  const kws = keywords.split(/[,;]/).map((k) => k.trim()).filter(Boolean);
  const shown = kws.slice(0, limit);
  const extra = kws.length - limit;
  let html = shown.map((kw) =>
    `<span class="inline-block px-2 py-0.5 rounded text-xs font-mono bg-[var(--surface-2)] text-[var(--text-secondary)]">${escHtml(kw)}</span>`
  ).join('');
  if (extra > 0) {
    html += `<span class="text-xs" style="color: var(--text-muted);">+${extra} more</span>`;
  }
  return html;
}

export function renderProjectCard(p: ProjectData, options: { showSpp?: boolean } = {}): string {
  const aiScore = p.ai > 0
    ? `<span class="text-xs font-mono px-1.5 py-0.5 rounded" style="background: #3b82f620; color: #3b82f6;">AI ${p.ai.toFixed(1)}</span>`
    : '';
  const wearScore = p.wear > 0
    ? `<span class="text-xs font-mono px-1.5 py-0.5 rounded" style="background: #f59e0b20; color: #f59e0b;">W ${p.wear.toFixed(1)}</span>`
    : '';
  const scores = (aiScore || wearScore) ? `<div class="flex gap-2 shrink-0">${aiScore}${wearScore}</div>` : '';

  const sppLink = options.showSpp && p.sppSlug
    ? `<a href="${import.meta.env.BASE_URL}programs/${escHtml(p.sppSlug)}/" class="text-xs text-[#14b8a6] hover:underline">${escHtml(p.spp)}</a>`
    : '';

  const matchedTags = renderTags(p.aiKw, 'ai') + renderTags(p.wearKw, 'wearables');
  const keywordTags = renderKeywordTags(p.keywords);
  const hasTags = matchedTags || keywordTags;

  const detailContent = [
    p.abstract ? `<p class="text-sm mt-2 leading-relaxed" style="color: var(--text-muted);">${escHtml(p.abstract.slice(0, 600))}${p.abstract.length > 600 ? '&hellip;' : ''}</p>` : '',
    p.subjectArea ? `<p class="text-xs mt-2" style="color: var(--text-muted);"><strong>Subject area:</strong> ${escHtml(p.subjectArea)}</p>` : '',
    p.dfgClass ? `<p class="text-xs mt-1" style="color: var(--text-muted);"><strong>DFG classification:</strong> ${escHtml(p.dfgClass)}</p>` : '',
    p.keywords ? `<div class="flex flex-wrap gap-1 mt-2"><span class="text-xs font-medium" style="color: var(--text-muted);">Keywords:</span> ${renderKeywordTags(p.keywords, 999)}</div>` : '',
  ].filter(Boolean).join('');

  const expandable = detailContent
    ? `<details class="mt-2"><summary class="text-xs cursor-pointer select-none" style="color: var(--text-muted);">Show details</summary><div class="mt-2">${detailContent}</div></details>`
    : '';

  return `<div class="block rounded-xl border p-4 transition-all duration-200" style="background: var(--surface-1); border-color: var(--border);">
    <div class="flex items-start justify-between gap-3">
      <div class="flex-1 min-w-0">
        <a href="${escHtml(p.url)}" target="_blank" rel="noopener" class="text-sm font-semibold hover:text-[#14b8a6] transition-colors line-clamp-2" style="color: var(--text-primary);">${escHtml(p.title)}</a>
        ${p.pi ? `<p class="text-xs mt-1" style="color: var(--text-muted);">${escHtml(p.pi)}</p>` : ''}
        ${p.funding ? `<p class="text-xs mt-0.5" style="color: var(--text-muted);">${escHtml(p.funding)}</p>` : ''}
        ${sppLink ? `<p class="mt-1">${sppLink}</p>` : ''}
        ${hasTags ? `<div class="flex flex-wrap gap-1 mt-2">${matchedTags}${keywordTags}</div>` : ''}
        ${expandable}
        ${p.url ? `<a href="${escHtml(p.url)}" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-xs mt-2 hover:underline" style="color: #14b8a6;">GEPRIS &#8599;</a>` : ''}
      </div>
      ${scores}
    </div>
  </div>`;
}

// ── Focus page card (different layout with ScoreBar) ─────────────

export function renderFocusCard(p: ProjectData, type: 'ai' | 'wearables', sppSlug?: string): string {
  const mainScore = type === 'ai' ? p.ai : p.wear;
  const altScore = type === 'ai' ? p.wear : p.ai;
  const mainColor = type === 'ai' ? '#3b82f6' : '#f59e0b';
  const altColor = type === 'ai' ? '#f59e0b' : '#3b82f6';
  const mainLabel = type === 'ai' ? 'AI' : 'Wearables';
  const altLabel = type === 'ai' ? 'Wear.' : 'AI';
  const matchedKw = type === 'ai' ? p.aiKw : p.wearKw;

  const badgeBg = type === 'ai' ? '#3b82f620' : '#f59e0b20';

  function scoreBar(score: number, color: string, label: string, max = 10): string {
    const pct = Math.min((score / max) * 100, 100);
    return `<div class="flex items-center gap-3">
      <span class="text-xs font-medium shrink-0 w-20" style="color: var(--text-secondary);">${label}</span>
      <div class="flex-1 h-2 rounded-full overflow-hidden" style="background: var(--surface-2);">
        <div class="h-full rounded-full" style="width: ${pct}%; background: ${color};"></div>
      </div>
      <span class="text-xs font-mono tabular-nums shrink-0 w-8 text-right" style="color: var(--text-muted);">${score.toFixed(1)}</span>
    </div>`;
  }

  const keywordTags = renderKeywordTags(p.keywords);
  const matchedTags = renderTags(matchedKw, type);

  const detailContent = [
    p.abstract ? `<p class="text-sm mt-2 leading-relaxed" style="color: var(--text-muted);">${escHtml(p.abstract.slice(0, 600))}${p.abstract.length > 600 ? '&hellip;' : ''}</p>` : '',
    p.subjectArea ? `<p class="text-xs mt-2" style="color: var(--text-muted);"><strong>Subject area:</strong> ${escHtml(p.subjectArea)}</p>` : '',
    p.dfgClass ? `<p class="text-xs mt-1" style="color: var(--text-muted);"><strong>DFG classification:</strong> ${escHtml(p.dfgClass)}</p>` : '',
    p.keywords ? `<div class="flex flex-wrap gap-1 mt-2"><span class="text-xs font-medium" style="color: var(--text-muted);">Keywords:</span> ${renderKeywordTags(p.keywords, 999)}</div>` : '',
  ].filter(Boolean).join('');

  const expandable = detailContent
    ? `<details class="mt-2"><summary class="text-xs cursor-pointer select-none" style="color: var(--text-muted);">Show details</summary><div class="mt-2">${detailContent}</div></details>`
    : '';

  const desc = p.abstract || '';
  const descHtml = desc ? `<p class="text-sm mt-2 line-clamp-3" style="color: var(--text-muted);">${escHtml(desc.slice(0, 300))}${desc.length > 300 ? '&hellip;' : ''}</p>` : '';

  return `<div class="block rounded-xl border p-6 transition-all duration-200" style="background: var(--surface-1); border-color: var(--border);">
    <div class="flex flex-col sm:flex-row gap-4">
      <div class="flex-1 min-w-0">
        <div class="flex flex-wrap items-center gap-2 mb-2">
          <span class="inline-flex items-center rounded-full font-medium px-2 py-0.5 text-xs" style="background: ${badgeBg}; color: ${mainColor};">${mainLabel} Score: ${mainScore.toFixed(1)}</span>
          ${sppSlug ? `<a href="${import.meta.env.BASE_URL}programs/${escHtml(sppSlug)}/" class="text-xs hover:underline" style="color: #14b8a6;">${escHtml(p.spp)}</a>` : ''}
          ${p.funding ? `<span class="text-xs" style="color: var(--text-muted);">${escHtml(p.funding)}</span>` : ''}
        </div>
        <a href="${escHtml(p.url)}" target="_blank" rel="noopener" class="text-base font-semibold hover:text-[#14b8a6] transition-colors" style="color: var(--text-primary);">${escHtml(p.title)}</a>
        ${p.pi ? `<p class="text-sm mt-1" style="color: var(--text-secondary);">${escHtml(p.pi)}</p>` : ''}
        ${descHtml}
        ${matchedTags ? `<div class="flex flex-wrap gap-1 mt-3">${matchedTags}</div>` : ''}
        ${keywordTags ? `<div class="flex flex-wrap gap-1 mt-2">${keywordTags}</div>` : ''}
        ${expandable}
        ${p.url ? `<a href="${escHtml(p.url)}" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-xs mt-2 hover:underline" style="color: #14b8a6;">GEPRIS &#8599;</a>` : ''}
      </div>
      <div class="shrink-0 w-32">
        ${scoreBar(mainScore, mainColor, mainLabel)}
        ${altScore > 0 ? `<div class="mt-2">${scoreBar(altScore, altColor, altLabel)}</div>` : ''}
      </div>
    </div>
  </div>`;
}
