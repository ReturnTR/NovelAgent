import { useEffect, useCallback, useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { SessionPanel } from '@/components/SessionPanel';
import { ChatContainer } from '@/components/Chat';
import { MessageInput } from '@/components/Input';
import { Header } from '@/components/Layout';
import { Notification } from '@/components/common';
import { useAgentsStore } from '@/features/agents/agentsStore';
import { useChatStore } from '@/features/chat/chatStore';
import { useThemeStore } from '@/features/theme/themeStore';
import { agentsApi } from '@/features/agents/agentsApi';
import { streamChat } from '@/features/chat/chatApi';
import type { Message } from '@/types';

export function App() {
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);
  const [sessionPanelVisible, setSessionPanelVisible] = useState(true);

  const {
    agents,
    sessions,
    currentSessionId,
    currentAgentId,
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
    if (firstAgent?.session_id && !currentSessionId) {
      selectAgent(firstAgent.session_id).then(() => {
        // Selection complete
      });
    }
  }, [agents, currentSessionId, selectAgent]);

  // Transform agent session format to frontend format
  // Agent stores: reasoning msg, tool_call msg, tool_result msg as SEPARATE messages
  // Frontend expects: tool_call msg with tool_results attached
  function transformSessionMessages(messages: any[]): any[] {
    const result: any[] = [];
    let i = 0;

    while (i < messages.length) {
      const msg = messages[i];

      // Pass through A2A messages as-is
      if (msg.type === 'agent_request' || msg.type === 'agent_response') {
        result.push(msg);
        i++;
        continue;
      }

      if (msg.role === 'assistant') {
        const hasReasoning = !!msg.reasoning_content;
        const hasToolCalls = !!(msg.tool_calls && msg.tool_calls.length > 0);
        const hasContent = !!(msg.content && msg.content.trim());

        if (hasToolCalls) {
          // Look ahead for tool results
          let toolResults: any[] = [];
          if (i + 1 < messages.length && messages[i + 1].role === 'tool') {
            const toolMsg = messages[i + 1];
            toolResults = [{
              tool_call_id: toolMsg.tool_call_id,
              content: toolMsg.content
            }];
            i++; // Skip tool message
          }

          result.push({
            ...msg,
            tool_results: toolResults,
            // If no content but has reasoning, keep reasoning for display
            reasoning_content: hasContent ? undefined : msg.reasoning_content
          });
        } else if (hasReasoning || hasContent) {
          // Regular assistant message with reasoning or content
          result.push(msg);
        }
        // Skip empty messages that aren't reasoning or tool_calls
      } else if (msg.role === 'user' || msg.role === 'tool') {
        result.push(msg);
      }

      i++;
    }

    return result;
  }

  const handleSelectAgent = useCallback(async (sessionId: string) => {
    if (!sessionId) {
      resetMessages();
      await selectAgent('');
      return;
    }

    setSessionPanelVisible(true);
    await selectAgent(sessionId);
    resetMessages();

    try {
      const sessionData = await agentsApi.getSession(sessionId);
      const transformed = transformSessionMessages(sessionData.messages);
      const loadedMessages: Message[] = transformed.map((msg, index) => ({
        type: msg.type as 'message' | 'agent_request' | 'agent_response' | undefined,
        role: msg.role as 'user' | 'assistant' | 'tool' | 'system',
        content: msg.content || '',
        index,
        tool_calls: msg.tool_calls as Array<{ id?: string; name: string; arguments: Record<string, unknown> }>,
        tool_results: msg.tool_results as Array<{ tool_call_id: string; content: string }>,
        reasoning_content: msg.reasoning_content,
        tool_call_id: msg.tool_call_id,
        source_agent_id: msg.source_agent_id,
        target_agent_id: msg.target_agent_id,
        task: msg.task,
        event_id: msg.event_id,
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
        currentAgentId,
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
  }, [messages, currentAgentId, isStreaming, addMessage, updateStreamingContent, setToolCalls, addToolResult, appendReasoning, clearStreamingState]);

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
    ? (sessions.find(s => s.session_id === currentSessionId)?.session_name || currentAgentType)
    : 'Select an Agent';

  return (
    <div className="app-container">
      <Sidebar
        currentSessionId={currentSessionId}
        onSelectAgent={handleSelectAgent}
        onShowNotification={(message, type) => setNotification({ message, type })}
      />

      <SessionPanel
        currentSessionId={currentSessionId}
        visible={sessionPanelVisible}
        onHide={() => setSessionPanelVisible(false)}
        onSelectSession={handleSelectAgent}
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