<!-- Adapted from CS-BAOYAN-DDL Header.svelte (MIT). -->
<script lang="ts">
  import { Clock3, Sun, Moon, ArrowUpRight } from 'lucide-svelte';
  import { theme, toggleTheme } from '$lib/theme.svelte';
</script>
<header class="site-header">
  <div class="header-inner">
    <a class="wordmark" href={import.meta.env.BASE_URL} aria-label="浙选推免日历首页">
      <span class="brand-mark"><Clock3 size={21} strokeWidth={1.7}/></span>
      <span><strong>浙选 <span class="brand-separator">/</span> 推免日历</strong><small>GRADUATE ADMISSIONS TRACKER</small></span>
    </a>
    <div class="header-actions"><span class="season-tag">2027 级硕士</span>
      <a class="reference-link" href="https://xds.ecnu.edu.cn/68/b9/c51123a747705/page.psp" target="_blank" rel="noreferrer">名单依据 <ArrowUpRight size={14}/></a>
      <button class="icon-button" onclick={toggleTheme} aria-label={theme.value === 'dark' ? '切换浅色主题' : '切换深色主题'}>{#if theme.value === 'dark'}<Sun size={17}/>{:else}<Moon size={17}/>{/if}</button>
    </div>
  </div>
</header>
