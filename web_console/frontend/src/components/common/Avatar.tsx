interface AvatarProps {
  role: 'user' | 'assistant' | 'tool';
  className?: string;
}

export function Avatar({ role, className }: AvatarProps) {
  const emoji = role === 'user' ? '👤' : role === 'assistant' ? '🤖' : '🔧';

  return (
    <div className={`avatar ${className || ''}`}>
      {emoji}
    </div>
  );
}