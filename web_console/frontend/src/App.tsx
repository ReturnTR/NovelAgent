import { useEffect, useCallback, useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { ChatContainer } from '@/components/Chat';
import { MessageInput } from '@/components/Input';
import { Header } from '@/components/Layout';
import { Notification } from '@/components/common';
import { useAgentsStore } from '@/features/agents/agentsStore';
import { useChatStore } from '@/features/chat/chatStore';
import { useThemeStore } from '@/features/theme/themeStore';
import { agentsApi } from '@/features/agents/agentsApi';
import { streamChat } from '@/features/chat/chatApi';
import { formatAgentType } from '@/utils/formatters';
import type { Message } from '@/types';

export function App() {
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  const {
    agents,
    currentSessionId,
    currentAgentType,
    selectAgent,
    fetchAgents,
  } = useAgentsStore();

  const {
    messages,
    isStreaming,
    currentStreamingContent,
    currentToolCalls,
    currentToolResults,
    currentReasoning,
    addMessage,
    updateStreamingContent,
    setToolCalls,
    addToolResult,
    appendReasoning,
    clearStreamingState,
    resetMessages,
  } = useChatStore();

  const { theme } = useThemeStore();

  useEffect(() => {
    document.body.classList.toggle('dark-theme', theme === 'dark');
  }, [theme]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  useEffect(() => {
    const firstAgent = agents[0];
    if (firstAgent && !currentSessionId) {
      selectAgent(firstAgent.session_id);
    }
  }, [agents, currentSessionId, selectAgent]);

  const handleSelectAgent = useCallback(async (sessionId: string) => {
    if (!sessionId) {
      resetMessages();
      await selectAgent('');
      return;
    }

    await selectAgent(sessionId);
    resetMessages();

    try {
      const sessionData = await agentsApi.getSession(sessionId);
      const loadedMessages: Message[] = sessionData.messages.map((msg, index) => ({
        role: msg.role as 'user' | 'assistant' | 'tool' | 'system',
        content: msg.content,
        index,
        tool_calls: msg.tool_calls as Array<{ id?: string; name: string; arguments: Record<string, unknown> }>,
        tool_results: msg.tool_results as Array<{ tool_call_id: string; content: string }>,
        reasoning_content: msg.reasoning_content,
      }));
      useChatStore.getState().setMessages(loadedMessages);
    } catch (error) {
      console.error('Failed to load session:', error);
    }
  }, [selectAgent, resetMessages]);

  const handleSendMessage = useCallback(async (message: string) => {
    if (isStreaming) return;

    addMessage({ role: 'user', content: message });

    const assistantMessageId = `assistant-${Date.now()}`;
    let streamingContent = '';
    let toolCalls: Array<{ id?: string; name: string; arguments: Record<string, unknown> }> = [];
    let toolResults: Array<{ tool_call_id: string; content: string }> = [];
    let reasoning = '';

    useChatStore.setState({ isStreaming: true });

    try {
      await streamChat(
        message,
        messages,
        currentSessionId,
        {
          onContent: (content) => {
            streamingContent += content;
            updateStreamingContent(streamingContent);
          },
          onToolCall: (calls) => {
            toolCalls = calls;
            setToolCalls(calls);
          },
          onToolResult: (toolCallId, content) => {
            toolResults.push({ tool_call_id: toolCallId, content });
            addToolResult({ tool_call_id: toolCallId, content });
          },
          onReasoning: (content) => {
            reasoning += content;
            appendReasoning(content);
          },
          onError: (error) => {
            streamingContent = `错误: ${error}`;
            updateStreamingContent(streamingContent);
          },
          onDone: () => {
            addMessage({
              id: assistantMessageId,
              role: 'assistant',
              content: streamingContent,
              tool_calls: toolCalls,
              tool_results: toolResults,
              reasoning_content: reasoning,
            });
            clearStreamingState();
          },
        }
      );
    } catch (error) {
      console.error('Chat error:', error);
      updateStreamingContent(`请求失败: ${(error as Error).message}`);
      clearStreamingState();
    }
  }, [messages, currentSessionId, isStreaming, addMessage, updateStreamingContent, setToolCalls, addToolResult, appendReasoning, clearStreamingState]);

  const handleDeleteMessage = useCallback(async (index: number) => {
    if (!currentSessionId) return;
    if (!confirm('确定要删除此消息吗？')) return;

    try {
      await fetch(`${agentsApi.getSession}/${currentSessionId}/messages/${index}`, { method: 'DELETE' });
      await handleSelectAgent(currentSessionId);
      setNotification({ message: '消息已删除', type: 'info' });
    } catch (error) {
      setNotification({ message: `删除失败: ${(error as Error).message}`, type: 'error' });
    }
  }, [currentSessionId, handleSelectAgent]);

  const title = currentSessionId
    ? `${formatAgentType(currentAgentType)} Agent`
    : 'Select an Agent';

  return (
    <div className="app-container">
      <Sidebar
        currentSessionId={currentSessionId}
        onSelectAgent={handleSelectAgent}
        onShowNotification={(message, type) => setNotification({ message, type })}
      />

      <div className="main-content">
        <Header title={title} isStreaming={isStreaming} />

        <ChatContainer
          messages={messages}
          currentToolCalls={currentToolCalls}
          currentToolResults={currentToolResults}
          currentReasoning={currentReasoning}
          streamingContent={currentStreamingContent}
          isStreaming={isStreaming}
          onDeleteMessage={handleDeleteMessage}
        />

        <MessageInput
          onSend={handleSendMessage}
          disabled={isStreaming || !currentSessionId}
        />
      </div>

      {notification && (
        <Notification
          message={notification.message}
          type={notification.type}
          onHide={() => setNotification(null)}
        />
      )}
    </div>
  );
}