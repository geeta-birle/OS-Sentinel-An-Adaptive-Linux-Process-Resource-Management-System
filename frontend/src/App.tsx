import { useState, useEffect, useCallback, useRef } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { OverviewPage } from './pages/OverviewPage';
import { ProcessesPage } from './pages/ProcessesPage';
import { AlertsPage } from './pages/AlertsPage';
import { RecommendationsPage } from './pages/RecommendationsPage';
import { HistoryPage } from './pages/HistoryPage';
import { SettingsPage } from './pages/SettingsPage';
import { ApiService, ApiClientError } from './services/api';
import type {
  DashboardView,
  ApiConnectionState,
  Alert,
  Recommendation,
  SystemHistoryResponse
} from './types/api';
import './App.css';

export function App() {
  const [currentView, setCurrentView] = useState<DashboardView>('overview');
  const [refreshInterval, setRefreshInterval] = useState<number>(5); // default 5s
  const [historyData, setHistoryData] = useState<SystemHistoryResponse | null>(null);

  const [connectionState, setConnectionState] = useState<ApiConnectionState>({
    isConnected: false,
    isLoading: true,
    error: null,
    lastChecked: null,
    health: null,
    summary: null,
    alerts: [],
    recommendations: [],
  });

  const isFetchingRef = useRef<boolean>(false);

  const fetchTelemetry = useCallback(async (isManual = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;

    if (isManual) {
      setConnectionState((prev) => ({ ...prev, isLoading: true }));
    }

    try {
      const [health, summary] = await Promise.all([
        ApiService.getHealth(),
        ApiService.getSystemSummary(),
      ]);

      let alerts: Alert[] = [];
      let recommendations: Recommendation[] = [];
      let history: SystemHistoryResponse | null = null;

      try {
        const [alertsRes, recsRes, histRes] = await Promise.all([
          ApiService.getAlerts('all').catch(() => ({ alerts: [] })),
          ApiService.getRecommendations().catch(() => ({ recommendations: [] })),
          ApiService.getHistory(30).catch(() => ({ count: 0, limit: 30, since: null, history: [] })),
        ]);
        alerts = (alertsRes.alerts as Alert[]) || [];
        recommendations = (recsRes.recommendations as Recommendation[]) || [];
        history = histRes as SystemHistoryResponse;
      } catch {
        // Fallback for Phase 1/mock test environments
      }

      setHistoryData(history);
      setConnectionState({
        isConnected: true,
        isLoading: false,
        error: null,
        lastChecked: new Date().toISOString(),
        health,
        summary,
        alerts,
        recommendations,
      });
    } catch (err: unknown) {
      const errorMessage =
        err instanceof ApiClientError
          ? err.message
          : err instanceof Error
          ? err.message
          : 'Unable to communicate with backend';

      setConnectionState({
        isConnected: false,
        isLoading: false,
        error: errorMessage,
        lastChecked: new Date().toISOString(),
        health: null,
        summary: null,
        alerts: [],
        recommendations: [],
      });
    } finally {
      isFetchingRef.current = false;
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchTelemetry();
  }, [fetchTelemetry]);

  // Polling loop
  useEffect(() => {
    if (refreshInterval <= 0) return;
    const intervalId = setInterval(() => {
      fetchTelemetry();
    }, refreshInterval * 1000);

    return () => clearInterval(intervalId);
  }, [refreshInterval, fetchTelemetry]);

  const activeAlerts = (connectionState.alerts || []).filter((a) => a.status === 'active');

  return (
    <div className="sentinel-app">
      {/* Top Header for project & phase identification */}
      <Header appName="OS Sentinel" phase="Phase 1: Foundation" />

      {/* Main Grid: Sidebar + Viewport */}
      <div className="sentinel-body">
        <Sidebar
          currentView={currentView}
          onSelectView={setCurrentView}
          connectionState={connectionState}
          refreshInterval={refreshInterval}
          onChangeRefreshInterval={setRefreshInterval}
          onManualRefresh={() => fetchTelemetry(true)}
          activeAlertCount={activeAlerts.length}
        />

        <main className="sentinel-main">
          {/* Top Operational Status Bar */}
          <div
            className={`connection-bar ${
              connectionState.isConnected
                ? 'connected'
                : connectionState.isLoading
                ? 'loading'
                : 'disconnected'
            }`}
          >
            <div className="status-indicator">
              <span
                className={`status-dot ${
                  connectionState.isConnected
                    ? 'dot-green'
                    : connectionState.isLoading
                    ? 'dot-yellow'
                    : 'dot-red'
                }`}
              />
              <span className="status-label">
                {connectionState.isLoading
                  ? 'Checking connection...'
                  : connectionState.isConnected
                  ? 'Backend Connected'
                  : 'Disconnected'}
              </span>
            </div>
            <div className="connection-actions">
              <span className="api-url-tag">API: {ApiService.getBaseUrl()}</span>
              {connectionState.lastChecked && (
                <span className="last-checked">
                  Verified: {new Date(connectionState.lastChecked).toLocaleTimeString()}
                </span>
              )}
              <button
                type="button"
                className="refresh-btn"
                onClick={() => fetchTelemetry(true)}
                disabled={connectionState.isLoading}
              >
                {connectionState.isLoading ? 'Checking...' : 'Refresh Status'}
              </button>
            </div>
          </div>

          {/* Connection Error / Disconnected Box */}
          {!connectionState.isConnected && !connectionState.isLoading && connectionState.error && (
            <div className="error-box" data-testid="connection-error-box">
              <div className="error-title">⚠️ Backend Disconnected</div>
              <p className="error-message">{connectionState.error}</p>
              <div className="error-guidance">
                <strong>Troubleshooting tips:</strong>
                <ul>
                  <li>Ensure the Python Flask backend is running on <code>http://localhost:5000</code>.</li>
                  <li>Verify that CORS is enabled and allows <code>http://localhost:5173</code>.</li>
                  <li>Check backend terminal logs for unexpected startup errors or database issues.</li>
                </ul>
              </div>
            </div>
          )}

          {/* Page Routing */}
          <div className="view-content-wrapper">
            {currentView === 'overview' && (
              <OverviewPage
                summary={connectionState.summary}
                history={historyData}
                alerts={connectionState.alerts || []}
                onNavigate={setCurrentView}
              />
            )}

            {currentView === 'processes' && <ProcessesPage />}

            {currentView === 'alerts' && (
              <AlertsPage
                initialAlerts={connectionState.alerts}
                onRefresh={() => fetchTelemetry(true)}
              />
            )}

            {currentView === 'recommendations' && (
              <RecommendationsPage onNavigate={setCurrentView} />
            )}

            {currentView === 'history' && <HistoryPage />}

            {currentView === 'settings' && <SettingsPage />}
          </div>
        </main>
      </div>

      <footer className="app-footer">
        OS Sentinel &bull; Adaptive Linux Process &amp; Resource Management System &bull; Phase 4 Dashboard &bull; Strict Read-Only Policy
      </footer>
    </div>
  );
}

export default App;
