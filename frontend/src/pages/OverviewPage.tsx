import React from 'react';
import type { SystemSummary, Alert, SystemHistoryResponse, DashboardView } from '../types/api';
import { HistoryChart } from '../components/HistoryChart';

interface OverviewPageProps {
  summary: SystemSummary | null;
  history: SystemHistoryResponse | null;
  alerts: Alert[];
  onNavigate: (view: DashboardView) => void;
}

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

function formatUptime(seconds: number | null | undefined): string {
  if (seconds == null) return 'Unavailable';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${h}h ${m}m ${s}s`;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  summary,
  history,
  alerts,
  onNavigate,
}) => {
  if (!summary) {
    return (
      <div className="page-empty-state">
        <span className="empty-icon">⏳</span>
        <h3>Awaiting System Summary</h3>
        <p>Telemetry inspector has not returned host data yet.</p>
      </div>
    );
  }

  const { host, runtime, linux_environment, metrics, phase_notes } = summary;
  const activeAlerts = alerts.filter((a) => a.status === 'active');

  return (
    <div className="overview-container">
      {/* Alert Banner if Active Alerts */}
      {activeAlerts.length > 0 && (
        <div className="alert-callout-banner" onClick={() => onNavigate('alerts')}>
          <div className="banner-left">
            <span className="banner-icon">🚨</span>
            <div>
              <strong>{activeAlerts.length} Active Resource Pressure Alert{activeAlerts.length === 1 ? '' : 's'}</strong>
              <div className="banner-sub">
                {activeAlerts.map((a) => a.alert_type).join(', ')} &bull; Click to inspect investigative details
              </div>
            </div>
          </div>
          <button type="button" className="btn-alert-action">View Alerts &rarr;</button>
        </div>
      )}

      {/* Top Metrics Row */}
      <div className="metric-cards-grid">
        {/* CPU Card */}
        <div className="metric-card">
          <div className="card-top">
            <span className="card-label">CPU Utilization</span>
            <span className="metric-badge">
              {metrics?.cpu?.logical_cores ?? host.cpu_cores_logical} Cores
            </span>
          </div>
          <div className="metric-primary-val">
            {metrics?.cpu?.total_percent != null ? `${metrics.cpu.total_percent}%` : 'Unavailable'}
          </div>
          <div className="metric-sub">
            {metrics?.cpu?.physical_cores != null ? `${metrics.cpu.physical_cores} Physical Cores` : 'Logical execution units'}
          </div>
          <div className="metric-progress-bar">
            <div
              className={`metric-progress-fill ${
                (metrics?.cpu?.total_percent ?? 0) > 85 ? 'fill-red' : (metrics?.cpu?.total_percent ?? 0) > 70 ? 'fill-amber' : 'fill-cyan'
              }`}
              style={{ width: `${Math.min(100, Math.max(0, metrics?.cpu?.total_percent ?? 0))}%` }}
            />
          </div>
        </div>

        {/* Memory Card */}
        <div className="metric-card">
          <div className="card-top">
            <span className="card-label">Memory (RAM)</span>
            <span className="metric-badge">
              {metrics?.memory?.percent != null ? `${metrics.memory.percent}%` : 'Unavailable'}
            </span>
          </div>
          <div className="metric-primary-val">
            {metrics?.memory?.used_bytes != null ? formatBytes(metrics.memory.used_bytes) : 'Unavailable'}
          </div>
          <div className="metric-sub">
            Total: {metrics?.memory?.total_bytes != null ? formatBytes(metrics.memory.total_bytes) : 'N/A'} &bull; Avail: {metrics?.memory?.available_bytes != null ? formatBytes(metrics.memory.available_bytes) : 'N/A'}
          </div>
          <div className="metric-progress-bar">
            <div
              className={`metric-progress-fill ${
                (metrics?.memory?.percent ?? 0) > 90 ? 'fill-red' : (metrics?.memory?.percent ?? 0) > 80 ? 'fill-amber' : 'fill-purple'
              }`}
              style={{ width: `${Math.min(100, Math.max(0, metrics?.memory?.percent ?? 0))}%` }}
            />
          </div>
        </div>

        {/* Swap Card */}
        <div className="metric-card">
          <div className="card-top">
            <span className="card-label">Swap Storage</span>
            <span className={`metric-badge ${metrics?.swap?.swap_configured ? 'badge-neutral' : 'badge-warning'}`}>
              {metrics?.swap?.swap_configured ? `${metrics.swap.percent}%` : 'Unconfigured'}
            </span>
          </div>
          <div className="metric-primary-val">
            {metrics?.swap?.swap_configured && metrics.swap.used_bytes != null ? formatBytes(metrics.swap.used_bytes) : 'Disabled'}
          </div>
          <div className="metric-sub">
            {metrics?.swap?.swap_configured
              ? `Total: ${formatBytes(metrics?.swap?.total_bytes)}`
              : 'Zero swap configured in kernel'}
          </div>
          <div className="metric-progress-bar">
            <div
              className="metric-progress-fill fill-cyan"
              style={{ width: `${Math.min(100, Math.max(0, metrics?.swap?.percent ?? 0))}%` }}
            />
          </div>
        </div>

        {/* Load Average / Task Queue Card */}
        <div className="metric-card">
          <div className="card-top">
            <span className="card-label">Task Queue (Load Avg)</span>
            <span className={`metric-badge ${metrics?.load_average?.supported ? 'badge-neutral' : 'badge-warning'}`}>
              {metrics?.load_average?.supported ? 'Supported' : 'Unsupported on Windows'}
            </span>
          </div>
          <div className="metric-primary-val">
            {metrics?.load_average?.supported && metrics.load_average.load_1m != null
              ? `${metrics.load_average.load_1m} (1m)`
              : 'N/A'}
          </div>
          <div className="metric-sub">
            {metrics?.load_average?.supported
              ? `5m: ${metrics.load_average.load_5m} &bull; 15m: ${metrics.load_average.load_15m}`
              : 'Requires Linux or WSL2 kernel'}
          </div>
        </div>
      </div>

      {/* History Time-Series Chart */}
      <HistoryChart data={history?.history ?? []} />

      {/* Host & Environment Information Grid */}
      <div className="summary-grid">
        <div className="card">
          <h3 className="card-title">Factual Host Information</h3>
          <div className="card-content">
            <div className="data-row">
              <span className="data-key">Hostname</span>
              <span className="data-value">{host.hostname || 'Unknown'}</span>
            </div>
            <div className="data-row">
              <span className="data-key">Operating System</span>
              <span className="data-value">{host.os} ({host.os_release})</span>
            </div>
            <div className="data-row">
              <span className="data-key">Architecture</span>
              <span className="data-value">{host.architecture}</span>
            </div>
            <div className="data-row">
              <span className="data-key">Logical CPU Cores</span>
              <span className="data-value">{host.cpu_cores_logical}</span>
            </div>
            <div className="data-row">
              <span className="data-key">Uptime</span>
              <span className="data-value">{formatUptime(host.uptime_seconds)}</span>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 className="card-title">Linux &amp; Runtime Environment</h3>
          <div className="card-content">
            <div className="data-row">
              <span className="data-key">Python Runtime</span>
              <span className="data-value">{runtime.python_version} ({runtime.platform})</span>
            </div>
            <div className="data-row">
              <span className="data-key">Platform Scope</span>
              <span className={`badge ${linux_environment.is_linux ? 'badge-success' : 'badge-warning'}`}>
                {linux_environment.is_linux ? 'Linux Platform Active' : 'Non-Linux Host'}
              </span>
            </div>
            <div className="data-row">
              <span className="data-key">Virtual Environment / WSL</span>
              <span className="badge badge-neutral">
                {linux_environment.is_wsl ? 'Ubuntu WSL2 Guest' : 'Native Platform'}
              </span>
            </div>
            <div className="data-row">
              <span className="data-key">/proc Filesystem</span>
              <span className={`badge ${linux_environment.proc_fs_available ? 'badge-success' : 'badge-neutral'}`}>
                {linux_environment.proc_fs_available ? 'Available (/proc)' : 'Unavailable'}
              </span>
            </div>
          </div>
        </div>

        {/* Phase Notes & Architecture Constraints */}
        <div className="card card-notice" style={{ gridColumn: '1 / -1' }}>
          <h3 className="card-title">{summary.phase}</h3>
          <p className="notice-body">{phase_notes.message}</p>
          <div className="data-row" style={{ marginTop: '0.75rem' }}>
            <span className="data-key">Telemetry Engine:</span>
            <span className={`badge ${phase_notes.live_metrics_collected ? 'badge-success' : 'badge-neutral'}`}>
              {phase_notes.live_metrics_collected ? 'Real Telemetry Active' : 'Foundation Mode'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
