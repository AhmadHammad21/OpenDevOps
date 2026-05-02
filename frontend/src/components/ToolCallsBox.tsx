import { useState } from 'react';
import { Wrench, ChevronDown } from 'lucide-react';
import { cn, fmtJson } from '../lib/utils';
import type { ToolCall } from '../types';

interface Props {
  calls: ToolCall[];
  streaming: boolean;
}

export default function ToolCallsBox({ calls, streaming }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="shrink-0 border border-gray-200 dark:border-[#27272F] rounded-[7px] overflow-hidden text-xs">
      <div
        className="flex items-center gap-2 px-2.5 py-[5px] bg-gray-100 dark:bg-[#1E1E24] cursor-pointer hover:bg-gray-200/60 dark:hover:bg-[#27272F] transition-colors select-none"
        onClick={() => setOpen(o => !o)}
      >
        <Wrench size={11} className="text-indigo-500 dark:text-[#818CF8] shrink-0" />
        <span className="text-indigo-500 dark:text-[#818CF8] font-semibold font-mono">{calls.length}</span>
        <span className="text-gray-500 dark:text-[#94A3B8]">tool calls</span>
        <ChevronDown
          size={10}
          className={cn('ml-auto text-gray-400 dark:text-[#64748B] transition-transform duration-200', open && 'rotate-180')}
        />
      </div>

      {open && (
        <div className="flex flex-col">
          {calls.map((tc, i) => (
            <div key={i} className="border-t border-gray-200 dark:border-[#27272F] p-2.5 flex flex-col gap-2">
              <div className="font-mono font-semibold flex items-center gap-1.5 text-[11px]" style={{ color: '#FBBF24' }}>
                <span className="w-[5px] h-[5px] rounded-full bg-indigo-500 dark:bg-[#818CF8] shrink-0" />
                {tc.tool}
              </div>
              <pre className="font-mono text-[11px] bg-gray-50 dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-[5px] px-2.5 py-1.5 text-gray-500 dark:text-[#94A3B8] overflow-auto max-h-24 leading-snug whitespace-pre">
                {fmtJson(tc.args)}
              </pre>
            </div>
          ))}

          {streaming && (
            <div className="border-t border-gray-200 dark:border-[#27272F] px-2.5 py-2 flex items-center gap-2 text-gray-400 dark:text-[#64748B]">
              <div className="spinner-dots"><span /><span /><span /></div>
              <span>Running tools…</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
