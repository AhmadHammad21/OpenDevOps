import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Loader2, Terminal, Eye, EyeOff } from 'lucide-react';

const inp = 'w-full text-base text-gray-900 dark:text-white bg-gray-50 dark:bg-[#18181B] border border-gray-200 dark:border-[#27272A] rounded-xl px-4 py-3.5 outline-none focus:border-indigo-500 dark:focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/10 transition-all placeholder:text-gray-400 dark:placeholder:text-[#52525B]';

export default function InitPage() {
  const navigate = useNavigate();
  const [loading, setLoading]   = useState(false);
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw]     = useState(false);
  const [error, setError]       = useState('');

  useEffect(() => {
    fetch('/api/init/status')
      .then(r => r.json())
      .then(d => { if (d.has_user) navigate('/', { replace: true }); })
      .catch(() => {});
  }, [navigate]);

  const createUser = async () => {
    if (!username.trim() || !password.trim()) { setError('Both fields are required'); return; }
    setLoading(true); setError('');
    const r = await fetch('/api/init/create-user', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.trim(), password }),
    });
    const data = await r.json();
    setLoading(false);
    if (data.error) { setError(data.error); return; }
    navigate('/', { replace: true });
  };

  return (
    <div className="h-screen bg-white dark:bg-[#09090B] flex flex-col overflow-hidden">
      <header className="shrink-0 px-8 py-5 flex items-center gap-3">
        <div className="w-9 h-9 bg-gradient-to-br from-indigo-500 to-violet-600 rounded-xl flex items-center justify-center">
          <Terminal size={16} className="text-white" />
        </div>
        <span className="text-base font-semibold text-gray-900 dark:text-white">OpenDevOps</span>
      </header>

      <main className="flex-1 overflow-y-auto px-6 pb-16">
        <div className="w-full max-w-xl mx-auto pt-16">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight mb-3">Create your account</h1>
          <p className="text-lg text-gray-500 dark:text-[#A1A1AA] mb-10 leading-relaxed">
            Set up the admin credentials you'll use to access the dashboard.
          </p>

          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-[#D4D4D8] mb-2">Username</label>
              <input value={username} onChange={e => setUsername(e.target.value)} placeholder="admin" className={inp} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-[#D4D4D8] mb-2">Password</label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && createUser()}
                  placeholder="At least 6 characters"
                  className={inp + ' pr-11'}
                />
                <button type="button" onClick={() => setShowPw(p => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-white transition-colors">
                  {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
          </div>

          {error && <p className="mt-4 text-sm text-red-500">{error}</p>}

          <button onClick={createUser} disabled={loading}
            className="w-full mt-10 flex items-center justify-center gap-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 text-base font-semibold py-4 rounded-xl hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors disabled:opacity-50">
            {loading ? <Loader2 size={18} className="animate-spin" /> : <>Create account <ArrowRight size={16} /></>}
          </button>

          <p className="mt-6 text-center text-sm text-gray-400 dark:text-[#52525B]">
            AWS configuration can be set up in <span className="font-medium text-gray-600 dark:text-[#A1A1AA]">Settings → AWS Configuration</span> after login.
          </p>
        </div>
      </main>
    </div>
  );
}
