import { History, Settings } from 'lucide-react';
import { Link, useMatch } from 'react-router-dom';

export default function Header() {
  const match = useMatch('/chat/:sessionId');
  const sessionId = match?.params.sessionId;

  return (
    <header className="px-6 py-3 border-b border-gray-700 bg-gray-800 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 bg-gradient-to-br from-emerald-500 to-emerald-700 rounded-lg flex items-center justify-center text-sm select-none">
          ⚡
        </div>
        <h1 className="text-sm font-semibold text-gray-100">OpenDevOps Agent</h1>
        <span className="text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/25 rounded px-1.5 py-px font-medium">
          BETA
        </span>
      </div>

      <div className="flex items-center gap-3">
        {sessionId && (
          <span className="text-xs text-gray-500 font-mono">{sessionId.slice(0, 8)}</span>
        )}
        <Link to="/history"  className="text-gray-500 hover:text-gray-300 transition-colors" title="Session history">
          <History size={16} />
        </Link>
        <Link to="/settings" className="text-gray-500 hover:text-gray-300 transition-colors" title="Settings">
          <Settings size={16} />
        </Link>
      </div>
    </header>
  );
}
