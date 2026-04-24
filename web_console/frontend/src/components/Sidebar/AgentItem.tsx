import { useState, useRef, useEffect } from 'react';
import type { Agent } from '@/types';
import { formatAgentType } from '@/utils/formatters';

interface AgentItemProps {
  agent: Agent;
  isActive: boolean;
  onSelect: (sessionId: string) => void;
  onUpdateName: (sessionId: string, name: string) => Promise<boolean>;
  onSuspend: (sessionId: string, name: string) => void;
  onResume: (sessionId: string, name: string) => void;
  onDelete: (sessionId: string, name: string) => void;
}

export function AgentItem({
  agent,
  isActive,
  onSelect,
  onUpdateName,
  onSuspend,
  onResume,
  onDelete,
}: AgentItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(agent.agent_name);
  const [showMenu, setShowMenu] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditName(agent.agent_name);
    setIsEditing(true);
  };

  const handleSaveName = async () => {
    if (editName.trim() && editName !== agent.agent_name) {
      await onUpdateName(agent.session_id, editName.trim());
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSaveName();
    } else if (e.key === 'Escape') {
      setEditName(agent.agent_name);
      setIsEditing(false);
    }
  };

  const handleMenuClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMenu(!showMenu);
  };

  return (
    <div
      className={`agent-item ${isActive ? 'active' : ''}`}
      data-session-id={agent.session_id}
      onClick={() => onSelect(agent.session_id)}
    >
      <span className={`agent-status ${agent.status}`} />

      <div className="agent-info" onDoubleClick={handleDoubleClick}>
        {isEditing ? (
          <input
            ref={inputRef}
            type="text"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onBlur={handleSaveName}
            onKeyDown={handleKeyDown}
            style={{ flex: 1, padding: '4px 8px', border: '1px solid var(--color-accent)', borderRadius: 'var(--radius-sm)', fontSize: '14px', fontWeight: 500, outline: 'none' }}
          />
        ) : (
          <>
            <div className="agent-name">{agent.agent_name}</div>
            <div className="agent-type">{formatAgentType(agent.agent_type)}</div>
          </>
        )}
      </div>

      <button className="agent-menu-btn" onClick={handleMenuClick}>
        ▾
      </button>

      {showMenu && (
        <div className="agent-dropdown show" ref={menuRef}>
          {agent.status === 'active' ? (
            <div className="agent-dropdown-item suspend" onClick={() => { onSuspend(agent.session_id, agent.agent_name); setShowMenu(false); }}>
              挂起
            </div>
          ) : (
            <div className="agent-dropdown-item resume" onClick={() => { onResume(agent.session_id, agent.agent_name); setShowMenu(false); }}>
              恢复
            </div>
          )}
          <div className="agent-dropdown-item delete" onClick={() => { onDelete(agent.session_id, agent.agent_name); setShowMenu(false); }}>
            删除
          </div>
        </div>
      )}
    </div>
  );
}
