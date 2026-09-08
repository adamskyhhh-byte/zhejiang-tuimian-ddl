<!-- Opportunity-row layout adapted from CS-BAOYAN-DDL SchoolRow.svelte (MIT). -->
<script lang="ts">
  import { Star, ChevronRight, AlertCircle, Landmark, MapPin } from 'lucide-svelte';
  import logoMap from '$lib/logos.json';
  import type { Row } from '$lib/types';
  import { STATUS_LABELS, ASSESSMENT_LABELS } from '$lib/types';
  import { assessmentModeOf } from '$lib/filter';
  import { deadlineLabel, formatPoint, withinDays } from '$lib/time';
  import { clock } from '$lib/clock.svelte';
  import { saved, toggleFavorite } from '$lib/urlState.svelte';
  let { row, onSelect }: { row: Row; onSelect: (id: string) => void } = $props();
  const urgent = $derived(row.status === 'open' && withinDays(row.opportunity.applicationEnd, clock.now, 3));
  const p = $derived(row.opportunity);
  const logoPath = $derived((logoMap as Record<string, string>)[row.school.id]);
  let failedLogo = $state<string | undefined>();
</script>
<article class="opportunity-row" class:urgent class:closed={row.status === 'closed' || row.status === 'cancelled'} data-testid="opportunity-row">
  <button class="row-main" onclick={() => onSelect(p.id)} aria-label={'查看' + row.school.name + row.unit.name + p.batch + '详情'}>
    <div class="school-logo">
      {#if logoPath && failedLogo !== logoPath}
        <img src={import.meta.env.BASE_URL + logoPath} alt={row.school.name + '校徽'} width="48" height="48" loading="lazy" decoding="async" onerror={() => { failedLogo = logoPath; }}/>
      {:else}
        <span class="school-logo-fallback" role="img" aria-label={row.school.name + '校徽暂不可用'} title="校徽暂不可用"><Landmark size={23}/></span>
      {/if}
    </div>
    <div class="row-content"><div class="row-title"><h3>{row.school.name}</h3><span class="status-badge status-{row.status}"><i></i>{STATUS_LABELS[row.status]}</span>{#if row.stale}<span class="stale-label" title="关联来源尚未成功检查，或距上次成功已超过 36 小时"><AlertCircle size={11}/>来源待更新</span>{/if}</div>
      <div class="unit-name">{row.unit.name}{#if row.unit.campus}<span> · {row.unit.campus}</span>{/if}</div>
      <div class="row-tags"><span class="row-location"><MapPin size={10}/>{row.school.province}</span><span class="format-label" title="考核形式，以官方考核安排为准">{assessmentModeOf(p) === 'unknown' ? '形式未核验' : ASSESSMENT_LABELS[assessmentModeOf(p)] + '考核'}</span><span>{p.batch || '预推免'}</span>{#each p.degrees as degree}<span>{degree === 'academic' ? '学硕' : '专硕'}</span>{:else}<span>硕士类型未细分</span>{/each}<span class:related={p.relevance === 'related'}>{p.relevance === 'core' ? '核心相关' : '交叉相关'}</span><small>{p.disciplines.join(' / ')}</small></div>
    </div>
    <div class="deadline-block" class:danger={urgent}>
      <strong>{deadlineLabel(row, clock.now)}</strong>
      <span>{p.applicationEnd.precision === 'date' && row.endDay ? '具体时刻未公布' : row.endDay ? formatPoint(p.applicationEnd).replace('2026/', '') : '以官方通知为准'}</span>
      {#if row.status === 'review'}<small>时间信息待核验</small>{/if}
    </div>
    <ChevronRight size={15} class="row-chevron"/>
  </button>
  <button class="favorite-toggle" class:saved={saved.ids.includes(p.id)} data-testid="favorite-toggle" aria-label={saved.ids.includes(p.id) ? '取消收藏' : '收藏项目'} aria-pressed={saved.ids.includes(p.id)} onclick={() => toggleFavorite(p.id)}><Star size={16} fill={saved.ids.includes(p.id) ? 'currentColor' : 'none'}/></button>
</article>
