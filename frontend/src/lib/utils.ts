import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface CostBreakdown {
  inCost: number | null;
  outCost: number | null;
  total: number;
}

export function calcCost(
  costUsd?: number,
): CostBreakdown | null {
  if (costUsd == null) return null;
  return { inCost: null, outCost: null, total: costUsd };
}

export function fmtCost(n: number): string {
  if (n < 0.000001) return '< $0.000001';
  return '$' + n.toFixed(6).replace(/0+$/, '').replace(/\.$/, '');
}

export function fmtTok(n?: number): string {
  if (n == null) return '—';
  return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n);
}

export function relativeTime(isoStr: string): string {
  const normalized = isoStr.includes('Z') || isoStr.includes('+') ? isoStr : isoStr + 'Z';
  const diff = Date.now() - new Date(normalized).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)  return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function fmtJson(o: unknown): string {
  try { return JSON.stringify(o, null, 2); } catch { return String(o); }
}
