export const DEFAULT_SERVICE_BASE_URL = "http://127.0.0.1:8000";
export const SERVICE_BASE_URL_STORAGE_KEY = "cmag.serviceBaseUrl";

export type ConfigKind =
  | "data_validate"
  | "environment_check"
  | "train"
  | "agent"
  | "tune"
  | "report";

export type JobKind =
  | ConfigKind
  | "backtest"
  | "reproduce"
  | "formal_experiment";

export type JobStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface ConfigCatalogEntry {
  kind: ConfigKind;
  path: string;
  name: string;
  size_bytes: number;
}

export interface ConfigContent {
  kind: ConfigKind;
  path: string;
  content: string;
  sha256: string;
}

export interface ConfigValidationResult {
  valid: boolean;
  kind: ConfigKind;
  config_path: string;
  errors: string[];
  safety_checks: Record<string, boolean>;
}

export interface FormalExperimentGate {
  protocol: string;
  matrix: string;
  expected_commit: string;
  current_commit: string;
  ready: boolean;
}

export interface Capabilities {
  execution_enabled: boolean;
  algorithms: string[];
  searchers: string[];
  schedulers: string[];
  agent_topologies: string[];
  conflict_policies: string[];
  agent_model: string;
  agent_layers: string[];
  dependencies: Record<string, boolean>;
  formal_experiment_gate: FormalExperimentGate;
}

export interface JobRequest {
  kind: JobKind;
  config_path?: string;
  config_yaml?: string;
  run_id?: string;
  partition?: "validation" | "test";
  acknowledge_locked_test?: boolean;
  reproduce_mode?: "verify_only" | "execute_compare";
  formal_group?: "A" | "B" | "C" | "D" | "E" | "F";
  formal_method?: string;
  formal_seed?: number;
  acknowledge_frozen_protocol?: boolean;
}

export interface JobRecord {
  job_id: string;
  kind: JobKind;
  status: JobStatus;
  command: string[];
  config_path: string | null;
  run_id: string | null;
  partition: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  return_code: number | null;
  pid: number | null;
  log_path: string;
  error: string | null;
}

export interface JobLog {
  job_id: string;
  status: JobStatus;
  output: string;
  truncated_to_bytes: number;
}

export class ServiceApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ServiceApiError";
  }
}

export function normalizeServiceBaseUrl(value: string): string {
  const parsed = new URL(value);
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("服务地址必须使用 HTTP 或 HTTPS。");
  }
  if (parsed.username || parsed.password) {
    throw new Error("服务地址不得包含用户名或密码。");
  }
  return parsed.toString().replace(/\/$/, "");
}

export function readServiceBaseUrl(): string {
  if (typeof window === "undefined") return DEFAULT_SERVICE_BASE_URL;
  const stored = window.localStorage.getItem(SERVICE_BASE_URL_STORAGE_KEY);
  if (!stored) return DEFAULT_SERVICE_BASE_URL;
  try {
    return normalizeServiceBaseUrl(stored);
  } catch {
    return DEFAULT_SERVICE_BASE_URL;
  }
}

async function request<T>(
  baseUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  let normalized: string;
  try {
    normalized = normalizeServiceBaseUrl(baseUrl);
  } catch (error) {
    throw new ServiceApiError(
      error instanceof Error ? error.message : "无效的服务地址。",
      0,
    );
  }

  let response: Response;
  try {
    response = await fetch(`${normalized}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ServiceApiError(
      `无法连接本地服务 ${normalized}。请运行 cmag service run --config configs/reporting/gui.yaml。`,
      0,
    );
  }

  const payload = (await response.json().catch(() => null)) as
    | Record<string, unknown>
    | null;
  if (!response.ok) {
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : `本地服务返回 HTTP ${response.status}。`;
    throw new ServiceApiError(detail, response.status);
  }
  return payload as T;
}

export function getCapabilities(baseUrl: string): Promise<Capabilities> {
  return request<Capabilities>(baseUrl, "/api/capabilities");
}

export async function listConfigs(
  baseUrl: string,
  kind: ConfigKind,
): Promise<ConfigCatalogEntry[]> {
  const payload = await request<{ configs: ConfigCatalogEntry[] }>(
    baseUrl,
    `/api/configs?kind=${encodeURIComponent(kind)}`,
  );
  return payload.configs;
}

export function getConfigContent(
  baseUrl: string,
  kind: ConfigKind,
  path: string,
): Promise<ConfigContent> {
  return request<ConfigContent>(
    baseUrl,
    `/api/configs/content?kind=${encodeURIComponent(kind)}&path=${encodeURIComponent(path)}`,
  );
}

export function validateConfig(
  baseUrl: string,
  kind: ConfigKind,
  configPath: string,
  configYaml: string,
): Promise<ConfigValidationResult> {
  return request<ConfigValidationResult>(baseUrl, "/api/configs/validate", {
    method: "POST",
    body: JSON.stringify({
      kind,
      config_path: configPath,
      config_yaml: configYaml,
    }),
  });
}

export function submitJob(
  baseUrl: string,
  payload: JobRequest,
): Promise<JobRecord> {
  return request<JobRecord>(baseUrl, "/api/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getJob(baseUrl: string, jobId: string): Promise<JobRecord> {
  return request<JobRecord>(
    baseUrl,
    `/api/jobs/${encodeURIComponent(jobId)}`,
  );
}

export function getJobLog(baseUrl: string, jobId: string): Promise<JobLog> {
  return request<JobLog>(
    baseUrl,
    `/api/jobs/${encodeURIComponent(jobId)}/log`,
  );
}

export function cancelJob(baseUrl: string, jobId: string): Promise<JobRecord> {
  return request<JobRecord>(
    baseUrl,
    `/api/jobs/${encodeURIComponent(jobId)}`,
    { method: "DELETE" },
  );
}
