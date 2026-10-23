import React from 'react';
import type { DashboardView, ApiConnectionState } from '../types/api';

interface SidebarProps {
  currentView: DashboardView;
  onSelectView: (view: DashboardView) => void;
  connectionState: ApiConnectionState;
  refreshInterval: number; // in seconds, 0 = paused
  onChangeRefreshInterval: (seconds: number) => void;
  onManualRefresh: () => void;
  activeAlertCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onSelectView,
  connectionState,
  refreshInterval,
  onChangeRefreshInterval,
  onManualRefresh,
  activeAlertCount,
}) => {
  const { isConnected, isLoading, lastChecked } = connectionState;

  const navItems: Array<{ id: DashboardView; label: string; icon: string; badge?: number }> = [
    { id: 'overview', label: 'Overview', icon: '📊' },
    { id: 'processes', label: 'Process Explorer', icon: '⚡' },
    { id: 'alerts', label: 'Alerts & Analysis', icon: '🚨', badge: activeAlertCount },
    { id: 'recommendations', label: 'Recommendations', icon: '💡' },
    { id: 'history', label: 'History & Audit', icon: '📜' },
    { id: 'settings', label: 'Settings', icon: '⚙️' },
  ];

  return (
    <aside className="sentinel-sidebar">
      {/* Brand Header */}
      <div className="sidebar-brand">
        <div className="brand-icon">🛡️</div>
        <div className="brand-text">
          <h2 className="brand-title">Operations Console</h2>
          <span className="brand-subtitle">v0.4.0 &bull; Operations</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              type="button"
              className={`nav-button ${isActive ? 'active' : ''}`}
              onClick={() => onSelectView(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
              {item.badge != null && item.badge > 0 && (
                <span className="nav-badge alert-badge">{item.badge}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Polling & Refresh Controls */}
      <div className="sidebar-section">
        <div className="section-label">Auto-Refresh</div>
        <div className="refresh-controls">
          <select
            className="interval-select"
            value={refreshInterval}
            onChange={(e) => onChangeRefreshInterval(Number(e.target.value))}
            aria-label="Polling interval"
          >
            <option value={3}>Every 3s</option>
            <option value={5}>Every 5s (Default)</option>
            <option value={10}>Every 10s</option>
            <option value={30}>Every 30s</option>
            <option value={0}>Paused</option>
          </select>

          <button
            type="button"
            className="sidebar-refresh-btn"
            onClick={onManualRefresh}
            disabled={isLoading}
            title="Trigger instant refresh"
          >
            {isLoading ? '⏳' : '🔄'}
          </button>
        </div>
      </div>

      {/* Backend Status Footer */}
      <div className="sidebar-footer">
        <div className="connection-status-row">
          <span className={`status-dot ${isConnected ? 'dot-green' : isLoading ? 'dot-yellow' : 'dot-red'}`} />
          <span className="connection-text">
            {isLoading ? 'Connecting...' : isConnected ? 'API Online' : 'Offline'}
          </span>
        </div>
        {lastChecked && (
          <div className="last-sync-text">
            Synced: {new Date(lastChecked).toLocaleTimeString()}
          </div>
        )}
      </div>
    </aside>
  );
};
