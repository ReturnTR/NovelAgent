import type { Message } from '@/types';

const getBaseUrl = () => {
  const port = window.location.port;
  return port === '3000' ? '' : `http://${window.location.hostname}:8000`;
};

const API_URL = `${getBaseUrl()}/chat/stream`;

export interface StreamCallbacks {
  onContent: (content: string) => void;
  onToolCall: (toolCalls: Array<{ id?: string; name: string; arguments: Record<string, unknown> }>) => void;
  onToolResult: (toolCallId: string, content: string) => void;
  onReasoning: (content: string) => void;
  onError: (error: string) => void;
  onDone: () => void;
}

export async function streamChat(
  message: string,
  history: Message[],
  sessionId: string | null,
  callbacks: StreamCallbacks
): Promise<void> {
  const formattedHistory = history.map(msg => {
    const item: Record<string, unknown> = { role: msg.role };
    if (msg.role === 'user') {
      item.content = msg.content;
    } else if (msg.role === 'assistant') {
      item.content = msg.content;
      if (msg.tool_calls && msg.tool_calls.length > 0) {
        item.tool_calls = msg.tool_calls;
      }
    } else if (msg.role === 'tool') {
      item.content = msg.content;
      item.tool_call_id = msg.tool_call_id;
    }
    return item;
  });

  const response = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      history: formattedHistory,
      agent_id: sessionId,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        try {
          const parsed = JSON.parse(data);

          switch (parsed.type) {
            case 'content':
              callbacks.onContent(parsed.content || '');
              break;
            case 'tool_call':
              callbacks.onToolCall(parsed.tool_calls || []);
              break;
            case 'reasoning':
              callbacks.onReasoning(parsed.content || '');
              break;
            case 'tool_result':
              callbacks.onToolResult(parsed.tool_call_id, parsed.content);
              break;
            case 'error':
              callbacks.onError(parsed.error || 'Unknown error');
              break;
          }
        } catch (e) {
          console.error('Parse error:', e, data);
        }
      }
    }

    await new Promise(resolve => setTimeout(resolve, 0));
  }

  callbacks.onDone();
}