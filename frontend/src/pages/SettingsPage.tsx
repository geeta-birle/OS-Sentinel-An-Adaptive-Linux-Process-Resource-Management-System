import React, { useState, useEffect, useCallback } from 'react';
import type { DetectionSettings } from '../types/api';
import { ApiService } from '../services/api';

export const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<DetectionSettings | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fetchSettings = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await ApiService.getSettings();
      setSettings(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch detection settings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  // Validation function matching backend DetectionSettings rules
  const validateSettings = (s: DetectionSettings): string | null => {
    // CPU
    if (s.cpu.recovery >= s.cpu.warning) return 'CPU: Recovery threshold must be strictly less than warning threshold.';
    if (s.cpu.warning >= s.cpu.critical) return 'CPU: Warning threshold must be strictly less than critical threshold.';
    if (s.cpu.recovery < 0 || s.cpu.critical > 100) return 'CPU: Thresholds must fall within 0% - 100%.';
    if (s.cpu.persistence_samples < 1 || s.cpu.persistence_samples > 30) return 'CPU: Persistence samples must be between 1 and 30.';
    if (s.cpu.cooldown_seconds < 5 || s.cpu.cooldown_seconds > 86400) return 'CPU: Cooldown must be between 5s and 86400s.';

    // Memory
    if (s.memory.recovery >= s.memory.warning) return 'Memory: Recovery threshold must be strictly less than warning threshold.';
    if (s.memory.warning >= s.memory.critical) return 'Memory: Warning threshold must be strictly less than critical threshold.';
    if (s.memory.recovery < 0 || s.memory.critical > 100) return 'Memory: Thresholds must fall within 0% - 100%.';
    if (s.memory.persistence_samples < 1 || s.memory.persistence_samples > 30) return 'Memory: Persistence samples must be between 1 and 30.';
    if (s.memory.cooldown_seconds < 5 || s.memory.cooldown_seconds > 86400) return 'Memory: Cooldown must be between 5s and 86400s.';

    // Swap
    if (s.swap.recovery >= s.swap.warning) return 'Swap: Recovery threshold must be strictly less than warning threshold.';
    if (s.swap.warning >= s.swap.critical) return 'Swap: Warning threshold must be strictly less than critical threshold.';
    if (s.swap.recovery < 0 || s.swap.critical > 100) return 'Swap: Thresholds must fall within 0% - 100%.';
    if (s.swap.persistence_samples < 1 || s.swap.persistence_samples > 30) return 'Swap: Persistence samples must be between 1 and 30.';
    if (s.swap.cooldown_seconds < 5 || s.swap.cooldown_seconds > 86400) return 'Swap: Cooldown must be between 5s and 86400s.';

    // Load
    if (s.load.recovery_ratio <= 0) return 'Load Average: Recovery ratio must be greater than 0.';
    if (s.load.recovery_ratio >= s.load.warning_ratio) return 'Load Average: Recovery ratio must be strictly less than warning ratio.';
    if (s.load.warning_ratio >= s.load.critical_ratio) return 'Load Average: Warning ratio must be strictly less than critical ratio.';
    if (s.load.persistence_samples < 1 || s.load.persistence_samples > 30) return 'Load Average: Persistence samples must be between 1 and 30.';
    if (s.load.cooldown_seconds < 5 || s.load.cooldown_seconds > 86400) return 'Load Average: Cooldown must be between 5s and 86400s.';

    return null;
  };

  const handleChange = (
    section: 'cpu' | 'memory' | 'swap' | 'load',
    field: string,
    value: number
  ) => {
    if (!settings) return;
    const updated = {
      ...settings,
      [section]: {
        ...settings[section],
        [field]: value
      }
    };
    setSettings(updated);
    const err = validateSettings(updated);
    setValidationError(err);
    setSuccessMessage(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;

    const validation = validateSettings(settings);
    if (validation) {
      setValidationError(validation);
      return;
    }

    try {
      setSaving(true);
      setError(null);
      setSuccessMessage(null);
      const res = await ApiService.updateSettings(settings);
      setSettings(res.settings);
      setSuccessMessage(res.message || 'Settings saved successfully to backend SQLite store.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update settings');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings-page">
      <div className="page-header">
        <div>
          <h2>Thresholds & Engine Settings</h2>
          <p className="page-subtitle">
            Configure dynamic warning/critical thresholds, observation windows, and alert cooldowns
          </p>
        </div>
        <button
          className="btn btn-secondary"
          onClick={fetchSettings}
          disabled={loading || saving}
          data-testid="reload-settings-btn"
        >
          {loading ? 'Reloading...' : 'Reload from Server'}
        </button>
      </div>

      {/* Safety Notice */}
      <div className="sentinel-alert-banner alert-banner-info">
        <span className="banner-icon">&#x2139;</span>
        <div className="banner-text">
          <strong>Threshold Policy:</strong> Values are stored in SQLite and actively applied by the detection engine.
          Lowering thresholds makes detection more sensitive; increasing persistence samples prevents transient spikes from triggering alerts.
        </div>
      </div>

      {/* Success & Error Banners */}
      {successMessage && (
        <div className="sentinel-alert-banner alert-banner-success" data-testid="settings-success">
          <span className="banner-icon">&#x2714;</span>
          <div className="banner-text">{successMessage}</div>
        </div>
      )}

      {(error || validationError) && (
        <div className="sentinel-alert-banner alert-banner-critical" data-testid="settings-error">
          <span className="banner-icon">&#x26A0;</span>
          <div className="banner-text">
            <strong>Validation Error:</strong> {validationError || error}
          </div>
        </div>
      )}

      {loading && (
        <div className="state-panel loading-state" data-testid="settings-loading">
          <div className="spinner"></div>
          <p>Loading detection configuration from server...</p>
        </div>
      )}

      {!loading && settings && (
        <form onSubmit={handleSubmit} className="settings-form" data-testid="settings-form">
          {/* CPU Settings Card */}
          <div className="settings-card">
            <div className="settings-card-header">
              <h3>CPU Utilization Thresholds</h3>
              <span className="badge badge-category">Processor</span>
            </div>
            <div className="settings-grid">
              <div className="form-group">
                <label htmlFor="cpu-warning">Warning Threshold (%)</label>
                <input
                  id="cpu-warning"
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={settings.cpu.warning}
                  onChange={(e) => handleChange('cpu', 'warning', parseFloat(e.target.value) || 0)}
                  className="form-input"
                  data-testid="input-cpu-warning"
                />
              </div>
              <div className="form-group">
                <label htmlFor="cpu-critical">Critical Threshold (%)</label>
                <input
                  id="cpu-critical"
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={settings.cpu.critical}
                  onChange={(e) => handleChange('cpu', 'critical', parseFloat(e.target.value) || 0)}
                  className="form-input"
                  data-testid="input-cpu-critical"
                />
              </div>
              <div className="form-group">
                <label htmlFor="cpu-recovery">Recovery Threshold (%)</label>
                <input
                  id="cpu-recovery"
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={settings.cpu.recovery}
                  onChange={(e) => handleChange('cpu', 'recovery', parseFloat(e.target.value) || 0)}
                  className="form-input"
                  data-testid="input-cpu-recovery"
                />
              </div>
              <div className="form-group">
                <label htmlFor="cpu-persistence">Persistence (Samples)</label>
                <input
                  id="cpu-persistence"
                  type="number"
                  step="1"
                  min="1"
                  max="30"
                  value={settings.cpu.persistence_samples}
                  onChange={(e) => handleChange('cpu', 'persistence_samples', parseInt(e.target.value, 10) || 1)}
                  className="form-input"
                  data-testid="input-cpu-persistence"
                />
              </div>
              <div className="form-group">
                <label htmlFor="cpu-cooldown">Cooldown (Seconds)</label>
                <input
                  id="cpu-cooldown"
                  type="number"
                  step="5"
                  min="5"
                  max="86400"
                  value={settings.cpu.cooldown_seconds}
                  onChange={(e) => handleChange('cpu', 'cooldown_seconds', parseInt(e.target.value, 10) || 5)}
                  className="form-input"
                  data-testid="input-cpu-cooldown"
                />
              </div>
            </div>
          </div>

          {/* Memory Settings Card */}
          <div className="settings-card">
            <div className="settings-card-header">
              <h3>Memory Utilization Thresholds</h3>
              <span className="badge badge-category">RAM</span>
            </div>
            <div className="settings-grid">
              <div className="form-group">
                <label htmlFor="mem-warning">Warning Threshold (%)</label>
                <input
                  id="mem-warning"
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={settings.memory.warning}
                  onChange={(e) => handleChange('memory', 'warning', parseFloat(e.target.value) || 0)}
                  className="form-input"
                  data-testid="input-mem-warning"
                />
              </div>
              <div className="form-group">
                <label htmlFor="mem-critical">Critical Threshold (%)</label>
                <input
                  id="mem-critical"
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={settings.memory.critical}
                  onChange={(e) => handleChange('memory', 'critical', parseFloat(e.target.value) || 0)}
                  className="form-input"
                  data-testid="input-mem-critical"
                />
              </div>
              <div className="form-group">
                <label htmlFor="mem-recovery">Recovery Threshold (%)</label>
                <input
                  id="mem-recovery"
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={settings.memory.recovery}
                  onChange={(e) => handleChange('memory', 'recovery', parseFloat(e.target.value) || 0)}
                  className="form-input"
                  data-testid="input-mem-recovery"
                />
              </div>
              <div className="form-group">
                <label htmlFor="mem-persistence">Persistence (Samples)</label>
                <input
                  id="mem-persistence"
                  type="number"
                  step="1"
                  min="1"
                  max="30"
                  value={settings.memory.persistence_samples}
                  onChange={(e) => handleChange('memory', 'persistence_samples', parseInt(e.target.value, 10) || 1)}
                  className="form-input"
                  data-testid="input-mem-persistence"
                />
              </div>
              <div className="form-group">
                <label htmlFor="mem-cooldown">Cooldown (Seconds)</label>
                <input
                  id="mem-cooldown"
                  type="number"
                  step="5"
                  min="5"
                  max="86400"
                  value={settings.memory.cooldown_seconds}
                  onChange={(e) => handleChange('memory', 'cooldown_seconds', parseInt(e.target.value, 10) || 5)}
                  className="form-input"
                  data-testid="input-mem-cooldown"
                />
              </div>
            </div>
          </div>

          {/* Swap Settings Card */}
          <div className="settings-card">
            <div className="settings-card-header">
              <h3>Swap Utilization Thresholds</h3>
              <span className="badge badge-category">Virtual Memory</span>
            </div>
            <div className="settings-grid">
              <div className="form-group">
                <label htmlFor="swap-warning">Warning Threshold (%)</label>
                <input
                  id="swap-warning"
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={settings.swap.warning}
                  onChange={(e) => handleChange('swap', 'warning', parseFloat(e.target.value) || 0)}
                  className="form-input"
                  data-testid="input-swap-warning"
                />
              </div>
              <div className="form-group">
                <label htmlFor="swap-critical">Critical Threshold (%)</label>
                <input
                  id="swap-critical"
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={settings.swap.critical}
                  onChange={(e) => handleChange('swap', 'critical', parseFloat(e.target.value) || 0)}
                  className="form-input"
                  data-testid="input-swap-critical"
                />
              </div>
              <div className="form-group">
                <label htmlFor="swap-recovery">Recovery Threshold (%)</label>
                <input
                  id="swap-recovery"
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={settings.swap.recovery}
                  onChange={(e) => handleChange('swap', 'recovery', parseFloat(e.target.value) || 0)}
                  className="form-input"
                  data-testid="input-swap-recovery"
                />
              </div>
              <div className="form-group">
                <label htmlFor="swap-persistence">Persistence (Samples)</label>
                <input
                  id="swap-persistence"
                  type="number"
                  step="1"
                  min="1"
                  max="30"
                  value={settings.swap.persistence_samples}
                  onChange={(e) => handleChange('swap', 'persistence_samples', parseInt(e.target.value, 10) || 1)}
                  className="form-input"
                  data-testid="input-swap-persistence"
                />
              </div>
              <div className="form-group">
                <label htmlFor="swap-cooldown">Cooldown (Seconds)</label>
                <input
                  id="swap-cooldown"
                  type="number"
                  step="5"
                  min="5"
                  max="86400"
                  value={settings.swap.cooldown_seconds}
                  onChange={(e) => handleChange('swap', 'cooldown_seconds', parseInt(e.target.value, 10) || 5)}
                  className="form-input"
                  data-testid="input-swap-cooldown"
                />
              </div>
            </div>
          </div>

          {/* Load Ratio Settings Card */}
          <div className="settings-card">
            <div className="settings-card-header">
              <h3>Load Average Ratios (Per CPU Core)</h3>
              <span className="badge badge-category">Linux Run-Queue</span>
            </div>
            <div className="settings-grid">
              <div className="form-group">
                <label htmlFor="load-warning">Warning Ratio (× Cores)</label>
                <input
                  id="load-warning"
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="50"
                  value={settings.load.warning_ratio}
                  onChange={(e) => handleChange('load', 'warning_ratio', parseFloat(e.target.value) || 0)}
                  className="form-input"
                  data-testid="input-load-warning"
                />
              </div>
              <div className="form-group">
                <label htmlFor="load-critical">Critical Ratio (× Cores)</label>
                <input
                  id="load-critical"
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="50"
                  value={settings.load.critical_ratio}
                  onChange={(e) => handleChange('load', 'critical_ratio', parseFloat(e.target.value) || 0)}
                  className="form-input"
                  data-testid="input-load-critical"
                />
              </div>
              <div className="form-group">
                <label htmlFor="load-recovery">Recovery Ratio (× Cores)</label>
                <input
                  id="load-recovery"
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="50"
                  value={settings.load.recovery_ratio}
                  onChange={(e) => handleChange('load', 'recovery_ratio', parseFloat(e.target.value) || 0)}
                  className="form-input"
                  data-testid="input-load-recovery"
                />
              </div>
              <div className="form-group">
                <label htmlFor="load-persistence">Persistence (Samples)</label>
                <input
                  id="load-persistence"
                  type="number"
                  step="1"
                  min="1"
                  max="30"
                  value={settings.load.persistence_samples}
                  onChange={(e) => handleChange('load', 'persistence_samples', parseInt(e.target.value, 10) || 1)}
                  className="form-input"
                  data-testid="input-load-persistence"
                />
              </div>
              <div className="form-group">
                <label htmlFor="load-cooldown">Cooldown (Seconds)</label>
                <input
                  id="load-cooldown"
                  type="number"
                  step="5"
                  min="5"
                  max="86400"
                  value={settings.load.cooldown_seconds}
                  onChange={(e) => handleChange('load', 'cooldown_seconds', parseInt(e.target.value, 10) || 5)}
                  className="form-input"
                  data-testid="input-load-cooldown"
                />
              </div>
            </div>
          </div>

          {/* Form Actions */}
          <div className="form-actions-bar">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={saving || !!validationError}
              data-testid="save-settings-btn"
            >
              {saving ? 'Validating & Saving...' : 'Save Configuration'}
            </button>
            {validationError && (
              <span className="validation-error-hint">{validationError}</span>
            )}
          </div>
        </form>
      )}
    </div>
  );
};
