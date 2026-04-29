import { useState } from 'react';
import { calcCost, fmtCost, fmtTok } from '../lib/utils';
import type { Usage } from '../types';

interface Props {
  usage: Usage;
}

export default function UsageBox({ usage }: Props) {
  const [open, setOpen] = useState(false);
  const secs = ((usage.latency_ms ?? 0) / 1000).toFixed(1) + 's';
  const cost = calcCost(usage.model, usage.input_tokens, usage.output_tokens);

  return (
    <div className="usage-box">
      <div className="usage-header" onClick={() => setOpen(o => !o)}>
        <span className="uh-icon">⚡</span>
        <span className="uh-summary">
          <b>{secs}</b>
          {cost && <> · <b>{fmtCost(cost.total)}</b></>}
        </span>
        <span className={`usage-chevron${open ? ' open' : ''}`}>▼</span>
      </div>
      {open && (
        <div className="usage-body">
          <div className="usage-row">
            <span className="uk">Latency</span>
            <span className="uv">{secs}</span>
          </div>
          <div className="usage-row">
            <span className="uk">Input tokens</span>
            <span className="uv">
              {fmtTok(usage.input_tokens)}
              {cost && <span className="tok-cost"> ({fmtCost(cost.inCost)})</span>}
            </span>
          </div>
          <div className="usage-row">
            <span className="uk">Output tokens</span>
            <span className="uv">
              {fmtTok(usage.output_tokens)}
              {cost && <span className="tok-cost"> ({fmtCost(cost.outCost)})</span>}
            </span>
          </div>
          {cost && (
            <div className="usage-row usage-total">
              <span className="uk">Total cost</span>
              <span className="uv">{fmtCost(cost.total)}</span>
            </div>
          )}
          <div className="usage-model">{usage.model}</div>
        </div>
      )}
    </div>
  );
}
