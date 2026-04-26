import { useState } from 'react';

interface ReasoningContentProps {
  content: string;
}

export function ReasoningContent({ content }: ReasoningContentProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className={`reasoning-content ${isExpanded ? 'expanded' : ''}`}>
      <div className="reasoning-header" onClick={() => setIsExpanded(!isExpanded)}>
        <span className="reasoning-icon">🧠</span>
        <span className="reasoning-title">思考</span>
        <span className="reasoning-toggle">{isExpanded ? '▲ 收起' : '▼ 展开'}</span>
      </div>
      <div className="reasoning-body">
        <pre>{content}</pre>
      </div>
    </div>
  );
}