// Deadline and calendar helpers adapted from CS-BAOYAN-DDL; all dates use Asia/Shanghai.
import type { Opportunity, Row, Source, Status, TimePoint } from './types';

export const DAY = 86_400_000;
export function dateKey(ms: number): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(ms);
}
export function timePointMs(point: TimePoint | null): number | null {
  if (!point?.value || point.precision === 'unknown') return null;
  const value = point.precision === 'date' ? `${point.value}T00:00:00+08:00` : point.value;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}
export function pointDay(point: TimePoint): string | null {
  const ms = timePointMs(point);
  return ms === null ? null : dateKey(ms);
}
export function primaryDeadline(p: Opportunity): Row['deadline'] {
  if (timePointMs(p.applicationEnd) !== null) return { kind: 'application', point: p.applicationEnd };
  if (p.materialsEnd && timePointMs(p.materialsEnd) !== null) return { kind: 'materials', point: p.materialsEnd };
  return { kind: 'application', point: p.applicationEnd };
}
export function dueWithinDays(row: Row, now: number, days: number): boolean {
  return row.opportunity.verification === 'verified' && row.status !== 'cancelled' && withinDays(row.deadline.point, now, days);
}
export function statusOf(p: Opportunity, now: number): Status {
  if (p.availability === 'cancelled') return 'cancelled';
  if (p.verification !== 'verified') return 'review';
  const end = timePointMs(p.applicationEnd);
  if (end !== null && (p.applicationEnd.precision === 'date' ? dateKey(now) > dateKey(end) : now >= end)) return 'closed';
  const start = timePointMs(p.applicationStart);
  if (start !== null && start > now) return 'upcoming';
  if ((start !== null && start <= now) || p.availability === 'open') return 'open';
  return 'unknown';
}
export function sourceStale(source: Source | undefined, now: number): boolean {
  if (!source?.lastSuccessAt) return true;
  const ms = Date.parse(source.lastSuccessAt);
  return !Number.isFinite(ms) || now - ms > 36 * 3_600_000;
}
export function formatTimestamp(value: string | null): string {
  if (!value || !Number.isFinite(Date.parse(value))) return '尚未成功检查';
  return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value));
}
export function formatPoint(point: TimePoint | null): string {
  if (!point?.value || timePointMs(point) === null) {
    if (point?.raw && /不设置截止|无统一截止/.test(point.raw)) return '无统一截止';
    if (point?.raw && /建议/.test(point.raw)) return '仅公布建议时间';
    return point?.raw ? '待确认' : '未公布';
  }
  return point.precision === 'date' ? `${point.value} · 具体时刻未公布` : formatTimestamp(point.value);
}
export function formatRemaining(ms: number): string {
  if (ms <= 0) return '已截止';
  const days = Math.floor(ms / DAY);
  const hours = Math.floor(ms % DAY / 3_600_000);
  const minutes = Math.floor(ms % 3_600_000 / 60_000);
  if (days > 0) return `${days} 天 ${hours} 小时`;
  if (hours > 0) return `${hours} 小时 ${minutes} 分`;
  return minutes > 0 ? `${minutes} 分钟` : '不足 1 分钟';
}
export function deadlineLabel(row: Row, now: number): string {
  if (row.status === 'cancelled') return '已取消';
  if (row.status === 'closed') return '已截止';
  if (row.remainingMs !== null) return row.remainingMs > 0 ? formatRemaining(row.remainingMs) : row.deadline.kind === 'materials' && row.opportunity.verification === 'verified' ? '材料时限已过' : '原文时间已过';
  if (row.endDay) {
    const today = dateKey(now);
    if (row.endDay < today) return row.deadline.kind === 'materials' && row.opportunity.verification === 'verified' ? '材料时限已过' : '原文日期已过';
    if (row.endDay === today) return row.status === 'review' ? '原文日期为今日' : '今日截止';
    return row.endDay.slice(5).replace('-', ' / ');
  }
  return /不设置截止|不设统一截止|无统一截止/.test(row.opportunity.applicationEnd.raw) ? '无统一截止' : '截止待确认';
}
export function withinDays(point: TimePoint, now: number, days: number): boolean {
  const end = timePointMs(point);
  if (end === null) return false;
  if (point.precision === 'date') {
    const today = Date.parse(`${dateKey(now)}T00:00:00+08:00`);
    return end >= today && end < today + days * DAY;
  }
  return end > now && end <= now + days * DAY;
}
export function calendarCells(month: string): { key: string; inMonth: boolean }[] {
  const [year, m] = month.split('-').map(Number);
  const first = Date.UTC(year, m - 1, 1);
  const offset = (new Date(first).getUTCDay() + 6) % 7;
  return Array.from({ length: 42 }, (_, i) => {
    const key = new Date(first + (i - offset) * DAY).toISOString().slice(0, 10);
    return { key, inMonth: key.startsWith(month) };
  });
}
