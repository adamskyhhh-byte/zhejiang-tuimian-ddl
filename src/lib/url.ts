import type { FilterState, Quick, View } from './types';
import { ASSESSMENT_LABELS, FILTER_TAGS } from './types';
export function defaultFilters(): FilterState {
  return { view: 'list', query: '', school: '', province: '', discipline: '', relevance: '', degree: '', group: '', status: '', quick: '', favoritesOnly: false, tags: [], formats: [] };
}
export function readFilters(search: string): FilterState {
  const p = new URLSearchParams(search), f = defaultFilters();
  for (const key of ['query', 'school', 'province', 'discipline', 'relevance', 'degree', 'group', 'status'] as const) f[key] = p.get(key) || '';
  if (['list', 'calendar', 'coverage'].includes(p.get('view') || '')) f.view = p.get('view') as View;
  if (['open', 'three', 'seven', 'today'].includes(p.get('quick') || '')) f.quick = p.get('quick') as Quick;
  if (!['', 'core', 'related'].includes(f.relevance)) f.relevance = '';
  if (!['', 'academic', 'professional'].includes(f.degree)) f.degree = '';
  if (!['', 'open', 'upcoming', 'closed', 'unknown', 'review', 'cancelled'].includes(f.status)) f.status = '';
  f.favoritesOnly = p.get('favoritesOnly') === '1';
  f.tags = [...new Set(p.getAll('tags').flatMap(value => value.split(',')))].filter(value => (FILTER_TAGS as readonly string[]).includes(value));
  f.formats = [...new Set(p.getAll('formats').flatMap(value => value.split(',')))].filter(value => Object.hasOwn(ASSESSMENT_LABELS, value));
  return f;
}
export function serializeFilters(f: FilterState): string {
  const p = new URLSearchParams(), defaults = defaultFilters();
  for (const key of Object.keys(f) as (keyof FilterState)[]) {
    const value = f[key];
    if (Array.isArray(value)) { if (value.length) p.set(key, [...new Set(value)].join(',')); }
    else if (value !== defaults[key] && value) p.set(key, value === true ? '1' : String(value));
  }
  return p.toString();
}
