import { CheckCircle, XCircle, AlertTriangle, Cpu } from 'lucide-react';
import { cn } from '../lib/utils';
import type { LlmBackendInfo } from '../types';

interface Props {
  backend: LlmBackendInfo;
  className?: string;
}

const SOURCE_STYLE: Record<string, { color: string; bg: string; border: string }> = {
  claude_code:         { color: 'text-amber-700 dark:text-amber-300',  bg: 'bg-amber-50 dark:bg-amber-500/10',  border: 'border-amber-200 dark:border-amber-500/20' },
  anthropic:           { color: 'text-orange-700 dark:text-orange-300', bg: 'bg-orange-50 dark:bg-orange-500/10', border: 'border-orange-200 dark:border-orange-500/20' },
  openrouter:          { color: 'text-purple-700 dark:text-purple-300', bg: 'bg-purple-50 dark:bg-purple-500/10', border: 'border-purple-200 dark:border-purple-500/20' },
  openai:              { color: 'text-green-700 dark:text-green-300',   bg: 'bg-green-50 dark:bg-green-500/10',   border: 'border-green-200 dark:border-green-500/20' },
  groq:                { color: 'text-blue-700 dark:text-blue-300',     bg: 'bg-blue-50 dark:bg-blue-500/10',     border: 'border-blue-200 dark:border-blue-500/20' },
  custom:              { color: 'text-indigo-700 dark:text-indigo-300', bg: 'bg-indigo-50 dark:bg-indigo-500/10', border: 'border-indigo-200 dark:border-indigo-500/20' },
  claude_code_no_auth: { color: 'text-amber-700 dark:text-amber-300',  bg: 'bg-amber-50 dark:bg-amber-500/10',  border: 'border-amber-200 dark:border-amber-500/20' },
  default:             { color: 'text-gray-500 dark:text-[#71717A]',   bg: 'bg-gray-50 dark:bg-[#18181B]',      border: 'border-gray-200 dark:border-[#27272A]' },
};

function StatusIcon({ configured, source }: { configured: boolean; source: string }) {
  if (source === 'claude_code_no_auth') return <AlertTriangle size={14} className="text-amber-500 shrink-0" />;
  if (source === 'default')             return <XCircle       size={14} className="text-gray-400 shrink-0" />;
  if (configured)                       return <CheckCircle   size={14} className="text-emerald-500 shrink-0" />;
  return                                       <XCircle       size={14} className="text-red-500 shrink-0" />;
}

export default function LlmBackendCard({ backend, className }: Props) {
  const style = SOURCE_STYLE[backend.source] ?? SOURCE_STYLE.default;

  return (
    <div className={cn('rounded-xl border p-4', style.bg, style.border, className)}>
      <div className="flex items-start gap-3">
        <div className={cn('mt-0.5 rounded-lg p-1.5', style.bg)}>
          <Cpu size={14} className={style.color} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <StatusIcon configured={backend.configured} source={backend.source} />
            <span className={cn('text-sm font-semibold', style.color)}>{backend.display_name}</span>
          </div>
          <p className="text-xs text-gray-500 dark:text-[#71717A] font-mono truncate">{backend.detail}</p>
          {backend.configured && (
            <p className="text-xs text-gray-400 dark:text-[#52525B] mt-1 font-mono truncate">{backend.model}</p>
          )}
        </div>
      </div>
    </div>
  );
}
