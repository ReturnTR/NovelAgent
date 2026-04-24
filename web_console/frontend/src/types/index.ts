export interface Agent {
  session_id: string;
  agent_name: string;
  agent_type: string;
  status: 'active' | 'inactive' | 'not_created';
  updated_at?: string;
}

export interface Message {
  id?: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  tool_calls?: ToolCall[];
  tool_results?: ToolResult[];
  reasoning_content?: string;
  tool_call_id?: string;
  index?: number;
}

export interface ToolCall {
  id?: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface ToolResult {
  tool_call_id: string;
  content: string;
}

export interface ChatStreamEvent {
  type: 'content' | 'tool_call' | 'tool_result' | 'reasoning' | 'error';
  content?: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  error?: string;
}

export interface CreateAgentPayload {
  agent_name: string;
  agent_type: string;
}