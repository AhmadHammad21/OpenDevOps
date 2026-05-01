export interface ToolCall {
  tool: string;
  args: unknown;
  result: unknown;
}

export interface Usage {
  latency_ms: number;
  model: string;
  input_tokens?: number;
  output_tokens?: number;
  cost_usd?: number;
}

export interface UserMessage {
  id: string;
  role: 'user';
  content: string;
}

export interface AgentMessage {
  id: string;
  role: 'agent';
  content: string;
  toolCalls: ToolCall[];
  usage: Usage | null;
  streaming: boolean;
  streamLabel: string;
  error?: string;
}

export type Message = UserMessage | AgentMessage;

export interface Session {
  id: string;
  title: string | null;
  model: string;
  aws_region: string;
  last_active_at: string;
}

export interface MessageRecord {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  tool_calls: Array<{ tool_name: string; args: unknown; result: unknown }>;
  usage: Usage | null;
  created_at: string;
}
