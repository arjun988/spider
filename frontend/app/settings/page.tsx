"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Shell } from "@/components/layout/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

type Provider = "gemini" | "litellm";

export default function SettingsPage() {
  const qc = useQueryClient();
  const system = useQuery({ queryKey: ["system"], queryFn: api.systemStatus });
  const gemini = useQuery({ queryKey: ["gemini"], queryFn: api.geminiConfig });

  const [provider, setProvider] = useState<Provider>("gemini");
  const [litellmBaseUrl, setLitellmBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [primaryModel, setPrimaryModel] = useState("");
  const [embeddingModel, setEmbeddingModel] = useState("");
  const [temperature, setTemperature] = useState("0.1");
  const [maxTokens, setMaxTokens] = useState("8192");
  const [budget, setBudget] = useState("100");
  const [severity, setSeverity] = useState("medium");
  const [confidence, setConfidence] = useState("0.6");
  const [autoReview, setAutoReview] = useState(true);
  const [maxFiles, setMaxFiles] = useState("50");
  const [contextLimit, setContextLimit] = useState("20");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!gemini.data) return;
    setProvider(gemini.data.llm_provider || "gemini");
    setLitellmBaseUrl(gemini.data.litellm_base_url || "");
    setPrimaryModel(gemini.data.primary_model);
    setEmbeddingModel(gemini.data.embedding_model);
    setTemperature(String(gemini.data.temperature));
    setMaxTokens(String(gemini.data.max_output_tokens));
    setBudget(String(gemini.data.monthly_budget_usd));
    setSeverity(gemini.data.severity_threshold);
    setConfidence(String(gemini.data.confidence_threshold));
    setAutoReview(gemini.data.auto_review_enabled);
    setMaxFiles(String(gemini.data.max_files_per_review));
    setContextLimit(String(gemini.data.context_retrieval_limit));
  }, [gemini.data]);

  const save = useMutation({
    mutationFn: () =>
      api.updateGeminiConfig({
        llm_provider: provider,
        litellm_base_url: provider === "litellm" ? litellmBaseUrl.trim() : litellmBaseUrl.trim() || null,
        ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
        primary_model: primaryModel,
        embedding_model: embeddingModel,
        temperature: Number(temperature),
        max_output_tokens: Number(maxTokens),
        monthly_budget_usd: Number(budget),
        severity_threshold: severity,
        confidence_threshold: Number(confidence),
        auto_review_enabled: autoReview,
        max_files_per_review: Number(maxFiles),
        context_retrieval_limit: Number(contextLimit),
        validate_key: true,
      }),
    onSuccess: () => {
      setApiKey("");
      setMessage("Settings saved. Keys are encrypted at rest and never returned in full.");
      qc.invalidateQueries({ queryKey: ["gemini"] });
      qc.invalidateQueries({ queryKey: ["system"] });
    },
    onError: (err: Error) => setMessage(err.message),
  });

  const validate = useMutation({
    mutationFn: () => api.validateLlm(),
    onSuccess: (res) => {
      setMessage(
        res.valid
          ? `${res.provider} connected — ${res.detail}`
          : `${res.provider} invalid — ${res.detail}`,
      );
      qc.invalidateQueries({ queryKey: ["gemini"] });
    },
    onError: (err: Error) => setMessage(err.message),
  });

  const inputClass =
    "mt-1.5 w-full rounded-md border border-input bg-card px-3 py-2 text-sm outline-none transition-shadow placeholder:text-muted-foreground focus-visible:shadow-focus";

  return (
    <Shell
      title="Settings"
      description="LLM provider, GitHub App status, and review thresholds"
      breadcrumb="System / Settings"
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>GitHub App</CardTitle>
            <CardDescription>Installation credentials stay server-side only.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Connection</span>
              <Badge variant={system.data?.github_app_configured ? "success" : "warning"}>
                {system.data?.github_app_configured ? "configured" : "not configured"}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">App ID</span>
              <span className="font-mono text-xs">{system.data?.github_app_id || "—"}</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Set GITHUB_APP_* variables in `.env` and place the private key under `secrets/`.
              Install the app from the Repositories page, then sync connected repos.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>LLM connection</CardTitle>
            <CardDescription>
              Gemini is the default. Switch to LiteLLM to route through any OpenAI-compatible proxy.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Provider</span>
              <Badge variant="accent">{gemini.data?.llm_provider ?? "gemini"}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Status</span>
              <Badge
                variant={
                  gemini.data?.connection_status === "connected" ? "success" : "warning"
                }
              >
                {gemini.data?.connection_status ?? "…"}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Key</span>
              <span className="font-mono text-xs">
                {gemini.data?.api_key_masked || "not set"}
              </span>
            </div>
            {gemini.data?.llm_provider === "litellm" && gemini.data.litellm_base_url ? (
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">LiteLLM URL</span>
                <span className="truncate font-mono text-[11px]">
                  {gemini.data.litellm_base_url}
                </span>
              </div>
            ) : null}
            {gemini.data?.budget ? (
              <div className="rounded-md border border-border p-3 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Spent this month</span>
                  <span>${Number(gemini.data.budget.spent_usd ?? 0).toFixed(4)}</span>
                </div>
                <div className="mt-1 flex justify-between">
                  <span className="text-muted-foreground">Remaining</span>
                  <span>${Number(gemini.data.budget.remaining_usd ?? 0).toFixed(2)}</span>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>LLM configuration</CardTitle>
          <CardDescription>
            Agents read models from this config. LiteLLM model IDs look like{" "}
            <span className="font-mono">gemini/gemini-2.5-flash</span> or{" "}
            <span className="font-mono">openai/gpt-4o</span>.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <label className="text-xs text-muted-foreground sm:col-span-2">
            Provider
            <select
              className={inputClass}
              value={provider}
              onChange={(e) => {
                const next = e.target.value as Provider;
                setProvider(next);
                if (next === "litellm" && !primaryModel.includes("/")) {
                  setPrimaryModel("gemini/gemini-2.5-flash");
                  setEmbeddingModel("gemini/text-embedding-004");
                }
                if (next === "gemini" && primaryModel.includes("/")) {
                  setPrimaryModel("gemini-2.5-flash");
                  setEmbeddingModel("gemini-embedding-001");
                }
              }}
            >
              <option value="gemini">Gemini (default — Google GenAI SDK)</option>
              <option value="litellm">LiteLLM (OpenAI-compatible proxy)</option>
            </select>
          </label>

          {provider === "litellm" ? (
            <label className="text-xs text-muted-foreground sm:col-span-2">
              LiteLLM base URL
              <input
                className={inputClass}
                placeholder="http://localhost:4000"
                value={litellmBaseUrl}
                onChange={(e) => setLitellmBaseUrl(e.target.value)}
              />
              <span className="mt-1 block text-[11px] text-muted-foreground">
                Spider calls <span className="font-mono">/v1/chat/completions</span> and{" "}
                <span className="font-mono">/v1/embeddings</span> on this host.
              </span>
            </label>
          ) : null}

          <label className="text-xs text-muted-foreground sm:col-span-2">
            {provider === "litellm" ? "LiteLLM API key (optional for local proxies)" : "Gemini API key"}
            <input
              type="password"
              className={inputClass}
              placeholder={
                gemini.data?.api_key_masked
                  ? "Leave blank to keep existing key"
                  : provider === "litellm"
                    ? "LiteLLM master key / provider key"
                    : "Paste Gemini API key"
              }
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              autoComplete="off"
            />
          </label>
          <label className="text-xs text-muted-foreground">
            Primary model
            <input className={inputClass} value={primaryModel} onChange={(e) => setPrimaryModel(e.target.value)} />
          </label>
          <label className="text-xs text-muted-foreground">
            Embedding model
            <input className={inputClass} value={embeddingModel} onChange={(e) => setEmbeddingModel(e.target.value)} />
          </label>
          <label className="text-xs text-muted-foreground">
            Temperature
            <input className={inputClass} value={temperature} onChange={(e) => setTemperature(e.target.value)} />
          </label>
          <label className="text-xs text-muted-foreground">
            Max output tokens
            <input className={inputClass} value={maxTokens} onChange={(e) => setMaxTokens(e.target.value)} />
          </label>
          <label className="text-xs text-muted-foreground">
            Severity threshold
            <select className={inputClass} value={severity} onChange={(e) => setSeverity(e.target.value)}>
              {["critical", "high", "medium", "low", "informational"].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-muted-foreground">
            Confidence threshold
            <input className={inputClass} value={confidence} onChange={(e) => setConfidence(e.target.value)} />
          </label>
          <label className="text-xs text-muted-foreground">
            Monthly budget (USD)
            <input className={inputClass} value={budget} onChange={(e) => setBudget(e.target.value)} />
          </label>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={autoReview}
              onChange={(e) => setAutoReview(e.target.checked)}
            />
            Org auto-review enabled
          </label>
          <label className="text-xs text-muted-foreground">
            Max files per review
            <input className={inputClass} value={maxFiles} onChange={(e) => setMaxFiles(e.target.value)} />
          </label>
          <label className="text-xs text-muted-foreground">
            Context retrieval limit
            <input className={inputClass} value={contextLimit} onChange={(e) => setContextLimit(e.target.value)} />
          </label>

          <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
            <Button onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save settings"}
            </Button>
            <Button
              variant="outline"
              onClick={() => validate.mutate()}
              disabled={validate.isPending}
            >
              {validate.isPending ? "Testing…" : "Test connection"}
            </Button>
            {message ? <p className="text-xs text-muted-foreground">{message}</p> : null}
          </div>
        </CardContent>
      </Card>
    </Shell>
  );
}
