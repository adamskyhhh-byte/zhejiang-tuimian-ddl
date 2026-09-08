<!-- Filter-panel structure adapted from CS-BAOYAN-DDL (MIT). -->
<script lang="ts">
  import { SlidersHorizontal, RotateCcw, Star } from 'lucide-svelte';
  import type { Catalog, Row } from '$lib/types';
  import { STATUS_LABELS, ASSESSMENT_LABELS, FILTER_TAGS } from '$lib/types';
  import { filterCounts } from '$lib/filter';
  import { filters, clearFilters, saved } from '$lib/urlState.svelte';
  let { catalog, rows, onDone }: { catalog: Catalog; rows: Row[]; onDone?: () => void } = $props();
  const provinces = $derived([...new Set(catalog.schools.map(s => s.province))].sort((a,b) => a.localeCompare(b, 'zh-CN')));
  const disciplines = $derived([...new Set([...catalog.units.flatMap(u => u.disciplines), ...catalog.opportunities.flatMap(p => p.disciplines)])].sort((a,b) => a.localeCompare(b, 'zh-CN')));
  const groups = $derived([...new Set(catalog.schools.flatMap(s => s.groups))]);
  const counts = $derived(filterCounts(rows));
  function toggleChip(group: 'tags' | 'formats', value: string) {
    filters[group] = filters[group].includes(value) ? filters[group].filter(item => item !== value) : [...filters[group], value];
    if (filters.view === 'coverage') filters.view = 'list';
  }
  function toggleStatus(value: 'open' | 'closed') {
    filters.status = filters.status === value ? '' : value;
    filters.quick = '';
    if (filters.view === 'coverage') filters.view = 'list';
  }
</script>
<div class="filter-panel panel">
  <div class="filter-heading"><h2><SlidersHorizontal size={15}/> 筛选条件</h2><button class="text-button muted" onclick={clearFilters} aria-label="重置筛选"><RotateCcw size={12}/> 重置</button></div>
  <div class="filter-body">
    <label class="filter-field">学校<select bind:value={filters.school} data-testid="filter-school"><option value="">全部 {catalog.schools.length} 所院校 / 机构</option>{#each catalog.schools as s}<option value={s.id}>{s.name}</option>{/each}</select></label>
    <div class="chip-count-note">数字为当前招生季全部项目数</div>
    <fieldset class="filter-field chip-field" data-testid="tag-filter"><legend>院校 / 项目标签 <span>可多选</span></legend><div class="filter-chips">{#each FILTER_TAGS as tag}<button class:active={filters.tags.includes(tag)} aria-pressed={filters.tags.includes(tag)} disabled={!counts.tags[tag] && !filters.tags.includes(tag)} onclick={() => toggleChip('tags', tag)} aria-label={`${tag}，${counts.tags[tag]} 个项目`}><span>{tag}</span><small>{counts.tags[tag]}</small></button>{/each}</div>{#if filters.tags.length}<button class="chip-clear" onclick={() => filters.tags = []}>清除标签</button>{/if}</fieldset>
    <fieldset class="filter-field chip-field" data-testid="status-chip-filter"><legend>状态</legend><div class="filter-chips">{#each [{ id: 'open' as const, label: '开放' }, { id: 'closed' as const, label: '已结束' }] as item}<button class:active={filters.status === item.id} aria-pressed={filters.status === item.id} disabled={!counts.statuses[item.id] && filters.status !== item.id} onclick={() => toggleStatus(item.id)} aria-label={`${item.label}，${counts.statuses[item.id]} 个项目`}><span>{item.label}</span><small>{counts.statuses[item.id]}</small></button>{/each}</div></fieldset>
    <fieldset class="filter-field chip-field" data-testid="format-filter"><legend>考核形式 <span>可多选</span></legend><div class="filter-chips">{#each Object.entries(ASSESSMENT_LABELS) as [key, label]}<button class:active={filters.formats.includes(key)} aria-pressed={filters.formats.includes(key)} disabled={!counts.formats[key as keyof typeof ASSESSMENT_LABELS] && !filters.formats.includes(key)} onclick={() => toggleChip('formats', key)} aria-label={`${label}，${counts.formats[key as keyof typeof ASSESSMENT_LABELS]} 个项目`}><span>{label}</span><small>{counts.formats[key as keyof typeof ASSESSMENT_LABELS]}</small></button>{/each}</div>{#if filters.formats.length}<button class="chip-clear" onclick={() => filters.formats = []}>清除形式</button>{/if}</fieldset>
    <label class="filter-field">所在地区<select bind:value={filters.province}><option value="">全部地区</option>{#each provinces as p}<option value={p}>{p}</option>{/each}</select></label>
    <label class="filter-field">学科方向<select bind:value={filters.discipline}><option value="">全部相关方向</option>{#each disciplines as d}<option value={d}>{d}</option>{/each}</select></label>
    <fieldset class="filter-field"><legend>学科相关性</legend><div class="segment"><button class:active={!filters.relevance} onclick={() => filters.relevance = ''}>全部</button><button class:active={filters.relevance === 'core'} onclick={() => filters.relevance = 'core'}>核心</button><button class:active={filters.relevance === 'related'} onclick={() => filters.relevance = 'related'}>交叉相关</button></div></fieldset>
    <fieldset class="filter-field"><legend>硕士类型</legend><div class="segment"><button class:active={!filters.degree} onclick={() => filters.degree = ''}>全部</button><button class:active={filters.degree === 'academic'} onclick={() => filters.degree = 'academic'}>学硕</button><button class:active={filters.degree === 'professional'} onclick={() => filters.degree = 'professional'}>专硕</button></div></fieldset>
    <label class="filter-field">选调名单类别<select bind:value={filters.group}><option value="">全部名单</option>{#each groups as g}<option value={g}>{g}</option>{/each}</select></label>
    <label class="filter-field">更多报名状态<select bind:value={filters.status} data-testid="filter-status" onchange={() => filters.quick = ''}><option value="">全部状态</option>{#each Object.entries(STATUS_LABELS) as [key, label]}<option value={key}>{label}</option>{/each}</select></label>
    <button class="favorite-filter" class:active={filters.favoritesOnly} aria-pressed={filters.favoritesOnly} onclick={() => filters.favoritesOnly = !filters.favoritesOnly}><Star size={15} fill={filters.favoritesOnly ? 'currentColor' : 'none'}/> 只看我的收藏 <span>{saved.ids.length}</span></button>
  </div>
  <div class="filter-note"><span class="tiny-label">收录范围</span><p>计算机 · 软件 · 网安 · AI<br/>及电子信息、自动化等交叉方向</p><p>学校入选不等于所有专业均符合选调资格，请核对详情中的专业限制。</p><details class="chip-help"><summary>标签与形式口径</summary><p>标签允许重叠，211 包含 985。TOP2 为清华、北大；华五为复旦、上海交大、浙大、南大、中科大；港三为港大、港中文、港科大。C9 为九校联盟。</p><p>双非指非 985、非 211；四非在此基础上排除 2022 年第二轮双一流建设高校。中央党校不套用高校工程分类。</p><p>研究院按培养单位名称含“研究院 / 研究所”识别；联培仅按公告明确记录的联合培养项目标记。未核验指官方考核形式尚未确认，网上报名不代表线上考核。</p><p>同组标签 / 形式满足任意一项即可，不同组同时满足。数字为全部项目数，不随筛选变化。</p></details></div>
  {#if onDone}<button class="primary-button drawer-done" onclick={onDone}>查看筛选结果</button>{/if}
</div>
