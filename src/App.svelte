<!-- Application composition adapted from CS-BAOYAN/CS-BAOYAN-DDL (MIT). -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { ArrowUpRight, RefreshCw, Radio, ArrowRight, X, Check, Copy, AlertCircle } from 'lucide-svelte';
  import Header from '$components/Header.svelte';
  import Toolbar from '$components/Toolbar.svelte';
  import FilterPanel from '$components/FilterPanel.svelte';
  import ListView from '$components/ListView.svelte';
  import CalendarView from '$components/CalendarView.svelte';
  import CoverageView from '$components/CoverageView.svelte';
  import DetailPanel from '$components/DetailPanel.svelte';
  import type { Catalog, Quick } from '$lib/types';
  import { deriveRows, applyFilters } from '$lib/filter';
  import { clock, startClock } from '$lib/clock.svelte';
  import { filters, saved, initFilterSync, clearFilters } from '$lib/urlState.svelte';
  import { dateKey, dueWithinDays, formatTimestamp } from '$lib/time';

  let catalog = $state<Catalog | null>(null);
  let loading = $state(true);
  let error = $state('');
  let selectedId = $state<string | null>(null);
  let drawerOpen = $state(false);
  let mobileDialog: HTMLDialogElement;
  let copied = $state(false);
  let copyError = $state(false);
  let copyTimer: ReturnType<typeof setTimeout>;
  async function loadCatalog() {
    loading = true; error = '';
    try {
      const response = await fetch(`${import.meta.env.BASE_URL}data/catalog.json`, { cache: 'no-cache' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json() as Catalog;
      if (data.schemaVersion !== 1 || !Array.isArray(data.schools) || !Array.isArray(data.units) || !Array.isArray(data.sources) || !Array.isArray(data.opportunities) || !Array.isArray(data.changes) || !data.run) throw new Error('不支持的数据格式');
      catalog = data;
    } catch (e) { error = e instanceof Error ? e.message : '请求失败'; }
    finally { loading = false; }
  }
  onMount(() => {
    const stopClock = startClock(), stopSync = initFilterSync();
    void loadCatalog();
    return () => { stopClock(); stopSync(); clearTimeout(copyTimer); };
  });
  const allRows = $derived(catalog ? deriveRows(catalog, clock.now) : []);
  const visible = $derived(applyFilters(allRows, filters, saved.ids, clock.now));
  const selected = $derived(allRows.find(r => r.opportunity.id === selectedId));
  const stats = $derived([
    { id: 'open' as Quick, label: '正在报名', value: allRows.filter(r => r.status === 'open').length, note: '把握每一次机会', tone: 'green' },
    { id: 'three' as Quick, label: '3 天内截止', value: allRows.filter(r => dueWithinDays(r, clock.now, 3)).length, note: '含已核验的材料截止', tone: 'orange' },
    { id: 'seven' as Quick, label: '7 天内截止', value: allRows.filter(r => dueWithinDays(r, clock.now, 7)).length, note: '含已核验的材料截止', tone: 'neutral' },
    { id: 'today' as Quick, label: '今日新增 / 变更', value: allRows.filter(r => dateKey(Date.parse(r.opportunity.updatedAt)) === dateKey(clock.now)).length, note: '持续追踪官方公告', tone: 'neutral' },
  ]);
  const staleCount = $derived(allRows.filter(r => r.stale).length);
  const discoveredSchoolCount = $derived(new Set(allRows.map(row => row.school.id)).size);
  function showCoverage() { clearFilters(); filters.view = 'coverage'; }
  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') { selectedId = null; closeDrawer(); }
    const target = e.target as HTMLElement;
    if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) && !target.isContentEditable && !selectedId && !drawerOpen) { e.preventDefault(); document.getElementById('search-input')?.focus(); }
  }
  function openDrawer() { drawerOpen = true; mobileDialog.showModal(); }
  function closeDrawer() { drawerOpen = false; mobileDialog?.close(); }
  async function share() {
    try { await navigator.clipboard.writeText(location.href); copied = true; copyError = false; }
    catch { copyError = true; }
    clearTimeout(copyTimer); copyTimer = setTimeout(() => { copied = false; copyError = false; }, 4000);
  }
</script>

