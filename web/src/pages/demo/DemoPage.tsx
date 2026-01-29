import { useEffect, useMemo, useRef, useState } from "react";

type MetricBag = Record<string, any>;

type Metrics = {
  system: MetricBag;
  api: MetricBag;
  ollama: MetricBag;
  gpu: MetricBag;
};

type Source = {
  idx: number;
  chunk_id?: number | null;
  title?: string | null;
  section?: string | null;
  score?: number | null;
  snippet?: string | null;
};

type RagSearchCandidate = {
  page_id: number;
  title: string;
};

type RagSearchMode = "fts" | "lexical" | "vector";

type RagSearchHit = {
  title: string;
  page_id: number;
  chunk_id: number;
  chunk_idx: number;
  content: string;
  cleaned_content?: string;
  snippet: string;
  dist: number;
};

type RagSearchResult = {
  question: string;
  candidates: RagSearchCandidate[];
  hits: RagSearchHit[];
  debug?: {
    keywords_used?: string[];
    normalized_query?: string;
  } | null;
  prompt_context?: string | null;
};

const envBase = (import.meta.env.VITE_API_BASE_URL || "").trim();
const inferredBase = `${window.location.protocol}//${window.location.hostname}:8000`;
const shouldOverride =
  envBase &&
  /(localhost|127\.0\.0\.1)/.test(envBase) &&
  !/(localhost|127\.0\.0\.1)/.test(window.location.hostname);
const API_BASE = (shouldOverride ? inferredBase : envBase || inferredBase).replace(/\/$/, "");

const recommended = [
  { name: "llama3.2:3b", note: "balanced" },
  { name: "qwen2.5:3b", note: "fast general" },
  { name: "gemma2:2b", note: "tiny" },
  { name: "phi3.5:3b", note: "reasoning" },
  { name: "deepseek-r1:1.5b", note: "compact" },
];

const RAG_TOPK = 6;
const RAG_MAX_CHARS = 4200;
const RAG_WINDOW = 2;
const RAG_PAGE_LIMIT = 8;
const RAG_EMBED_MISSING = true;
const RAG_MODES: { id: RagSearchMode; label: string }[] = [
  { id: "vector", label: "Vector" },
  { id: "fts", label: "FTS" },
  { id: "lexical", label: "Lexical" },
];

function formatBytes(bytes: number | null | undefined) {
  if (bytes === null || bytes === undefined) return "--";
  const gb = bytes / (1024 * 1024 * 1024);
  if (gb >= 1) return `${gb.toFixed(2)} GB`;
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(0)} MB`;
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) return "--";
  return `${Math.round(value)}%`;
}

async function apiGet(path: string) {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} failed`);
  return res.json();
}

async function apiPost(
  path: string,
  payload: unknown,
  options?: { signal?: AbortSignal }
) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: options?.signal,
  });
  if (!res.ok) throw new Error(`POST ${path} failed`);
  return res.json();
}

async function fetchRagSearch(
  question: string,
  searchMode: RagSearchMode,
  signal?: AbortSignal
): Promise<RagSearchResult> {
  const data = await apiPost("/api/wiki/search", {
    question,
    top_k: RAG_TOPK,
    window: RAG_WINDOW,
    page_limit: RAG_PAGE_LIMIT,
    embed_missing: RAG_EMBED_MISSING,
    search_mode: searchMode,
  }, { signal });

  if (Array.isArray(data?.candidates) && Array.isArray(data?.hits)) {
    return {
      question: data.question ?? question,
      candidates: data.candidates,
      hits: data.hits,
      debug: data.debug ?? null,
      prompt_context: data.prompt_context ?? null,
    };
  }

  const sources = Array.isArray(data?.sources) ? data.sources : [];
  const candidates = sources.map((s) => ({
    page_id: s.page_id,
    title: s.title,
  }));
  const hits = sources.map((s) => ({
    title: s.title,
    page_id: s.page_id,
    chunk_id: s.chunk_id ?? 0,
    chunk_idx: s.chunk_idx ?? 0,
    content: s.snippet || "",
    snippet: s.snippet || "",
    dist: typeof s.dist === "number" ? s.dist : 0,
  }));

  return {
    question: data.question ?? question,
    candidates,
    hits,
    debug: data.debug ?? null,
    prompt_context: data.prompt_context ?? null,
  };
}

