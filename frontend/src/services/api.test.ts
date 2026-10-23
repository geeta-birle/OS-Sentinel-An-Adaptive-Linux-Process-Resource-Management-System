import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiService, ApiClientError } from './api';

describe('ApiService', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('successfully fetches health status', async () => {
    const mockHealth = {
      status: 'healthy',
      timestamp: '2026-10-22T10:00:00Z',
      service: 'OS Sentinel Backend',
      version: '0.1.0',
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockHealth,
    } as unknown as Response);

    const result = await ApiService.getHealth();
    expect(result).toEqual(mockHealth);
  });

  it('throws ApiClientError when response is not ok', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    } as unknown as Response);

    await expect(ApiService.getHealth()).rejects.toThrow(ApiClientError);
  });
});
