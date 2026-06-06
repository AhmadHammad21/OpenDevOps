import { useState, useEffect, useRef } from 'react';
import { useParams, Navigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Plus } from 'lucide-react';
import EmptyState from '../components/EmptyState';
import UserMessage from '../components/UserMessage';
import AgentMessage from '../components/AgentMessage';
import InputArea from '../components/InputArea';
import { fetchMessages, getAuthToken } from '../lib/api';
import type { Message, AgentMessage as AgentMsg, MessageRecord } from '../types';

function recordsToMessages(records: MessageRecord[]): Message[] {
  return records.map(r => {
    if (r.role === 'user') {
      return { id: r.id, role: 'user' as const, content: r.content };
    }
    return {
      id: r.id,
      role: 'agent' as const,
      content: r.content,
      toolCalls: (r.tool_calls ?? []).map(tc => ({
        tool: tc.tool_name,
        args: tc.args,
        result: tc.result,
      })),
      usage: r.usage,
      streaming: false,
      streamLabel: '',
    };
  });
}

interface Props {
  onSessionsChange: () => void;
  onNew: () => void;
}

export default function ChatPage({ onSessionsChange, onNew }: Props) {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const [messages,          setMessages]          = useState<Message[]>([]);
  const [busy,              setBusy]              = useState(false);
  const [followUpQuestions, setFollowUpQuestions] = useState<string[]>([]);
  const abortRef                                  = useRef<AbortController | null>(null);
  const bottomRef                                 = useRef<HTMLDivElement>(null);
  const autoPromptFired                           = useRef(false);

  useEffect(() => {
    if (sessionId) localStorage.setItem('devops-session-id', sessionId);
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    setMessages([]);
    fetchMessages(sessionId)
      .then(records => { if (records.length) setMessages(recordsToMessages(records)); })
      .catch(() => {});
  }, [sessionId]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ block: 'end' }); }, [messages]);

  // Auto-submit a pre-seeded prompt from the Monitoring dashboard deeplink
  useEffect(() => {
    const prompt = searchParams.get('prompt');
    if (prompt && !autoPromptFired.current && !busy) {
      autoPromptFired.current = true;
      setSearchParams({}, { replace: true });
      send(prompt);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const patch = (id: string, update: Partial<AgentMsg>) =>
    setMessages(prev => prev.map(m => m.id === id ? { ...m, ...update } as AgentMsg : m));

  const send = async (text: string) => {
    if (!sessionId || busy || !text.trim()) return;
    setFollowUpQuestions([]);

    const agentId = crypto.randomUUID();
    setMessages(prev => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', content: text },
      { id: agentId, role: 'agent', content: '', toolCalls: [], usage: null, streaming: true, streamLabel: 'On the case…' },
    ]);
    setBusy(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    let contentAcc = '';

    try {
      const token = getAuthToken();
      const resp = await fetch('/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ session_id: sessionId, message: text }),
        signal: ctrl.signal,
      });

      if (!resp.ok) {
        const msg = resp.statusText;
        patch(agentId, { streaming: false, error: msg });
        toast.error(msg);
        return;
      }

      const reader  = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          let payload: Record<string, unknown>;
          try { payload = JSON.parse(line.slice(6)) as Record<string, unknown>; } catch { continue; }

          if (payload.type === 'token') {
            contentAcc += payload.text as string;
            patch(agentId, { content: contentAcc });
          } else if (payload.type === 'tool_status') {
            patch(agentId, { streamLabel: payload.label as string });
          } else if (payload.type === 'tool_call') {
            setMessages(prev => prev.map(m => {
              if (m.id !== agentId) return m;
              const a = m as AgentMsg;
              return { ...a, toolCalls: [...a.toolCalls, { tool: payload.tool as string, args: payload.args, result: payload.result }] };
            }));
          } else if (payload.type === 'done') {
            patch(agentId, { streaming: false, usage: payload.usage as AgentMsg['usage'] });
            const fq = payload.follow_up_questions;
            if (Array.isArray(fq) && fq.length > 0) setFollowUpQuestions(fq as string[]);
          } else if (payload.type === 'error') {
            const msg = payload.message as string;
            patch(agentId, { streaming: false, error: msg });
            toast.error(msg, { duration: 6000 });
          }
        }
      }
    } catch (err: unknown) {
      const isAbort = err instanceof Error && err.name === 'AbortError';
      if (!isAbort) {
        const msg = (err as Error).message;
        patch(agentId, { streaming: false, error: msg });
        toast.error(msg);
      } else {
        patch(agentId, { streaming: false });
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
      onSessionsChange();
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    if (sessionId) {
      const token = getAuthToken();
      fetch(`/chat/${sessionId}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      }).catch(() => {});
    }
  };

  if (!sessionId) return <Navigate to="/" replace />;

  return (
    <div className="flex-1 flex flex-col overflow-hidden min-h-0 bg-white dark:bg-[#000000]">
      {/* Chat sub-header */}
      <div className="px-5 py-2.5 border-b border-gray-200 dark:border-[#1E222B] bg-white dark:bg-[#0A0C10] flex items-center gap-2.5 shrink-0">
        <div className="w-[30px] h-[30px] bg-indigo-50 dark:bg-[#04103A] rounded-lg flex items-center justify-center text-sm shrink-0 select-none">
          ⚡
        </div>
        <div>
          <div className="text-[13px] font-semibold text-gray-900 dark:text-[#E4E1EA]">DevOps Agent</div>
          <div className="text-[11px] text-emerald-500 dark:text-[#00A3FF] flex items-center gap-1">
            <span className="w-[5px] h-[5px] rounded-full bg-emerald-500 dark:bg-[#00A3FF] inline-block" />
            Active
          </div>
        </div>
        <button
          onClick={onNew}
          className="ml-auto flex items-center gap-1.5 px-2.5 py-[5px] bg-indigo-500 hover:bg-indigo-600 text-white text-[12px] font-medium rounded-[5px] transition-colors"
        >
          <Plus size={12} />
          New chat
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-[18px] min-h-0">
        {messages.length === 0 ? (
          <EmptyState onChip={send} />
        ) : (
          messages.map(m =>
            m.role === 'user'
              ? <UserMessage  key={m.id} content={m.content} />
              : <AgentMessage key={m.id} message={m} />
          )
        )}
        <div ref={bottomRef} />
      </div>

      {followUpQuestions.length > 0 && !busy && (
        <div className="px-6 pb-2 flex flex-wrap gap-2">
          {followUpQuestions.map((q, i) => (
            <button
              key={i}
              onClick={() => send(q)}
              className="text-[13px] px-3 py-1.5 rounded-full border border-indigo-200 dark:border-[#0E4FA6] bg-indigo-50 dark:bg-[#04103A] text-indigo-600 dark:text-[#00A3FF] hover:bg-indigo-100 dark:hover:bg-[#071A57] transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      )}
      <InputArea busy={busy} onSend={send} onStop={stop} />
    </div>
  );
}
