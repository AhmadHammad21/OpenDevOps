import { useState } from 'react';
import { fmtJson } from '../lib/utils';
import type { ToolCall } from '../types';

interface Props {
  calls: ToolCall[];
  streaming: boolean;
}

export default function ToolCallsBox({ calls, streaming }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="tool-calls-box">
      <div className="tc-header" onClick={() => setOpen(o => !o)}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z" />
        </svg>
        <span className="tc-count">{calls.length}</span>
        <span className="tc-label">tool calls</span>
        <span className={`tc-chevron${open ? ' open' : ''}`}>▼</span>
      </div>
      {open && (
        <div className="tc-body">
          {calls.map((tc, i) => (
            <div key={i} className="tc-item">
              <div className="tc-name">
                <span className="tc-dot" />
                {tc.tool}
              </div>
              <div className="tc-section">
                <div className="tc-section-label">Input</div>
                <div className="tc-json">{fmtJson(tc.args)}</div>
              </div>
              <div className="tc-section">
                <div className="tc-section-label">Output</div>
                <div className="tc-json">{fmtJson(tc.result)}</div>
              </div>
            </div>
          ))}
          {streaming && (
            <div className="tc-spinner">
              <div className="spinner-dots"><span /><span /><span /></div>
              <span>Running tools…</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
