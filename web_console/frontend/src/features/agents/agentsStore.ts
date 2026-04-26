import { create } from 'zustand';
import type { Agent, Session } from '@/types';
import { agentsApi } from './agentsApi';

interface AgentsState {
  agents: Agent[];
  sessions: Session[];
  currentSessionId: string | null;
  currentAgentId: string | null;
  currentAgentType: string;
  loading: boolean;
  error: string | null;
  fetchAgents: () => Promise<void>;
  fetchSessions: () => Promise<void>;
  selectAgent: (sessionId: string) => Promise<void>;
  createAgent: (name: string, type: string) => Promise<boolean>;
  updateAgentName: (sessionId: string, name: string) => Promise<boolean>;
  suspendAgent: (agentId: string) => Promise<boolean>;
  resumeAgent: (agentId: string) => Promise<boolean>;
  deleteAgent: (agentId: string) => Promise<boolean>;
  createSession: (agentId: string) => Promise<boolean>;
  deleteSession: (sessionId: string) => Promise<boolean>;
  renameSession: (sessionId: string, name: string) => Promise<boolean>;
  activateSession: (sessionId: string) => Promise<boolean>;
}

export const useAgentsStore = create<AgentsState>((set, get) => ({
  agents: [],
  sessions: [],
  currentSessionId: null,
  currentAgentId: null,
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

  fetchSessions: async () => {
    try {
      const data = await agentsApi.fetchSessions();
      const { currentSessionId, currentAgentId } = get();
      const updates: Partial<AgentsState> = { sessions: data.sessions };
      // Resolve currentAgentId if it's still null after sessions loaded
      if (currentSessionId && !currentAgentId) {
        const session = data.sessions.find((s: Session) => s.session_id === currentSessionId);
        if (session) {
          updates.currentAgentId = session.agent_id;
          updates.currentAgentType = session.agent_type || 'supervisor';
        }
      }
      set(updates);
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  selectAgent: async (sessionId: string) => {
    if (sessionId === get().currentSessionId) return;
    set({ currentSessionId: sessionId });

    const session = get().sessions.find(s => s.session_id === sessionId);
    if (session) {
      set({ currentAgentId: session.agent_id, currentAgentType: session.agent_type || 'supervisor' });
    } else {
      // Fallback: look up agent_id from agents list
      const agent = get().agents.find(a => a.session_id === sessionId);
      if (agent) {
        set({ currentAgentId: agent.agent_id, currentAgentType: agent.agent_type || 'supervisor' });
      }
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

  suspendAgent: async (agentId: string) => {
    try {
      await agentsApi.suspendAgent(agentId);
      await get().fetchAgents();
      return true;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },

  resumeAgent: async (agentId: string) => {
    try {
      await agentsApi.resumeAgent(agentId);
      await get().fetchAgents();
      return true;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },

  deleteAgent: async (agentId: string) => {
    try {
      await agentsApi.deleteAgent(agentId);
      const { currentSessionId } = get();
      if (currentSessionId === agentId) {
        set({ currentSessionId: null, currentAgentType: 'supervisor' });
      }
      await get().fetchAgents();
      return true;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },

  createSession: async (agentId: string) => {
    try {
      const result = await agentsApi.createSession(agentId);
      await get().fetchSessions();
      if (result.session_id) {
        set({ currentSessionId: result.session_id });
      }
      return true;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },

  deleteSession: async (sessionId: string) => {
    try {
      await agentsApi.deleteSession(sessionId);
      const { currentSessionId } = get();
      if (currentSessionId === sessionId) {
        set({ currentSessionId: null, currentAgentType: 'supervisor' });
      }
      await get().fetchSessions();
      return true;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },

  renameSession: async (sessionId: string, name: string) => {
    try {
      await agentsApi.renameSession(sessionId, name);
      await get().fetchSessions();
      return true;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },

  activateSession: async (sessionId: string) => {
    try {
      await agentsApi.activateSession(sessionId);
      set({ currentSessionId: sessionId });
      await get().fetchSessions();
      return true;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },
}));
