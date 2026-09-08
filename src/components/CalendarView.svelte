<!-- Month grid adapted from CS-BAOYAN-DDL CalendarView.svelte (MIT). -->
<script lang="ts">
  import { ChevronLeft, ChevronRight, CalendarDays } from 'lucide-svelte';
  import type { Row } from '$lib/types';
  import { calendarCells, dateKey } from '$lib/time';
  import { clock } from '$lib/clock.svelte';
  import SchoolRow from './SchoolRow.svelte';
  let { rows, onSelect }: { rows: Row[]; onSelect: (id: string) => void } = $props();
  let month = $state(dateKey(Date.now()).slice(0, 7));
  let selectedDay = $state<string | null>(null);
  let showUnknown = $state(false);
  const cells = $derived(calendarCells(month));
  const today = $derived(dateKey(clock.now));
  const unknown = $derived(rows.filter(r => !r.endDay));
  const grouped = $derived.by(() => {
    const map = new Map<string, Row[]>();
    for (const row of rows) if (row.endDay) map.set(row.endDay, [...(map.get(row.endDay) || []), row]);
    return map;
  });
  function move(delta: number) { const [y,m] = month.split('-').map(Number); month = new Date(Date.UTC(y,m-1+delta,1)).toISOString().slice(0,7); selectedDay = null; }
</script>
<div class="panel calendar-panel">
  <div class="calendar-header"><h3><CalendarDays size={17}/>{month.replace('-', ' 年 ')} 月</h3><div><button class="text-button" onclick={() => month = today.slice(0,7)}>本月</button><button class="icon-button" onclick={() => move(-1)} aria-label="上个月"><ChevronLeft size={18}/></button><button class="icon-button" onclick={() => move(1)} aria-label="下个月"><ChevronRight size={18}/></button></div></div>
  <div class="calendar-scroll"><div class="calendar-grid">
    {#each ['一','二','三','四','五','六','日'] as day}<div class="calendar-weekday">{day}</div>{/each}
    {#each cells as cell}
      {@const items = grouped.get(cell.key) || []}
      <div class="calendar-cell" class:outside={!cell.inMonth} class:today={cell.key === today}>
        <div class="day-heading"><span>{Number(cell.key.slice(-2))}</span>{#if items.length}<small>{items.length} 项</small>{/if}</div>
        {#each items.slice(0,3) as row (row.opportunity.id)}<button class="calendar-event status-{row.status}" onclick={() => onSelect(row.opportunity.id)} title={row.school.name + ' · ' + row.unit.name + (row.deadline.kind === 'materials' ? ' · 材料提交截止' : ' · 报名截止')}><i></i>{row.school.name}{row.deadline.kind === 'materials' ? ' · 材料' : ''}</button>{/each}
        {#if items.length > 3}<button class="calendar-more" data-testid="calendar-more" onclick={() => { selectedDay = cell.key; showUnknown = false; }}>查看全部 {items.length} 项 →</button>{/if}
      </div>
    {/each}
  </div></div>
  <div class="calendar-footer"><span>北京时间 · 报名截止未知时显示材料截止</span><button class="text-button" onclick={() => { showUnknown = !showUnknown; selectedDay = null; }}>截止待确认 <b>{unknown.length}</b></button></div>
</div>
{#if selectedDay || showUnknown}<div class="panel calendar-day-details"><div class="calendar-header"><h3>{showUnknown ? '截止日期未公布' : selectedDay + ' · 全部报名项目'}</h3><button class="text-button" onclick={() => { selectedDay = null; showUnknown = false; }}>收起</button></div>{#each showUnknown ? unknown : grouped.get(selectedDay!) || [] as row (row.opportunity.id)}<SchoolRow {row} {onSelect}/>{/each}{#if showUnknown && !unknown.length}<p class="empty-small">当前筛选下没有截止日期未知的项目。</p>{/if}</div>{/if}
