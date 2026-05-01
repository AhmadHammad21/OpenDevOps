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
    <div className="flex-1 min-w-0 border border-gray-700 rounded-lg overflow-hidden text-xs">
      <div
        className="flex items-center gap-2 px-3 py-1.5 bg-gray-700/50 cursor-pointer hover:bg-gray-700/80 transition-colors select-none"
        onClick={() => setOpen(o => !o)}
      >
        <Wrench size={12} className="text-emerald-500 shrink-0" />
        <span className="text-emerald-400 font-semibold font-mono">{calls.length}</span>
        <span className="text-gray-400">tool calls</span>
        <ChevronDown
          size={10}
          className={cn('ml-auto text-gray-500 transition-transform duration-200', open && 'rotate-180')}
        />
      </div>

      {open && (
        <div className="flex flex-col">
          {calls.map((tc, i) => (
            <div key={i} className="border-t border-gray-700 p-3 flex flex-col gap-2">
              <div className="font-mono text-amber-400 font-semibold flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                {tc.tool}
              </div>
              <div className="flex flex-col gap-1">
                <div className="text-[10px] uppercase tracking-widest text-gray-500">Input</div>
                <pre className="font-mono text-[11px] bg-gray-900 border border-gray-700 rounded px-2.5 py-1.5 text-gray-400 whitespace-pre max-h-48 overflow-auto leading-snug">
                  {fmtJson(tc.args)}
                </pre>
              </div>
              <div className="flex flex-col gap-1">
                <div className="text-[10px] uppercase tracking-widest text-gray-500">Output</div>
                <pre className="font-mono text-[11px] bg-gray-900 border border-gray-700 rounded px-2.5 py-1.5 text-gray-400 whitespace-pre max-h-48 overflow-auto leading-snug">
                  {fmtJson(tc.result)}
                </pre>
              </div>
            </div>
          ))}

          {streaming && (
            <div className="border-t border-gray-700 px-3 py-2 flex items-center gap-2 text-gray-500">
              <div className="spinner-dots"><span /><span /><span /></div>
              <span>Running tools…</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
