import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

interface DebugData {
  jwt_secret_set: boolean;
  jwt_secret_preview: string | null;
  checkpoint_backend: string;
  database_url_set: boolean;
  user_count: number;
  jwt_expire_minutes: number;
}

export default function AuthDebugPanel() {
  const { user, token, authRequired, isAuthenticated, loading } = useAuth();
  const [open, setOpen] = useState(true);
  const [serverData, setServerData] = useState<DebugData | null>(null);
  const [authStatus, setAuthStatus] = useState<{ required: boolean } | null>(null);
  const [meData, setMeData] = useState<unknown>(null);
  const [fetchError, setFetchError] = useState('');

  useEffect(() => {
    const run = async () => {
      try {
        const [dbg, status, me] = await Promise.all([
          fetch('/debug/auth').then(r => r.json()),
          fetch('/auth/status').then(r => r.json()),
          fetch('/auth/me', {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          }).then(r => r.json()),
        ]);
        setServerData(dbg as DebugData);
        setAuthStatus(status as { required: boolean });
        setMeData(me);
      } catch (e) {
        setFetchError(String(e));
      }
    };
    void run();
  }, [token]);

  const storedToken = localStorage.getItem('auth-token');

  const Row = ({ label, value, ok }: { label: string; value: string; ok?: boolean }) => (
    <div className="flex gap-2 py-[3px] border-b border-gray-100 last:border-0 text-[11px]">
      <span className="text-gray-400 w-40 shrink-0">{label}</span>
      <span className={ok === true ? 'text-emerald-600 font-medium' : ok === false ? 'text-red-500 font-medium' : 'text-gray-800 font-mono'}>
        {value}
      </span>
    </div>
  );

  return (
    <div className="fixed bottom-4 right-4 z-50 w-72 shadow-xl rounded-lg overflow-hidden border border-gray-200 bg-white text-[12px]">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full px-3 py-2 bg-indigo-500 text-white text-left font-semibold flex items-center justify-between"
      >
        <span>Auth Debug Panel</span>
        <span>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="px-3 py-2 max-h-[70vh] overflow-y-auto">
          {fetchError && (
            <div className="text-red-500 text-[11px] mb-2">Fetch error: {fetchError}</div>
          )}

          <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1 mt-1">Server (.env)</div>
          {serverData ? (
            <>
              <Row label="JWT_SECRET set" value={String(serverData.jwt_secret_set)} ok={serverData.jwt_secret_set} />
              <Row label="JWT_SECRET preview" value={serverData.jwt_secret_preview ?? '(none)'} />
              <Row label="checkpoint_backend" value={serverData.checkpoint_backend} ok={serverData.checkpoint_backend === 'postgres'} />
              <Row label="DATABASE_URL set" value={String(serverData.database_url_set)} ok={serverData.database_url_set} />
              <Row label="user_count in DB" value={String(serverData.user_count)} />
            </>
          ) : (
            <div className="text-gray-400 text-[11px]">Loading…</div>
          )}

          <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1 mt-3">/auth/status response</div>
          <Row label="required" value={authStatus ? String(authStatus.required) : '…'} ok={authStatus?.required} />

          <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1 mt-3">Frontend state</div>
          <Row label="loading" value={String(loading)} />
          <Row label="authRequired" value={String(authRequired)} ok={authRequired} />
          <Row label="isAuthenticated" value={String(isAuthenticated)} ok={isAuthenticated} />
          <Row label="user.role" value={user?.role ?? '(null)'} />
          <Row label="user.name" value={user?.name ?? '(null)'} />
          <Row label="user.auth_enabled" value={user ? String((user as { auth_enabled?: boolean }).auth_enabled) : '(null)'} />

          <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1 mt-3">localStorage</div>
          <Row label="auth-token" value={storedToken ? storedToken.slice(0, 20) + '…' : '(none)'} ok={!!storedToken} />

          <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1 mt-3">/auth/me response</div>
          <pre className="text-[10px] text-gray-700 bg-gray-50 rounded p-1.5 overflow-x-auto whitespace-pre-wrap break-all">
            {JSON.stringify(meData, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
