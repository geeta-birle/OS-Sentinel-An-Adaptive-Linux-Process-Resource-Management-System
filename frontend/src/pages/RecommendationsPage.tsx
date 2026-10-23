import React, { useState, useEffect, useCallback } from 'react';
import type { Recommendation, DashboardView } from '../types/api';
import { ApiService } from '../services/api';

interface RecommendationsPageProps {
  onNavigate?: (view: DashboardView) => void;
}

export const RecommendationsPage: React.FC<RecommendationsPageProps> = ({ onNavigate }) => {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [activeAlertsCount, setActiveAlertsCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRecommendations = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await ApiService.getRecommendations();
      setRecommendations(res.recommendations || []);
      setActiveAlertsCount(res.active_alerts_count || 0);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch recommendations');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  return (
    <div className="recommendations-page">
      <div className="page-header">
        <div>
          <h2>Investigative Recommendations</h2>
          <p className="page-subtitle">
            Conservative, evidence-backed diagnostic suggestions with explicit uncertainty boundaries
          </p>
        </div>
        <button
          className="btn btn-secondary"
          onClick={fetchRecommendations}
          disabled={loading}
          data-testid="refresh-recs-btn"
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Safety & Explanatory Banner */}
      <div className="sentinel-alert-banner alert-banner-warning">
        <span className="banner-icon">&#x26A0;</span>
        <div className="banner-text">
          <strong>Advisory Notice:</strong> Recommendations are advisory and intended for human operators.
          High memory or swap utilization alone does not prove malfunction (e.g. Linux page cache / buffer allocation).
          OS Sentinel does not execute automated destructive actions or process killings.
        </div>
      </div>

      {/* Overview Stat Bar */}
      <div className="alerts-stats-bar">
        <div className="stat-pill stat-active">
          <span className="stat-label">Correlated Active Alerts</span>
          <span className="stat-value">{activeAlertsCount}</span>
        </div>
        <div className="stat-pill stat-total">
          <span className="stat-label">Generated Recommendations</span>
          <span className="stat-value">{recommendations.length}</span>
        </div>
      </div>

      {/* Loading & Error States */}
      {loading && (
        <div className="state-panel loading-state" data-testid="recs-loading">
          <div className="spinner"></div>
          <p>Analyzing telemetry signatures for investigative insights...</p>
        </div>
      )}

      {error && (
        <div className="state-panel error-state" data-testid="recs-error">
          <span className="error-icon">&#x26A0;</span>
          <p>Failed to retrieve recommendations: {error}</p>
          <button className="btn btn-secondary" onClick={fetchRecommendations}>Retry</button>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && recommendations.length === 0 && (
        <div className="state-panel empty-state" data-testid="recs-empty">
          <span className="empty-icon">&#x2714;</span>
          <h3>All Monitored Subsystems Normal</h3>
          <p>No anomalous resource pressure patterns detected. No investigations are necessary at this time.</p>
        </div>
      )}

      {/* Recommendations Cards */}
      {!loading && !error && recommendations.length > 0 && (
        <div className="recommendations-list" data-testid="recommendations-list">
          {recommendations.map((rec) => (
            <div
              key={rec.id}
              className={`rec-card rec-card-${rec.severity}`}
              data-testid={`rec-item-${rec.id}`}
            >
              <div className="rec-card-header">
                <div className="rec-title-group">
                  <span className={`badge badge-severity badge-${rec.severity}`}>
                    {rec.severity.toUpperCase()}
                  </span>
                  <span className="badge badge-category">{rec.category.toUpperCase()}</span>
                  <h3 className="rec-title">{rec.title}</h3>
                </div>
                {onNavigate && (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => onNavigate('processes')}
                    data-testid={`inspect-procs-btn-${rec.id}`}
                  >
                    Inspect Running Processes &rarr;
                  </button>
                )}
              </div>

              <p className="rec-description">{rec.description}</p>

              {/* Actionable Investigation Steps */}
              {rec.suggested_investigations && rec.suggested_investigations.length > 0 && (
                <div className="rec-section">
                  <h4 className="rec-section-title">Recommended Investigative Steps</h4>
                  <ul className="rec-investigation-list">
                    {rec.suggested_investigations.map((step, idx) => (
                      <li key={idx} className="rec-step-item">
                        <code>{step}</code>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Reasoning */}
              <div className="rec-section">
                <h4 className="rec-section-title">Reasoning & Evidence Correlation</h4>
                <p className="rec-reasoning-text">{rec.reasoning}</p>
              </div>

              {/* Uncertainty Boundaries */}
              <div className="rec-section rec-uncertainty-box">
                <h4 className="rec-section-title uncertainty-title">
                  <span className="uncertainty-icon">&#x2139;</span> Uncertainty Boundaries & Caveats
                </h4>
                <p className="rec-uncertainty-text">{rec.uncertainty_note}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
