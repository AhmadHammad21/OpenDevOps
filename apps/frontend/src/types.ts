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

export interface LlmBackendInfo {
  source: string;       // claude_code | anthropic | openrouter | openai | groq | custom | default
  model: string;
  display_name: string;
  provider: string;
  configured: boolean;
  detail: string;
}

export interface LlmProviderInfo {
  name: string;
  label: string;
  configured: boolean;
  models: string[];
  note: string;
}

export interface LlmPick {
  source: string;
  model: string;
}

export interface LlmSettings {
  providers: LlmProviderInfo[];
  current: LlmPick;
  backend: LlmBackendInfo;
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

export interface HistoryAlarm {
  alarm_name: string;
  session_count: number;
  total_lookups: number;
  last_seen: string | null;
}

export interface HistoryLambda {
  function_name: string;
  session_count: number;
  total_calls: number;
  last_seen: string | null;
}

export interface HistoryError {
  tool_name: string;
  error_snippet: string;
  count: number;
  last_seen: string | null;
}

export interface HistoryTrendPoint {
  date: string;
  count: number;
}

export interface HistoryStats {
  days: number;
  top_alarms: HistoryAlarm[];
  top_lambdas: HistoryLambda[];
  recurring_errors: HistoryError[];
  trend: HistoryTrendPoint[];
}

export interface SearchResult {
  id: string;
  title: string | null;
  last_active_at: string | null;
  model: string;
  snippet: string;
}

export interface Session {
  id: string;
  title: string | null;
  model: string;
  aws_region: string;
  last_active_at: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'user';
  created_at: string;
}

export interface MessageRecord {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  tool_calls: Array<{ tool_name: string; args: unknown; result: unknown }>;
  usage: Usage | null;
  created_at: string;
}

export interface AlertNotification {
  channel: string;
  status: 'delivered' | 'failed' | 'attempted';
  error: string | null;
  sent_at: string;
}

export interface Alert {
  id: string;
  service: string;
  error: string;
  resolution: string;
  evidence: string[];
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  status: 'completed' | 'failed';
  sns_sent: boolean;
  timestamp: string;
  session_id?: string;
  trigger_source?: 'poller' | 'event_consumer';
  dedup_key?: string;
  notifications?: AlertNotification[];
}

export interface ServiceStatus {
  name: string;
  status: 'healthy' | 'error' | 'unknown';
  last_check: string;
  last_error: string | null;
}
