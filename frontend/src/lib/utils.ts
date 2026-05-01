import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const PRICING: Record<string, { input: number; output: number }> = {
  'google/gemma-4-26b-a4b-it':   { input: 0.07,  output: 0.35  },
  'anthropic/claude-3.5-sonnet': { input: 3.00,  output: 15.00 },
  'openai/gpt-4o':               { input: 2.50,  output: 10.00 },
};

export interface CostBreakdown {
  inCost: number;
  outCost: number;
  total: number;
}

export function calcCost(
  model: string,
  inputTok?: number,
  outputTok?: number,
): CostBreakdown | null {
  const p = PRICING[model];
  if (!p || inputTok == null) return null;
  const inCost  = (inputTok          / 1e6) * p.input;
  const outCost = ((outputTok ?? 0)  / 1e6) * p.output;
  return { inCost, outCost, total: inCost + outCost };
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
  const diff = Date.now() - new Date(isoStr).getTime();
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
