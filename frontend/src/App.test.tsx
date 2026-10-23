import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';
import { ApiService } from './services/api';

describe('OS Sentinel App - Phase 1 Foundation', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders application header and connects to backend successfully', async () => {
    vi.spyOn(ApiService, 'getHealth').mockResolvedValue({
      status: 'healthy',
      timestamp: '2026-10-22T12:00:00Z',
      service: 'OS Sentinel Backend',
      version: '0.1.0',
    });

    vi.spyOn(ApiService, 'getSystemSummary').mockResolvedValue({
      status: 'online',
      timestamp: '2026-10-22T12:00:00Z',
      service: 'OS Sentinel Backend',
      phase: 'Phase 1 - Project Foundation',
      host: {
        hostname: 'sentinel-node-01',
        os: 'Linux',
        os_release: '6.18.33.2-WSL2',
        os_version: '#1 SMP',
        architecture: 'x86_64',
        cpu_cores_logical: 8,
        uptime_seconds: 3600,
      },
      runtime: {
        python_version: '3.14.4',
        platform: 'linux',
      },
      linux_environment: {
        is_linux: true,
        proc_fs_available: true,
      },
      phase_notes: {
        live_metrics_collected: false,
        message: 'Phase 1 establishes foundation and health connectivity only.',
      },
    });

    render(<App />);

    // Header presence
    expect(screen.getByText('OS Sentinel')).toBeInTheDocument();
    expect(screen.getByText('Phase 1: Foundation')).toBeInTheDocument();

    // Check loading or success transition
    await waitFor(() => {
      expect(screen.getByText('Backend Connected')).toBeInTheDocument();
    });

    // Verify factual platform data rendered
    expect(screen.getByText('sentinel-node-01')).toBeInTheDocument();
    expect(screen.getByText('Linux Platform Active')).toBeInTheDocument();
    expect(screen.getByText('Available (/proc)')).toBeInTheDocument();
    expect(screen.getByText('Phase 1 - Project Foundation')).toBeInTheDocument();
    expect(screen.getByText(/Phase 1 establishes foundation/)).toBeInTheDocument();
  });

  it('renders disconnected state and guidance when backend is unreachable', async () => {
    vi.spyOn(ApiService, 'getHealth').mockRejectedValue(
      new Error('Failed to reach backend at http://localhost:5000/api/v1/health')
    );
    vi.spyOn(ApiService, 'getSystemSummary').mockRejectedValue(
      new Error('Failed to reach backend at http://localhost:5000/api/v1/system/summary')
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Disconnected')).toBeInTheDocument();
      expect(screen.getByText(/Troubleshooting tips/)).toBeInTheDocument();
    });
  });

  it('handles backend disconnection followed by successful reconnection', async () => {
    const healthSpy = vi.spyOn(ApiService, 'getHealth');
    const summarySpy = vi.spyOn(ApiService, 'getSystemSummary');

    // 1. Initially unreachable
    healthSpy.mockRejectedValueOnce(new Error('Network error: server unreachable'));
    summarySpy.mockRejectedValueOnce(new Error('Network error: server unreachable'));

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Disconnected')).toBeInTheDocument();
    });

    // 2. Backend recovers
    healthSpy.mockResolvedValue({
      status: 'healthy',
      timestamp: '2026-10-23T10:00:00Z',
      service: 'OS Sentinel Backend',
      version: '0.1.0',
    });
    summarySpy.mockResolvedValue({
      status: 'online',
      timestamp: '2026-10-23T10:00:00Z',
      service: 'OS Sentinel Backend',
      phase: 'Phase 1 - Project Foundation',
      host: {
        hostname: 'sentinel-reconnected',
        os: 'Linux',
        os_release: '6.18.33.2-WSL2',
        os_version: '#1 SMP',
        architecture: 'x86_64',
        cpu_cores_logical: 4,
        uptime_seconds: 120,
      },
      runtime: {
        python_version: '3.9.13',
        platform: 'win32',
      },
      linux_environment: {
        is_linux: false,
        proc_fs_available: false,
      },
      phase_notes: {
        live_metrics_collected: true,
        message: 'Operational',
      },
    });

    // Trigger manual refresh to reconnect
    const refreshBtn = screen.getByTitle('Trigger instant refresh');
    fireEvent.click(refreshBtn);

    // Verify recovery to connected state
    await waitFor(() => {
      expect(screen.getByText('Backend Connected')).toBeInTheDocument();
      expect(screen.getByText('sentinel-reconnected')).toBeInTheDocument();
    });
  });
});
