import { useState, useRef, useEffect } from 'react';
import { useAgentsStore } from '@/features/agents/agentsStore';
import { formatRelativeTime } from '@/utils/formatters';
import type { Session } from '@/types';

interface SessionPanelProps {
  currentSessionId: string | null;
  visible: boolean;
  onHide: () => void;
  onSelectSession: (sessionId: string) => void;
  onShowNotification: (message: string, type: 'success' | 'error' | 'warning' | 'info') => void;
}

function SessionItem({
  session,
  isActive,
  onSelect,
  onDelete,
  onRename,
  onActivate,
}: {
  session: Session;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRename: (name: string) => void;
  onActivate: () => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(session.session_name || session.session_id);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleSaveName = () => {
    const trimmed = editName.trim();
    if (trimmed && trimmed !== (session.session_name || session.session_id)) {
      onRename(trimmed);
    }
    setIsEditing(false);
  };

  const displayName = session.session_name || session.session_id;
  const isSessionActive = session.status === 'active';

  return (
    <div className={`session-item ${isActive ? 'active' : ''}`} onClick={onSelect}>
      <span className={`session-status ${isSessionActive ? 'active' : 'inactive'}`} />
      <div className="session-item-content">
        {isEditing ? (
          <input
            ref={inputRef}
            type="text"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onBlur={handleSaveName}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSaveName();
              else if (e.key === 'Escape') setIsEditing(false);
            }}
            onClick={(e) => e.stopPropagation()}
            className="session-rename-input"
          />
        ) : (
          <span className="session-name">{displayName}</span>
        )}
        <span className="session-time">{formatRelativeTime(session.updated_at)}</span>
      </div>
      <div className="session-item-actions">
        <button
          className="session-action-btn"
          title="激活"
          onClick={(e) => { e.stopPropagation(); onActivate(); }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
          </svg>
        </button>
        <button
          className="session-action-btn"
          title="重命名"
          onClick={(e) => { e.stopPropagation(); setEditName(displayName); setIsEditing(true); }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </button>
        <button
          className="session-action-btn"
          title="删除"
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="3,6 5,6 21,6"/>
            <path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2v2"/>
          </svg>
        </button>
      </div>
    </div>
  );
}

export function SessionPanel({ currentSessionId, visible, onHide, onSelectSession, onShowNotification }: SessionPanelProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const panelRef = useRef<HTMLDivElement>(null);
  const resizeRef = useRef<HTMLDivElement>(null);
  const isResizingRef = useRef(false);

  const {
    sessions,
    fetchSessions,
    createSession,
    deleteSession,
    renameSession,
    activateSession,
    currentAgentId,
  } = useAgentsStore();

  useEffect(() => {
    if (currentAgentId) {
      fetchSessions(currentAgentId);
    }
  }, [fetchSessions, currentAgentId]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingRef.current || !panelRef.current) return;

      const rect = panelRef.current.getBoundingClientRect();
      const newWidth = e.clientX - rect.left;

      if (newWidth > 150 && newWidth < 600) {
        panelRef.current.style.width = `${newWidth}px`;
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

  const handleNewSession = async () => {
    if (!currentAgentId) {
      onShowNotification('没有可用的 Agent', 'warning');
      return;
    }
    const success = await createSession(currentAgentId);
    if (success) {
      onShowNotification('Session 创建成功', 'success');
    } else {
      onShowNotification('Session 创建失败', 'error');
    }
  };

  const handleDeleteSession = async (session: Session) => {
    const name = session.session_name || session.session_id;
    if (!confirm(`确定要删除 "${name}" 吗？`)) return;
    const success = await deleteSession(session.session_id);
    if (success) {
      onShowNotification(`"${name}" 已删除`, 'info');
    } else {
      onShowNotification('删除失败', 'error');
    }
  };

  const handleRenameSession = async (session: Session, name: string) => {
    const success = await renameSession(session.session_id, name);
    if (success) {
      onShowNotification('名称已更新', 'success');
    } else {
      onShowNotification('名称更新失败', 'error');
    }
  };

  const handleActivateSession = async (session: Session) => {
    const success = await activateSession(session.session_id);
    if (success) {
      onSelectSession(session.session_id);
      onShowNotification('Session 已激活', 'success');
    } else {
      onShowNotification('激活失败', 'error');
    }
  };

  const agentSessions = sessions.filter(s => s.agent_id === currentAgentId);

  const filteredSessions = agentSessions.filter(s => {
    const name = s.session_name || s.session_id;
    return name.toLowerCase().includes(searchQuery.toLowerCase());
  });

  return (
    <>
      <div className={`session-panel ${!visible ? 'hidden' : ''}`} ref={panelRef}>
        <div className="session-panel-header">
          <h2>Sessions</h2>
          <div className="session-panel-header-actions">
            <button onClick={handleNewSession} title="新建 Session">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
            </button>
            <button onClick={() => currentAgentId && fetchSessions(currentAgentId)} title="刷新">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M23 4v6h-6M1 20v-6h6"/>
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
              </svg>
            </button>
            <button onClick={onHide} title="隐藏">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="15 18 9 12 15 6"/>
              </svg>
            </button>
          </div>
        </div>

        <div className="session-search">
          <input
            type="text"
            placeholder="Search sessions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="session-list">
          {filteredSessions.map(session => (
            <SessionItem
              key={session.session_id}
              session={session}
              isActive={session.session_id === currentSessionId}
              onSelect={() => onSelectSession(session.session_id)}
              onDelete={() => handleDeleteSession(session)}
              onRename={(name) => handleRenameSession(session, name)}
              onActivate={() => handleActivateSession(session)}
            />
          ))}
          {filteredSessions.length === 0 && (
            <div className="session-empty">{searchQuery ? '无匹配结果' : '暂无 Session'}</div>
          )}
        </div>
      </div>

      <div className={`resize-handle ${!visible ? 'hidden' : ''}`} ref={resizeRef} onMouseDown={handleMouseDown} />
    </>
  );
}
