import React from 'react';
import type { ProcessDetail } from '../types/api';

interface ProcessDetailModalProps {
  process: ProcessDetail | null;
  isLoading: boolean;
  error: string | null;
  onClose: () => void;
}

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export const ProcessDetailModal: React.FC<ProcessDetailModalProps> = ({
  process,
  isLoading,
  error,
  onClose,
}) => {
  if (!process && !isLoading && !error) return null;

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-row">
            <span className="modal-badge">PID {process?.pid ?? '...'}</span>
            <h3 className="modal-title">{process?.name ?? 'Process Details'}</h3>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close modal">
            &times;
          </button>
        </div>

        <div className="modal-body">
          {isLoading && (
            <div className="modal-loading">
              <span className="loading-spinner">⏳</span> Querying process telemetry...
            </div>
          )}

          {error && (
            <div className="modal-error">
              <strong>Error inspecting process:</strong> {error}
            </div>
          )}

          {process && !isLoading && (
            <div className="process-detail-grid">
              {/* Core Attributes */}
              <div className="detail-group">
                <div className="detail-row">
                  <span className="detail-key">Process Name</span>
                  <span className="detail-val">{process.name}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Process ID (PID)</span>
                  <span className="detail-val mono">{process.pid}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Parent PID (PPID)</span>
                  <span className="detail-val mono">{process.ppid ?? 'None'}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Status</span>
                  <span className="badge badge-success">{process.status}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Owner / Username</span>
                  <span className="detail-val">{process.username ?? 'Unknown / Restricted'}</span>
                </div>
              </div>

              {/* Resource Metrics */}
              <div className="detail-group">
                <div className="detail-row">
                  <span className="detail-key">CPU Utilization</span>
                  <span className="detail-val mono">{process.cpu_percent}%</span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Memory Utilization</span>
                  <span className="detail-val mono">{process.memory_percent}%</span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Resident Memory (RSS)</span>
                  <span className="detail-val mono">{formatBytes(process.memory_rss_bytes)}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Virtual Memory (VMS)</span>
                  <span className="detail-val mono">{formatBytes(process.memory_vms_bytes)}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Active Threads</span>
                  <span className="detail-val mono">{process.num_threads ?? 'N/A'}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Scheduling Priority (Nice)</span>
                  <span className="detail-val mono">{process.nice ?? 'N/A'}</span>
                </div>
              </div>

              {/* Executable & Command Line */}
              <div className="detail-full-row">
                <span className="detail-key">Executable Binary</span>
                <div className="mono-path-box">{process.exe || 'Access Restricted / Kernel Worker'}</div>
              </div>

              <div className="detail-full-row">
                <span className="detail-key">Command Line Arguments ({process.cmdline?.length ?? 0})</span>
                {process.cmdline && process.cmdline.length > 0 ? (
                  <div className="cmdline-container">
                    {process.cmdline.map((arg, idx) => (
                      <span key={idx} className="cmd-token">{arg}</span>
                    ))}
                  </div>
                ) : (
                  <div className="mono-path-box text-muted">No command line arguments exposed.</div>
                )}
              </div>

              {/* Read-only Security Notice */}
              <div className="detail-notice">
                🛡️ <strong>Safety Policy:</strong> Process execution, suspension, priority adjustment, and termination are strictly disabled in Sentinel.
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
