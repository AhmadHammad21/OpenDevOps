import { useState, useEffect, useRef } from 'react';
import { useParams, Navigate } from 'react-router-dom';
import { toast } from 'sonner';
import EmptyState from '../components/EmptyState';
import UserMessage from '../components/UserMessage';
import AgentMessage from '../components/AgentMessage';
import InputArea from '../components/InputArea';
import { fetchMessages } from '../lib/api';
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
}

export default function ChatPage({ onSessionsChange }: Props) {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [messages,  setMessages] = useState<Message[]>([]);
  const [busy,      setBusy]     = useState(false);
  const abortRef                 = useRef<AbortController | null>(null);
  const bottomRef                = useRef<HTMLDivElement>(null);

  // Keep localStorage in sync so the redirect on `/` goes to the last session
  useEffect(() => {
    if (sessionId) localStorage.setItem('devops-session-id', sessionId);
  }, [sessionId]);

  // Load history when session changes
  useEffect(() => {
    if (!sessionId) return;
    setMessages([]);
    fetchMessages(sessionId)
      .then(records => { if (records.length) setMessages(recordsToMessages(records)); })
      .catch(() => {});
  }, [sessionId]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ block: 'end' }); }, [messages]);

  const patch = (id: string, update: Partial<AgentMsg>) =>
    setMessages(prev => prev.map(m => m.id === id ? { ...m, ...update } as AgentMsg : m));

  const send = async (text: string) => {
    if (!sessionId || busy || !text.trim()) return;

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
      const resp = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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

  const stop = () => abortRef.current?.abort();

  if (!sessionId) return <Navigate to="/" replace />;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto px-6 py-7 flex flex-col gap-5">
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
      <InputArea busy={busy} onSend={send} onStop={stop} />
    </div>
  );
}
