import React, { useState, useEffect, useCallback } from 'react';
import type { Alert } from '../types/api';
import { ApiService } from '../services/api';

interface AlertsPageProps {
  initialAlerts?: Alert[];
  onRefresh?: () => void;
}

export const AlertsPage: React.FC<AlertsPageProps> = ({ initialAlerts }) => {
  const [alerts, setAlerts] = useState<Alert[]>(initialAlerts || []);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(!initialAlerts);
  const [error, setError] = useState<string | null>(null);

  const fetchAlerts = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const sev = severityFilter === 'all' ? undefined : severityFilter;
      const res = await ApiService.getAlerts(statusFilter, sev, 100);
      setAlerts(res.alerts || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch alerts');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, severityFilter]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const activeCount = alerts.filter(a => a.status === 'active').length;
  const criticalCount = alerts.filter(a => a.severity === 'critical' && a.status === 'active').length;
  const warningCount = alerts.filter(a => a.severity === 'warning' && a.status === 'active').length;

  return (
    <div className="alerts-page">
      <div className="page-header">
        <div>
          <h2>Alerts & Telemetry Analysis</h2>
          <p className="page-subtitle">
            Explainable threshold violations, persistence tracking, and recovery verification
          </p>
        </div>
        <button
          className="btn btn-secondary"
          onClick={fetchAlerts}
          disabled={loading}
          data-testid="refresh-alerts-btn"
        >
          {loading ? 'Refreshing...' : 'Refresh Alerts'}
        </button>
      </div>

      {/* Safety & Diagnostic Policy Notice */}
      <div className="sentinel-alert-banner alert-banner-info">
        <span className="banner-icon">&#x2139;</span>
        <div className="banner-text">
          <strong>Diagnostic Policy:</strong> Alerts reflect sustained resource pressure detected over configurable observation windows.
          OS Sentinel is strictly <em>read-only</em>; no automated termination or priority modifications are executed.
        </div>
      </div>

      {/* Stats Summary Bar */}
      <div className="alerts-stats-bar">
        <div className="stat-pill stat-active">
          <span className="stat-label">Active Pressure Alerts</span>
          <span className="stat-value">{activeCount}</span>
        </div>
        <div className="stat-pill stat-critical">
          <span className="stat-label">Active Critical</span>
          <span className="stat-value">{criticalCount}</span>
        </div>
        <div className="stat-pill stat-warning">
          <span className="stat-label">Active Warning</span>
          <span className="stat-value">{warningCount}</span>
        </div>
        <div className="stat-pill stat-total">
          <span className="stat-label">Total Filtered</span>
          <span className="stat-value">{alerts.length}</span>
        </div>
      </div>

      {/* Filter Controls */}
      <div className="alerts-filter-bar">
        <div className="filter-group">
          <label htmlFor="alert-status-filter">Status:</label>
          <select
            id="alert-status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="filter-select"
            data-testid="alert-status-select"
          >
            <option value="all">All Statuses</option>
            <option value="active">Active Only</option>
            <option value="recovered">Recovered Only</option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="alert-severity-filter">Severity:</label>
          <select
            id="alert-severity-filter"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="filter-select"
            data-testid="alert-severity-select"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
          </select>
        </div>
      </div>

      {/* Loading & Error States */}
      {loading && (
        <div className="state-panel loading-state" data-testid="alerts-loading">
          <div className="spinner"></div>
          <p>Evaluating alerts against current detection rules...</p>
        </div>
      )}

      {error && (
        <div className="state-panel error-state" data-testid="alerts-error">
          <span className="error-icon">&#x26A0;</span>
          <p>Failed to retrieve alerts: {error}</p>
          <button className="btn btn-secondary" onClick={fetchAlerts}>Retry</button>
        </div>
      )}

      {/* Alert Cards List */}
      {!loading && !error && alerts.length === 0 && (
        <div className="state-panel empty-state" data-testid="alerts-empty">
          <span className="empty-icon">&#x2714;</span>
          <h3>No Alerts Recorded</h3>
          <p>No resource alerts match your current status ({statusFilter}) and severity ({severityFilter}) filters.</p>
        </div>
      )}

      {!loading && !error && alerts.length > 0 && (
        <div className="alerts-list" data-testid="alerts-list">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`alert-card alert-card-${alert.severity} alert-card-${alert.status}`}
              data-testid={`alert-item-${alert.id}`}
            >
              <div className="alert-card-header">
                <div className="alert-title-row">
                  <span className={`badge badge-severity badge-${alert.severity}`}>
                    {alert.severity.toUpperCase()}
                  </span>
                  <span className={`badge badge-status badge-status-${alert.status}`}>
                    {alert.status.toUpperCase()}
                  </span>
                  <span className="alert-type-title">{alert.alert_type.replace(/_/g, ' ').toUpperCase()}</span>
                </div>
                <span className="alert-id-tag">ID: #{alert.id}</span>
              </div>

              <div className="alert-explanation">
                <p>{alert.explanation}</p>
              </div>

              {/* Observed Timestamps */}
              <div className="alert-timing-grid">
                <div className="timing-item">
                  <span className="timing-label">First Detected:</span>
                  <span className="timing-value">{new Date(alert.first_observed_at).toLocaleString()}</span>
                </div>
                <div className="timing-item">
                  <span className="timing-label">Last Observed:</span>
                  <span className="timing-value">{new Date(alert.last_observed_at).toLocaleString()}</span>
                </div>
                {alert.recovered_at && (
                  <div className="timing-item timing-recovered">
                    <span className="timing-label">Recovered At:</span>
                    <span className="timing-value">{new Date(alert.recovered_at).toLocaleString()}</span>
                  </div>
                )}
              </div>

              {/* Evidence details */}
              {alert.evidence && Object.keys(alert.evidence).length > 0 && (
                <div className="alert-evidence-section">
                  <h4 className="evidence-header">Diagnostic Evidence</h4>
                  <div className="evidence-chips">
                    {Object.entries(alert.evidence).map(([key, val]) => (
                      <div key={key} className="evidence-chip">
                        <span className="chip-key">{key.replace(/_/g, ' ')}:</span>
                        <span className="chip-val">
                          {typeof val === 'number' ? (Number.isInteger(val) ? val : val.toFixed(2)) : String(val)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
