import React, { useState } from 'react';

interface HistoryPoint {
  timestamp: string;
  cpu?: { total_percent: number | null };
  memory?: { percent: number | null; used_bytes: number; total_bytes: number };
}

interface HistoryChartProps {
  data: HistoryPoint[];
  title?: string;
  height?: number;
}

export const HistoryChart: React.FC<HistoryChartProps> = ({
  data,
  title = 'System Telemetry History (CPU & RAM %)',
  height = 180,
}) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (!data || data.length === 0) {
    return (
      <div className="chart-empty-container" style={{ height }}>
        <p className="chart-empty-text">No time-series samples recorded yet. Data accumulates every 5s.</p>
      </div>
    );
  }

  const width = 600;
  const padding = { top: 20, right: 30, bottom: 25, left: 40 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  const pointsCount = data.length;
  const getX = (index: number) => {
    if (pointsCount <= 1) return padding.left + innerWidth / 2;
    return padding.left + (index / (pointsCount - 1)) * innerWidth;
  };

  const getY = (percent: number | null | undefined) => {
    const val = percent == null ? 0 : Math.min(100, Math.max(0, percent));
    return padding.top + innerHeight - (val / 100) * innerHeight;
  };

  // Build SVG path strings
  const cpuCoords = data.map((d, i) => `${getX(i)},${getY(d.cpu?.total_percent)}`);
  const memCoords = data.map((d, i) => `${getX(i)},${getY(d.memory?.percent)}`);

  const cpuPath = cpuCoords.length > 0 ? `M ${cpuCoords.join(' L ')}` : '';
  const memPath = memCoords.length > 0 ? `M ${memCoords.join(' L ')}` : '';

  const hoveredPoint = hoverIndex !== null && data[hoverIndex] ? data[hoverIndex] : null;

  return (
    <div className="history-chart-card">
      <div className="chart-header">
        <h4 className="chart-title">{title}</h4>
        <div className="chart-legend">
          <span className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: '#06b6d4' }} /> CPU %
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: '#a855f7' }} /> Memory %
          </span>
        </div>
      </div>

      <div className="svg-container" style={{ position: 'relative' }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="telemetry-svg"
          preserveAspectRatio="none"
          role="img"
          aria-label={title}
        >
          {/* Horizontal Grid lines */}
          {[0, 25, 50, 75, 100].map((level) => {
            const y = getY(level);
            return (
              <g key={level} className="grid-line-group">
                <line
                  x1={padding.left}
                  y1={y}
                  x2={width - padding.right}
                  y2={y}
                  stroke="#334155"
                  strokeDasharray="3 3"
                  strokeWidth="1"
                />
                <text
                  x={padding.left - 8}
                  y={y + 4}
                  fill="#64748b"
                  fontSize="10"
                  textAnchor="end"
                  fontFamily="monospace"
                >
                  {level}%
                </text>
              </g>
            );
          })}

          {/* Lines */}
          <path d={memPath} fill="none" stroke="#a855f7" strokeWidth="2.5" strokeLinecap="round" />
          <path d={cpuPath} fill="none" stroke="#06b6d4" strokeWidth="2.5" strokeLinecap="round" />

          {/* Interactive Hover Zones */}
          {data.map((_, idx) => (
            <rect
              key={idx}
              x={getX(idx) - (innerWidth / pointsCount) / 2}
              y={padding.top}
              width={innerWidth / pointsCount}
              height={innerHeight}
              fill="transparent"
              onMouseEnter={() => setHoverIndex(idx)}
              onMouseLeave={() => setHoverIndex(null)}
              style={{ cursor: 'pointer' }}
            />
          ))}

          {/* Hover indicator dot */}
          {hoverIndex !== null && (
            <g className="hover-marker">
              <line
                x1={getX(hoverIndex)}
                y1={padding.top}
                x2={getX(hoverIndex)}
                y2={height - padding.bottom}
                stroke="#94a3b8"
                strokeWidth="1"
                strokeDasharray="2 2"
              />
              <circle
                cx={getX(hoverIndex)}
                cy={getY(data[hoverIndex]?.cpu?.total_percent)}
                r="4.5"
                fill="#06b6d4"
                stroke="#0f172a"
                strokeWidth="1.5"
              />
              <circle
                cx={getX(hoverIndex)}
                cy={getY(data[hoverIndex]?.memory?.percent)}
                r="4.5"
                fill="#a855f7"
                stroke="#0f172a"
                strokeWidth="1.5"
              />
            </g>
          )}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoveredPoint && hoverIndex !== null && (
          <div
            className="chart-tooltip"
            style={{
              left: `${Math.min(80, Math.max(15, (getX(hoverIndex) / width) * 100))}%`,
              top: '8px',
            }}
          >
            <div className="tooltip-time">
              {new Date(hoveredPoint.timestamp).toLocaleTimeString()}
            </div>
            <div className="tooltip-metric" style={{ color: '#06b6d4' }}>
              CPU: {hoveredPoint.cpu?.total_percent != null ? `${hoveredPoint.cpu.total_percent}%` : 'N/A'}
            </div>
            <div className="tooltip-metric" style={{ color: '#a855f7' }}>
              RAM: {hoveredPoint.memory?.percent != null ? `${hoveredPoint.memory.percent}%` : 'N/A'}
            </div>
          </div>
        )}
      </div>

      <div className="chart-footer">
        <span className="footer-label">Oldest: {new Date(data[0].timestamp).toLocaleTimeString()}</span>
        <span className="footer-label">
          {data.length} sample{data.length === 1 ? '' : 's'} (5s intervals)
        </span>
        <span className="footer-label">Latest: {new Date(data[data.length - 1].timestamp).toLocaleTimeString()}</span>
      </div>
    </div>
  );
};
