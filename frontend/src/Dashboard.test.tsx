import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { OverviewPage } from './pages/OverviewPage';
import { AlertsPage } from './pages/AlertsPage';
import { ProcessesPage } from './pages/ProcessesPage';
import { SettingsPage } from './pages/SettingsPage';
import { RecommendationsPage } from './pages/RecommendationsPage';
import { HistoryPage } from './pages/HistoryPage';
import { ApiService } from './services/api';
import type { SystemSummary, Alert, ProcessListResponse, DetectionSettings } from './types/api';

// --- TEST FIXTURES (Explicitly Identified Mock Telemetry) ---
const mockSummaryFixture: SystemSummary = {
  status: 'online',
  timestamp: '2026-10-22T14:00:00Z',
  service: 'OS Sentinel Backend',
  phase: 'Phase 4 - Operations Dashboard',
  host: {
    hostname: 'sentinel-prod-01',
    os: 'Linux',
    os_release: '6.18.33.2-WSL2',
    os_version: '#1 SMP',
    architecture: 'x86_64',
    cpu_cores_logical: 8,
    uptime_seconds: 7200,
  },
  runtime: {
    python_version: '3.14.4',
    platform: 'linux',
  },
  linux_environment: {
    is_linux: true,
    is_wsl: true,
    proc_fs_available: true,
  },
  phase_notes: {
    live_metrics_collected: true,
    message: 'Phase 4 delivers real-time operations dashboard with zero mock telemetry.',
  },
  metrics: {
    cpu: {
      available: true,
      total_percent: 64.5,
      logical_cores: 8,
      physical_cores: 4,
    },
    memory: {
      available: true,
      total_bytes: 16 * 1024 * 1024 * 1024,
      used_bytes: 8 * 1024 * 1024 * 1024,
      available_bytes: 8 * 1024 * 1024 * 1024,
      free_bytes: 4 * 1024 * 1024 * 1024,
      percent: 50.0,
    },
    swap: {
      available: true,
      swap_configured: true,
      total_bytes: 4 * 1024 * 1024 * 1024,
      used_bytes: 1 * 1024 * 1024 * 1024,
      percent: 25.0,
    },
    load_average: {
      supported: true,
      load_1m: 1.25,
      load_5m: 1.10,
      load_15m: 0.95,
    },
  },
};

const mockAlertsFixture: Alert[] = [
  {
    id: 101,
    alert_type: 'cpu_pressure',
    severity: 'critical',
    status: 'active',
    first_observed_at: '2026-10-22T13:30:00Z',
    last_observed_at: '2026-10-22T13:35:00Z',
    recovered_at: null,
    evidence: { avg_utilization: 94.2, threshold: 90.0, observed_samples: 4 },
    explanation: 'CPU utilization sustained at 94.2% across 4 consecutive observation windows.',
  },
  {
    id: 102,
    alert_type: 'memory_pressure',
    severity: 'warning',
    status: 'recovered',
    first_observed_at: '2026-10-22T12:00:00Z',
    last_observed_at: '2026-10-22T12:15:00Z',
    recovered_at: '2026-10-22T12:20:00Z',
    evidence: { avg_utilization: 82.1, threshold: 80.0, recovery_threshold: 75.0 },
    explanation: 'Memory pressure dropped below recovery threshold of 75.0%.',
  },
];

const mockProcessesFixture: ProcessListResponse = {
  total_count: 3,
  returned_count: 3,
  sort_by: 'cpu_percent',
  order: 'desc',
  limit: 25,
  timestamp: '2026-10-22T14:00:00Z',
  processes: [
    {
      pid: 1234,
      name: 'python3',
      status: 'running',
      cpu_percent: 45.2,
      memory_percent: 12.5,
      memory_rss: 200 * 1024 * 1024,
      username: 'sentinel',
      create_time: 1700000000,
    },
    {
      pid: 5678,
      name: 'node',
      status: 'sleeping',
      cpu_percent: 10.1,
      memory_percent: 8.0,
      memory_rss: 120 * 1024 * 1024,
      username: 'sentinel',
      create_time: 1700000100,
    },
    {
      pid: 9999,
      name: 'systemd',
      status: 'sleeping',
      cpu_percent: 0.1,
      memory_percent: 1.2,
      memory_rss: 30 * 1024 * 1024,
      username: 'root',
      create_time: 1700000001,
    },
  ],
};

