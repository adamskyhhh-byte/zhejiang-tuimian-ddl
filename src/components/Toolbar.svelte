<!-- Toolbar adapted from CS-BAOYAN-DDL (MIT). -->
<script lang="ts">
  import { Search, List, CalendarDays, LibraryBig, SlidersHorizontal, X } from 'lucide-svelte';
  import { filters } from '$lib/urlState.svelte';
  import type { View } from '$lib/types';
  let { visibleCount, onOpenDrawer }: { visibleCount: number; onOpenDrawer: () => void } = $props();
  const tabs: { id: View; label: string; icon: typeof List }[] = [{ id:'list',label:'报名列表',icon:List },{id:'calendar',label:'截止日历',icon:CalendarDays},{id:'coverage',label:'院校覆盖',icon:LibraryBig}];
</script>
<div class="toolbar">
  <div class="view-tabs" role="tablist" aria-label="信息视图">{#each tabs as tab}<button role="tab" data-testid={'tab-' + tab.id} aria-selected={filters.view === tab.id} class:active={filters.view === tab.id} onclick={() => filters.view = tab.id}><tab.icon size={15}/><span>{tab.label}</span></button>{/each}</div>
  <div class="search-box"><Search size={16}/><input id="search-input" data-testid="search-input" bind:value={filters.query} placeholder="搜索学校、学院、方向…" aria-label="搜索学校学院方向"/>{#if filters.query}<button class="icon-button" onclick={() => filters.query = ''} aria-label="清除搜索"><X size={13}/></button>{:else}<kbd>/</kbd>{/if}</div>
  <button class="icon-button mobile-filter" onclick={onOpenDrawer} data-testid="mobile-filter-toggle" aria-label="打开筛选条件"><SlidersHorizontal size={17}/></button>
</div>
{#if filters.view !== 'coverage'}<div class="result-line"><span>共 <strong>{visibleCount}</strong> 条报名信息{#if filters.quick}<button class="clear-quick" onclick={() => filters.quick = ''}>清除快捷筛选 <X size={11}/></button>{/if}</span><span class="muted">报名中优先 · 截止时间升序 <span class="timezone">UTC+8</span></span></div>{/if}
