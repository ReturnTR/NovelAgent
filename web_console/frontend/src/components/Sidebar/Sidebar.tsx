import { useState, useRef, useEffect } from 'react';
import { AgentList } from './AgentList';
import { CreateAgentModal } from './CreateAgentModal';
import { useAgentsStore } from '@/features/agents/agentsStore';

interface SidebarProps {
  currentSessionId: string | null;
  onSelectAgent: (sessionId: string) => void;
  onShowNotification: (message: string, type: 'success' | 'error' | 'warning' | 'info') => void;
}

export function Sidebar({ currentSessionId, onSelectAgent, onShowNotification }: SidebarProps) {
  const [showCreateModal, setShowCreateModal] = useState(false);

  const {
    agents,
    loading,
    fetchAgents,
    createAgent,
    updateAgentName,
    suspendAgent,
    resumeAgent,
    deleteAgent,
  } = useAgentsStore();

  const resizeRef = useRef<HTMLDivElement>(null);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const isResizingRef = useRef(false);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingRef.current || !sidebarRef.current) return;

      const container = sidebarRef.current.parentElement;
      if (!container) return;

      const containerRect = container.getBoundingClientRect();
      const newWidth = e.clientX - containerRect.left;

      if (newWidth > 150 && newWidth < containerRect.width - 200) {
        sidebarRef.current.style.width = `${newWidth}px`;
      }
    };

    const handleMouseUp = () => {
      if (isResizingRef.current) {
        isResizingRef.current = false;
        resizeRef.current?.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  const handleMouseDown = () => {
    isResizingRef.current = true;
    resizeRef.current?.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  const handleCreateAgent = async (name: string, type: string) => {
    const success = await createAgent(name, type);
    if (success) {
      onShowNotification(`${name} 创建成功`, 'success');
      return true;
    } else {
      onShowNotification(`${name} 创建失败`, 'error');
      return false;
    }
  };

  const handleDeleteAgent = async (sessionId: string, agentName: string) => {
    if (!confirm(`确定要删除 ${agentName} 吗？此操作不可恢复！`)) return;

    const success = await deleteAgent(sessionId);
    if (success) {
      onShowNotification(`${agentName} 已删除`, 'info');
      if (currentSessionId === sessionId) {
        onSelectAgent('');
      }
    } else {
      onShowNotification(`${agentName} 删除失败`, 'error');
    }
  };

  const handleSuspendAgent = async (sessionId: string, agentName: string) => {
    const success = await suspendAgent(sessionId);
    if (success) {
      onShowNotification(`${agentName} 已挂起`, 'info');
    } else {
      onShowNotification(`${agentName} 挂起失败`, 'error');
    }
  };

  const handleResumeAgent = async (sessionId: string, agentName: string) => {
    const success = await resumeAgent(sessionId);
    if (success) {
      onShowNotification(`${agentName} 已恢复`, 'success');
    } else {
      onShowNotification(`${agentName} 恢复失败`, 'error');
    }
  };

  const handleUpdateName = async (sessionId: string, name: string) => {
    const success = await updateAgentName(sessionId, name);
    if (success) {
      onShowNotification('名字更新成功', 'success');
    } else {
      onShowNotification('名字更新失败', 'error');
    }
    return success;
  };

  return (
    <>
      <div className="sidebar" ref={sidebarRef}>
        <div className="sidebar-header">
          <h2>
            <svg width="24" height="24" viewBox="0 0 64 64" fill="none" style={{ verticalAlign: 'middle' }}>
              <path d="M12 14C12 12.8954 12.8954 12 14 12H42C43.1046 12 44 12.8954 44 14V50C44 51.1046 43.1046 52 42 52H14C12.8954 52 12 51.1046 12 50V14Z" fill="#667eea"/>
              <path d="M14 12H42V52H14V12Z" fill="#8B9AEB"/>
              <path d="M16 16H40V48H16V16Z" fill="white"/>
              <path d="M32 16V48" stroke="#667eea" strokeWidth="2"/>
              <path d="M44 8L50 14L46 18L40 12L44 8Z" fill="#FFC107"/>
              <path d="M40 12L34 18L30 14L36 8L40 12Z" fill="#FFD54F"/>
              <path d="M30 14L26 18L34 26L38 22L30 14Z" fill="#FF8F00"/>
              <path d="M26 18L22 22L30 30L34 26L26 18Z" fill="#FFC107"/>
              <path d="M30 30L34 26L38 22L42 26L46 22L50 26L50 28L54 32L50 36L46 32L42 36L38 40L34 36L30 40L26 36L22 32L18 28L22 24L26 28L30 30Z" fill="#333"/>
              <path d="M34 26L30 30L26 36L22 32L18 28L22 24L26 28L30 30Z" fill="#FFD54F"/>
            </svg>
            Agents
          </h2>
          <button onClick={() => fetchAgents()} title="刷新">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M23 4v6h-6M1 20v-6h6"/>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
          </button>
        </div>

        <AgentList
          agents={agents}
          currentSessionId={currentSessionId}
          loading={loading}
          onSelectAgent={onSelectAgent}
          onUpdateName={handleUpdateName}
          onSuspendAgent={handleSuspendAgent}
          onResumeAgent={handleResumeAgent}
          onDeleteAgent={handleDeleteAgent}
        />

        <div className="sidebar-footer">
          <button className="new-agent-btn" onClick={() => setShowCreateModal(true)}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            新建Agent
          </button>
        </div>
      </div>

      <div className="resize-handle" ref={resizeRef} onMouseDown={handleMouseDown} />

      <CreateAgentModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={handleCreateAgent}
      />
    </>
  );
}