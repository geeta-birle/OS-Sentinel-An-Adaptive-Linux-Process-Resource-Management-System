import React from 'react';
import type { ApiConnectionState } from '../types/api';

interface StatusCardProps {
  state: ApiConnectionState;
  onRefresh: () => void;
  apiUrl: string;
}

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export const StatusCard: React.FC<StatusCardProps> = ({ state, onRefresh, apiUrl }) => {
  const { isConnected, isLoading, error, lastChecked, health, summary, alerts, recommendations } = state;
  const metrics = summary?.metrics;

  return (
    <div className="status-container">
      {/* Connection Indicator Bar */}
      <div className={`connection-bar ${isConnected ? 'connected' : isLoading ? 'loading' : 'disconnected'}`}>
        <div className="status-indicator">
          <span className={`status-dot ${isConnected ? 'dot-green' : isLoading ? 'dot-yellow' : 'dot-red'}`} />
          <span className="status-label">
            {isLoading ? 'Checking connection...' : isConnected ? 'Backend Connected' : 'Disconnected'}
          </span>
        </div>
        <div className="connection-actions">
          <span className="api-url-tag">Target: {apiUrl}</span>
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="refresh-btn"
            type="button"
          >
            {isLoading ? 'Checking...' : 'Refresh Status'}
          </button>
        </div>
      </div>

      {lastChecked && (
        <div className="last-checked">
          Last verified: <strong>{new Date(lastChecked).toLocaleTimeString()}</strong>
        </div>
      )}

      {/* Error View */}
      {!isConnected && error && !isLoading && (
        <div className="error-box">
          <div className="error-title">⚠️ Connection Error</div>
          <p className="error-message">{error}</p>
          <div className="error-guidance">
            <strong>Troubleshooting tips:</strong>
            <ul>
              <li>Ensure the Python Flask backend is running on <code>http://localhost:5000</code>.</li>
              <li>Verify that CORS is enabled and allows <code>http://localhost:5173</code>.</li>
              <li>Check your <code>.env</code> file in the frontend folder for the correct <code>VITE_API_BASE_URL</code>.</li>
            </ul>
          </div>
        </div>
      )}

      {/* Connected Summary View */}
      {isConnected && summary && (
        <div className="summary-grid">
          {/* Health & Liveness Card */}
          <div className="card">
            <h3 className="card-title">Backend Health & Readiness</h3>
            <div className="card-content">
              <div className="data-row">
                <span className="data-key">Service Name</span>
                <span className="data-value">{summary.service}</span>
              </div>
              <div className="data-row">
                <span className="data-key">API Version</span>
                <span className="data-value">{health?.version || '0.3.0'}</span>
              </div>
              <div className="data-row">
                <span className="data-key">Liveness Status</span>
                <span className="badge badge-success">{summary.status}</span>
              </div>
              <div className="data-row">
                <span className="data-key">Phase Status</span>
                <span className="data-value">{summary.phase}</span>
              </div>
            </div>
          </div>

          {/* Host & Environment Card */}
          <div className="card">
            <h3 className="card-title">Factual Host Information</h3>
            <div className="card-content">
              <div className="data-row">
                <span className="data-key">Hostname</span>
                <span className="data-value">{summary.host.hostname || 'Unknown'}</span>
              </div>
              <div className="data-row">
                <span className="data-key">Operating System</span>
                <span className="data-value">{summary.host.os} ({summary.host.os_release})</span>
              </div>
              <div className="data-row">
                <span className="data-key">Architecture</span>
                <span className="data-value">{summary.host.architecture}</span>
              </div>
              <div className="data-row">
                <span className="data-key">Logical CPU Cores</span>
                <span className="data-value">{summary.host.cpu_cores_logical}</span>
              </div>
              <div className="data-row">
                <span className="data-key">Uptime</span>
                <span className="data-value">
                  {summary.host.uptime_seconds != null
                    ? `${Math.floor(summary.host.uptime_seconds / 3600)}h ${Math.floor((summary.host.uptime_seconds % 3600) / 60)}m ${Math.floor(summary.host.uptime_seconds % 60)}s`
                    : 'Not available'}
                </span>
              </div>
            </div>
          </div>

          {/* Linux Target Architecture Card */}
          <div className="card">
            <h3 className="card-title">Linux & Runtime Environment</h3>
            <div className="card-content">
              <div className="data-row">
                <span className="data-key">Python Runtime</span>
                <span className="data-value">{summary.runtime.python_version} ({summary.runtime.platform})</span>
              </div>
              <div className="data-row">
                <span className="data-key">Platform Scope</span>
                <span className={`badge ${summary.linux_environment.is_linux ? 'badge-success' : 'badge-warning'}`}>
                  {summary.linux_environment.scope || (summary.linux_environment.is_linux ? 'Linux Platform Active' : 'Non-Linux Host')}
                </span>
              </div>
              <div className="data-row">
                <span className="data-key">/proc Filesystem</span>
                <span className={`badge ${summary.linux_environment.proc_fs_available ? 'badge-success' : 'badge-neutral'}`}>
                  {summary.linux_environment.proc_fs_available ? 'Available (/proc)' : 'Unavailable'}
                </span>
              </div>
            </div>
          </div>

          {/* Real Metrics Card (when available) */}
          {metrics && (
            <div className="card">
              <h3 className="card-title">Live Resource Utilization</h3>
              <div className="card-content">
                <div className="data-row">
                  <span className="data-key">CPU Utilization</span>
                  <span className="data-value">
                    {metrics.cpu?.total_percent != null ? `${metrics.cpu.total_percent}%` : 'Unavailable'}
                  </span>
                </div>
                <div className="data-row">
                  <span className="data-key">RAM Utilization</span>
                  <span className="data-value">
                    {metrics.memory?.percent != null
                      ? `${metrics.memory.percent}% (${formatBytes(metrics.memory.used_bytes)} / ${formatBytes(metrics.memory.total_bytes)})`
                      : 'Unavailable'}
                  </span>
                </div>
                <div className="data-row">
                  <span className="data-key">Swap Memory</span>
                  <span className="data-value">
                    {metrics.swap?.swap_configured
                      ? `${metrics.swap.percent}% (${formatBytes(metrics.swap.used_bytes)} / ${formatBytes(metrics.swap.total_bytes)})`
                      : 'Unconfigured / Disabled'}
                  </span>
                </div>
                <div className="data-row">
                  <span className="data-key">Load Average (1, 5, 15m)</span>
                  <span className="data-value">
                    {metrics.load_average?.supported
                      ? `${metrics.load_average.load_1m}, ${metrics.load_average.load_5m}, ${metrics.load_average.load_15m}`
                      : 'Unsupported on Windows Host'}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Active Alerts Card */}
          {alerts && alerts.length > 0 && (
            <div className="card" style={{ borderColor: 'rgba(239, 68, 68, 0.4)' }}>
              <h3 className="card-title" style={{ color: '#f87171' }}>Active Resource Pressure Alerts</h3>
              <div className="card-content">
                {alerts.map((alt) => (
                  <div key={alt.id} style={{ marginBottom: '0.75rem', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-color)' }}>
                    <div className="data-row">
                      <span className="data-key"><strong>{alt.alert_type}</strong></span>
                      <span className={`badge ${alt.severity === 'critical' ? 'badge-warning' : 'badge-neutral'}`}>
                        {alt.severity.toUpperCase()}
                      </span>
                    </div>
                    <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', margin: '0.35rem 0' }}>
                      {alt.explanation}
                    </p>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      First observed: {new Date(alt.first_observed_at).toLocaleTimeString()}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Investigative Recommendations Card */}
          {recommendations && recommendations.length > 0 && (
            <div className="card card-notice" style={{ gridColumn: '1 / -1' }}>
              <h3 className="card-title">Explainable Investigative Guidance</h3>
              {recommendations.map((rec) => (
                <div key={rec.id} style={{ marginBottom: '1rem' }}>
                  <div className="data-row" style={{ marginBottom: '0.35rem' }}>
                    <strong style={{ color: '#38bdf8' }}>{rec.title}</strong>
                    <span className="badge badge-neutral">{rec.category}</span>
                  </div>
                  <p className="notice-body" style={{ marginBottom: '0.5rem' }}>{rec.description}</p>
                  <div style={{ fontSize: '0.88rem', color: 'var(--text-primary)', marginBottom: '0.35rem' }}>
                    <strong>Suggested Investigations:</strong>
                  </div>
                  <ul style={{ margin: '0 0 0.5rem 1.25rem', padding: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    {rec.suggested_investigations.map((step, idx) => (
                      <li key={idx} style={{ marginBottom: '0.2rem' }}>{step}</li>
                    ))}
                  </ul>
                  <div style={{ fontSize: '0.82rem', color: '#94a3b8', fontStyle: 'italic' }}>
                    <strong>Caution:</strong> {rec.uncertainty_note}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Phase Boundary / Notice Card */}
          <div className="card card-notice">
            <h3 className="card-title">Engine Operating State</h3>
            <p className="notice-body">
              {summary.phase_notes.message}
            </p>
            <div className="data-row" style={{ marginTop: '0.75rem' }}>
              <span className="data-key">Telemetry Engine:</span>
              <span className={`badge ${summary.phase_notes.live_metrics_collected ? 'badge-success' : 'badge-neutral'}`}>
                {summary.phase_notes.live_metrics_collected ? 'Real Telemetry Active' : 'Foundation Mode'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
