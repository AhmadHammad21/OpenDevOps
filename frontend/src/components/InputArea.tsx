import { useState, useRef } from 'react';

interface Props {
  busy: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

export default function InputArea({ busy, onSend, onStop }: Props) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  };

  const submit = () => {
    const text = value.trim();
    if (!text || busy) return;
    onSend(text);
    setValue('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
  };

  return (
    <div id="input-area">
      <textarea
        ref={textareaRef}
        id="input"
        value={value}
        onChange={e => { setValue(e.target.value); resize(); }}
        onKeyDown={handleKey}
        placeholder="Describe an incident or ask about your AWS environment…"
        rows={1}
      />
      <button
        id="send-btn"
        className={busy ? 'stopping' : ''}
        onClick={busy ? onStop : submit}
        disabled={!busy && !value.trim()}
      >
        {busy ? (
          <svg viewBox="0 0 24 24"><rect x="5" y="5" width="14" height="14" rx="2" /></svg>
        ) : (
          <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" /></svg>
        )}
      </button>
    </div>
  );
}
