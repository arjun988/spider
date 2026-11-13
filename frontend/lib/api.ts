const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body || res.statusText);
  }

  return res.json() as Promise<T>;
}

export interface OverviewMetrics {
  total_repositories: number;
  total_prs_reviewed: number;
  total_findings: number;
  critical_findings: number;
  high_findings: number;
  average_review_time_ms: number | null;
  total_api_spend_usd: number;
  recent_reviews: Array<{
    id: string;
    pr_number: number | null;
    pr_title: string | null;
    status: string;
    findings_count: number;
    duration_ms: number | null;
    cost_usd: number;
    created_at: string | null;
  }>;
}

export interface OverviewResponse {
  metrics: OverviewMetrics;
  generated_at: string;
}

export interface Repository {
  id: string;
  name: string;
  full_name: string;
  owner_login: string;
  primary_language: string | null;
  indexing_status: string;
  last_indexed_commit_sha: string | null;
  last_indexed_at: string | null;
  auto_review_enabled: boolean;
  prs_reviewed_count: number;
  last_review_at: string | null;
  html_url: string | null;
}

export interface PullRequest {
  id: string;
  number: number;
  title: string;
  state: string;
  author_login: string;
  review_status: string;
  findings_count: number;
  critical_count: number;
  high_count: number;
  head_sha: string;
  html_url: string | null;
  last_reviewed_at: string | null;
  repository_id: string;
  repository_full_name: string | null;
  latest_review_job_id: string | null;
  created_at: string;
}

export interface GeminiConfig {
  configured: boolean;
  api_key_masked: string | null;
  api_key_validated: boolean;
  connection_status: string;
  primary_model: string;
  embedding_model: string;
  temperature: number;
  max_output_tokens: number;
  auto_review_enabled: boolean;
  severity_threshold: string;
  confidence_threshold: number;
  max_files_per_review: number;
  context_retrieval_limit: number;
  monthly_budget_usd: number;
  budget?: {
    monthly_budget_usd?: number;
    spent_usd?: number;
    remaining_usd?: number;
  } | null;
}

export interface SystemStatus {
  github_app_configured: boolean;
  github_app_id: string | null;
  gemini_env_configured: boolean;
  app_env: string;
  app_name: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  app: string;
  environment: string;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  overview: () => request<OverviewResponse>("/api/analytics/overview"),
  repositories: () =>
    request<{ items: Repository[]; total: number }>("/api/repositories"),
  pullRequests: (params?: { repository_id?: string; review_status?: string }) => {
    const q = new URLSearchParams();
    if (params?.repository_id) q.set("repository_id", params.repository_id);
    if (params?.review_status) q.set("review_status", params.review_status);
    const qs = q.toString();
    return request<{ items: PullRequest[]; total: number }>(
      `/api/pull-requests${qs ? `?${qs}` : ""}`,
    );
  },
  systemStatus: () => request<SystemStatus>("/api/settings/system"),
  geminiConfig: () => request<GeminiConfig>("/api/settings/gemini"),
  updateGeminiConfig: (body: Partial<GeminiConfig> & { api_key?: string }) =>
    request<GeminiConfig>("/api/settings/gemini", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  triggerReview: (prId: string, force = false) =>
    request<{ status: string; review_job_id: string; task_id?: string; job_status?: string }>(
      `/api/pull-requests/${prId}/review?force=${force ? "true" : "false"}`,
      { method: "POST" },
    ),
  getReview: (id: string) => request<ReviewDetail>(`/api/reviews/${id}`),
  submitFeedback: (
    findingId: string,
    body: { feedback_type: "helpful" | "false_positive" | "dismissed" | "fixed"; comment?: string },
  ) =>
    request(`/api/reviews/findings/${findingId}/feedback`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  usage: (days = 30) =>
    request<{
      timeseries: Array<{ date: string; cost_usd: number }>;
      models: Array<{ model: string; cost_usd: number; tokens: number }>;
      reviews: Array<{ date: string; count: number }>;
      by_repository: Array<{ repository: string; cost_usd: number; reviews: number }>;
    }>(`/api/analytics/usage?days=${days}`),
};

export interface ReviewFinding {
  id: string;
  finding_key: string;
  file_path: string;
  start_line: number;
  end_line: number;
  category: string;
  severity: string;
  confidence: number;
  title: string;
  explanation: string;
  failure_scenario: string;
  suggested_fix: string | null;
  verification_status: string;
  published: boolean;
  rejected_reason: string | null;
}

export interface ReviewDetail {
  id: string;
  pull_request_id: string;
  commit_sha: string;
  trigger: string;
  status: string;
  summary: string | null;
  findings_count: number;
  published_count: number;
  rejected_count: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  model_name: string | null;
  duration_ms: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  change_summary: Record<string, unknown> | null;
  timeline: Array<Record<string, unknown>> | null;
  findings: ReviewFinding[];
  pr_number: number | null;
  pr_title: string | null;
  pr_html_url: string | null;
  repository_full_name: string | null;
}