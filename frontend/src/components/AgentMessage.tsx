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
    <div className="flex flex-col items-start gap-1.5">
      {message.streaming && !message.content && (
        <StreamStatus label={message.streamLabel} />
      )}

      <div className="flex flex-row gap-2.5 items-start max-w-[780px]">
        <div className="w-[30px] h-[30px] rounded-lg flex items-center justify-center text-sm shrink-0 mt-0.5 bg-emerald-900/60 select-none">
          🤖
        </div>
        <div className="px-3.5 py-2.5 rounded-xl rounded-bl-sm text-sm leading-relaxed break-words max-w-[680px] bg-gray-800 border border-gray-700">
          {message.error ? (
            <span className="text-red-400 flex items-center gap-1.5">
              <span>⚠</span> {message.error}
            </span>
          ) : message.content ? (
            <div className="prose-chat">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          ) : message.streaming ? null : (
            <span className="text-gray-600">(no response)</span>
          )}
        </div>
      </div>

      {showMeta && (
        <div className="flex items-start gap-2 ml-10">
          <ToolCallsBox calls={message.toolCalls} streaming={message.streaming} />
          {message.usage && <UsageBox usage={message.usage} />}
        </div>
      )}
    </div>
  );
}
