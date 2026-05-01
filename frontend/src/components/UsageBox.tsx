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
  const cost = calcCost(usage.model, usage.input_tokens, usage.output_tokens);

  return (
    <div className="shrink-0 border border-gray-700 rounded-lg overflow-hidden text-xs min-w-[150px]">
      <div
        className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-700/50 cursor-pointer hover:bg-gray-700/80 transition-colors select-none whitespace-nowrap"
        onClick={() => setOpen(o => !o)}
      >
        <Zap size={11} className="text-gray-400 shrink-0" />
        <span className="text-gray-300 font-mono text-[11.5px]">
          <b className="text-gray-100 font-semibold">{secs}</b>
          {cost && <> · <b className="text-gray-100 font-semibold">{fmtCost(cost.total)}</b></>}
        </span>
        <ChevronDown
          size={10}
          className={cn('ml-auto text-gray-500 transition-transform duration-200', open && 'rotate-180')}
        />
      </div>

      {open && (
        <div className="flex flex-col gap-1.5 p-3 border-t border-gray-700 bg-gray-900">
          {[
            { label: 'Latency',       value: secs },
            { label: 'Input tokens',  value: fmtTok(usage.input_tokens),  extra: cost ? fmtCost(cost.inCost)  : null },
            { label: 'Output tokens', value: fmtTok(usage.output_tokens), extra: cost ? fmtCost(cost.outCost) : null },
          ].map(row => (
            <div key={row.label} className="flex justify-between items-center gap-4">
              <span className="text-[10px] uppercase tracking-widest text-gray-500">{row.label}</span>
              <span className="font-mono text-[11.5px] text-gray-100 font-medium">
                {row.value}
                {row.extra && <span className="text-gray-500 text-[10px]"> ({row.extra})</span>}
              </span>
            </div>
          ))}

          {cost && (
            <div className="flex justify-between items-center gap-4 pt-1.5 border-t border-gray-700">
              <span className="text-[10px] uppercase tracking-widest text-gray-500">Total cost</span>
              <span className="font-mono text-[12px] text-emerald-400 font-semibold">{fmtCost(cost.total)}</span>
            </div>
          )}

          <div className="text-[10px] text-gray-600 font-mono mt-0.5 break-all">{usage.model}</div>
        </div>
      )}
    </div>
  );
}
