/** Registry API for A2A Agent discovery */
import type { Agent } from '@/types';

const getBaseUrl = () => {
  const port = window.location.port;
  return port === '3000' ? '' : `http://${window.location.hostname}:8000`;
};

const REGISTRY_API = `${getBaseUrl()}/api/registry`;

export const registryApi = {
  async searchAgents(keywords?: string, agentType?: string): Promise<Agent[]> {
    const params = new URLSearchParams();
    if (keywords) params.append('keywords', keywords);
    if (agentType) params.append('agent_type', agentType);

    const response = await fetch(`${REGISTRY_API}/search?${params}`);
    if (!response.ok) throw new Error('Failed to search agents');
    const data = await response.json();
    return data.agents;
  },

  async getAgent(agentId: string): Promise<Agent> {
    const response = await fetch(`${REGISTRY_API}/agents/${agentId}`);
    if (!response.ok) throw new Error('Failed to get agent');
    return response.json();
  },

  async listAgents(): Promise<{ count: number; agents: Agent[] }> {
    const response = await fetch(`${REGISTRY_API}/agents`);
    if (!response.ok) throw new Error('Failed to list agents');
    return response.json();
  }
};