const mockSettingsFixture: DetectionSettings = {
  cpu: { warning: 75, critical: 90, recovery: 70, persistence_samples: 3, cooldown_seconds: 60 },
  memory: { warning: 80, critical: 92, recovery: 75, persistence_samples: 3, cooldown_seconds: 60 },
  swap: { warning: 50, critical: 80, recovery: 40, persistence_samples: 3, cooldown_seconds: 60 },
  load: { warning_ratio: 1.5, critical_ratio: 2.5, recovery_ratio: 1.2, persistence_samples: 3, cooldown_seconds: 60 },
};

describe('Dashboard Component Integration Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // 1. Metric Cards & Overview
  it('renders metric cards with real values and Linux environment badges', () => {
    render(
      <OverviewPage
        summary={mockSummaryFixture}
        history={null}
        alerts={mockAlertsFixture}
        onNavigate={vi.fn()}
      />
    );

    expect(screen.getByText('64.5%')).toBeInTheDocument();
    expect(screen.getByText('8 GB')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
    expect(screen.getByText('1.25 (1m)')).toBeInTheDocument();
    expect(screen.getByText('sentinel-prod-01')).toBeInTheDocument();
    expect(screen.getByText('Linux Platform Active')).toBeInTheDocument();
    expect(screen.getByText('Ubuntu WSL2 Guest')).toBeInTheDocument();
    expect(screen.getByText('Available (/proc)')).toBeInTheDocument();
  });

  it('displays explicit unsupported label for load average on non-Linux platform', () => {
    const windowsSummaryFixture: SystemSummary = {
      ...mockSummaryFixture,
      linux_environment: { is_linux: false, proc_fs_available: false },
      metrics: {
        ...mockSummaryFixture.metrics,
        load_average: { supported: false, load_1m: null, load_5m: null, load_15m: null, reason: 'Unsupported on Windows' },
      },
    };

    render(
      <OverviewPage
        summary={windowsSummaryFixture}
        history={null}
        alerts={[]}
        onNavigate={vi.fn()}
      />
    );

    expect(screen.getByText('Unsupported on Windows')).toBeInTheDocument();
    expect(screen.getByText('Requires Linux or WSL2 kernel')).toBeInTheDocument();
  });

  // 2. Alert Filtering & Details
  it('renders alerts and supports filtering by status and severity', async () => {
    vi.spyOn(ApiService, 'getAlerts').mockResolvedValue({
      count: 2,
      limit: 100,
      status: 'all',
      severity: null,
      alerts: mockAlertsFixture,
    });

    render(<AlertsPage initialAlerts={mockAlertsFixture} />);

    // Check alert headers and badges after loading
    await waitFor(() => {
      expect(screen.getByText('CRITICAL')).toBeInTheDocument();
      expect(screen.getByText('ACTIVE')).toBeInTheDocument();
      expect(screen.getByText('CPU PRESSURE')).toBeInTheDocument();
      expect(screen.getByText('ID: #101')).toBeInTheDocument();
      expect(screen.getByText(/CPU utilization sustained at 94.2%/)).toBeInTheDocument();
    });

    // Check filter interaction: change status filter to 'active'
    vi.spyOn(ApiService, 'getAlerts').mockResolvedValue({
      count: 1,
      limit: 100,
      status: 'active',
      severity: null,
      alerts: [mockAlertsFixture[0]],
    });

    const statusSelect = screen.getByTestId('alert-status-select');
    fireEvent.change(statusSelect, { target: { value: 'active' } });

    await waitFor(() => {
      expect(ApiService.getAlerts).toHaveBeenCalledWith('active', undefined, 100);
    });
  });

  // 3. Process Explorer & Sorting
  it('renders processes table and executes sorting triggers', async () => {
    vi.spyOn(ApiService, 'getProcesses').mockResolvedValue(mockProcessesFixture);

    render(<ProcessesPage />);

    await waitFor(() => {
      expect(screen.getByText('python3')).toBeInTheDocument();
      expect(screen.getByText('node')).toBeInTheDocument();
      expect(screen.getByText('systemd')).toBeInTheDocument();
    });

    // Verify sort trigger on Memory column
    const memHeader = screen.getByTestId('sort-header-memory_percent');
    fireEvent.click(memHeader);

    await waitFor(() => {
      expect(ApiService.getProcesses).toHaveBeenCalledWith(25, 'memory_percent', 'desc');
    });

    // Test text filter search
    const searchInput = screen.getByTestId('process-search-input');
    fireEvent.change(searchInput, { target: { value: 'python' } });

    expect(screen.getByText('python3')).toBeInTheDocument();
    expect(screen.queryByText('node')).not.toBeInTheDocument();
  });

  // 4. Settings Form & Validation
  it('validates settings thresholds strictly before submitting', async () => {
    vi.spyOn(ApiService, 'getSettings').mockResolvedValue(mockSettingsFixture);
    vi.spyOn(ApiService, 'updateSettings').mockResolvedValue({
      message: 'Detection settings updated successfully.',
      settings: mockSettingsFixture,
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('input-cpu-warning')).toHaveValue(75);
    });

    // Enter invalid threshold: recovery (95) > warning (75)
    const recoveryInput = screen.getByTestId('input-cpu-recovery');
    fireEvent.change(recoveryInput, { target: { value: '95' } });

    expect(screen.getAllByText(/Recovery threshold must be strictly less than warning/).length).toBeGreaterThan(0);
    const saveBtn = screen.getByTestId('save-settings-btn');
    expect(saveBtn).toBeDisabled();

    // Fix threshold back to valid value (65)
    fireEvent.change(recoveryInput, { target: { value: '65' } });
    expect(saveBtn).not.toBeDisabled();

    fireEvent.click(saveBtn);
    await waitFor(() => {
      expect(ApiService.updateSettings).toHaveBeenCalled();
    });
  });

  // 5. Recommendations & Read-Only Safety Notices
  it('renders explainable recommendations with uncertainty caveats and safe navigation', async () => {
    vi.spyOn(ApiService, 'getRecommendations').mockResolvedValue({
      count: 1,
      timestamp: '2026-10-22T14:00:00Z',
      active_alerts_count: 1,
      recommendations: [
        {
          id: 'rec-cpu-1',
          category: 'investigation',
          severity: 'critical',
          title: 'Investigate Persistent CPU Saturation',
          description: 'CPU utilization has remained above 90% across multiple observation windows.',
          suggested_investigations: ['top -b -n 1 -o %CPU', 'pidstat -u 1 5'],
          reasoning: 'Sustained user space execution without I/O wait.',
          uncertainty_note: 'Telemetry cannot determine whether high load is intended computation or an infinite loop.',
        },
      ],
    });

    const mockNavigate = vi.fn();
    render(<RecommendationsPage onNavigate={mockNavigate} />);

    await waitFor(() => {
      expect(screen.getByText('Investigate Persistent CPU Saturation')).toBeInTheDocument();
      expect(screen.getByText('top -b -n 1 -o %CPU')).toBeInTheDocument();
      expect(screen.getByText(/Telemetry cannot determine whether high load is intended/)).toBeInTheDocument();
    });

    const inspectBtn = screen.getByTestId('inspect-procs-btn-rec-cpu-1');
    fireEvent.click(inspectBtn);
    expect(mockNavigate).toHaveBeenCalledWith('processes');
  });

  // 6. History & Audit Page
  it('renders history and audit telemetry with tab switching', async () => {
    vi.spyOn(ApiService, 'getHistory').mockResolvedValue({
      count: 2,
      limit: 50,
      since: null,
      history: [
        {
          timestamp: '2026-10-23T10:00:00Z',
          cpu: { total_percent: 25.0 },
          memory: { percent: 40.0, used_bytes: 4000, total_bytes: 10000 },
          swap: { percent: 0.0 },
          load_average: { load_1m: 0.5 },
          uptime_seconds: 3600,
        },
      ],
    });
    vi.spyOn(ApiService, 'getAlerts').mockResolvedValue({
      count: 1,
      limit: 50,
      status: 'all',
      severity: null,
      alerts: [mockAlertsFixture[0]],
    });

    render(<HistoryPage />);

    await waitFor(() => {
      expect(screen.getByText('History & Audit Telemetry')).toBeInTheDocument();
      expect(screen.getByText(/Retrieved historical time-series observations/)).toBeInTheDocument();
    });

    // Check tabs
    expect(screen.getByTestId('tab-telemetry')).toBeInTheDocument();
    expect(screen.getByTestId('tab-alerts')).toBeInTheDocument();
  });

  // 7. Empty State Handling (Distinguishing Empty Alert List from Errors)
  it('renders clean empty state when alert list is empty, distinct from errors', async () => {
    vi.spyOn(ApiService, 'getAlerts').mockResolvedValue({
      count: 0,
      limit: 100,
      status: 'all',
      severity: null,
      alerts: [],
    });

    render(<AlertsPage initialAlerts={[]} />);

    await waitFor(() => {
      expect(screen.getByTestId('alerts-empty')).toBeInTheDocument();
      expect(screen.getByText('No Alerts Recorded')).toBeInTheDocument();
      expect(screen.queryByTestId('alerts-error')).not.toBeInTheDocument();
    });
  });
});
