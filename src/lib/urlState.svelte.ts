// URL state synchronization adapted from CS-BAOYAN-DDL (MIT).
import { defaultFilters, readFilters, serializeFilters } from './url';
export const filters = $state(readFilters(typeof window === 'undefined' ? '' : window.location.search));
function readFavorites(): string[] {
  try { const value: unknown = JSON.parse(localStorage.getItem('zj-ddl-favorites') || '[]'); return Array.isArray(value) ? value.filter((x): x is string => typeof x === 'string') : []; } catch { return []; }
}
export const saved = $state({ ids: readFavorites() });
export function toggleFavorite(id: string) {
  saved.ids = saved.ids.includes(id) ? saved.ids.filter(x => x !== id) : [...saved.ids, id];
  try { localStorage.setItem('zj-ddl-favorites', JSON.stringify(saved.ids)); } catch { /* 隐私模式仍可在本次会话收藏。 */ }
}
export function clearFilters() { Object.assign(filters, { ...defaultFilters(), view: filters.view }); }
export function initFilterSync() {
  const dispose = $effect.root(() => {
    $effect(() => {
      const query = serializeFilters(filters);
      history.replaceState(null, '', `${location.pathname}${query ? '?' + query : ''}${location.hash}`);
    });
  });
  const onPop = () => Object.assign(filters, readFilters(location.search));
  window.addEventListener('popstate', onPop);
  return () => { dispose(); window.removeEventListener('popstate', onPop); };
}
