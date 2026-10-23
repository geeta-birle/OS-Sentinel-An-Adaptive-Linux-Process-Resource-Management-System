import React, { useState, useEffect, useCallback, useMemo } from 'react';
import type { ProcessSummary, ProcessDetail } from '../types/api';
import { ApiService, ApiClientError } from '../services/api';
import { ProcessDetailModal } from '../components/ProcessDetailModal';

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export const ProcessesPage: React.FC = () => {
  const [processes, setProcesses] = useState<ProcessSummary[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Query state
  const [sortBy, setSortBy] = useState<string>('cpu_percent');
  const [order, setOrder] = useState<'desc' | 'asc'>('desc');
  const [limit, setLimit] = useState<number>(25);
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Process Detail Modal State
  const [selectedPid, setSelectedPid] = useState<number | null>(null);
  const [processDetail, setProcessDetail] = useState<ProcessDetail | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const fetchProcesses = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await ApiService.getProcesses(limit, sortBy, order);
      setProcesses(res.processes);
      setTotalCount(res.total_count);
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError ? err.message : 'Failed to query process list';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [limit, sortBy, order]);

  useEffect(() => {
    fetchProcesses();
  }, [fetchProcesses]);

  const handleOpenDetail = async (pid: number) => {
    setSelectedPid(pid);
    setProcessDetail(null);
    setIsDetailLoading(true);
    setDetailError(null);
    try {
      const detail = await ApiService.getProcessDetail(pid);
      setProcessDetail(detail);
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError ? err.message : `Failed to inspect PID ${pid}`;
      setDetailError(msg);
    } finally {
      setIsDetailLoading(false);
    }
  };

  const handleCloseDetail = () => {
    setSelectedPid(null);
    setProcessDetail(null);
    setDetailError(null);
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setOrder((prev) => (prev === 'desc' ? 'asc' : 'desc'));
    } else {
      setSortBy(field);
      setOrder('desc');
    }
  };

  // Filter client-side by search query
  const filteredProcesses = useMemo(() => {
    if (!searchTerm.trim()) return processes;
    const term = searchTerm.toLowerCase().trim();
    return processes.filter(
      (p) =>
        p.name.toLowerCase().includes(term) ||
        p.pid.toString().includes(term) ||
        (p.username && p.username.toLowerCase().includes(term))
    );
  }, [processes, searchTerm]);

  return (
    <div className="processes-page">
      {/* Header Controls */}
      <div className="page-header-row">
        <div>
          <h2 className="page-title">Process Explorer</h2>
          <p className="page-subtitle">
            Inspecting {processes.length} of {totalCount} active processes &bull; Read-only
          </p>
        </div>

        <div className="process-controls-row">
          <input
            type="search"
            placeholder="Search by name or PID..."
            className="search-input"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            aria-label="Filter processes"
            data-testid="process-search-input"
          />

          <select
            className="limit-select"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            aria-label="Process query limit"
          >
            <option value={10}>Show 10</option>
            <option value={25}>Show 25</option>
            <option value={50}>Show 50</option>
          </select>

          <button
            type="button"
            className="btn-refresh-processes"
            onClick={fetchProcesses}
            disabled={isLoading}
          >
            {isLoading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Error View */}
      {error && (
        <div className="error-box">
          <div className="error-title">⚠️ Error Loading Processes</div>
          <p className="error-message">{error}</p>
        </div>
      )}

      {/* Process Table */}
      <div className="table-wrapper">
        <table className="sentinel-table">
          <thead>
            <tr>
              <th onClick={() => toggleSort('pid')} className="sortable-th">
                PID {sortBy === 'pid' ? (order === 'desc' ? '▼' : '▲') : ''}
              </th>
              <th onClick={() => toggleSort('name')} className="sortable-th">
                Name {sortBy === 'name' ? (order === 'desc' ? '▼' : '▲') : ''}
              </th>
              <th onClick={() => toggleSort('status')} className="sortable-th">
                Status {sortBy === 'status' ? (order === 'desc' ? '▼' : '▲') : ''}
              </th>
              <th onClick={() => toggleSort('cpu_percent')} className="sortable-th text-right">
                CPU % {sortBy === 'cpu_percent' ? (order === 'desc' ? '▼' : '▲') : ''}
              </th>
              <th
                onClick={() => toggleSort('memory_percent')}
                className="sortable-th text-right"
                data-testid="sort-header-memory_percent"
              >
                RAM % {sortBy === 'memory_percent' ? (order === 'desc' ? '▼' : '▲') : ''}
              </th>
              <th onClick={() => toggleSort('memory_rss')} className="sortable-th text-right">
                RSS {sortBy === 'memory_rss' ? (order === 'desc' ? '▼' : '▲') : ''}
              </th>
              <th>User</th>
              <th className="text-center">Action</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && processes.length === 0 && (
              <tr>
                <td colSpan={8} className="table-empty-cell">
                  Scanning system processes...
                </td>
              </tr>
            )}

            {!isLoading && filteredProcesses.length === 0 && (
              <tr>
                <td colSpan={8} className="table-empty-cell">
                  {searchTerm ? `No processes matching "${searchTerm}"` : 'No processes found.'}
                </td>
              </tr>
            )}

            {filteredProcesses.map((p) => (
              <tr key={p.pid} onClick={() => handleOpenDetail(p.pid)} className="clickable-row">
                <td className="mono">{p.pid}</td>
                <td>
                  <strong>{p.name}</strong>
                </td>
                <td>
                  <span className={`badge ${p.status === 'running' ? 'badge-success' : 'badge-neutral'}`}>
                    {p.status}
                  </span>
                </td>
                <td className="text-right mono">
                  <span className={p.cpu_percent > 50 ? 'text-amber' : ''}>{p.cpu_percent}%</span>
                </td>
                <td className="text-right mono">{p.memory_percent}%</td>
                <td className="text-right mono">{formatBytes(p.memory_rss)}</td>
                <td className="text-muted">{p.username || 'System / N/A'}</td>
                <td className="text-center" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className="btn-inspect"
                    onClick={() => handleOpenDetail(p.pid)}
                  >
                    Inspect
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Process Detail Modal */}
      {selectedPid !== null && (
        <ProcessDetailModal
          process={processDetail}
          isLoading={isDetailLoading}
          error={detailError}
          onClose={handleCloseDetail}
        />
      )}
    </div>
  );
};
