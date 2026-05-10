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
import { fetchSessions, deleteSession as apiDeleteSession } from './lib/api';
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
  const stored = localStorage.getItem('devops-session-id');
  const id = stored ?? (() => {
    const newId = crypto.randomUUID();
    localStorage.setItem('devops-session-id', newId);
    return newId;
  })();
  return <Navigate to={`/chat/${id}`} replace />;
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

  const switchSession = (id: string) => {
    localStorage.setItem('devops-session-id', id);
    navigate('/chat/' + id);
  };

  const deleteSession = async (id: string) => {
    await apiDeleteSession(id);
    setSessions(prev => prev.filter(s => s.id !== id));
    if (id === currentSessionId) newChat();
  };

  return (
    <div className="flex w-full h-screen overflow-hidden bg-gray-50 dark:bg-[#0F0F12]">
      <Sidebar
        sessions={sessions}
        hasMore={hasMore}
        currentSessionId={currentSessionId}
        onNew={newChat}
        onSwitch={switchSession}
        onDelete={deleteSession}
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
