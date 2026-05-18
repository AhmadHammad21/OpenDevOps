import { useState, useEffect, useCallback } from 'react';
import { Routes, Route, Navigate, useNavigate, useMatch } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import ChatPage from './pages/ChatPage';
import DashboardPage from './pages/DashboardPage';
import HistoryPage from './pages/HistoryPage';
import SettingsPage from './pages/SettingsPage';
import UsersPage from './pages/UsersPage';
import LoginPage from './pages/LoginPage';
import MonitoringPage from './pages/MonitoringPage';
import AlertDetailPage from './pages/AlertDetailPage';
import InitPage from './pages/InitPage';
import ProtectedRoute from './components/ProtectedRoute';
import { apiFetch, fetchSessions, deleteSession as apiDeleteSession, renameSession as apiRenameSession } from './lib/api';
import { useAuth } from './context/AuthContext';
import type { Session } from './types';

function LogoutPage() {
  const { logout, authRequired } = useAuth();
  const [done, setDone] = useState(false);

  useEffect(() => {
    logout();
    setDone(true);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!done) return null;
  return <Navigate to={authRequired ? '/login' : '/'} replace />;
}

function RedirectToSession() {
  const [ready, setReady] = useState<'init' | 'chat' | null>(null);
  const { user, authRequired, loading } = useAuth();

  useEffect(() => {
    if (loading) return;

    let cancelled = false;
    const routeAfterInitCheck = async () => {
      if (authRequired && user?.role !== 'admin') {
        if (!cancelled) setReady('chat');
        return;
      }

      try {
        const r = await apiFetch('/api/init/status');
        const d = await r.json();
        const setupComplete = Boolean(d.setup_complete ?? d.initialized);
        const accountReady = Boolean(d.has_user || !d.auth_enabled);
        if (!cancelled) setReady(setupComplete && accountReady ? 'chat' : 'init');
      } catch {
        if (!cancelled) setReady('chat');
      }
    };

    setReady(null);
    void routeAfterInitCheck();
    return () => { cancelled = true; };
  }, [authRequired, loading, user?.role]);

  if (ready === 'init') return <Navigate to="/init" replace />;
  if (ready === 'chat') {
    const stored = localStorage.getItem('devops-session-id');
    const id = stored ?? (() => {
      const newId = crypto.randomUUID();
      localStorage.setItem('devops-session-id', newId);
      return newId;
    })();
    return <Navigate to={`/chat/${id}`} replace />;
  }
  return null;
}

const PAGE_SIZE = 15;

function AppLayout() {
  const navigate = useNavigate();
  const [sessions, setSessions]   = useState<Session[]>([]);
  const [hasMore,  setHasMore]    = useState(false);
  const [offset,   setOffset]     = useState(0);
  const chatMatch = useMatch('/chat/:sessionId');
  const currentSessionId = chatMatch?.params.sessionId ?? '';

  const loadSessions = useCallback(async () => {
    try {
      const data = await fetchSessions(PAGE_SIZE, 0);
      setSessions(data);
      setOffset(PAGE_SIZE);
      setHasMore(data.length === PAGE_SIZE);
    } catch { /* silent */ }
  }, []);

  const loadMoreSessions = useCallback(async () => {
    try {
      const data = await fetchSessions(PAGE_SIZE, offset);
      setSessions(prev => [...prev, ...data]);
      setOffset(prev => prev + PAGE_SIZE);
      setHasMore(data.length === PAGE_SIZE);
    } catch { /* silent */ }
  }, [offset]);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  const newChat = () => {
    const id = crypto.randomUUID();
    localStorage.setItem('devops-session-id', id);
    navigate('/chat/' + id);
  };

  const deleteSession = async (id: string) => {
    await apiDeleteSession(id);
    setSessions(prev => prev.filter(s => s.id !== id));
    if (id === currentSessionId) newChat();
  };

  const renameSession = async (id: string, title: string) => {
    await apiRenameSession(id, title);
    setSessions(prev => prev.map(s => s.id === id ? { ...s, title } : s));
  };

  return (
    <div className="flex w-full h-screen overflow-hidden bg-gray-50 dark:bg-[#0F0F12]">
      <Sidebar
        sessions={sessions}
        hasMore={hasMore}
        currentSessionId={currentSessionId}
        onNew={newChat}
        onDelete={deleteSession}
        onRename={renameSession}
        onLoadMore={loadMoreSessions}
      />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0 min-h-0">
        <Routes>
          <Route path="/"                       element={<RedirectToSession />} />
          <Route path="/chat/:sessionId"        element={<ChatPage onSessionsChange={loadSessions} onNew={newChat} />} />
          <Route path="/dashboard"              element={<DashboardPage />} />
          <Route path="/history"               element={<HistoryPage />} />
          <Route path="/settings"              element={<SettingsPage />} />
          <Route path="/users"                 element={<UsersPage />} />
          <Route path="/monitoring"            element={<MonitoringPage />} />
          <Route path="/monitoring/:alertId"   element={<AlertDetailPage />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login"  element={<LoginPage />} />
      <Route path="/logout" element={<LogoutPage />} />
      <Route path="/init"   element={<InitPage />} />
      <Route path="/*" element={
        <ProtectedRoute>
          <AppLayout />
        </ProtectedRoute>
      } />
    </Routes>
  );
}
