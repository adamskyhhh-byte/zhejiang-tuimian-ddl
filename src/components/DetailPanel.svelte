<!-- Detail drawer adapted from CS-BAOYAN-DDL DetailPanel.svelte (MIT). -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { X, ArrowUpRight, Clock3, Star, AlertCircle } from 'lucide-svelte';
  import type { Catalog, Row, TimePoint } from '$lib/types';
  import { STATUS_LABELS, ASSESSMENT_LABELS } from '$lib/types';
  import { assessmentModeOf } from '$lib/filter';
  import { formatPoint, formatRemaining, formatTimestamp, sourceStale } from '$lib/time';
  import { saved, toggleFavorite } from '$lib/urlState.svelte';
  import { clock } from '$lib/clock.svelte';
  let { row, catalog, onClose }: { row: Row; catalog: Catalog; onClose: () => void } = $props();
  let dialog: HTMLDialogElement;
  const p = $derived(row.opportunity);
  const changes = $derived(catalog.changes.filter(c => c.opportunityId === p.id).sort((a,b) => b.detectedAt.localeCompare(a.detectedAt)));
  const nodes = $derived<{ label: string; point: TimePoint | null }[]>([{label:'报名开始',point:p.applicationStart},{label:'报名截止',point:p.applicationEnd},{label:'材料提交截止',point:p.materialsEnd}]);
  onMount(() => { dialog.showModal(); const previous = document.body.style.overflow; document.body.style.overflow = 'hidden'; return () => document.body.style.overflow = previous; });
</script>
<dialog bind:this={dialog} class="detail-dialog" data-testid="detail-panel" aria-labelledby="detail-title" oncancel={onClose} onclick={e => { if (e.target === dialog) onClose(); }} onkeydown={e => { if (e.key === 'Escape') onClose(); }}>
  <div class="detail-shell">
    <div class="detail-header"><span class="tiny-label">OPPORTUNITY DETAILS</span><button class="icon-button" onclick={onClose} aria-label="关闭详情"><X size={19}/></button></div>
    <div class="detail-body">
      <span class="detail-school">{row.school.province} / {row.school.name}</span><h2 id="detail-title">{row.unit.name}</h2><p class="detail-subtitle">{p.title}</p>
      <div class="detail-badges"><span class="status-badge status-{row.status}"><i></i>{STATUS_LABELS[row.status]}</span><span class="tag">{p.batch}</span><span class="tag">考核形式：{ASSESSMENT_LABELS[assessmentModeOf(p)]}</span>{#if p.programTags?.includes('joint')}<span class="tag">含联培方向</span>{/if}{#each p.degrees as d}<span class="tag">{d === 'academic' ? '学硕' : '专硕'}</span>{:else}<span class="tag">硕士类型未细分</span>{/each}</div>
      <div class="deadline-hero"><span><Clock3 size={14}/> {row.deadline.kind === 'materials' ? '材料提交截止' : '报名截止'} · 北京时间</span><strong>{row.status === 'cancelled' ? '项目已取消' : row.remainingMs !== null && row.remainingMs > 0 ? formatRemaining(row.remainingMs) : formatPoint(row.deadline.point)}</strong>{#if row.remainingMs !== null}<small>{formatPoint(row.deadline.point)}</small>{/if}</div>
      {#if p.verification !== 'verified'}<p class="notice-warning"><AlertCircle size={15}/>{p.verification === 'conflict' ? '官方来源之间存在冲突，时间及报名状态待核验。' : '该信息正在核验，请阅读官方原文确认时间和硕士适用范围。'}</p>{/if}
      <section class="detail-section"><h3>时间节点与原文</h3><div class="timeline">{#each nodes as node}<div class="timeline-item"><span>{node.label}</span><strong>{formatPoint(node.point)}</strong>{#if node.point?.raw}<blockquote>{node.point.raw}</blockquote>{/if}</div>{/each}<div class="timeline-item"><span>考核安排</span><strong>{p.assessment || '未公布，请关注后续通知'}</strong></div></div></section>
      <section class="detail-section"><h3>招生方向</h3><div class="detail-badges">{#each p.disciplines as discipline}<span class="tag">{discipline}</span>{/each}<span class="tag accent-tag">{p.relevance === 'core' ? '核心相关' : '交叉相关'}</span></div>{#if p.notes}<p class="detail-copy">{p.notes}</p>{/if}</section>
      <section class="detail-section"><h3>选调名单与专业限制</h3><p class="detail-copy">{row.school.rosterYear} 年名单 · {row.school.groups.join(' / ')}</p><p class="detail-copy">{row.school.eligibilityNote || '请依照官方名单核对具体专业与报考条件。'}</p>{#if row.school.disciplineRestrictions.length}<p class="detail-copy">{row.school.disciplineRestrictions.join('；')}</p>{/if}{#each row.school.rosterSources as url, i}<a class="source-link" href={url} target="_blank" rel="noreferrer">官方名单依据 {i+1}<ArrowUpRight size={13}/></a>{/each}</section>
      <section class="detail-section"><h3>官方证据</h3>{#each p.evidence as evidence}<a class="source-link" href={evidence.url} target="_blank" rel="noreferrer">{evidence.title}<ArrowUpRight size={13}/></a><blockquote class="evidence-quote">{evidence.excerpt}</blockquote>{/each}{#if !p.evidence.length}<p class="muted">尚无提取的原文片段，请查看官方通知。</p>{/if}</section>
      <section class="detail-section"><h3>来源检查</h3>
        {#each row.sources as source}<div class="source-check">
          <a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url}<ArrowUpRight size={12}/></a>
          <p>最后成功检查：{formatTimestamp(source.lastSuccessAt)}{source.checkMethod === 'browser' ? '（浏览器复核）' : source.checkMethod === 'pdf_visual_review' ? '（PDF 人工复核）' : ''}</p>
          {#if sourceStale(source, clock.now)}<span class="warning-text">{source.lastSuccessAt ? '超过 36 小时未成功检查，信息可能已变动' : '尚未成功检查此来源，请先阅读官方通知'}</span>{/if}
          {#if source.error}<p class="warning-text">本次检查异常：{source.error}</p>{/if}
        </div>{/each}
      </section>
      <section class="detail-section"><h3>变更历史 <span>{changes.length}</span></h3>{#each changes as change}<div class="change-item"><small>{formatTimestamp(change.detectedAt)}</small><p>{change.summary}</p>{#if change.before || change.after}<span>{change.before || '未记录'} → {change.after || '未记录'}</span>{/if}</div>{/each}{#if !changes.length}<p class="muted">暂无已记录变更。</p>{/if}</section>
    </div>
    <div class="detail-footer"><button class="icon-button" onclick={() => toggleFavorite(p.id)} aria-label={saved.ids.includes(p.id) ? '取消收藏' : '收藏项目'} aria-pressed={saved.ids.includes(p.id)}><Star size={18} fill={saved.ids.includes(p.id) ? 'currentColor' : 'none'}/></button><a class="secondary-button" href={p.noticeUrl} target="_blank" rel="noreferrer">官方通知 <ArrowUpRight size={14}/></a>{#if p.applicationUrl}<a class="primary-button" href={p.applicationUrl} target="_blank" rel="noreferrer">前往报名 <ArrowUpRight size={14}/></a>{/if}</div>
  </div>
</dialog>
