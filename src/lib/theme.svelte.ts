// Theme controller adapted from CS-BAOYAN-DDL (MIT).
type Theme = 'light' | 'dark';
function detect(): Theme { try { return localStorage.getItem('zj-ddl-theme') === 'dark' ? 'dark' : 'light'; } catch { return 'light'; } }
export const theme = $state<{ value: Theme }>({ value: detect() });
export function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark';
  document.documentElement.classList.toggle('dark', theme.value === 'dark');
  try { localStorage.setItem('zj-ddl-theme', theme.value); } catch { /* 浏览器可能禁用存储。 */ }
}
