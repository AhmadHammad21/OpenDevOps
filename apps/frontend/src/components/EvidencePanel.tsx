import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { X, Copy, ExternalLink, Download, FlaskConical, Wrench, Terminal } from 'lucide-react';
import { fetchEvidence } from '../lib/api';
import { cn, fmtJson } from '../lib/utils';
import type { EvidencePack, EvidenceToolCall } from '../types';

interface Props {
  sessionId: string;
  onClose: () => void;
}

const CONFIDENCE_STYLES: Record<string, string> = {
  HIGH: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
  MEDIUM: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400',
  LOW: 'bg-gray-100 text-gray-600 dark:bg-gray-500/15 dark:text-gray-400',
};

function copy(text: string, label = 'Copied') {
  navigator.clipboard.writeText(text).then(
    () => toast.success(label),
    () => toast.error('Copy failed'),
  );
}

function ToolCallCard({ tc }: { tc: EvidenceToolCall }) {
  return (
    <div
      id={`evidence-tc-${tc.id}`}
      className="border border-gray-200 dark:border-[#1E222B] rounded-[7px] overflow-hidden scroll-mt-4"
    >
      <div className="flex items-center gap-2 px-2.5 py-1.5 bg-gray-100 dark:bg-[#15181F]">
        <span className="w-[5px] h-[5px] rounded-full bg-indigo-500 dark:bg-[#00A3FF] shrink-0" />
        <span className="font-mono font-semibold text-[11px] text-gray-800 dark:text-[#E4E1EA]">{tc.tool}</span>
        <span className="text-[10px] text-gray-400 dark:text-[#64748B]">{tc.service}</span>
        {tc.error && <span className="text-[10px] text-red-500">error</span>}
        <div className="ml-auto flex items-center gap-1.5">
          {tc.console_url && (
            <a
              href={tc.console_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-[11px] text-indigo-600 dark:text-[#00A3FF] hover:underline"
            >
              <ExternalLink size={11} /> Console
            </a>
          )}
        </div>
      </div>

      {tc.command != null && (
        <div className="px-2.5 pt-2 flex flex-col gap-1">
          <div className="flex items-center gap-1.5">
            <Terminal size={11} className="text-gray-400 dark:text-[#64748B]" />
            <span className="text-[10px] uppercase tracking-[0.07em] font-semibold text-gray-400 dark:text-[#64748B]">
              Exact query / command
            </span>
            <button
              onClick={() => copy(tc.command ?? '', 'Command copied')}
              className="ml-auto text-gray-400 hover:text-indigo-500 dark:hover:text-[#00A3FF]"
              title="Copy command"
            >
              <Copy size={11} />
            </button>
          </div>
          <pre className="font-mono text-[11px] bg-gray-900 text-gray-100 dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-[5px] px-2.5 py-1.5 overflow-auto max-h-28 leading-snug whitespace-pre-wrap">
            {tc.command}
          </pre>
        </div>
      )}

      <div className="px-2.5 py-2 flex flex-col gap-1">
        <span className="text-[10px] uppercase tracking-[0.07em] font-semibold text-gray-400 dark:text-[#64748B]">Input</span>
        <pre className="font-mono text-[11px] bg-gray-50 dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-[5px] px-2.5 py-1.5 text-gray-500 dark:text-[#94A3B8] overflow-auto max-h-24 leading-snug whitespace-pre">
          {fmtJson(tc.args)}
        </pre>
        {tc.result != null && (
          <>
            <span className="text-[10px] uppercase tracking-[0.07em] font-semibold text-gray-400 dark:text-[#64748B]">Output</span>
            <pre className="font-mono text-[11px] bg-gray-50 dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] rounded-[5px] px-2.5 py-1.5 text-gray-500 dark:text-[#94A3B8] overflow-auto max-h-32 leading-snug whitespace-pre">
              {fmtJson(tc.result)}
            </pre>
          </>
        )}
      </div>
    </div>
  );
}

export default function EvidencePanel({ sessionId, onClose }: Props) {
  const [pack, setPack] = useState<EvidencePack | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let live = true;
    fetchEvidence(sessionId)
      .then(p => { if (live) setPack(p); })
      .catch(() => { if (live) setError(true); });
    return () => { live = false; };
  }, [sessionId]);

  const exportJson = () => {
    if (!pack) return;
    const blob = new Blob([JSON.stringify(pack, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `evidence-${sessionId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const tcById = (id: string | null): EvidenceToolCall | undefined =>
    id ? pack?.tool_calls.find(t => t.id === id) : undefined;

  const scrollToCall = (id: string) => {
    const el = document.getElementById(`evidence-tc-${id}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('ring-2', 'ring-indigo-400');
      setTimeout(() => el.classList.remove('ring-2', 'ring-indigo-400'), 1200);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-[560px] h-full bg-white dark:bg-[#0A0C10] border-l border-gray-200 dark:border-[#1E222B] flex flex-col shadow-xl">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-[#1E222B] flex items-center gap-2 shrink-0">
          <FlaskConical size={15} className="text-indigo-500 dark:text-[#00A3FF]" />
          <span className="text-[14px] font-semibold text-gray-900 dark:text-[#E4E1EA]">Evidence pack</span>
          {pack?.aws_region && (
            <span className="text-[11px] text-gray-400 dark:text-[#64748B] font-mono">{pack.aws_region}</span>
          )}
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={exportJson}
              disabled={!pack}
              className="flex items-center gap-1.5 px-2.5 py-[5px] text-[12px] font-medium rounded-[5px] border border-gray-200 dark:border-[#1E222B] text-gray-700 dark:text-[#CBD5E1] hover:bg-gray-100 dark:hover:bg-[#15181F] disabled:opacity-40"
            >
              <Download size={12} /> JSON
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-700 dark:hover:text-[#E4E1EA]">
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-5">
          {error && <p className="text-[13px] text-red-500">Failed to load evidence.</p>}
          {!error && !pack && <p className="text-[13px] text-gray-400 dark:text-[#64748B]">Loading…</p>}

          {pack && !pack.has_conclusion && (
            <p className="text-[13px] text-gray-400 dark:text-[#64748B]">
              No completed investigation in this session yet — the evidence pack appears once the agent
              submits its conclusion.
            </p>
          )}

          {pack && pack.has_conclusion && (
            <>
              {/* Hypotheses */}
              <section className="flex flex-col gap-3">
                <h3 className="text-[12px] uppercase tracking-[0.07em] font-semibold text-gray-400 dark:text-[#64748B]">
                  Ranked hypotheses
                </h3>
                {pack.hypotheses.map((h, i) => (
                  <div key={i} className="border border-gray-200 dark:border-[#1E222B] rounded-[8px] p-3 flex flex-col gap-2">
                    <div className="flex items-start gap-2">
                      <span className="text-[12px] font-mono text-gray-400 dark:text-[#64748B] mt-0.5">#{i + 1}</span>
                      <p className="text-[14px] font-medium text-gray-900 dark:text-[#E4E1EA] flex-1">{h.hypothesis}</p>
                      <span className={cn('text-[10px] font-semibold px-1.5 py-0.5 rounded', CONFIDENCE_STYLES[h.confidence] ?? CONFIDENCE_STYLES.LOW)}>
                        {h.confidence}
                      </span>
                    </div>
                    {h.evidence.length > 0 && (
                      <ul className="flex flex-col gap-1.5 pl-1">
                        {h.evidence.map((ev, j) => {
                          const tc = tcById(ev.tool_call_id);
                          return (
                            <li key={j} className="text-[13px] text-gray-700 dark:text-[#CBD5E1] flex flex-col gap-0.5">
                              <span className="leading-snug">• {ev.text}</span>
                              {tc && (
                                <button
                                  onClick={() => scrollToCall(tc.id)}
                                  className="self-start flex items-center gap-1 text-[11px] text-indigo-600 dark:text-[#00A3FF] hover:underline ml-3"
                                >
                                  <Wrench size={10} /> from {tc.tool}
                                </button>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                ))}
              </section>

              {/* Replay */}
              <section className="flex flex-col gap-2">
                <h3 className="text-[12px] uppercase tracking-[0.07em] font-semibold text-gray-400 dark:text-[#64748B]">
                  Replay — {pack.tool_calls.length} tool call{pack.tool_calls.length === 1 ? '' : 's'}
                </h3>
                {pack.tool_calls.map(tc => <ToolCallCard key={tc.id} tc={tc} />)}
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