<svelte:window onkeydown={onKey}/>
<Header/>
<div class="page-wrap">
  <section class="hero">
    <div><div class="eyebrow"><span></span> 2026 申请季 <span class="eyebrow-slash">/</span> 浙江选调院校</div><h1>下一站，<em>研究生。</em></h1><p>计算机与交叉学科硕士预推免，让每一个重要日期清晰可见。</p></div>
    <div class="hero-aside"><div class="scope-numbers"><strong>{catalog?.schools.length ?? '—'}</strong><span>所院校 / 机构<br/><b>官方名单收录</b></span></div><button class="text-button" onclick={() => filters.view = 'coverage'}>查看收录范围 <ArrowUpRight size={15}/></button></div>
  </section>
  {#if catalog}
    <div class="stats-grid">{#each stats as stat}<button class="stat-card tone-{stat.tone}" class:active={filters.quick === stat.id} onclick={() => { filters.quick = filters.quick === stat.id ? '' : stat.id; if (filters.view === 'coverage') filters.view = 'list'; }} aria-pressed={filters.quick === stat.id}><span class="stat-label">{stat.label}<ArrowUpRight size={14}/></span><strong>{String(stat.value).padStart(2,'0')}<span>项</span></strong><small>{stat.note}</small></button>{/each}</div>
    <div class="sync-strip"><div class="sync-info"><span class="sync-dot" class:warning={catalog.run.status !== 'success'}></span><strong>{catalog.run.status === 'success' ? '官方来源已同步' : catalog.run.status === 'partial' ? '部分来源检查异常' : catalog.run.status === 'failed' ? '本次检查失败 · 保留历史数据' : '等待首次自动检查'}</strong><span>最近运行 {formatTimestamp(catalog.run.finishedAt || catalog.generatedAt)}</span><span class="sync-schedule">每天 07:23 增量检查</span></div><button class="text-button" onclick={share}>{#if copied}<Check size={13}/>{:else}<Copy size={13}/>{/if}{copied ? '链接已复制' : '分享筛选'}</button></div>
    <div class="coverage-progress" data-testid="coverage-progress"><p><strong>已发现公告 {discoveredSchoolCount} / {catalog.schools.length} 个机构</strong><span> · {catalog.schools.length === 68 ? '学校名单齐全' : '学校名单仍在核对'}，公告与学院盘点仍在补充</span></p><button class="text-button" onclick={showCoverage}>查看院校覆盖 <ArrowRight size={12}/></button></div>
    {#if copyError}<p class="inline-notice" role="status">浏览器暂不支持复制，请复制地址栏链接分享当前筛选。</p>{/if}
    {#if staleCount}<div class="inline-notice"><AlertCircle size={13}/>{staleCount} 条信息存在尚未成功检查或超过 36 小时未更新的来源，已在项目中标注。</div>{/if}
    <div class="workspace"><aside class="desktop-sidebar"><FilterPanel {catalog} rows={allRows}/><div class="sidebar-footnote"><Radio size={14}/><span>追踪变化，保留依据。<br/>以学校最新官方通知为准。</span></div></aside><main id="main-content"><Toolbar visibleCount={visible.length} onOpenDrawer={openDrawer}/>{#if filters.view === 'list'}<ListView rows={visible} {catalog} onSelect={id => selectedId = id}/>{:else if filters.view === 'calendar'}<CalendarView rows={visible} onSelect={id => selectedId = id}/>{:else}<CoverageView {catalog}/>{/if}<div class="main-note"><span>所有时间均为北京时间 · 仅收录硕士预推免</span><button class="text-button" onclick={() => filters.view = 'coverage'}>发现更多院校 <ArrowRight size={12}/></button></div></main></div>
  {:else if loading}<div class="loading-state panel" role="status"><RefreshCw size={25} class="spin"/><h2>正在读取官方信息索引</h2><p>学校、招生单位和报名截止数据即将就绪。</p></div>
  {:else}<div class="loading-state panel" role="alert"><AlertCircle size={28}/><h2>暂时无法加载报名信息</h2><p>{error}</p><button class="primary-button" onclick={loadCatalog}>重新加载</button></div>{/if}
  <footer class="site-footer"><span>浙选 / 推免日历 <span class="footer-dot">·</span> 为下一程，早做准备。</span><a href="https://github.com/CS-BAOYAN/CS-BAOYAN-DDL" target="_blank" rel="noreferrer">基于 CS-BAOYAN-DDL · MIT <ArrowUpRight size={12}/></a></footer>
</div>
{#if selected && catalog}<DetailPanel row={selected} {catalog} onClose={() => selectedId = null}/>{/if}
<dialog bind:this={mobileDialog} class="mobile-dialog" aria-label="筛选条件" oncancel={closeDrawer} onclick={e => { if (e.target === mobileDialog) closeDrawer(); }} onkeydown={e => { if (e.key === 'Escape') closeDrawer(); }}><div class="mobile-dialog-inner"><div class="mobile-dialog-header"><strong>筛选报名信息</strong><button class="icon-button" aria-label="关闭筛选" onclick={closeDrawer}><X size={19}/></button></div>{#if catalog && drawerOpen}<FilterPanel {catalog} rows={allRows} onDone={closeDrawer}/>{/if}</div></dialog>
