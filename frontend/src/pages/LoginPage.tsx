import { useState, type FormEvent } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

type Mode = 'login' | 'register';

export default function LoginPage() {
  const { login, register, isAuthenticated, authRequired } = useAuth();
  const [mode, setMode]       = useState<Mode>('login');
  const [email, setEmail]     = useState('');
  const [name, setName]       = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]     = useState('');
  const [busy, setBusy]       = useState(false);

  if (!authRequired || isAuthenticated) return <Navigate to="/" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        if (!name.trim()) { setError('Name is required'); setBusy(false); return; }
        await register(email, name, password);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex w-full h-screen items-center justify-center bg-gray-50 dark:bg-[#0F0F12]">
      <div className="w-full max-w-[360px] mx-4">
        {/* Logo / title */}
        <div className="text-center mb-8">
          <div className="text-[22px] font-bold text-gray-900 dark:text-[#F1F5F9] tracking-[-0.02em]">
            OpenDevOps
          </div>
          <div className="text-[13px] text-gray-500 dark:text-[#94A3B8] mt-1">
            AWS incident investigation agent
          </div>
        </div>

        <div className="bg-white dark:bg-[#18181C] border border-gray-200 dark:border-[#27272F] rounded-xl shadow-[0_2px_8px_rgba(0,0,0,0.06)] overflow-hidden">
          {/* Mode tabs */}
          <div className="flex border-b border-gray-200 dark:border-[#27272F]">
            {(['login', 'register'] as Mode[]).map(m => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(''); }}
                className={`flex-1 py-3 text-[13px] font-medium transition-colors ${
                  mode === m
                    ? 'text-indigo-500 dark:text-[#818CF8] border-b-2 border-indigo-500 dark:border-[#818CF8] -mb-px'
                    : 'text-gray-500 dark:text-[#94A3B8] hover:text-gray-700 dark:hover:text-[#F1F5F9]'
                }`}
              >
                {m === 'login' ? 'Sign in' : 'Register'}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="p-6 flex flex-col gap-4">
            {mode === 'register' && (
              <div>
                <label className="block text-[12px] font-medium text-gray-700 dark:text-[#CBD5E1] mb-1.5">
                  Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Your name"
                  required
                  className="w-full text-[13px] text-gray-900 dark:text-[#F1F5F9] bg-white dark:bg-[#18181C] border border-gray-300 dark:border-[#3F3F47] rounded-[6px] px-3 py-2 outline-none focus:border-indigo-500 dark:focus:border-[#818CF8] focus:shadow-[0_0_0_3px_rgba(99,102,241,0.12)] dark:focus:shadow-[0_0_0_3px_rgba(129,140,248,0.12)] transition-all"
                />
              </div>
            )}
            <div>
              <label className="block text-[12px] font-medium text-gray-700 dark:text-[#CBD5E1] mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="w-full text-[13px] text-gray-900 dark:text-[#F1F5F9] bg-white dark:bg-[#18181C] border border-gray-300 dark:border-[#3F3F47] rounded-[6px] px-3 py-2 outline-none focus:border-indigo-500 dark:focus:border-[#818CF8] focus:shadow-[0_0_0_3px_rgba(99,102,241,0.12)] dark:focus:shadow-[0_0_0_3px_rgba(129,140,248,0.12)] transition-all"
              />
            </div>
            <div>
              <label className="block text-[12px] font-medium text-gray-700 dark:text-[#CBD5E1] mb-1.5">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={8}
                className="w-full text-[13px] text-gray-900 dark:text-[#F1F5F9] bg-white dark:bg-[#18181C] border border-gray-300 dark:border-[#3F3F47] rounded-[6px] px-3 py-2 outline-none focus:border-indigo-500 dark:focus:border-[#818CF8] focus:shadow-[0_0_0_3px_rgba(99,102,241,0.12)] dark:focus:shadow-[0_0_0_3px_rgba(129,140,248,0.12)] transition-all"
              />
            </div>

            {error && (
              <div className="text-[12px] text-red-500 dark:text-[#F87171] bg-red-50 dark:bg-[#2D1B1B] border border-red-200 dark:border-[#4A2020] rounded-[6px] px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full py-2.5 text-[13px] font-medium text-white bg-indigo-500 dark:bg-[#818CF8] hover:bg-indigo-600 dark:hover:bg-[#6366F1] disabled:opacity-50 rounded-[6px] transition-colors shadow-[0_1px_2px_rgba(99,102,241,0.25)]"
            >
              {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>

            {mode === 'register' && (
              <p className="text-[11px] text-gray-400 dark:text-[#64748B] text-center leading-relaxed">
                First account created becomes the admin. Configure SNS, SQS, and AWS permissions in <span className="font-medium text-gray-500 dark:text-[#94A3B8]">Settings → AWS Configuration</span> after login.
              </p>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
