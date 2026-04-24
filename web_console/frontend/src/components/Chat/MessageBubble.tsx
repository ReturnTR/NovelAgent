import { renderMarkdown } from '@/utils/markdown';

interface MessageBubbleProps {
  role: 'user' | 'assistant' | 'tool';
  content: string;
}

export function MessageBubble({ role, content }: MessageBubbleProps) {
  return (
    <div className="bubble">
      {role === 'tool' ? (
        <div className="tool-message-header">
          <span className="tool-icon">🔧</span>
          <span className="tool-message-title">工具执行结果</span>
          <span className="tool-toggle">▼</span>
        </div>
      ) : (
        <div dangerouslySetInnerHTML={{ __html: renderMarkdown(content || '思考中...') }} />
      )}
    </div>
  );
}