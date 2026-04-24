interface WelcomeMessageProps {
  currentAgentName?: string;
}

export function WelcomeMessage({ currentAgentName }: WelcomeMessageProps) {
  if (currentAgentName) {
    return (
      <div className="welcome-message">
        <h2>✨ 已切换到 {currentAgentName}</h2>
        <p>你可以开始与这个 Agent 对话了</p>
      </div>
    );
  }

  return (
    <div className="welcome-message">
      <div style={{ fontSize: '48px', marginBottom: '24px' }}>📚</div>
      <h2>欢迎使用 Novel Agent</h2>
      <p>多 Agent 协作的智能小说创作系统</p>
      <ul>
        <li><strong>Supervisor</strong> — 主控 Agent，统筹协调</li>
        <li><strong>Character</strong> — 人物塑造，角色设定</li>
        <li><strong>Outline</strong> — 故事大纲，情节规划</li>
        <li><strong>Content</strong> — 文案撰写，内容生成</li>
        <li><strong>Theme</strong> — 主题分析，风格把控</li>
      </ul>
      <p className="example">💡 试试说："创建一个勇敢的男主角"</p>
    </div>
  );
}