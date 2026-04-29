import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import StreamStatus from './StreamStatus';
import ToolCallsBox from './ToolCallsBox';
import UsageBox from './UsageBox';
import type { AgentMessage as AgentMsg } from '../types';

interface Props {
  message: AgentMsg;
}

export default function AgentMessage({ message }: Props) {
  const showMeta = message.toolCalls.length > 0 || message.streaming || message.usage != null;

  return (
    <div className="turn agent">
      {message.streaming && !message.content && (
        <StreamStatus label={message.streamLabel} />
      )}
      <div className="msg-row">
        <div className="avatar">🤖</div>
        <div className="bubble agent-bubble">
          {message.error ? (
            <span className="error-text">⚠ {message.error}</span>
          ) : message.content ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          ) : message.streaming ? null : (
            <span style={{ color: 'var(--text-faint)' }}>(no response)</span>
          )}
        </div>
      </div>
      {showMeta && (
        <div className="meta-row">
          <ToolCallsBox calls={message.toolCalls} streaming={message.streaming} />
          {message.usage && <UsageBox usage={message.usage} />}
        </div>
      )}
    </div>
  );
}
