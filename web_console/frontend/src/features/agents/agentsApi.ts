import type { Agent, CreateAgentPayload } from '@/types';
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

  async updateAgentName(sessionId: string, agentName: string): Promise<void> {
    const response = await fetch(`${AGENTS_API}/${sessionId}/name`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_name: agentName }),
    });
    if (!response.ok) throw new Error('Failed to update agent name');
  },

  async suspendAgent(sessionId: string): Promise<void> {
    const base = getBaseUrl();
    const response = await fetch(`${base}/api/agents/${sessionId}/suspend`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to suspend agent');
  },

  async resumeAgent(sessionId: string): Promise<void> {
    const base = getBaseUrl();
    const response = await fetch(`${base}/api/agents/${sessionId}/resume`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to resume agent');
  },

  async deleteAgent(sessionId: string): Promise<void> {
    const base = getBaseUrl();
    const response = await fetch(`${base}/api/agents/${sessionId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete agent');
  },

  async getSession(sessionId: string): Promise<{
    metadata: { agent_name: string; agent_type: string };
    messages: Array<{
      role: string;
      content: string;
      tool_calls?: unknown[];
      tool_results?: unknown[];
      reasoning_content?: string;
    }>;
  }> {
    const base = getBaseUrl();
    const response = await fetch(`${base}/api/sessions/${sessionId}`);
    if (!response.ok) throw new Error('Failed to load session');
    return response.json();
  },

  async discoverAgents(keywords?: string, type?: string): Promise<Agent[]> {
    return registryApi.searchAgents(keywords, type);
  },
};