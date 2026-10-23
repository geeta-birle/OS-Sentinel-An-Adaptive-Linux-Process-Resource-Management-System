import type {
  HealthStatus,
  ReadinessStatus,
  SystemSummary,
  ProcessListResponse,
  ProcessDetail,
  AlertListResponse,
  RecommendationsResponse,
  DetectionSettings,
  SystemHistoryResponse
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000/api/v1';

export class ApiClientError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const response = await fetch(url, {
      credentials: 'omit',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        ...(options?.headers || {})
      },
      ...options
    });

    if (!response.ok) {
      let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`;
      try {
        const errJson = await response.json();
        if (errJson && errJson.error) {
          errorMessage = errJson.error;
        }
      } catch {
        // Fallback to response statusText
      }
      throw new ApiClientError(errorMessage, response.status);
    }

    return await response.json();
  } catch (error: unknown) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    const message = error instanceof Error ? error.message : 'Unknown network failure';
    throw new ApiClientError(`Failed to reach backend at ${url}: ${message}`);
  }
}

export const ApiService = {
  getBaseUrl(): string {
    return API_BASE_URL;
  },

  async getHealth(): Promise<HealthStatus> {
    return request<HealthStatus>('/health');
  },

  async getReadiness(): Promise<ReadinessStatus> {
    return request<ReadinessStatus>('/health/readiness');
  },

  async getSystemSummary(): Promise<SystemSummary> {
    return request<SystemSummary>('/system/summary');
  },

  async getHistory(limit = 50, since?: string): Promise<SystemHistoryResponse> {
    const query = new URLSearchParams({ limit: limit.toString() });
    if (since) query.set('since', since);
    return request<SystemHistoryResponse>(`/system/history?${query.toString()}`);
  },

  async getProcesses(limit = 25, sortBy = 'cpu_percent', order = 'desc'): Promise<ProcessListResponse> {
    const query = new URLSearchParams({
      limit: limit.toString(),
      sort_by: sortBy,
      order: order
    });
    return request<ProcessListResponse>(`/processes?${query.toString()}`);
  },

  async getProcessDetail(pid: number): Promise<ProcessDetail> {
    return request<ProcessDetail>(`/processes/${pid}`);
  },

  async getAlerts(status = 'all', severity?: string, limit = 50): Promise<AlertListResponse> {
    const query = new URLSearchParams({ status, limit: limit.toString() });
    if (severity) query.set('severity', severity);
    return request<AlertListResponse>(`/alerts?${query.toString()}`);
  },

  async getRecommendations(): Promise<RecommendationsResponse> {
    return request<RecommendationsResponse>('/recommendations');
  },

  async getSettings(): Promise<DetectionSettings> {
    return request<DetectionSettings>('/settings');
  },

  async updateSettings(settings: Partial<DetectionSettings>): Promise<{ message: string; settings: DetectionSettings }> {
    return request('/settings', {
      method: 'PUT',
      body: JSON.stringify(settings)
    });
  }
};
