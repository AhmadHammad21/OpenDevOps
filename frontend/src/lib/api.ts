import type { Session, MessageRecord } from '../types';

export async function fetchSessions(): Promise<Session[]> {
  const res = await fetch('/sessions');
  if (!res.ok) throw new Error('Failed to load sessions');
  return res.json() as Promise<Session[]>;
}

export async function fetchMessages(sessionId: string): Promise<MessageRecord[]> {
  const res = await fetch(`/sessions/${sessionId}/messages`);
  if (!res.ok) throw new Error('Failed to load messages');
  return res.json() as Promise<MessageRecord[]>;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`/sessions/${sessionId}`, { method: 'DELETE' });
}
