import { describe, expect, it, vi } from 'vitest';
import type { Catalog, Opportunity, Source, TimePoint } from './types';
import { calendarCells, dateKey, deadlineLabel, formatPoint, sourceStale, statusOf, timePointMs, withinDays } from './time';
import { applyFilters, deriveRows, rowTags, filterCounts } from './filter';
import { defaultFilters, readFilters, serializeFilters } from './url';

vi.mock('./school-tags.json', () => ({ default: { school: ['985', '211', 'C9'] } }));

const now = Date.parse('2026-09-08T12:00:00+08:00');
const unknown: TimePoint = { value: null, precision: 'unknown', raw: '', sourceId: null };
const point = (value: string, precision: 'date' | 'datetime' = 'datetime'): TimePoint => ({ value, precision, raw: value, sourceId: 'source' });
const opportunity: Opportunity = {
  id: 'op-1', schoolId: 'school', unitId: 'unit', title: '硕士预推免', year: 2027, season: 2026,
  batch: '第一批', degrees: ['academic'], disciplines: ['计算机'], relevance: 'core', stage: 'pre_admission',
  applicationStart: point('2026-09-01', 'date'), applicationEnd: point('2026-09-09T12:00:00+08:00'),
  materialsEnd: null, assessment: '', applicationUrl: null, noticeUrl: 'https://example.edu.cn/notice',
  sourceIds: ['source'], evidence: [], verification: 'verified', availability: 'announced',
  firstSeenAt: '2026-09-01T00:00:00+08:00', updatedAt: '2026-09-08T01:00:00+08:00', notes: '',
};
const source: Source = { id: 'source', schoolId: 'school', unitId: 'unit', url: 'https://example.edu.cn', title: '', kind: 'notice', lastAttemptAt: null, lastSuccessAt: '2026-09-08T09:00:00+08:00', lastParsedAt: null, error: null };
const catalog: Catalog = {
  schemaVersion: 1, generatedAt: '', rosterYear: 2026, admissionYear: 2027, season: 2026,
  schools: [{ id: 'school', name: '测试大学', province: '浙江', groups: ['常规'], rosterYear: 2026, rosterSources: [], eligibilityNote: '', disciplineRestrictions: [], homepage: '', inventoryStatus: 'reviewed', inventoryNote: '' }],
  units: [{ id: 'unit', schoolId: 'school', name: '计算机学院', campus: '', disciplines: ['计算机'], relevance: 'core', directoryUrl: '', admissionUrl: '', coverage: 'published', note: '' }],
  sources: [source], opportunities: [opportunity], changes: [],
  run: { startedAt: '', finishedAt: '', status: 'success', checked: 1, succeeded: 1, failed: 0, discovered: 0, changed: 0 },
};
describe('北京时间及官方精度', () => {
  it('与浏览器所在时区无关，并正确跨日', () => {
    expect(dateKey(Date.parse('2026-09-08T18:00:00Z'))).toBe('2026-09-09');
    expect(timePointMs(point('2026-09-08', 'date'))).toBe(Date.parse('2026-09-08T00:00:00+08:00'));
    expect(formatPoint(point('2026-09-08', 'date'))).toContain('具体时刻未公布');
  });
  it('日期截止保留到当天，精确截止到达即关闭', () => {
    const dateOnly = { ...opportunity, applicationEnd: point('2026-09-08', 'date') };
    expect(statusOf(dateOnly, now)).toBe('open');
    expect(statusOf(dateOnly, Date.parse('2026-09-09T00:00:00+08:00'))).toBe('closed');
    expect(statusOf(opportunity, timePointMs(opportunity.applicationEnd)!)).toBe('closed');
    expect(withinDays(dateOnly.applicationEnd, now, 3)).toBe(true);
  });
  it('24:00 跨日标准 ISO 与午夜处理相同', () => {
    expect(timePointMs(point('2026-09-08T24:00:00+08:00'))).toBe(Date.parse('2026-09-09T00:00:00+08:00'));
  });
  it('未知开放时间、冲突及取消不能变成报名中', () => {
    expect(statusOf({ ...opportunity, applicationStart: unknown }, now)).toBe('unknown');
    expect(statusOf({ ...opportunity, applicationStart: unknown, availability: 'open', applicationEnd: unknown }, now)).toBe('open');
    expect(statusOf({ ...opportunity, verification: 'conflict' }, now)).toBe('review');
    expect(statusOf({ ...opportunity, availability: 'cancelled' }, now)).toBe('cancelled');
  });
  it('新鲜度按每个来源判定，失败不抹去上次成功', () => {
    expect(sourceStale({ ...source, lastSuccessAt: '2026-09-06T00:00:00+08:00' }, now)).toBe(true);
    expect(sourceStale({ ...source, error: '本次失败' }, now)).toBe(false);
    const rows = deriveRows({ ...catalog, opportunities: [{ ...opportunity, sourceIds: ['source', 'missing'] }] }, now);
    expect(rows[0].stale).toBe(true);
  });
});
describe('筛选、稳定 ID 和日历', () => {
  it('多条件筛选使用 AND，收藏使用 ID，多批次保持独立', () => {
    const rows = deriveRows({ ...catalog, opportunities: [opportunity, { ...opportunity, id: 'op-2', batch: '第二批' }] }, now);
    expect(applyFilters(rows, { ...defaultFilters(), query: '计算机', province: '浙江', favoritesOnly: true }, ['op-2'], now).map(r => r.opportunity.id)).toEqual(['op-2']);
    expect(applyFilters(rows, { ...defaultFilters(), degree: 'professional' }, [], now)).toHaveLength(0);
    expect(applyFilters(rows, { ...defaultFilters(), quick: 'three' }, [], now)).toHaveLength(2);
  });
  it('排除其他招生季，保留未细分硕士类型的公告', () => {
    const rows = deriveRows({ ...catalog, opportunities: [opportunity, { ...opportunity, id: 'old', year: 2026 }, { ...opportunity, id: 'unknown-degree', degrees: [] }] }, now);
    expect(rows.map(r => r.opportunity.id)).toEqual(['op-1', 'unknown-degree']);
    expect(applyFilters(rows, { ...defaultFilters(), degree: 'academic' }, [], now).map(r => r.opportunity.id)).toEqual(['op-1']);
  });
  it('日期精度不会生成倒计时，未知截止仍保留', () => {
    const rows = deriveRows({ ...catalog, opportunities: [{ ...opportunity, applicationEnd: point('2026-09-08', 'date') }, { ...opportunity, id: 'unknown', applicationEnd: unknown }] }, now);
    expect(rows[0].remainingMs).toBeNull();
    expect(rows[1].endDay).toBeNull();
    expect(applyFilters(rows, defaultFilters(), [], now)).toHaveLength(2);
  });
  it('待核验的过去时间不能误显示截止未公布，也不能认定已截止', () => {
    const rows = deriveRows({ ...catalog, opportunities: [{ ...opportunity, verification: 'pending', applicationEnd: point('2026-08-25T17:30:00+08:00') }, { ...opportunity, id: 'date', verification: 'pending', applicationEnd: point('2026-08-25', 'date') }] }, now);
    expect(rows[0].status).toBe('review');
    expect(deadlineLabel(rows[0], now)).toBe('原文时间已过');
    expect(deadlineLabel(rows[1], now)).toBe('原文日期已过');
  });
  it('URL 所有可分享筛选项往返不变，异常枚举安全回退', () => {
    const state = { ...defaultFilters(), view: 'calendar' as const, query: 'AI & 计算机', school: 'cn-001', quick: 'seven' as const, favoritesOnly: true, tags: ['985', '联培'], formats: ['online', 'unknown'] };
    expect(readFilters(serializeFilters(state))).toEqual(state);
    expect(readFilters('?view=bad&quick=bad&status=bad').view).toBe('list');
    expect(readFilters('?status=bad').status).toBe('');
    expect(readFilters('?tags=985,invalid,985&tags=C9&formats=unknown,bad').tags).toEqual(['985', 'C9']);
    expect(readFilters('?tags=985,invalid,985&formats=unknown,bad').formats).toEqual(['unknown']);
    expect(serializeFilters(defaultFilters())).toBe('');
  });
  it('标签同组 OR、形式同组 OR、跨组 AND，缺失形式为未核验', () => {
    const rows = deriveRows({ ...catalog, opportunities: [
      { ...opportunity, id: 'online', assessmentMode: 'online' },
      { ...opportunity, id: 'offline', assessmentMode: 'offline', programTags: ['joint'] },
      { ...opportunity, id: 'legacy' },
    ] }, now);
    expect(applyFilters(rows, { ...defaultFilters(), tags: ['TOP2', '联培'], formats: ['offline', 'hybrid'] }, [], now).map(r => r.opportunity.id)).toEqual(['offline']);
    expect(applyFilters(rows, { ...defaultFilters(), tags: ['985'], formats: ['online', 'unknown'] }, [], now).map(r => r.opportunity.id)).toEqual(['legacy', 'online']);
    expect(applyFilters(rows, { ...defaultFilters(), tags: ['研究院'] }, [], now)).toHaveLength(0);
    expect(applyFilters(rows, { ...defaultFilters(), formats: ['unknown'] }, [], now).map(r => r.opportunity.id)).toEqual(['legacy']);
  });
  it('研究院和联培只按明确单位名称及项目标签，计数不重复且保留零项', () => {
    const rows = deriveRows({ ...catalog, opportunities: [
      { ...opportunity, id: 'normal', assessmentMode: 'online', notes: '联合培养相关说明' },
      { ...opportunity, id: 'joint', assessmentMode: 'hybrid', programTags: ['joint', 'joint'] },
    ] }, now);
    expect(rowTags(rows[0])).toEqual(['C9', '985', '211']);
    expect(rowTags({ ...rows[0], unit: { ...rows[0].unit, name: '人工智能研究院' } })).toContain('研究院');
    expect(rowTags({ ...rows[0], unit: { ...rows[0].unit, name: '软件研究所' } })).toContain('研究院');
    expect(rowTags(rows[0])).not.toContain('联培');
    expect(rowTags(rows[1])).toContain('联培');
    const counts = filterCounts(rows);
    expect(counts.tags['985']).toBe(2);
    expect(counts.tags['联培']).toBe(1);
    expect(counts.tags['港三']).toBe(0);
    expect(counts.formats).toEqual({ online: 1, offline: 0, hybrid: 1, unknown: 0 });
    expect(counts.statuses).toEqual({ open: 2, closed: 0 });
  });
  it('日历周一起始且跨年时无本地时区偏移', () => {
    const cells = calendarCells('2027-01');
    expect(cells).toHaveLength(42);
    expect(cells[0]).toEqual({ key: '2026-12-28', inMonth: false });
    expect(cells.filter(c => c.inMonth)).toHaveLength(31);
  });
});
