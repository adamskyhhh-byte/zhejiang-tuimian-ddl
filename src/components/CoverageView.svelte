<script lang="ts">
  import { ArrowUpRight, ChevronDown, LibraryBig } from 'lucide-svelte';
  import type { Catalog, Coverage, School } from '$lib/types';
  import { COVERAGE_LABELS } from '$lib/types';
  import { filters } from '$lib/urlState.svelte';
  let { catalog }: { catalog: Catalog } = $props();
  let status = $state('');
  function unitsFor(id: string) { return catalog.units.filter(u => u.schoolId === id); }
  function schoolCoverage(school: School): Coverage[] {
    const units = unitsFor(school.id);
    const states: Coverage[] = [];
    if (units.some(u => u.coverage === 'published')) states.push('published');
    if (units.some(u => u.coverage === 'error') || catalog.sources.some(s => s.schoolId === school.id && s.error)) states.push('error');
    if (school.inventoryStatus === 'pending' || !units.length || units.some(u => u.coverage === 'pending')) states.push('pending');
    if (!states.length) states.push(units.every(u => u.coverage === 'no_related') ? 'no_related' : 'not_found');
    return states;
  }
  const visible = $derived(catalog.schools.filter(s => {
    const units = unitsFor(s.id), query = filters.query.toLocaleLowerCase();
    return (!filters.school || filters.school === s.id) && (!filters.province || filters.province === s.province) && (!filters.group || s.groups.includes(filters.group)) &&
      (!filters.discipline || units.some(u => u.disciplines.includes(filters.discipline))) && (!filters.relevance || units.some(u => u.relevance === filters.relevance)) &&
      (!query || [s.name,...units.map(u=>u.name)].join(' ').toLocaleLowerCase().includes(query)) && (!status || schoolCoverage(s).includes(status as Coverage));
  }));
</script>
<div class="coverage-intro panel"><div><LibraryBig size={21}/><h2>每一所学校，都有记录</h2></div><p>覆盖 {catalog.schools.length} 个院校 / 机构，{catalog.units.length} 个培养单位。未检索到公告仅代表当前检查结果，不代表报名尚未开始。</p><p class="muted">院校覆盖视图使用学校、地区、学科、相关性、名单及搜索条件；院校 / 项目标签、考核形式、硕士类型、报名状态和收藏仅作用于招生项目视图。</p></div>
<div class="coverage-controls"><span>显示 <strong>{visible.length}</strong> / {catalog.schools.length} 所</span><select bind:value={status} aria-label="筛选覆盖状态"><option value="">全部盘点状态</option>{#each Object.entries(COVERAGE_LABELS) as [key,label]}<option value={key}>{label}</option>{/each}</select></div>
<div class="panel coverage-list">{#each visible as school (school.id)}
  {@const units = unitsFor(school.id)}{@const coverage = schoolCoverage(school)}
  <details class="coverage-school"><summary><div><h3>{school.name}</h3><span>{school.province} · {school.groups.join(' / ')} · {units.length} 个单位</span></div><span class="coverage-statuses">{#each coverage as state}<span class="coverage-badge coverage-{state}">{COVERAGE_LABELS[state]}</span>{/each}</span><ChevronDown size={15}/></summary>
    <div class="coverage-content"><p>{school.inventoryNote || '院系与招生栏目持续核对中。'}</p><p class="eligibility-note">{school.eligibilityNote}</p>{#if school.disciplineRestrictions.length}<p class="eligibility-note">专业限制：{school.disciplineRestrictions.join('；')}</p>{/if}<div class="coverage-links"><a href={school.homepage} target="_blank" rel="noreferrer">学校官网 <ArrowUpRight size={12}/></a>{#each school.rosterSources as url,i}<a href={url} target="_blank" rel="noreferrer">名单依据 {i+1}<ArrowUpRight size={12}/></a>{/each}</div>
    {#each units as unit}<div class="coverage-unit"><div class="coverage-unit-heading"><strong>{unit.name}{unit.campus ? ' · ' + unit.campus : ''}</strong><span class="coverage-badge coverage-{unit.coverage}">{COVERAGE_LABELS[unit.coverage]}</span></div><span class="muted">{unit.disciplines.join(' / ')} · {unit.relevance === 'core' ? '核心相关' : '交叉相关'}</span><p>{unit.note}</p><div class="coverage-links">{#if unit.directoryUrl}<a href={unit.directoryUrl} target="_blank" rel="noreferrer">院系 / 专业依据 <ArrowUpRight size={12}/></a>{/if}{#if unit.admissionUrl}<a href={unit.admissionUrl} target="_blank" rel="noreferrer">招生栏目 <ArrowUpRight size={12}/></a>{/if}</div></div>{/each}
    {#if !units.length}<p class="muted">暂无完成核验的培养单位记录，盘点待完成。</p>{/if}</div>
  </details>{/each}{#if !visible.length}<p class="empty-small">没有符合筛选条件的学校。</p>{/if}</div>
