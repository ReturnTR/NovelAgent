import { AgentItem } from './AgentItem';
import type { Agent } from '@/types';

interface AgentListProps {
  agents: Agent[];
  currentSessionId: string | null;
  loading: boolean;
  onSelectAgent: (sessionId: string) => void;
  onUpdateName: (sessionId: string, name: string) => Promise<boolean>;
  onSuspendAgent: (sessionId: string, name: string) => void;
  onResumeAgent: (sessionId: string, name: string) => void;
  onDeleteAgent: (sessionId: string, name: string) => void;
}

export function AgentList({
  agents,
  currentSessionId,
  loading,
  onSelectAgent,
  onUpdateName,
  onSuspendAgent,
  onResumeAgent,
  onDeleteAgent,
}: AgentListProps) {
  if (loading) {
    return <div className="loading">加载中...</div>;
  }

  if (agents.length === 0) {
    return <div className="error">暂无Agent</div>;
  }

  return (
    <div className="agent-list">
      {agents.map((agent) => (
        <AgentItem
          key={agent.session_id}
          agent={agent}
          isActive={agent.session_id === currentSessionId}
          onSelect={onSelectAgent}
          onUpdateName={onUpdateName}
          onSuspend={onSuspendAgent}
          onResume={onResumeAgent}
          onDelete={onDeleteAgent}
        />
      ))}
    </div>
  );
}