import { useRef, useEffect } from 'react';
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

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages, streamingContent]);

  const hasMessages = messages.length > 0 || streamingContent;

  return (
    <div className="chat-container" ref={containerRef}>
      {!hasMessages && <WelcomeMessage />}

      {messages.map((message, index) => (
        <div key={message.id || index} className={`message ${message.role}`}>
          <Avatar role={message.role as 'user' | 'assistant' | 'tool'} />
          <MessageBubble
            role={message.role as 'user' | 'assistant' | 'tool'}
            content={message.content}
          />
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