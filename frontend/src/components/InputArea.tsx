import { useState, useRef } from 'react';
import { Send, Square } from 'lucide-react';
import { cn } from '../lib/utils';

interface Props {
  busy: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

export default function InputArea({ busy, onSend, onStop }: Props) {
  const [value, setValue] = useState('');
  const ref = useRef<HTMLTextAreaElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const resize = () => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  };

  const submit = () => {
    const text = value.trim();
    if (!text || busy) return;
    onSend(text);
    setValue('');
    if (ref.current) ref.current.style.height = 'auto';
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
  };

  return (
    <div className="px-5 py-3 border-t border-gray-200 dark:border-[#27272F] bg-white dark:bg-[#18181C] shrink-0">
      <div
        ref={wrapRef}
        className="flex gap-2 items-end border border-gray-300 dark:border-[#3F3F47] rounded-[10px] px-2.5 py-2 shadow-sm transition-all duration-150 focus-within:border-indigo-500 dark:focus-within:border-[#818CF8] focus-within:shadow-[0_0_0_3px_rgba(99,102,241,0.12)] dark:focus-within:shadow-[0_0_0_3px_rgba(129,140,248,0.12)]"
      >
        <textarea
          ref={ref}
          value={value}
          onChange={e => { setValue(e.target.value); resize(); }}
          onKeyDown={handleKey}
          placeholder="Describe an incident or ask about your AWS environment…"
          rows={1}
          className="flex-1 border-none outline-none resize-none font-sans text-[13px] text-gray-900 dark:text-[#F1F5F9] bg-transparent leading-[1.55] max-h-[140px] overflow-y-auto placeholder:text-gray-400 dark:placeholder:text-[#64748B]"
        />
        <button
          onClick={busy ? onStop : submit}
          disabled={!busy && !value.trim()}
          className={cn(
            'w-8 h-8 rounded-[7px] shrink-0 flex items-center justify-center transition-colors',
            busy
              ? 'bg-gray-200 dark:bg-[#27272F] hover:bg-gray-300 dark:hover:bg-[#3F3F47]'
              : value.trim()
                ? 'bg-indigo-500 dark:bg-[#818CF8] hover:bg-indigo-600 dark:hover:bg-[#6366F1]'
                : 'bg-gray-200 dark:bg-[#27272F] cursor-default',
          )}
        >
          {busy
            ? <Square size={12} className="fill-gray-600 dark:fill-[#94A3B8] stroke-none" />
            : <Send size={13} className={value.trim() ? 'text-white' : 'text-gray-400 dark:text-[#64748B]'} />
          }
        </button>
      </div>
      <div className="text-[11px] text-gray-400 dark:text-[#64748B] text-center mt-1.5">
        Enter to send · Shift+Enter for new line
      </div>
    </div>
  );
}
