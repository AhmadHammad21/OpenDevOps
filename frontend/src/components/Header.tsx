import { History, LogOut, Settings } from 'lucide-react';
import { Link, useMatch } from 'react-router-dom';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';

function DarkToggle() {
  const { theme, toggle } = useTheme();
  const dark = theme === 'dark';
  return (
    <button
      onClick={toggle}
      title="Toggle dark mode"
      className="relative w-9 h-5 rounded-full shrink-0 transition-colors duration-200"
      style={{ background: dark ? '#818CF8' : '#E5E7EB' }}
    >
      <span
        className="absolute top-[2px] w-4 h-4 rounded-full bg-white flex items-center justify-center text-[9px] transition-all duration-200"
        style={{ left: dark ? '18px' : '2px' }}
      >
        {dark ? '🌙' : '☀️'}
      </span>
    </button>
  );
}

export default function Header() {
  const match = useMatch('/chat/:sessionId');
  const sessionId = match?.params.sessionId;
  const { authRequired, logout, user } = useAuth();

  return (
    <header className="px-5 py-2.5 border-b border-gray-200 dark:border-[#27272F] bg-white dark:bg-[#18181C] flex items-center justify-between shrink-0">
      <div className="flex items-center gap-2.5">
        <div className="w-[26px] h-[26px] bg-indigo-500 rounded-[7px] flex items-center justify-center shrink-0">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
          </svg>
        </div>
        <span className="text-[13px] font-semibold text-gray-900 dark:text-[#F1F5F9]">OpenDevOps</span>
        <span className="text-[10px] text-indigo-500 dark:text-[#818CF8] bg-indigo-50 dark:bg-[#1E1B4B] border border-indigo-200 dark:border-[#3730A3] rounded px-1.5 py-px font-semibold tracking-[0.04em]">
          BETA
        </span>
      </div>

      <div className="flex items-center gap-2.5">
        {sessionId && (
          <span className="text-xs text-gray-400 dark:text-[#64748B] font-mono">{sessionId.slice(0, 8)}</span>
        )}
        <Link to="/history" className="text-gray-400 dark:text-[#64748B] hover:text-gray-600 dark:hover:text-[#94A3B8] transition-colors p-0.5" title="Session history">
          <History size={15} />
        </Link>
        <Link to="/settings" className="text-gray-400 dark:text-[#64748B] hover:text-gray-600 dark:hover:text-[#94A3B8] transition-colors p-0.5" title="Settings">
          <Settings size={15} />
        </Link>
        <DarkToggle />
        {authRequired && (
          <button
            onClick={logout}
            title={`Sign out${user?.id ? '' : ''}`}
            className="text-gray-400 dark:text-[#64748B] hover:text-red-500 dark:hover:text-[#F87171] transition-colors p-0.5"
          >
            <LogOut size={15} />
          </button>
        )}
      </div>
    </header>
  );
}
