import { useState } from 'react';
import { Modal } from '@/components/common';

interface CreateAgentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (name: string, type: string) => Promise<boolean>;
}

export function CreateAgentModal({ isOpen, onClose, onCreate }: CreateAgentModalProps) {
  const [name, setName] = useState('');
  const [type, setType] = useState('character');
  const [isCreating, setIsCreating] = useState(false);

  const handleCreate = async () => {
    if (!name.trim()) return;

    setIsCreating(true);
    const success = await onCreate(name.trim(), type);
    setIsCreating(false);

    if (success) {
      setName('');
      setType('character');
      onClose();
    }
  };

  const handleClose = () => {
    setName('');
    setType('character');
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="新建Agent"
      footer={
        <>
          <button className="btn btn-secondary" onClick={handleClose}>
            取消
          </button>
          <button className="btn btn-primary" onClick={handleCreate} disabled={!name.trim() || isCreating}>
            {isCreating ? '创建中...' : '创建'}
          </button>
        </>
      }
    >
      <div className="form-group">
        <label>Agent名称</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="请输入Agent名称"
          onKeyDown={(e) => e.key === 'Enter' && name.trim() && handleCreate()}
        />
      </div>
      <div className="form-group">
        <label>Agent类型</label>
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="supervisor">Supervisor - 主控</option>
          <option value="character">Character - 人物</option>
          <option value="outline">Outline - 大纲</option>
          <option value="content">Content - 内容</option>
          <option value="theme">Theme - 主题</option>
        </select>
      </div>
    </Modal>
  );
}