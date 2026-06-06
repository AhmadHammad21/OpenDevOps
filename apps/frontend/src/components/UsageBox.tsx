import { useState } from 'react';
import { ChevronDown, Zap } from 'lucide-react';
import { cn, calcCost, fmtCost, fmtTok } from '../lib/utils';
import type { Usage } from '../types';

interface Props {
  usage: Usage;
}

export default function UsageBox({ usage }: Props) {
  const [open, setOpen] = useState(false);
  const secs = ((usage.latency_ms ?? 0) / 1000).toFixed(1) + 's';
  const cost = calcCost(usage.cost_usd);

  return (
    <div className="shrink-0 border border-gray-200 dark:border-[#1E222B] rounded-[7px] overflow-hidden text-xs min-w-[140px]">
      <div
        className="flex items-center gap-1.5 px-2.5 py-[5px] bg-gray-100 dark:bg-[#15181F] cursor-pointer hover:bg-gray-200/60 dark:hover:bg-[#1E222B] transition-colors select-none whitespace-nowrap"
        onClick={() => setOpen(o => !o)}
      >
        <Zap size={11} className="text-gray-400 dark:text-[#64748B] shrink-0" />
        <span className="text-gray-700 dark:text-[#CBD5E1] font-mono text-[11px]">
          <strong className="text-gray-900 dark:text-[#E4E1EA] font-semibold">{secs}</strong>
          {cost && (
            <> · <strong className="text-indigo-500 dark:text-[#00A3FF] font-semibold">${cost.total.toFixed(4)}</strong></>
          )}
        </span>
        <ChevronDown
          size={10}
          className={cn('ml-auto text-gray-400 dark:text-[#64748B] transition-transform duration-200', open && 'rotate-180')}
        />
      </div>

      {open && (
        <div className="flex flex-col gap-1.5 p-2.5 border-t border-gray-200 dark:border-[#1E222B] bg-white dark:bg-[#0A0C10]">
          {[
            { label: 'Latency',       value: secs },
            { label: 'In tokens',     value: fmtTok(usage.input_tokens) },
            { label: 'Out tokens',    value: fmtTok(usage.output_tokens) },
          ].map(row => (
            <div key={row.label} className="flex justify-between items-center gap-4">
              <span className="text-[10px] uppercase tracking-[0.08em] text-gray-400 dark:text-[#64748B]">{row.label}</span>
              <span className="font-mono text-[11px] text-gray-900 dark:text-[#E4E1EA] font-medium">{row.value}</span>
            </div>
          ))}

          {cost && (
            <div className="flex justify-between items-center gap-4 pt-1.5 border-t border-gray-200 dark:border-[#1E222B]">
              <span className="text-[10px] uppercase tracking-[0.08em] text-gray-400 dark:text-[#64748B]">Cost</span>
              <span className="font-mono text-[11px] text-indigo-500 dark:text-[#00A3FF] font-semibold">{fmtCost(cost.total)}</span>
            </div>
          )}

          <div className="text-[10px] text-gray-400 dark:text-[#64748B] font-mono mt-0.5 break-all border-t border-gray-200 dark:border-[#1E222B] pt-1.5">
            {usage.model}
          </div>
        </div>
      )}
    </div>
  );
}
