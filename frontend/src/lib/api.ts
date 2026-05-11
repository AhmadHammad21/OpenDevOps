import type { Session, MessageRecord, HistoryStats, SearchResult, User, Alert, ServiceStatus } from '../types';

export function getAuthToken(): string | null {
  return localStorage.getItem('auth-token');
}

export async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> ?? {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return fetch(url, { ...options, headers });
}

export async function fetchSessions(limit = 15, offset = 0): Promise<Session[]> {
  const res = await apiFetch(`/sessions?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error('Failed to load sessions');
  return res.json() as Promise<Session[]>;
}

export async function fetchMessages(sessionId: string): Promise<MessageRecord[]> {
  const res = await apiFetch(`/sessions/${sessionId}/messages`);
  if (!res.ok) throw new Error('Failed to load messages');
  return res.json() as Promise<MessageRecord[]>;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await apiFetch(`/sessions/${sessionId}`, { method: 'DELETE' });
}

export async function renameSession(sessionId: string, title: string): Promise<void> {
  await apiFetch(`/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
}

export async function fetchHistory(days = 30): Promise<HistoryStats> {
  const res = await apiFetch(`/api/history?days=${days}`);
  if (!res.ok) throw new Error('Failed to load history');
  return res.json() as Promise<HistoryStats>;
}

export async function searchHistory(query: string): Promise<SearchResult[]> {
  const res = await apiFetch(`/api/history/search?q=${encodeURIComponent(query)}&limit=10`);
  if (!res.ok) throw new Error('Failed to search history');
  const data = await res.json() as { results: SearchResult[] };
  return data.results;
}

// ── User management (admin only) ─────────────────────────────────────────

export async function fetchUsers(): Promise<User[]> {
  const res = await apiFetch('/api/users');
  if (!res.ok) throw new Error('Failed to load users');
  return res.json() as Promise<User[]>;
}

export async function createUser(data: { email: string; name: string; password: string; role: string }): Promise<User> {
  const res = await apiFetch('/api/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json() as { detail?: string };
    throw new Error(err.detail ?? 'Failed to create user');
  }
  return res.json() as Promise<User>;
}

export async function updateUser(id: string, data: { name?: string; role?: string; password?: string }): Promise<User> {
  const res = await apiFetch(`/api/users/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json() as { detail?: string };
    throw new Error(err.detail ?? 'Failed to update user');
  }
  return res.json() as Promise<User>;
}

export async function deleteUser(id: string): Promise<void> {
  const res = await apiFetch(`/api/users/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete user');
}

// ── Monitoring ────────────────────────────────────────────────────────────

export async function fetchAlerts(limit = 50): Promise<Alert[]> {
  const res = await apiFetch(`/api/monitoring/alerts?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to load alerts');
  return res.json() as Promise<Alert[]>;
}

export async function fetchAlert(id: string): Promise<Alert> {
  const res = await apiFetch(`/api/monitoring/alerts/${id}`);
  if (!res.ok) throw new Error('Alert not found');
  return res.json() as Promise<Alert>;
}

export async function fetchServices(): Promise<ServiceStatus[]> {
  const res = await apiFetch('/api/monitoring/services');
  if (!res.ok) throw new Error('Failed to load services');
  return res.json() as Promise<ServiceStatus[]>;
}
