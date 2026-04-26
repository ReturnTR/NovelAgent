import { useRef, useEffect, useState } from 'react';
import type { Message } from '@/types';
import { Avatar } from '@/components/common';
import { MessageBubble } from './MessageBubble';
import { ToolCallUI } from './ToolCallUI';
import { ReasoningContent } from './ReasoningContent';
import { WelcomeMessage } from './WelcomeMessage';

interface ChatContainerProps {
  messages: Message[];
  currentToolCalls: Array<{ id?: string; name: string; arguments: Record<string, unknown> }>;
  currentToolResults: Array<{ tool_call_id: string; content: string }>;
  currentReasoning: string;
  streamingContent: string;
  isStreaming: boolean;
  onDeleteMessage?: (index: number) => void;
}

export function ChatContainer({
  messages,
  currentToolCalls,
  currentToolResults,
  currentReasoning,
  streamingContent,
  isStreaming,
  onDeleteMessage,
}: ChatContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [expandedA2A, setExpandedA2A] = useState<Record<number, boolean>>({});

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages, streamingContent]);

  const hasMessages = messages.length > 0 || streamingContent;

  const toggleExpanded = (index: number) => {
    setExpandedA2A(prev => ({ ...prev, [index]: !prev[index] }));
  };

  const renderA2AMessage = (message: Message, index: number) => {
    // agent_request 默认展开，agent_response 默认折叠
    const isExpanded = message.type === 'agent_response'
      ? (expandedA2A[index] ?? false)
      : true;

    if (message.type === 'agent_request') {
      return (
        <div className="a2a-message a2a-request">
          <div className="a2a-header" onClick={() => toggleExpanded(index)}>
            <span className="a2a-icon">📥</span>
            <span className="a2a-label">来自 {message.source_agent_id} 的请求</span>
            <span className="a2a-toggle">{isExpanded ? '▲' : '▼'}</span>
          </div>
          {isExpanded && (
            <div className="a2a-content">
              <MessageBubble role="user" content={message.content} />
            </div>
          )}
        </div>
      );
    }

    if (message.type === 'agent_response') {
      return (
        <div className="a2a-message a2a-response">
          <div className="a2a-header" onClick={() => toggleExpanded(index)}>
            <span className="a2a-icon">📤</span>
            <span className="a2a-label">发送给 {message.target_agent_id}</span>
            <span className="a2a-toggle">{isExpanded ? '▲' : '▼'}</span>
          </div>
          {isExpanded && (
            <div className="a2a-content">
              <MessageBubble role="assistant" content={message.content} />
            </div>
          )}
        </div>
      );
    }

    return null;
  };

  return (
    <div className="chat-container" ref={containerRef}>
      {!hasMessages && <WelcomeMessage />}

      {messages.map((message, index) => (
        <div key={message.id || index} className={`message ${message.role}`}>
          <Avatar role={message.role as 'user' | 'assistant' | 'tool'} />
          <div className="message-content">
            {/* Render A2A messages (agent_request/agent_response) with collapsible header */}
            {(message.type === 'agent_request' || message.type === 'agent_response') && (
              renderA2AMessage(message, index)
            )}

            {/* Render standard messages */}
            {message.type !== 'agent_request' && message.type !== 'agent_response' && (
              <>
                {/* Render reasoning_content if present (for assistant messages with empty content) */}
                {message.role === 'assistant' && message.reasoning_content && !message.content && (
                  <ReasoningContent content={message.reasoning_content} />
                )}

                {/* Render tool_calls if present */}
                {message.role === 'assistant' && message.tool_calls && message.tool_calls.length > 0 && (
                  <div className="bubble">
                    <ToolCallUI
                      toolCalls={message.tool_calls}
                      toolResults={message.tool_results || []}
                    />
                  </div>
                )}

                {/* Render tool result if this is a tool message */}
                {message.role === 'tool' && message.content && (
                  <div className="tool-result-display">
                    <pre>{(() => {
                      try {
                        const parsed = JSON.parse(message.content);
                        return JSON.stringify(parsed, null, 2);
                      } catch {
                        return message.content;
                      }
                    })()}</pre>
                  </div>
                )}

                {/* Render content for user messages or assistant messages with actual content */}
                {(message.role === 'user' || (message.role === 'assistant' && message.content)) && (
                  <MessageBubble
                    role={message.role as 'user' | 'assistant' | 'tool'}
                    content={message.content}
                    reasoning_content={message.reasoning_content}
                  />
                )}
              </>
            )}
          </div>
          <button
            className="delete-message-btn"
            onClick={() => onDeleteMessage?.(index)}
            title="删除此消息"
          >
            🗑️
          </button>
        </div>
      ))}

      {isStreaming && streamingContent && (
        <div className="message assistant">
          <Avatar role="assistant" />
          <MessageBubble role="assistant" content={streamingContent} />
        </div>
      )}

      {isStreaming && currentReasoning && <ReasoningContent content={currentReasoning} />}

      {isStreaming && currentToolCalls.length > 0 && (
        <div className="message assistant">
          <Avatar role="assistant" />
          <div className="bubble">
            <ToolCallUI toolCalls={currentToolCalls} toolResults={currentToolResults} />
          </div>
        </div>
      )}
    </div>
  );
}