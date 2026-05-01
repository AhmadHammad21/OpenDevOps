import { Link } from 'react-router-dom';
import { ArrowLeft, ExternalLink } from 'lucide-react';

const ENV_VARS = [
  { key: 'OPENROUTER_API_KEY',   desc: 'OpenRouter API key (sk-or-…)' },
  { key: 'OPENROUTER_MODEL',     desc: 'Model ID, e.g. anthropic/claude-3.5-sonnet' },
  { key: 'OPENROUTER_BASE_URL',  desc: 'Defaults to https://openrouter.ai/api/v1' },
  { key: 'AWS_REGION',           desc: 'AWS region, e.g. us-east-1' },
  { key: 'AWS_PROFILE',          desc: 'Optional IAM profile name' },
  { key: 'MAX_TOOL_CALLS',       desc: 'Hard cap on tool calls per investigation (default 20)' },
  { key: 'DATABASE_URL',         desc: 'Postgres connection string for session storage' },
  { key: 'LOG_LEVEL',            desc: 'INFO / DEBUG / WARNING' },
];

export default function SettingsPage() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-700 bg-gray-800 flex items-center gap-4 shrink-0">
        <Link
          to="/"
          className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-100 transition-colors"
        >
          <ArrowLeft size={14} />
          Back
        </Link>
        <h1 className="text-sm font-semibold text-gray-100">Settings</h1>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-xl">
          <p className="text-sm text-gray-400 mb-6 leading-relaxed">
            Configuration is managed via environment variables in your{' '}
            <code className="text-emerald-400 bg-gray-800 border border-gray-700 rounded px-1.5 py-px text-xs font-mono">.env</code>{' '}
            file at the project root. Restart the server after changes.
          </p>

          <div className="border border-gray-700 rounded-lg overflow-hidden">
            <div className="px-4 py-2 bg-gray-800 border-b border-gray-700">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-widest">Environment Variables</span>
            </div>
            <div className="divide-y divide-gray-700/60">
              {ENV_VARS.map(v => (
                <div key={v.key} className="px-4 py-3 flex flex-col gap-0.5 hover:bg-gray-800/40 transition-colors">
                  <code className="text-sm font-mono text-amber-400 font-semibold">{v.key}</code>
                  <span className="text-xs text-gray-500">{v.desc}</span>
                </div>
              ))}
            </div>
          </div>

          <a
            href="https://openrouter.ai/models"
            target="_blank"
            rel="noreferrer"
            className="mt-6 inline-flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300 transition-colors"
          >
            Browse available models on OpenRouter
            <ExternalLink size={13} />
          </a>
        </div>
      </div>
    </div>
  );
}
