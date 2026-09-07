# 静态数据契约 v1

发布 `public/data/catalog.json`，前端从 `${BASE_URL}data/catalog.json` 读取。UTF-8 JSON，所有时间有 +08:00 或 Z，日期 YYYY-MM-DD；不使用日期的伪 23:59 时间。

```ts
type Precision = 'datetime' | 'date' | 'unknown';
type TimePoint = { value: string | null; precision: Precision; raw: string; sourceId: string | null };
type Evidence = { sourceId: string; url: string; title: string; excerpt: string };
type School = { id: string; name: string; province: string; groups: string[]; rosterYear: number; rosterSources: string[]; eligibilityNote: string; disciplineRestrictions: string[]; homepage: string; inventoryStatus: 'reviewed' | 'pending'; inventoryNote: string };
type Unit = { id: string; schoolId: string; name: string; campus: string; disciplines: string[]; relevance: 'core' | 'related'; directoryUrl: string; admissionUrl: string; coverage: 'published' | 'not_found' | 'no_related' | 'pending' | 'error'; note: string };
type Source = { id: string; schoolId: string; unitId: string | null; url: string; title: string; kind: 'listing' | 'notice' | 'pdf'; lastAttemptAt: string | null; lastSuccessAt: string | null; lastParsedAt: string | null; error: string | null };
type Change = { id: string; opportunityId: string; detectedAt: string; kind: 'new' | 'extended' | 'shortened' | 'corrected' | 'cancelled' | 'reopened'; summary: string; before: string | null; after: string | null; sourceId: string };
type Opportunity = { id: string; schoolId: string; unitId: string; title: string; year: number; season: number; batch: string; degrees: ('academic' | 'professional')[]; disciplines: string[]; relevance: 'core' | 'related'; stage: 'pre_admission'; applicationStart: TimePoint; applicationEnd: TimePoint; materialsEnd: TimePoint | null; assessment: string; applicationUrl: string | null; noticeUrl: string; sourceIds: string[]; evidence: Evidence[]; verification: 'verified' | 'pending' | 'conflict'; availability: 'announced' | 'open' | 'cancelled'; firstSeenAt: string; updatedAt: string; notes: string };
type Catalog = { schemaVersion: 1; generatedAt: string; rosterYear: 2026; admissionYear: 2027; season: 2026; schools: School[]; units: Unit[]; sources: Source[]; opportunities: Opportunity[]; changes: Change[]; run: { startedAt: string; finishedAt: string; status: 'success' | 'partial' | 'failed' | 'not_run'; checked: number; succeeded: number; failed: number; discovered: number; changed: number } };
```

配置约定：`data/schools.json`、`data/units.json`、`data/sources.json`、`data/seeds.json`、`data/overrides.json`。sources 配置在公开 Source 字段外可有 `unitIds`, `includePatterns`, `excludePatterns`, `contentSelector`, `linkSelector`, `render`, `enabled`、`scope`（定位汇总页中的学院段落）。seeds 为 Opportunity 数组，须有官方原文短证据；抓取后校验后才 verified。

抓取状态、持久 ID、已发现通知、正文 hash 和历史保存在 `data/state.json`；生成静态 catalog 使用独立导出命令。状态包含 published 机会，错误时不得覆盖成空。原页面声明只招直博时必须排除；模糊硕士时间进入 pending。

前端自行根据当前北京时间计算报名状态，verification 和新鲜度是独立维度。缺少开始时间且 availability 非 open，不能自动认定报名中。截止仅日期时当天显示今日截止时刻未公布，次日已截止。精确截止到达即已截止。已宣布 open 但截止未知允许显示报名中/截止未知；conflict 一律提示状态待核验，不能列作确认报名中。
