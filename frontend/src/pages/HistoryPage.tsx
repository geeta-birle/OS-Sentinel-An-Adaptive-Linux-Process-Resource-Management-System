import React, { useState, useEffect, useCallback } from 'react';
import type { Alert } from '../types/api';
import { ApiService } from '../services/api';
import { HistoryChart } from '../components/HistoryChart';

type HistorySubTab = 'telemetry' | 'alerts';

interface TelemetryPoint {
  timestamp: string;
  cpu?: { total_percent: number | null };
  memory?: { percent: number | null; used_bytes: number; total_bytes: number };
  swap?: { percent: number | null };
  load_average?: { load_1m: number | null };
  uptime_seconds?: number | null;
}

export const HistoryPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<HistorySubTab>('telemetry');
  const [telemetryHistory, setTelemetryHistory] = useState<TelemetryPoint[]>([]);
  const [alertHistory, setAlertHistory] = useState<Alert[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState<number>(50);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [histRes, alertsRes] = await Promise.all([
        ApiService.getHistory(limit),
        ApiService.getAlerts('all', undefined, limit)
      ]);
      setTelemetryHistory(histRes.history || []);
      setAlertHistory(alertsRes.alerts || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to retrieve historical telemetry records');
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="history-page">
      <div className="page-header">
        <div>
          <h2>History & Audit Telemetry</h2>
          <p className="page-subtitle">
            Retrieved historical time-series observations and persisted alert records from SQLite
          </p>
        </div>
        <div className="controls-row">
          <label htmlFor="history-limit-select">Limit:</label>
          <select
            id="history-limit-select"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="filter-select"
            data-testid="history-limit-select"
          >
            <option value="25">25 rows</option>
            <option value="50">50 rows</option>
            <option value="100">100 rows</option>
          </select>
          <button
            className="btn btn-secondary"
            onClick={fetchData}
            disabled={loading}
            data-testid="refresh-history-btn"
          >
            {loading ? 'Refreshing...' : 'Refresh Records'}
          </button>
        </div>
      </div>

      {/* Persistence Note */}
      <div className="sentinel-alert-banner alert-banner-info">
        <span className="banner-icon">&#x2139;</span>
        <div className="banner-text">
          <strong>Database Persistence Audit:</strong> Records shown here are persisted to SQLite (<code>os_sentinel.db</code>)
          by the background metrics collector and detection engine. Old records are pruned according to retention limits.
        </div>
      </div>

      {/* Tabs */}
      <div className="history-tabs">
        <button
          className={`tab-btn ${activeTab === 'telemetry' ? 'tab-active' : ''}`}
          onClick={() => setActiveTab('telemetry')}
          data-testid="tab-telemetry"
        >
          System Metric Time-Series ({telemetryHistory.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'alerts' ? 'tab-active' : ''}`}
          onClick={() => setActiveTab('alerts')}
          data-testid="tab-alerts"
        >
          Alert Audit Log ({alertHistory.length})
        </button>
      </div>

      {/* Loading & Error */}
      {loading && (
        <div className="state-panel loading-state" data-testid="history-loading">
          <div className="spinner"></div>
          <p>Querying SQLite telemetry store...</p>
        </div>
      )}

      {error && (
        <div className="state-panel error-state" data-testid="history-error">
          <span className="error-icon">&#x26A0;</span>
          <p>Error retrieving records: {error}</p>
          <button className="btn btn-secondary" onClick={fetchData}>Retry</button>
        </div>
      )}

      {/* Telemetry Tab Content */}
      {!loading && !error && activeTab === 'telemetry' && (
        <div className="telemetry-view" data-testid="telemetry-view">
          {telemetryHistory.length > 0 && (
            <div className="chart-container-card">
              <HistoryChart data={telemetryHistory} />
            </div>
          )}

          {telemetryHistory.length === 0 ? (
            <div className="state-panel empty-state">
              <p>No telemetry history has been collected yet. Ensure the collector is running.</p>
            </div>
          ) : (
            <div className="table-responsive">
              <table className="sentinel-table" data-testid="telemetry-history-table">
                <thead>
                  <tr>
                    <th>Timestamp (UTC)</th>
                    <th>CPU %</th>
                    <th>RAM %</th>
                    <th>Swap %</th>
                    <th>Load (1m)</th>
                    <th>Uptime</th>
                  </tr>
                </thead>
                <tbody>
                  {telemetryHistory.map((item, idx) => (
                    <tr key={idx}>
                      <td className="cell-timestamp">{new Date(item.timestamp).toLocaleString()}</td>
                      <td>
                        {item.cpu?.total_percent !== null && item.cpu?.total_percent !== undefined
                          ? `${item.cpu.total_percent.toFixed(1)}%`
                          : <span className="unavailable-text">N/A</span>}
                      </td>
                      <td>
                        {item.memory?.percent !== null && item.memory?.percent !== undefined
                          ? `${item.memory.percent.toFixed(1)}%`
                          : <span className="unavailable-text">N/A</span>}
                      </td>
                      <td>
                        {item.swap?.percent !== null && item.swap?.percent !== undefined
                          ? `${item.swap.percent.toFixed(1)}%`
                          : <span className="unavailable-text">N/A</span>}
                      </td>
                      <td>
                        {item.load_average?.load_1m !== null && item.load_average?.load_1m !== undefined
                          ? item.load_average.load_1m.toFixed(2)
                          : <span className="unavailable-text">N/A</span>}
                      </td>
                      <td>
                        {item.uptime_seconds != null
                          ? `${Math.floor(item.uptime_seconds / 3600)}h ${Math.floor((item.uptime_seconds % 3600) / 60)}m`
                          : <span className="unavailable-text">N/A</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Alert Audit Log Tab Content */}
      {!loading && !error && activeTab === 'alerts' && (
        <div className="alert-audit-view" data-testid="alert-audit-view">
          {alertHistory.length === 0 ? (
            <div className="state-panel empty-state">
              <p>No alert audit entries recorded in the database.</p>
            </div>
          ) : (
            <div className="table-responsive">
              <table className="sentinel-table" data-testid="alerts-audit-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Alert Type</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>First Observed</th>
                    <th>Last Observed</th>
                    <th>Recovered</th>
                    <th>Explanation</th>
                  </tr>
                </thead>
                <tbody>
                  {alertHistory.map((alert) => (
                    <tr key={alert.id}>
                      <td>#{alert.id}</td>
                      <td><code>{alert.alert_type}</code></td>
                      <td>
                        <span className={`badge badge-severity badge-${alert.severity}`}>
                          {alert.severity}
                        </span>
                      </td>
                      <td>
                        <span className={`badge badge-status badge-status-${alert.status}`}>
                          {alert.status}
                        </span>
                      </td>
                      <td className="cell-timestamp">{new Date(alert.first_observed_at).toLocaleString()}</td>
                      <td className="cell-timestamp">{new Date(alert.last_observed_at).toLocaleString()}</td>
                      <td className="cell-timestamp">
                        {alert.recovered_at ? new Date(alert.recovered_at).toLocaleString() : '-'}
                      </td>
                      <td className="cell-explanation">{alert.explanation}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