function DemoPage() {
  const [statusOk, setStatusOk] = useState(false);
  const [version, setVersion] = useState("-");
  const [metrics, setMetrics] = useState<Metrics>({
    system: {},
    api: {},
    ollama: {},
    gpu: {},
  });
  const [models, setModels] = useState<any[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [modelInput, setModelInput] = useState("");
  const [activeModel, setActiveModel] = useState("");
  const [pullInput, setPullInput] = useState("");
  const [pullStatus, setPullStatus] = useState("");
  const [searchMode, setSearchMode] = useState<RagSearchMode>("vector");
  const [showPromptContext, setShowPromptContext] = useState(false);
  const [ollamaStatus, setOllamaStatus] = useState("");
  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [ragMeta, setRagMeta] = useState<any>(null);
  const [useRag, setUseRag] = useState(true);
  const [ragSearchResult, setRagSearchResult] = useState<RagSearchResult | null>(null);
  const [lastPrompt, setLastPrompt] = useState("");
  const [streaming, setStreaming] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);

  const modelMeta = useMemo(() => {
    const name = modelInput || selectedModel;
    const found = models.find((m) => m.name === name);
    if (!found) return null;
    const details = found.details || {};
    return {
      size: formatBytes(found.size),
      family: details.family || "-",
      params: details.parameter_size || "-",
      quant: details.quantization_level || "-",
    };
  }, [modelInput, selectedModel, models]);

  const activeDisplay = activeModel || modelInput || selectedModel || "-";

  useEffect(() => {
    refreshAll();
    const timer = setInterval(loadMetrics, 3000);
    return () => clearInterval(timer);
  }, []);

  async function loadHealth() {
    try {
      const data = await apiGet("/api/health");
      const ok = data.ok ?? data.status === "healthy";
      setStatusOk(!!ok);
      setVersion(data.version ? `version ${data.version}` : "-");
      return !!ok;
    } catch (err) {
      setStatusOk(false);
      setVersion("-");
      return false;
    }
  }

  async function loadModels() {
    const data = await apiGet("/api/models");
    if (!data.ok) throw new Error("models fetch failed");
    const list = data.models || [];
    setModels(list);
    if (list.length) {
      const first = list[0].name;
      setSelectedModel((prev) => prev || first);
      setModelInput((prev) => prev || first);
      setActiveModel((prev) => prev || first);
    }
  }

  async function loadMetrics() {
    try {
      const data = await apiGet("/api/metrics");
      if (data.ok) setMetrics(data);
    } catch (err) {
      setMetrics({
        system: {},
        api: {},
        ollama: {},
        gpu: { ok: false, note: "metrics unavailable" },
      });
    }
  }

  async function refreshAll() {
    const ok = await loadHealth();
    await loadMetrics();
    if (ok) {
      await loadModels();
    }
  }

  async function setOllamaState(action: "up" | "down") {
    setOllamaStatus(`${action === "up" ? "Starting" : "Stopping"} Ollama...`);
    try {
      await apiPost(`/api/ollama/${action}`, {});
      await loadHealth();
      await loadMetrics();
      setOllamaStatus(`Ollama ${action === "up" ? "started" : "stopped"}`);
    } catch (err: any) {
      setOllamaStatus(`Ollama ${action} failed: ${err.message}`);
    }
  }

  function getActiveModel() {
    return activeModel || modelInput || selectedModel;
  }

  async function streamRag(model: string, question: string, signal: AbortSignal) {
    const pageIds = ragSearchResult?.candidates?.map((c) => c.page_id) || undefined;
    const res = await fetch(`${API_BASE}/api/wiki/rag-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        question,
        top_k: RAG_TOPK,
        max_chars: RAG_MAX_CHARS,
        page_ids: pageIds,
        search_mode: searchMode,
      }),
      signal,
    });
    if (!res.ok || !res.body) {
      let message = `HTTP ${res.status}`;
      try {
        const data = await res.json();
        if (data && data.error) message = data.error;
      } catch (err) {
        try {
          const text = await res.text();
          if (text) message = text.slice(0, 200);
        } catch (err2) {
          message = "stream failed";
        }
      }
      throw new Error(message);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        let data;
        try {
          data = JSON.parse(trimmed);
        } catch (err) {
          continue;
        }
        if (data.type === "sources") {
          setSources(data.sources || []);
          setRagMeta(data.meta || null);
          continue;
        }
        if (data.response) setResponse((prev) => prev + data.response);
        if (data.done) return;
      }
    }
  }

  async function streamGenerate(model: string, question: string, signal: AbortSignal) {
    const res = await fetch(`${API_BASE}/api/generate-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, prompt: question }),
      signal,
    });
    if (!res.ok || !res.body) {
      let message = `HTTP ${res.status}`;
      try {
        const data = await res.json();
        if (data && data.error) message = data.error;
      } catch (err) {
        try {
          const text = await res.text();
          if (text) message = text.slice(0, 200);
        } catch (err2) {
          message = "stream failed";
        }
      }
      throw new Error(message);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        let data;
        try {
          data = JSON.parse(trimmed);
        } catch (err) {
          continue;
        }
        if (data.response) setResponse((prev) => prev + data.response);
        if (data.done) return;
      }
    }
  }

  async function sendPrompt() {
    if (streaming) return;
    const model = getActiveModel();
    const question = prompt.trim();
    if (!model || !question) return;
    if (controllerRef.current) controllerRef.current.abort();
    controllerRef.current = new AbortController();
    setResponse("");
    setSources([]);
    setRagMeta(useRag ? null : { mode: "disabled", hits: 0 });
    setStreaming(true);
    setLastPrompt(question);
    setRagSearchResult(null);
    setShowPromptContext(false);
    try {
      if (useRag) {
        try {
          const searchResult = await fetchRagSearch(
            question,
            searchMode,
            controllerRef.current.signal
          );
          setRagSearchResult(searchResult);
        } catch (err) {
          setRagSearchResult(null);
        }
        await streamRag(model, question, controllerRef.current.signal);
      } else {
        await streamGenerate(model, question, controllerRef.current.signal);
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        setResponse((prev) => `${prev}\n[Stopped]`);
      } else {
        setResponse(`Error: ${err.message}`);
      }
    } finally {
      setStreaming(false);
      controllerRef.current = null;
    }
  }

  async function warmModel() {
    const model = getActiveModel();
    if (!model) return;
    try {
      await apiPost("/api/warm", { model });
    } catch (err: any) {
      setPullStatus(`Warm failed: ${err.message}`);
    }
  }

  async function pullModelStream(model: string) {
    const res = await fetch(`${API_BASE}/api/pull-stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: model }),
    });
    if (!res.ok || !res.body) throw new Error("pull stream failed");
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        let data;
        try {
          data = JSON.parse(trimmed);
        } catch (err) {
          continue;
        }
        if (data.error) throw new Error(data.error);
        const status = data.status || "";
        if (data.total && data.completed) {
          const pct = Math.round((data.completed / data.total) * 100);
          setPullStatus(
            `${status} ${formatBytes(data.completed)} / ${formatBytes(data.total)} (${pct}%)`
          );
        } else if (status) {
          setPullStatus(status);
        }
      }
    }
  }

  async function pullModel(name: string) {
    const model = (name || pullInput || "").trim();
    if (!model) return;
    setPullStatus(`Pulling ${model}...`);
    try {
      await pullModelStream(model);
      setPullStatus(`Pull complete: ${model}`);
      await loadModels();
      setModelInput(model);
      setSelectedModel(model);
      setActiveModel(model);
    } catch (err: any) {
      setPullStatus(`Pull failed: ${err.message}`);
    }
  }

  const system = metrics.system || {};
  const api = metrics.api || {};
  const ollama = metrics.ollama || {};
  const gpu = metrics.gpu || {};
  const ramPercent = system.percent || 0;
  const isGpuOk = !!gpu.ok;
  const gpuNote = gpu.note || "not wired";
  const gpuUtil = gpu.util !== null && gpu.util !== undefined ? gpu.util : null;
  const memUsed = gpu.mem_used;
  const memTotal = gpu.mem_total;
  const memPercent = memTotal ? Math.round(((memUsed || 0) / memTotal) * 100) : 0;
  const sendDisabled = streaming || !prompt.trim() || !getActiveModel();

  return (
    <main className="grid">
      <section className="card metric-card">
        <div className="card-head">
          <h3>System RAM</h3>
          <div className="metric-badge">{formatPercent(system.percent)}</div>
        </div>
        <div className="metric-value">
          {formatBytes(system.used)} / {formatBytes(system.total)}
        </div>
        <div className="metric-note">available: {formatBytes(system.available)}</div>
        <div className="metric-line">
          cpu <span>{formatPercent(system.cpu_percent)}</span>
        </div>
        <div className="progress">
          <div className="progress-bar" style={{ width: `${ramPercent}%` }}></div>
        </div>
      </section>

      <section className="card metric-card">
        <div className="card-head">
          <h3>API process</h3>
        </div>
        <div className="metric-line">
          pid <span>{api.pid ?? "--"}</span>
        </div>
        <div className="metric-line">
          cpu <span>{api.cpu !== null && api.cpu !== undefined ? `${api.cpu.toFixed(1)}%` : "--"}</span>
        </div>
        <div className="metric-line">
          rss <span>{formatBytes(api.rss)}</span>
        </div>
      </section>

      <section className="card metric-card">
        <div className="card-head">
          <h3>Ollama RAM (RSS)</h3>
          <div className="metric-badge">{(ollama.pids || []).length} pid</div>
        </div>
        <div className="metric-value">{formatBytes(ollama.rss)}</div>
        <div className="metric-note">{statusOk ? "Online" : "Offline"}</div>
        <div className="metric-note">{version}</div>
        <div className="row">
          <button className="pill ghost" onClick={() => setOllamaState("down")}>
            Ollama down
          </button>
          <button className="pill ghost" onClick={() => setOllamaState("up")}>
            Ollama up
          </button>
        </div>
        <div className="hint">{ollamaStatus || "per-process view later"}</div>
      </section>

      <section className="card metric-card">
        <div className="card-head">
          <h3>GPU</h3>
        </div>
        <div className="metric-note">{isGpuOk ? "nvidia-smi" : gpuNote}</div>
        <div className="metric-line">
          name <span>{gpu.name || "--"}</span>
        </div>
        <div className="usage">
          <div className="usage-line">
            <span>util</span>
            <span>{gpuUtil !== null ? `${gpuUtil}%` : "--"}</span>
          </div>
          <div className="usage-bar">
            <div className="usage-fill" style={{ width: `${gpuUtil || 0}%` }}></div>
          </div>
          <div className="usage-line">
            <span>mem</span>
            <span>{memTotal ? `${memUsed || 0} MB / ${memTotal} MB` : "--"}</span>
          </div>
          <div className="usage-bar">
            <div className="usage-fill" style={{ width: `${memPercent}%` }}></div>
          </div>
        </div>
      </section>

      <section className="card model">
        <div className="card-head">
          <h3>Model</h3>
          <button className="pill warm" onClick={warmModel}>
            Warm
          </button>
        </div>
        <label className="label">Installed</label>
        <select
          className="input"
          value={selectedModel}
          onChange={(e) => {
            setSelectedModel(e.target.value);
            setModelInput(e.target.value);
          }}
        >
          {models.map((m) => (
            <option key={m.name} value={m.name}>
              {m.name}
            </option>
          ))}
        </select>

        <label className="label">Or type</label>
        <input
          className="input"
          placeholder="model:tag"
          value={modelInput}
          onChange={(e) => setModelInput(e.target.value)}
        />
        <div className="row">
          <button className="pill" onClick={() => setActiveModel(modelInput || selectedModel)}>
            Use
          </button>
          <div className="active-pill">
            Active: <span>{activeDisplay}</span>
          </div>
        </div>

        <div className="meta">
          {modelMeta ? (
            <>
              <div>size: {modelMeta.size}</div>
              <div>family: {modelMeta.family}</div>
              <div>params: {modelMeta.params}</div>
              <div>quant: {modelMeta.quant}</div>
            </>
          ) : (
            <div>-</div>
          )}
        </div>

        <label className="label">Pull model</label>
        <div className="row">
          <input
            className="input"
            placeholder="llama3.2:3b"
            value={pullInput}
            onChange={(e) => setPullInput(e.target.value)}
          />
          <button className="pill" onClick={() => pullModel("")}>Pull</button>
        </div>
        <div className="hint">{pullStatus}</div>

        <div className="divider"></div>
        <div className="label">Recommended (one click)</div>
        <div className="recommend">
          {recommended.map((item) => {
            const installed = models.some((m) => m.name === item.name);
            return (
              <div className="recommend-item" key={item.name}>
                <div className="recommend-title">{item.name}</div>
                <div className="hint">
                  {item.note} {installed ? "(installed)" : ""}
                </div>
                <div className="recommend-actions">
                  <button
                    className="pill ghost"
                    onClick={() => {
                      setModelInput(item.name);
                      setSelectedModel(item.name);
                      setActiveModel(item.name);
                    }}
                  >
                    Use
                  </button>
                  <button className="pill" onClick={() => pullModel(item.name)}>
                    Pull
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="card prompt">
        <div className="card-head">
          <h3>Prompt</h3>
          <div className="row">
            <label className="toggle">
              <input
                type="checkbox"
                checked={useRag}
                onChange={(e) => setUseRag(e.target.checked)}
              />
              <span className="toggle-track"></span>
              <span className="toggle-label">RAG</span>
            </label>
            <div className="row">
              {RAG_MODES.map((mode) => (
                <button
                  key={mode.id}
                  className={`pill ${searchMode === mode.id ? "" : "ghost"}`}
                  onClick={() => setSearchMode(mode.id)}
                  disabled={!useRag}
                  type="button"
                >
                  {mode.label}
                </button>
              ))}
              <div className="hint">
                mode: {useRag ? searchMode : "off"}
              </div>
            </div>
            <button
              className="pill ghost"
              onClick={() => {
                setPrompt("");
                setResponse("");
                setSources([]);
                setRagMeta(null);
              }}
            >
              Clear
            </button>
            <button
              className="pill ghost stop"
              onClick={() => controllerRef.current && controllerRef.current.abort()}
              disabled={!streaming}
            >
              Stop
            </button>
            <button className="pill" onClick={sendPrompt} disabled={sendDisabled}>
              Send
            </button>
          </div>
        </div>
        <textarea
          className="textarea"
          placeholder="Ask something small..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <div className="label">Response</div>
        <div className="output">{response}</div>
        <div className="label">Sources</div>
        <div className="sources">
          {useRag ? (
            sources.length ? (
              sources.map((s) => (
                <div className="source-item" key={`${s.idx}-${s.chunk_id}`}>
                  <div className="source-title">
                    [{s.idx}] {s.title || "-"}
                  </div>
                  <div className="source-meta">
                    {s.section || "-"} | chunk {s.chunk_id ?? "-"} | score{" "}
                    {s.score !== null && s.score !== undefined ? s.score.toFixed(4) : "-"}
                  </div>
                  <div className="source-snippet">{s.snippet || ""}</div>
                </div>
              ))
            ) : (
              <div className="hint">No sources yet</div>
            )
          ) : (
            <div className="hint">RAG is off</div>
          )}
        </div>
        <section className="card rag-search">
          <div className="card-head">
            <h3>RAG DB Search</h3>
            <div className="hint">Prompt used: {lastPrompt || "-"}</div>
          </div>
          {useRag ? (
            ragSearchResult ? (
              <>
                <div className="label">Question</div>
                <div className="hint">{ragSearchResult.question}</div>
                <div className="label">Search keywords</div>
                <div className="hint">
                  {(ragSearchResult.debug?.keywords_used?.length ?? 0)
                    ? ragSearchResult.debug?.keywords_used?.join(", ")
                    : "-"}
                </div>
                <div className="label">Candidates</div>
                <div className="sources">
                  {(ragSearchResult?.candidates?.length ?? 0) ? (
                    (ragSearchResult?.candidates ?? []).map((c) => (
                      <div className="source-item" key={`candidate-${c.page_id}`}>
                        <div className="source-title">{c.title}</div>
                        <div className="source-meta">page {c.page_id}</div>
                      </div>
                    ))
                  ) : (
                    <div className="hint">No candidates found</div>
                  )}
                </div>
                <div className="label">Hits</div>
                <div className="sources">
                  {(ragSearchResult?.hits?.length ?? 0) ? (
                    (ragSearchResult?.hits ?? []).map((hit) => (
                      <div className="source-item" key={`hit-${hit.page_id}-${hit.chunk_id}`}>
                        <div className="source-title">
                          {hit.title} | chunk {hit.chunk_idx}
                        </div>
                        <div className="source-meta">
                          page {hit.page_id} | dist{" "}
                          {typeof hit.dist === "number" ? hit.dist.toFixed(4) : "-"}
                        </div>
                        <div className="source-snippet">{hit.snippet}</div>
                        <div className="source-snippet" style={{ whiteSpace: "pre-wrap" }}>
                          {hit.content}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="hint">No hits returned</div>
                  )}
                </div>
                <div className="label">Prompt context (cleaned)</div>
                <div className="sources">
                  {ragSearchResult.prompt_context ? (
                    <>
                      <div className="row">
                        <button
                          className="pill ghost"
                          type="button"
                          onClick={() => setShowPromptContext((prev) => !prev)}
                        >
                          {showPromptContext ? "Hide prompt context" : "Show prompt context"}
                        </button>
                        <div className="hint">
                          chars: {ragSearchResult.prompt_context.length}
                        </div>
                      </div>
                      {showPromptContext ? (
                        <div className="source-item">
                          <div
                            className="source-snippet"
                            style={{ whiteSpace: "pre-wrap", maxHeight: 320, overflow: "auto" }}
                          >
                            {ragSearchResult.prompt_context}
                          </div>
                        </div>
                      ) : (
                        <div className="hint">Hidden</div>
                      )}
                    </>
                  ) : (
                    <div className="hint">No prompt context yet</div>
                  )}
                </div>
              </>
            ) : (
              <div className="hint">Search data will appear after the next RAG query</div>
            )
          ) : (
            <div className="hint">Enable RAG to start database retrieval</div>
          )}
        </section>
        <div className="rag-log">
          {useRag ? (
            ragMeta ? (
              <>
                <div>RAG mode: {ragMeta.mode || "-"}</div>
                <div>search_mode: {ragMeta.search_mode || "-"}</div>
                {ragMeta.lexical_mode ? <div>lexical_mode: {ragMeta.lexical_mode}</div> : null}
                <div>hits: {ragMeta.hits ?? "-"}</div>
                <div>top_k: {ragMeta.top_k ?? "-"}</div>
                <div>max_chars: {ragMeta.max_chars ?? "-"}</div>
                {ragMeta.ts_query ? <div>ts_query: {ragMeta.ts_query}</div> : null}
              </>
            ) : (
              <div className="hint">RAG log will appear after a query</div>
            )
          ) : (
            <div>RAG mode: disabled</div>
          )}
        </div>
      </section>
    </main>
  );
}

export default DemoPage;
