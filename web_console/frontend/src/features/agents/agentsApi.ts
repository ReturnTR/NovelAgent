import type { Agent, CreateAgentPayload, Session } from '@/types';
import { registryApi } from '@/features/registry/registryApi';

const getBaseUrl = () => {
  const port = window.location.port;
  return port === '3000' ? '' : `http://${window.location.hostname}:8000`;
};

const AGENTS_API = `${getBaseUrl()}/api/agents`;

export const agentsApi = {
  async fetchAgents(): Promise<{ agents: Agent[] }> {
    const response = await fetch(AGENTS_API);
    if (!response.ok) throw new Error('Failed to fetch agents');
    return response.json();
  },

  async createAgent(data: CreateAgentPayload): Promise<Agent> {
    const response = await fetch(AGENTS_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create agent');
    }
    return response.json();
  },

  async updateAgentName(_agentId: string, _agentName: string): Promise<void> {
    // Backend doesn't support update name yet - no-op for now
    console.warn('updateAgentName not implemented');
  },

  async suspendAgent(agentId: string): Promise<void> {
    const base = getBaseUrl();
    const response = await fetch(`${base}/api/agents/${agentId}/suspend`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to suspend agent');
  },

  async resumeAgent(agentId: string): Promise<void> {
    const base = getBaseUrl();
    const response = await fetch(`${base}/api/agents/${agentId}/resume`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to resume agent');
  },

  async deleteAgent(agentId: string): Promise<void> {
    const base = getBaseUrl();
    const response = await fetch(`${base}/api/agents/${agentId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete agent');
  },

  async fetchSessions(): Promise<{ sessions: Session[] }> {
    const base = getBaseUrl();
    const response = await fetch(`${base}/api/sessions`);
    if (!response.ok) throw new Error('Failed to fetch sessions');
    return response.json();
  },

  async createSession(agentId: string): Promise<{ session_id: string }> {
    const base = getBaseUrl();
    const response = await fetch(`${base}/api/sessions/new`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_id: agentId }),
    });
    if (!response.ok) throw new Error('Failed to create session');
    return response.json();
  },

  async deleteSession(sessionId: string): Promise<void> {
    const base = getBaseUrl();
    const response = await fetch(`${base}/api/sessions/${sessionId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete session');
  },

  async renameSession(sessionId: string, sessionName: string): Promise<void> {
    const base = getBaseUrl();
    const response = await fetch(`${base}/api/sessions/${sessionId}/rename`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_name: sessionName }),
    });
    if (!response.ok) throw new Error('Failed to rename session');
  },

  async activateSession(sessionId: string): Promise<void> {
    const base = getBaseUrl();
    const response = await fetch(`${base}/api/sessions/${sessionId}/activate`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to activate session');
  },

  async getSession(sessionId: string): Promise<{
    metadata: { agent_name: string; agent_type: string };
    messages: Array<{
      type?: 'message' | 'agent_request' | 'agent_response';
      role: string;
      content: string;
      tool_calls?: unknown[];
      tool_results?: unknown[];
      reasoning_content?: string;
      tool_call_id?: string;
      source_agent_id?: string;
      target_agent_id?: string;
      task?: string;
      event_id?: string;
    }>;
  }> {
    const base = getBaseUrl();
    // Note: /api/sessions/{id} returns metadata only, /api/sessions/{id}/messages returns messages
    const [sessionRes, messagesRes] = await Promise.all([
      fetch(`${base}/api/sessions/${sessionId}`),
      fetch(`${base}/api/sessions/${sessionId}/messages`)
    ]);
    if (!sessionRes.ok) throw new Error('Failed to load session');
    if (!messagesRes.ok) throw new Error('Failed to load session messages');

    const sessionData = await sessionRes.json();
    const messagesData = await messagesRes.json();

    return {
      metadata: {
        agent_name: sessionData.agent_name || '',
        agent_type: sessionData.agent_type || ''
      },
      messages: messagesData.messages || []
    };
  },

  async discoverAgents(keywords?: string, type?: string): Promise<Agent[]> {
    return registryApi.searchAgents(keywords, type);
  },
};