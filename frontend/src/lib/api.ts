import type { Session, MessageRecord, HistoryStats, SearchResult } from '../types';

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

export async function fetchHistory(days: number = 30): Promise<HistoryStats> {
  const res = await fetch(`/history?days=${days}`);
  if (!res.ok) throw new Error('Failed to load history');
  return res.json() as Promise<HistoryStats>;
}

export async function searchHistory(query: string): Promise<SearchResult[]> {
  const res = await fetch(`/history/search?q=${encodeURIComponent(query)}&limit=10`);
  if (!res.ok) throw new Error('Failed to search history');
  const data = await res.json() as { results: SearchResult[] };
  return data.results;
}
