import { useState, useEffect, useCallback } from 'react';
import { Routes, Route, Navigate, useNavigate, useMatch } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import ChatPage from './pages/ChatPage';
import HistoryPage from './pages/HistoryPage';
import SettingsPage from './pages/SettingsPage';
import { fetchSessions, deleteSession as apiDeleteSession } from './lib/api';
import type { Session } from './types';

function RedirectToSession() {
  const stored = localStorage.getItem('devops-session-id');
  const id = stored ?? (() => {
    const newId = crypto.randomUUID();
    localStorage.setItem('devops-session-id', newId);
    return newId;
  })();
  return <Navigate to={`/chat/${id}`} replace />;
}

export default function App() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<Session[]>([]);
  const chatMatch = useMatch('/chat/:sessionId');
  const currentSessionId = chatMatch?.params.sessionId ?? '';

  const loadSessions = useCallback(async () => {
    try { setSessions(await fetchSessions()); } catch { /* silent */ }
  }, []);

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
    <div className="flex w-full h-screen overflow-hidden bg-gray-900 text-gray-50">
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onNew={newChat}
        onSwitch={switchSession}
        onDelete={deleteSession}
      />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0 min-h-0">
        <Header />
        <Routes>
          <Route path="/"                   element={<RedirectToSession />} />
          <Route path="/chat/:sessionId"    element={<ChatPage onSessionsChange={loadSessions} />} />
          <Route path="/history"            element={<HistoryPage />} />
          <Route path="/settings"           element={<SettingsPage />} />
        </Routes>
      </div>
    </div>
  );
}
