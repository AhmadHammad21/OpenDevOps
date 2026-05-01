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
    <div className="px-6 py-3.5 border-t border-gray-700 bg-gray-800 flex gap-2.5 items-end shrink-0">
      <textarea
        ref={ref}
        value={value}
        onChange={e => { setValue(e.target.value); resize(); }}
        onKeyDown={handleKey}
        placeholder="Describe an incident or ask about your AWS environment…"
        rows={1}
        className="flex-1 bg-gray-900 border border-gray-700 rounded-xl text-gray-50 text-sm px-3.5 py-2.5 resize-none outline-none min-h-[42px] max-h-40 leading-relaxed placeholder:text-gray-600 focus:border-emerald-500 transition-colors font-sans"
      />
      <button
        onClick={busy ? onStop : submit}
        disabled={!busy && !value.trim()}
        className={cn(
          'w-[42px] h-[42px] rounded-xl shrink-0 flex items-center justify-center transition-colors',
          busy
            ? 'bg-red-600 hover:bg-red-700'
            : 'bg-emerald-500 hover:bg-emerald-600 disabled:bg-gray-700 disabled:cursor-not-allowed',
        )}
      >
        {busy
          ? <Square size={14} className="fill-white stroke-none" />
          : <Send size={15} className="text-white" />
        }
      </button>
    </div>
  );
}
