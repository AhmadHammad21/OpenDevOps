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
    <div className="flex flex-col items-start gap-1.5" style={{ animation: 'fadeIn 200ms ease' }}>
      {message.streaming && !message.content && (
        <StreamStatus label={message.streamLabel} />
      )}

      <div className="flex flex-row gap-2.5 items-start max-w-[720px]">
        <div className="w-[30px] h-[30px] bg-indigo-50 dark:bg-[#04103A] rounded-lg flex items-center justify-center text-sm shrink-0 mt-0.5 select-none">
          ⚡
        </div>
        <div className="px-3.5 py-2.5 rounded-[2px_10px_10px_10px] text-[16px] leading-relaxed break-words max-w-[660px] bg-gray-50 dark:bg-[#0A0C10] border border-gray-200 dark:border-[#1E222B] text-gray-900 dark:text-[#CBD5E1]">
          {message.error ? (
            <span className="text-red-500 flex items-center gap-1.5">
              <span>⚠</span> {message.error}
            </span>
          ) : message.streaming && !message.content ? (
            <div className="flex gap-1">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-indigo-500 mx-px" style={{ animation: 'dot-bounce 1s infinite' }} />
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-indigo-500 mx-px" style={{ animation: 'dot-bounce 1s 0.15s infinite' }} />
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-indigo-500 mx-px" style={{ animation: 'dot-bounce 1s 0.3s infinite' }} />
            </div>
          ) : message.content ? (
            <div className="prose-chat">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          ) : !message.streaming ? (
            <span className="text-gray-400 dark:text-[#64748B]">(no response)</span>
          ) : null}
        </div>
      </div>

      {showMeta && (
        <div className="flex items-start gap-2 ml-10 flex-wrap">
          <ToolCallsBox calls={message.toolCalls} streaming={message.streaming} />
          {message.usage && <UsageBox usage={message.usage} />}
        </div>
      )}
    </div>
  );
}
