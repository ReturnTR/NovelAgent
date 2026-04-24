import { create } from 'zustand';
import type { Message } from '@/types';

interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  currentStreamingContent: string;
  currentToolCalls: Array<{ id?: string; name: string; arguments: Record<string, unknown> }>;
  currentToolResults: Array<{ tool_call_id: string; content: string }>;
  currentReasoning: string;
  addMessage: (msg: Message) => void;
  updateStreamingContent: (content: string) => void;
  setToolCalls: (calls: Array<{ id?: string; name: string; arguments: Record<string, unknown> }>) => void;
  addToolResult: (result: { tool_call_id: string; content: string }) => void;
  appendReasoning: (content: string) => void;
  clearStreamingState: () => void;
  resetMessages: () => void;
  setMessages: (messages: Message[]) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  currentStreamingContent: '',
  currentToolCalls: [],
  currentToolResults: [],
  currentReasoning: '',

  addMessage: (msg: Message) => {
    set({ messages: [...get().messages, msg] });
  },

  updateStreamingContent: (content: string) => {
    set({ currentStreamingContent: content });
  },

  setToolCalls: (calls) => {
    set({ currentToolCalls: calls });
  },

  addToolResult: (result) => {
    set({ currentToolResults: [...get().currentToolResults, result] });
  },

  appendReasoning: (content: string) => {
    set({ currentReasoning: get().currentReasoning + content });
  },

  clearStreamingState: () => {
    set({
      currentStreamingContent: '',
      currentToolCalls: [],
      currentToolResults: [],
      currentReasoning: '',
      isStreaming: false,
    });
  },

  resetMessages: () => {
    set({ messages: [], currentStreamingContent: '', currentToolCalls: [], currentToolResults: [], currentReasoning: '' });
  },

  setMessages: (messages: Message[]) => {
    set({ messages });
  },
}));