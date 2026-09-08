<script lang="ts">
  import { Inbox, ChevronDown, ArrowRight, ArrowUpRight } from 'lucide-svelte';
  import SchoolRow from './SchoolRow.svelte';
  import type { Catalog, Row } from '$lib/types';
  import { filters, clearFilters } from '$lib/urlState.svelte';
  import { sourceStale } from '$lib/time';
  import { clock } from '$lib/clock.svelte';
  let { rows, catalog, onSelect }: { rows: Row[]; catalog: Catalog; onSelect: (id: string) => void } = $props();
  let expanded = $state(false);
  const live = $derived(rows.filter(r => r.status !== 'closed' && r.status !== 'cancelled'));
  const expired = $derived(rows.filter(r => r.status === 'closed' || r.status === 'cancelled'));
  const school = $derived(catalog.schools.find(item => item.id === filters.school));
  const schoolHasAnnouncement = $derived(catalog.opportunities.some(item => item.schoolId === school?.id && item.year === catalog.admissionYear && item.season === catalog.season && item.stage === 'pre_admission'));
  const unitCount = $derived(catalog.units.filter(unit => unit.schoolId === school?.id).length);
  const sources = $derived(catalog.sources.filter(source => source.schoolId === school?.id));
  const sourceSummary = $derived([
    { label: '近期检查成功', count: sources.filter(source => !source.error && !sourceStale(source, clock.now)).length },
    { label: '检查异常', count: sources.filter(source => source.error).length },
    { label: '尚未成功检查', count: sources.filter(source => !source.error && !source.lastSuccessAt).length },
    { label: '检查记录待更新', count: sources.filter(source => !source.error && source.lastSuccessAt && sourceStale(source, clock.now)).length },
  ].filter(item => item.count).map(item => `${item.count} 个${item.label}`).join(' · '));
  function showSchoolCoverage() {
    const schoolId = school?.id || '';
    clearFilters(); filters.school = schoolId; filters.view = 'coverage';
  }
</script>
<div class="panel list-panel">
  <div class="list-heading"><span>院校 / 培养单位</span><span>距报名截止</span></div>
  {#each live as row (row.opportunity.id)}<SchoolRow {row} {onSelect}/>{/each}
  {#if !rows.length}<div class="empty-state" data-testid="list-empty-state"><Inbox size={33} strokeWidth={1.3}/>
    {#if school && !schoolHasAnnouncement}
      <h3>{school.name}已在学校目录中</h3>
      <p>已记录 {unitCount} 个培养单位，当前尚未收录该校本招生季的硕士预推免公告。<br/>这不代表报名未开始，也不代表没有相关招生。</p>
      <p class="empty-source-status">{sources.length ? `已配置 ${sources.length} 个官方来源：${sourceSummary}` : '尚未配置可检查的官方来源，待补充。'}</p>
      <div class="empty-actions"><button class="secondary-button" onclick={showSchoolCoverage}>查看该校覆盖情况 <ArrowRight size={12}/></button>{#if school.homepage}<a class="text-button" href={school.homepage} target="_blank" rel="noreferrer">学校官网 <ArrowUpRight size={12}/></a>{/if}</div>
    {:else}
      <h3>没有符合条件的报名信息</h3><p>试试放宽筛选，或前往院校覆盖查看公告盘点进度。</p><button class="secondary-button" onclick={clearFilters}>重置筛选</button>
    {/if}
  </div>{/if}
  {#if expired.length}<button class="expired-toggle" onclick={() => expanded = !expanded} aria-expanded={expanded || filters.status === 'closed' || filters.status === 'cancelled'}><span>已截止 / 已取消 <b>{expired.length}</b></span><span>{expanded ? '收起' : '展开'} <ChevronDown size={14}/></span></button>{#if expanded || filters.status === 'closed' || filters.status === 'cancelled'}{#each expired as row (row.opportunity.id)}<SchoolRow {row} {onSelect}/>{/each}{/if}{/if}
</div>
