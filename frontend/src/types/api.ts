export type DashboardView =
  | 'overview'
  | 'processes'
  | 'alerts'
  | 'recommendations'
  | 'history'
  | 'settings';

export interface HealthStatus {
  status: string;
  timestamp: string;
  service: string;
  version: string;
}

export interface ReadinessStatus {
  status: string;
  timestamp: string;
  service: string;
  checks: {
    api: string;
    system_inspector: string;
    database?: string;
  };
}

export interface HostSummary {
  hostname: string;
  os: string;
  os_release: string;
  os_version: string;
  architecture: string;
  cpu_cores_logical: number;
  uptime_seconds: number | null;
}

export interface RuntimeSummary {
  python_version: string;
  platform: string;
}

export interface LinuxEnvironment {
  is_linux: boolean;
  is_wsl?: boolean;
  scope?: string;
  proc_fs_available: boolean;
}

export interface PhaseNotes {
  live_metrics_collected: boolean;
  message: string;
}

export interface CpuMetrics {
  available: boolean;
  total_percent: number | null;
  per_core_percent?: number[];
  logical_cores?: number;
  physical_cores?: number | null;
  baseline_primed?: boolean;
}

export interface MemoryMetrics {
  available: boolean;
  total_bytes: number | null;
  used_bytes: number | null;
  free_bytes: number | null;
  available_bytes: number | null;
  percent: number | null;
  buffers_bytes?: number;
  cached_bytes?: number;
}

export interface SwapMetrics {
  available: boolean;
  swap_configured: boolean;
  total_bytes: number | null;
  used_bytes: number | null;
  free_bytes?: number | null;
  percent: number | null;
}

export interface LoadAverage {
  supported: boolean;
  load_1m: number | null;
  load_5m: number | null;
  load_15m: number | null;
  reason?: string;
}

export interface PlatformContext {
  os: string;
  scope: string;
  is_linux: boolean;
  is_wsl: boolean;
  wsl_distribution: string | null;
  description: string;
  proc_fs_available?: boolean;
}

export interface LiveMetrics {
  cpu?: CpuMetrics;
  memory?: MemoryMetrics;
  swap?: SwapMetrics;
  load_average?: LoadAverage;
  platform_context?: PlatformContext;
}

export interface SystemSummary {
  status: string;
  timestamp: string;
  service: string;
  phase: string;
  host: HostSummary;
  runtime: RuntimeSummary;
  linux_environment: LinuxEnvironment;
  phase_notes: PhaseNotes;
  metrics?: LiveMetrics;
}

export interface ProcessSummary {
  pid: number;
  name: string;
  status: string;
  cpu_percent: number;
  memory_percent: number;
  memory_rss: number;
  username: string | null;
  create_time: number | null;
}

export interface ProcessDetail extends ProcessSummary {
  exe: string | null;
  cmdline: string[];
  ppid: number | null;
  num_threads: number | null;
  nice: number | null;
  memory_rss_bytes: number;
  memory_vms_bytes: number;
  timestamp: string;
}

export interface ProcessListResponse {
  total_count: number;
  returned_count: number;
  sort_by: string;
  order: string;
  limit: number;
  timestamp: string;
  cache_hit?: boolean;
  cache_age_seconds?: number;
  processes: ProcessSummary[];
}

export interface Alert {
  id: number;
  alert_type: string;
  severity: 'warning' | 'critical';
  status: 'active' | 'recovered' | 'suppressed';
  first_observed_at: string;
  last_observed_at: string;
  recovered_at?: string | null;
  evidence: Record<string, unknown>;
  explanation: string;
}

export interface AlertListResponse {
  count: number;
  limit: number;
  status: string;
  severity: string | null;
  alerts: Alert[];
}

export interface Recommendation {
  id: string;
  category: string;
  severity: string;
  title: string;
  description: string;
  suggested_investigations: string[];
  reasoning: string;
  uncertainty_note: string;
}

export interface RecommendationsResponse {
  count: number;
  timestamp: string;
  active_alerts_count: number;
  recommendations: Recommendation[];
}

export interface ResourceThresholdSetting {
  warning: number;
  critical: number;
  recovery: number;
  persistence_samples: number;
  cooldown_seconds: number;
}

export interface LoadThresholdSetting {
  warning_ratio: number;
  critical_ratio: number;
  recovery_ratio: number;
  persistence_samples: number;
  cooldown_seconds: number;
}

export interface DetectionSettings {
  cpu: ResourceThresholdSetting;
  memory: ResourceThresholdSetting;
  swap: ResourceThresholdSetting;
  load: LoadThresholdSetting;
}

export interface SystemHistoryResponse {
  count: number;
  limit: number;
  since: string | null;
  history: Array<{
    timestamp: string;
    cpu?: { total_percent: number | null };
    memory?: { percent: number | null; used_bytes: number; total_bytes: number };
    swap?: { percent: number | null };
    load_average?: { load_1m: number | null };
    uptime_seconds?: number | null;
  }>;
}

export interface ApiConnectionState {
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
  lastChecked: string | null;
  health: HealthStatus | null;
  summary: SystemSummary | null;
  alerts?: Alert[];
  recommendations?: Recommendation[];
}
