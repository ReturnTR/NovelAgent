import { useState } from 'react';

interface ToolCallUIProps {
  toolCalls: Array<{
    id?: string;
    name: string;
    arguments: Record<string, unknown>;
  }>;
  toolResults: Array<{
    tool_call_id: string;
    content: string;
  }>;
}

export function ToolCallUI({ toolCalls, toolResults }: ToolCallUIProps) {
  const [expandedResults, setExpandedResults] = useState<Set<string>>(new Set());

  const toggleResult = (toolCallId: string) => {
    setExpandedResults((prev) => {
      const next = new Set(prev);
      if (next.has(toolCallId)) {
        next.delete(toolCallId);
      } else {
        next.add(toolCallId);
      }
      return next;
    });
  };

  return (
    <div className="tool-calls-container">
      {toolCalls.map((toolCall, index) => {
        const toolId = toolCall.id || `tool-${index}`;
        const result = toolResults.find((r) => r.tool_call_id === toolId);
        const isExpanded = expandedResults.has(toolId);
        const hasResult = !!result;

        return (
          <div key={toolId} className="tool-call-item" id={`tool-call-${toolId}`}>
            <div className="tool-call-header">
              <span className="tool-icon">🔧</span>
              <span className="tool-name">{toolCall.name}</span>
              <span className={`tool-status ${hasResult ? 'completed' : ''}`}>
                {hasResult ? '已完成' : '执行中...'}
              </span>
            </div>
            <div className="tool-call-args">
              <pre>{JSON.stringify(toolCall.arguments, null, 2)}</pre>
            </div>
            {result && (
              <div className="tool-call-result">
                <div className="tool-result-toggle" onClick={() => toggleResult(toolId)}>
                  {isExpanded ? '▲ 隐藏结果' : '▼ 查看结果'}
                </div>
                {isExpanded && (
                  <div className="tool-result-content">
                    <pre>{(() => {
                      try {
                        const parsed = JSON.parse(result.content);
                        return JSON.stringify(parsed, null, 2);
                      } catch {
                        return result.content;
                      }
                    })()}</pre>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}