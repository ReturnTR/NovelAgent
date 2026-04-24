import { useEffect, useState } from 'react';

export type NotificationType = 'info' | 'success' | 'error' | 'warning';

interface NotificationProps {
  message: string;
  type?: NotificationType;
  duration?: number;
  onHide?: () => void;
}

export function Notification({ message, type = 'info', duration = 3000, onHide }: NotificationProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    setIsVisible(true);
    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(() => onHide?.(), 300);
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onHide]);

  return (
    <div className={`notification ${isVisible ? 'show' : ''} ${type}`}>
      {message}
    </div>
  );
}