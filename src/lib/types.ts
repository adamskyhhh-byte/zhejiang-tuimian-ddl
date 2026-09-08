export type Precision = 'datetime' | 'date' | 'unknown';
export type TimePoint = { value: string | null; precision: Precision; raw: string; sourceId: string | null };
export type Evidence = { sourceId: string; url: string; title: string; excerpt: string };
export type School = {
  id: string; name: string; province: string; groups: string[]; rosterYear: number;
  rosterSources: string[]; eligibilityNote: string; disciplineRestrictions: string[];
  homepage: string; inventoryStatus: 'reviewed' | 'pending'; inventoryNote: string;
};
export type Coverage = 'published' | 'not_found' | 'no_related' | 'pending' | 'error';
export type Unit = {
  id: string; schoolId: string; name: string; campus: string; disciplines: string[];
  relevance: 'core' | 'related'; directoryUrl: string; admissionUrl: string; coverage: Coverage; note: string;
};
export type Source = {
  id: string; schoolId: string; unitId: string | null; url: string; title: string;
  kind: 'listing' | 'notice' | 'pdf'; lastAttemptAt: string | null; lastSuccessAt: string | null;
  lastParsedAt: string | null; error: string | null;
  checkMethod?: 'http' | 'browser' | 'pdf_visual_review';
};
export type Change = {
  id: string; opportunityId: string; detectedAt: string;
  kind: 'new' | 'extended' | 'shortened' | 'corrected' | 'cancelled' | 'reopened';
  summary: string; before: string | null; after: string | null; sourceId: string;
};
export type AssessmentMode = 'online' | 'offline' | 'hybrid' | 'unknown';
export const ASSESSMENT_LABELS: Record<AssessmentMode, string> = {
  online: '线上', offline: '线下', hybrid: '混合', unknown: '未核验',
};
export const FILTER_TAGS = ['TOP2', '港三', '华五', 'C9', '985', '211', '双非', '四非', '研究院', '联培'] as const;
export type Opportunity = {
  id: string; schoolId: string; unitId: string; title: string; year: number; season: number;
  batch: string; degrees: ('academic' | 'professional')[]; disciplines: string[];
  relevance: 'core' | 'related'; stage: 'pre_admission'; applicationStart: TimePoint;
  applicationEnd: TimePoint; materialsEnd: TimePoint | null; assessment: string;
  assessmentMode?: AssessmentMode; programTags?: string[];
  applicationUrl: string | null; noticeUrl: string; sourceIds: string[]; evidence: Evidence[];
  verification: 'verified' | 'pending' | 'conflict'; availability: 'announced' | 'open' | 'cancelled';
  firstSeenAt: string; updatedAt: string; notes: string;
};
export type Catalog = {
  schemaVersion: 1; generatedAt: string; rosterYear: number; admissionYear: number; season: number;
  schools: School[]; units: Unit[]; sources: Source[]; opportunities: Opportunity[]; changes: Change[];
  run: { startedAt: string; finishedAt: string; status: 'success' | 'partial' | 'failed' | 'not_run';
    checked: number; succeeded: number; failed: number; discovered: number; changed: number };
};
export type Status = 'open' | 'upcoming' | 'closed' | 'unknown' | 'review' | 'cancelled';
export const STATUS_LABELS: Record<Status, string> = {
  open: '报名中', upcoming: '即将开放', closed: '已截止', unknown: '开放时间未知', review: '状态待核验', cancelled: '已取消',
};
export const COVERAGE_LABELS: Record<Coverage, string> = {
  published: '已发现公告', not_found: '暂未检索到当年公告', no_related: '未发现相关招生单位',
  pending: '盘点待完成', error: '来源访问异常',
};
export type Row = { opportunity: Opportunity; school: School; unit: Unit; status: Status;
  deadline: { kind: 'application' | 'materials'; point: TimePoint };
  endMs: number | null; remainingMs: number | null; endDay: string | null; stale: boolean; sources: Source[] };
export type View = 'list' | 'calendar' | 'coverage';
export type Quick = '' | 'open' | 'three' | 'seven' | 'today';
export type FilterState = { view: View; query: string; school: string; province: string; discipline: string;
  relevance: string; degree: string; group: string; status: string; quick: Quick; favoritesOnly: boolean;
  tags: string[]; formats: string[] };
