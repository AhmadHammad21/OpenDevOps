import { useState, useEffect, useRef, useCallback } from 'react';
import { Routes, Route } from 'react-router-dom';
import { toast } from 'sonner';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import EmptyState from './components/EmptyState';
import UserMessage from './components/UserMessage';
import AgentMessage from './components/AgentMessage';
import InputArea from './components/InputArea';
import HistoryPage from './pages/HistoryPage';
import SettingsPage from './pages/SettingsPage';
import { fetchSessions, fetchMessages, deleteSession as apiDeleteSession } from './lib/api';
import type { Message, AgentMessage as AgentMsg, Session, MessageRecord } from './types';

function newSessionId(): string {
  const id = crypto.randomUUID();
  localStorage.setItem('devops-session-id', id);
  return id;
}

function getStoredSessionId(): string {
  return localStorage.getItem('devops-session-id') ?? newSessionId();
}

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

function ChatView({
  sessionId,
  messages,
  busy,
  onSend,
  onStop,
}: {
  sessionId: string;
  messages: Message[];
  busy: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ block: 'end' }); }, [messages]);

  return (
    <>
      <div className="flex-1 overflow-y-auto px-6 py-7 flex flex-col gap-5">
        {messages.length === 0 ? (
          <EmptyState onChip={onSend} />
        ) : (
          messages.map(m =>
            m.role === 'user'
              ? <UserMessage  key={m.id} content={m.content} />
              : <AgentMessage key={m.id} message={m} />
          )
        )}
        <div ref={bottomRef} />
      </div>
      <InputArea busy={busy} onSend={onSend} onStop={onStop} />
    </>
  );
}

export default function App() {
  const [sessionId, setSessionId] = useState<string>(getStoredSessionId);
  const [messages,  setMessages]  = useState<Message[]>([]);
  const [busy,      setBusy]      = useState(false);
  const [sessions,  setSessions]  = useState<Session[]>([]);
  const abortRef                  = useRef<AbortController | null>(null);

  const loadSessions = useCallback(async () => {
    try { setSessions(await fetchSessions()); } catch { /* silent */ }
  }, []);

  useEffect(() => {
    loadSessions();
    (async () => {
      try {
        const records = await fetchMessages(sessionId);
        if (records.length) setMessages(recordsToMessages(records));
      } catch { /* new session */ }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const newChat = () => {
    setSessionId(newSessionId());
    setMessages([]);
  };

  const switchSession = async (id: string) => {
    localStorage.setItem('devops-session-id', id);
    setSessionId(id);
    setMessages([]);
    try {
      const records = await fetchMessages(id);
      setMessages(records.length ? recordsToMessages(records) : []);
    } catch { /* empty */ }
  };

  const deleteSession = async (id: string) => {
    await apiDeleteSession(id);
    setSessions(prev => prev.filter(s => s.id !== id));
    if (id === sessionId) newChat();
  };

  const send = async (text: string) => {
    if (busy || !text.trim()) return;

    const agentId = crypto.randomUUID();
    setMessages(prev => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', content: text },
      { id: agentId, role: 'agent', content: '', toolCalls: [], usage: null, streaming: true, streamLabel: 'On the case…' },
    ]);
    setBusy(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    const patch = (update: Partial<AgentMsg>) =>
      setMessages(prev => prev.map(m =>
        m.id === agentId ? { ...m, ...update } as AgentMsg : m
      ));

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
        patch({ streaming: false, error: msg });
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
            patch({ content: contentAcc });
          } else if (payload.type === 'tool_status') {
            patch({ streamLabel: payload.label as string });
          } else if (payload.type === 'tool_call') {
            setMessages(prev => prev.map(m => {
              if (m.id !== agentId) return m;
              const a = m as AgentMsg;
              return { ...a, toolCalls: [...a.toolCalls, { tool: payload.tool as string, args: payload.args, result: payload.result }] };
            }));
          } else if (payload.type === 'done') {
            patch({ streaming: false, usage: payload.usage as AgentMsg['usage'] });
          } else if (payload.type === 'error') {
            const msg = payload.message as string;
            patch({ streaming: false, error: msg });
            toast.error(msg, { duration: 6000 });
          }
        }
      }
    } catch (err: unknown) {
      const isAbort = err instanceof Error && err.name === 'AbortError';
      if (!isAbort) {
        const msg = (err as Error).message;
        patch({ streaming: false, error: msg });
        toast.error(msg);
      } else {
        patch({ streaming: false });
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
      loadSessions();
    }
  };

  const stop = () => abortRef.current?.abort();

  return (
    <div className="flex h-screen overflow-hidden bg-gray-900 text-gray-50">
      <Sidebar
        sessions={sessions}
        currentSessionId={sessionId}
        onNew={newChat}
        onSwitch={switchSession}
        onDelete={deleteSession}
      />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Header sessionId={sessionId} />
        <Routes>
          <Route
            path="/"
            element={
              <ChatView
                sessionId={sessionId}
                messages={messages}
                busy={busy}
                onSend={send}
                onStop={stop}
              />
            }
          />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </div>
    </div>
  );
}
