import type { AssessmentMode, Catalog, FilterState, Opportunity, Row } from './types';
import { ASSESSMENT_LABELS, FILTER_TAGS } from './types';
import schoolTags from './school-tags.json';
import { dateKey, dueWithinDays, pointDay, primaryDeadline, sourceStale, statusOf, timePointMs } from './time';

export function assessmentModeOf(opportunity: Opportunity): AssessmentMode {
  return opportunity.assessmentMode && Object.hasOwn(ASSESSMENT_LABELS, opportunity.assessmentMode) ? opportunity.assessmentMode : 'unknown';
}
export function rowTags(row: Row): string[] {
  const tags = new Set((schoolTags as Record<string, string[]>)[row.school.id] || []);
  if (/研究院|研究所/.test(row.unit.name)) tags.add('研究院');
  if (row.opportunity.programTags?.includes('joint')) tags.add('联培');
  return FILTER_TAGS.filter(tag => tags.has(tag));
}
export function filterCounts(rows: Row[]) {
  const tags: Record<string, number> = Object.fromEntries(FILTER_TAGS.map(tag => [tag, 0]));
  const formats: Record<AssessmentMode, number> = { online: 0, offline: 0, hybrid: 0, unknown: 0 };
  const statuses = { open: 0, closed: 0 };
  for (const row of rows) {
    for (const tag of rowTags(row)) tags[tag]++;
    formats[assessmentModeOf(row.opportunity)]++;
    if (row.status === 'open' || row.status === 'closed') statuses[row.status]++;
  }
  return { tags, formats, statuses };
}

export function deriveRows(catalog: Catalog, now: number): Row[] {
  const schools = new Map(catalog.schools.map(s => [s.id, s]));
  const units = new Map(catalog.units.map(u => [u.id, u]));
  const sources = new Map(catalog.sources.map(s => [s.id, s]));
  return catalog.opportunities.flatMap(opportunity => {
    const school = schools.get(opportunity.schoolId), unit = units.get(opportunity.unitId);
    if (!school || !unit || opportunity.year !== catalog.admissionYear || opportunity.season !== catalog.season || opportunity.stage !== 'pre_admission') return [];
    const deadline = primaryDeadline(opportunity);
    const endMs = timePointMs(deadline.point);
    return [{ opportunity, school, unit, status: statusOf(opportunity, now), deadline, endMs,
      remainingMs: deadline.point.precision === 'datetime' && endMs !== null ? endMs - now : null,
      endDay: pointDay(deadline.point), stale: !opportunity.sourceIds.length || opportunity.sourceIds.some(id => sourceStale(sources.get(id), now)),
      sources: opportunity.sourceIds.flatMap(id => sources.get(id) ? [sources.get(id)!] : []),
    }];
  });
}
export function applyFilters(rows: Row[], f: FilterState, favorites: string[], now: number): Row[] {
  const query = f.query.trim().toLocaleLowerCase();
  return rows.filter(r => {
    const p = r.opportunity;
    if (f.school && r.school.id !== f.school || f.province && r.school.province !== f.province) return false;
    if (f.discipline && !p.disciplines.includes(f.discipline) || f.relevance && p.relevance !== f.relevance) return false;
    if (f.degree && !p.degrees.some(d => d === f.degree) || f.group && !r.school.groups.includes(f.group)) return false;
    if (f.status && r.status !== f.status || f.favoritesOnly && !favorites.includes(p.id)) return false;
    if (f.tags.length && !f.tags.some(tag => rowTags(r).includes(tag))) return false;
    if (f.formats.length && !f.formats.includes(assessmentModeOf(p))) return false;
    if (query && ![r.school.name, r.unit.name, r.unit.campus, p.title, p.batch, p.notes, ...p.disciplines].join(' ').toLocaleLowerCase().includes(query)) return false;
    if (f.quick === 'open' && r.status !== 'open') return false;
    if ((f.quick === 'three' || f.quick === 'seven') && !dueWithinDays(r, now, f.quick === 'three' ? 3 : 7)) return false;
    if (f.quick === 'today' && dateKey(Date.parse(p.updatedAt)) !== dateKey(now)) return false;
    return true;
  }).sort((a, b) => {
    const rank = { open: 0, upcoming: 1, review: 2, unknown: 3, closed: 4, cancelled: 5 };
    return rank[a.status] - rank[b.status] || (a.endMs ?? Infinity) - (b.endMs ?? Infinity) || a.school.name.localeCompare(b.school.name, 'zh-CN') || a.opportunity.id.localeCompare(b.opportunity.id);
  });
}
