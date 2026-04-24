import { create } from 'zustand';
import type { Agent } from '@/types';
import { agentsApi } from './agentsApi';

interface AgentsState {
  agents: Agent[];
  currentSessionId: string | null;
  currentAgentType: string;
  loading: boolean;
  error: string | null;
  fetchAgents: () => Promise<void>;
  selectAgent: (sessionId: string) => Promise<void>;
  createAgent: (name: string, type: string) => Promise<boolean>;
  updateAgentName: (sessionId: string, name: string) => Promise<boolean>;
  suspendAgent: (sessionId: string) => Promise<boolean>;
  resumeAgent: (sessionId: string) => Promise<boolean>;
  deleteAgent: (sessionId: string) => Promise<boolean>;
}

export const useAgentsStore = create<AgentsState>((set, get) => ({
  agents: [],
  currentSessionId: null,
  currentAgentType: 'supervisor',
  loading: false,
  error: null,

  fetchAgents: async () => {
    set({ loading: true, error: null });
    try {
      const data = await agentsApi.fetchAgents();
      set({ agents: data.agents, loading: false });
    } catch (error) {
      set({ error: (error as Error).message, loading: false });
    }
  },

  selectAgent: async (sessionId: string) => {
    if (sessionId === get().currentSessionId) return;
    set({ currentSessionId: sessionId });

    const agent = get().agents.find(a => a.session_id === sessionId);
    if (agent) {
      set({ currentAgentType: agent.agent_type });
    }
  },

  createAgent: async (name: string, type: string) => {
    try {
      await agentsApi.createAgent({ agent_name: name, agent_type: type });
      await get().fetchAgents();
      return true;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },

  updateAgentName: async (sessionId: string, name: string) => {
    try {
      await agentsApi.updateAgentName(sessionId, name);
      await get().fetchAgents();
      return true;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },

  suspendAgent: async (sessionId: string) => {
    try {
      await agentsApi.suspendAgent(sessionId);
      await get().fetchAgents();
      return true;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },

  resumeAgent: async (sessionId: string) => {
    try {
      await agentsApi.resumeAgent(sessionId);
      await get().fetchAgents();
      return true;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },

  deleteAgent: async (sessionId: string) => {
    try {
      await agentsApi.deleteAgent(sessionId);
      const { currentSessionId } = get();
      if (currentSessionId === sessionId) {
        set({ currentSessionId: null, currentAgentType: 'supervisor' });
      }
      await get().fetchAgents();
      return true;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },
}));