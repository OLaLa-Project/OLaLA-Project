import { useEffect, useRef, useState } from "react";

type SlotStatus = "idle" | "running" | "done" | "error";

type SlotMetrics = {
  total_ms?: number;
  load_ms?: number;
  prompt_tokens?: number;
  prompt_eval_ms?: number;
  gen_tokens?: number;
  gen_eval_ms?: number;
};

type Slot = {
  id: string;
  model: string;
  response: string;
  status: SlotStatus;
  error?: string;
  metrics?: SlotMetrics;
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function apiGet(path: string) {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} failed`);
  return res.json();
}

async function streamGenerate(
  model: string,
  prompt: string,
  signal: AbortSignal,
  onDelta: (chunk: string) => void,
  onDone: (meta: any) => void
) {
  const res = await fetch(`${API_BASE}/api/generate-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, prompt }),
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
      if (data.error) throw new Error(data.error);
      if (data.response) onDelta(data.response);
      if (data.done) {
        onDone(data);
        return;
      }
    }
  }
}

function TeamAPage() {
  const [models, setModels] = useState<string[]>([]);
  const [psMap, setPsMap] = useState<Record<string, any>>({});
  const [prompt, setPrompt] = useState("");
  const [slots, setSlots] = useState<Slot[]>([
    { id: "slot-0", model: "", response: "", status: "idle" },
    { id: "slot-1", model: "", response: "", status: "idle" },
    { id: "slot-2", model: "", response: "", status: "idle" },
  ]);
  const controllerRef = useRef<Record<string, AbortController>>({});
  const slotCounter = useRef(3);
  const hasRunning = slots.some((slot) => slot.status === "running");
  const canSend = prompt.trim() && slots.some((slot) => slot.model.trim());

  useEffect(() => {
    loadModels();
    return () => abortAllControllers();
  }, []);

  useEffect(() => {
    if (!models.length) return;
    setSlots((prev) =>
      prev.map((slot, index) => {
        if (slot.model) return slot;
        return { ...slot, model: models[index] || models[0] };
      })
    );
  }, [models]);

  useEffect(() => {
    if (!hasRunning) return;
    loadOllamaPs();
    const timer = setInterval(loadOllamaPs, 2500);
    return () => clearInterval(timer);
  }, [hasRunning]);

  async function loadModels() {
    try {
      const data = await apiGet("/api/models");
      if (data.ok) {
        const list = (data.models || []).map((item: any) => item.name).filter(Boolean);
        setModels(list);
      }
    } catch (err) {
      setModels([]);
    }
  }

  async function loadOllamaPs() {
    try {
      const data = await apiGet("/api/ps");
      if (data.ok) {
        const next: Record<string, any> = {};
        (data.models || []).forEach((item: any) => {
          const name = item.name || item.model;
          if (name) next[name] = item;
        });
        setPsMap(next);
      }
    } catch (err) {
      setPsMap({});
    }
  }

  function updateSlot(id: string, patch: Partial<Slot>) {
    setSlots((prev) => prev.map((slot) => (slot.id === id ? { ...slot, ...patch } : slot)));
  }

  function appendResponse(id: string, chunk: string) {
    setSlots((prev) =>
      prev.map((slot) =>
        slot.id === id ? { ...slot, response: `${slot.response}${chunk}` } : slot
      )
    );
  }

  function addSlot() {
    const id = `slot-${slotCounter.current++}`;
    setSlots((prev) => [
      ...prev,
      { id, model: models[0] || "", response: "", status: "idle" },
    ]);
  }

  function removeSlot(id: string) {
    const controller = controllerRef.current[id];
    if (controller) controller.abort();
    delete controllerRef.current[id];
    setSlots((prev) => prev.filter((slot) => slot.id !== id));
  }

  function abortAllControllers() {
    Object.values(controllerRef.current).forEach((controller) => controller.abort());
    controllerRef.current = {};
  }

  function stopAll() {
    abortAllControllers();
    setSlots((prev) =>
      prev.map((slot) => ({ ...slot, status: "idle", error: "", metrics: undefined }))
    );
  }

  function clearAll() {
    setSlots((prev) =>
      prev.map((slot) => ({ ...slot, response: "", error: "", metrics: undefined }))
    );
  }

  function toMs(value?: number) {
    if (!value && value !== 0) return undefined;
    return Math.round(value / 1_000_000);
  }

  function parseMetrics(meta: any): SlotMetrics {
    return {
      total_ms: toMs(meta.total_duration),
      load_ms: toMs(meta.load_duration),
      prompt_tokens: meta.prompt_eval_count ?? undefined,
      prompt_eval_ms: toMs(meta.prompt_eval_duration),
      gen_tokens: meta.eval_count ?? undefined,
      gen_eval_ms: toMs(meta.eval_duration),
    };
  }

  function formatMs(value?: number) {
    if (value === undefined) return "--";
    return `${value} ms`;
  }

  function formatCount(value?: number) {
    if (value === undefined) return "--";
    return `${value}`;
  }

  function formatBytes(value?: number) {
    if (value === undefined || value === null) return "--";
    if (value === 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let size = value;
    let unit = 0;
    while (size >= 1024 && unit < units.length - 1) {
      size /= 1024;
      unit += 1;
    }
    return `${size.toFixed(size >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
  }

  async function runParallel() {
    const question = prompt.trim();
    if (!question) return;
    stopAll();
    setSlots((prev) =>
      prev.map((slot) => {
        if (!slot.model.trim()) {
          return {
            ...slot,
            status: "error",
            response: "",
            error: "model required",
            metrics: undefined,
          };
        }
        return { ...slot, status: "running", response: "", error: "", metrics: undefined };
      })
    );

    slots.forEach((slot) => {
      const model = slot.model.trim();
      if (!model) return;
      const controller = new AbortController();
      controllerRef.current[slot.id] = controller;
      streamGenerate(
        model,
        question,
        controller.signal,
        (chunk) => appendResponse(slot.id, chunk),
        (meta) => updateSlot(slot.id, { metrics: parseMetrics(meta) })
      )
        .then(() => {
          updateSlot(slot.id, { status: "done" });
        })
        .catch((err: any) => {
          if (err.name === "AbortError") {
            updateSlot(slot.id, { status: "idle", error: "stopped" });
          } else {
            updateSlot(slot.id, { status: "error", error: err.message });
          }
        })
        .finally(() => {
          delete controllerRef.current[slot.id];
        });
    });
  }

  return (
    <div className="team">
      <div className="team-header">
        <h2>Team A (Evidence Pipeline)</h2>
        <p>Stage 1~5</p>
      </div>
      <div className="team-grid">
        <section className="team-card">
          <h3>Focus</h3>
          <ul>
            <li>stage01_normalize</li>
            <li>stage02_querygen</li>
            <li>stage03_retrieve</li>
            <li>stage04_rerank</li>
            <li>stage05_topk</li>
          </ul>
        </section>
        <section className="team-card">
          <h3>Working Paths</h3>
          <div className="team-paths">
            <div>backend/app/stages/stage01_normalize</div>
            <div>backend/app/stages/stage02_querygen</div>
            <div>backend/app/stages/stage03_retrieve</div>
            <div>backend/app/stages/stage04_rerank</div>
            <div>backend/app/stages/stage05_topk</div>
          </div>
        </section>
      </div>

      <section className="team-stage">
        <div className="team-stage-header">
          <div>
            <h3>Stage 4 Parallel Model Test</h3>
            <p>Run multiple Ollama models in parallel on a single server.</p>
          </div>
          <div className="row">
            <button className="pill ghost" onClick={addSlot}>
              Add model
            </button>
            <button className="pill ghost" onClick={loadModels}>
              Refresh models
            </button>
            <button className="pill ghost" onClick={loadOllamaPs}>
              Refresh VRAM
            </button>
          </div>
        </div>

        <div className="team-stage-grid">
          <section className="team-stage-card team-stage-controls">
            <div className="card-head">
              <h4>Prompt</h4>
              <div className="row">
                <button className="pill ghost" onClick={clearAll}>
                  Clear outputs
                </button>
                <button className="pill ghost stop" onClick={stopAll} disabled={!hasRunning}>
                  Stop all
                </button>
                <button className="pill" onClick={runParallel} disabled={!canSend}>
                  Send all
                </button>
              </div>
            </div>
            <textarea
              className="textarea"
              placeholder="Claim, snippet, and a scoring rule..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
            <div className="hint">
              Stage 4: EvidenceScorer (claim + snippet -&gt; relevance score).
            </div>
          </section>

          {slots.map((slot) => {
            const statusLabel =
              slot.status === "running"
                ? "Running"
                : slot.status === "done"
                  ? "Done"
                  : slot.status === "error"
                    ? "Error"
                    : "Idle";
            const statusState =
              slot.status === "running"
                ? "busy"
                : slot.status === "error"
                  ? "down"
                  : slot.status === "done"
                    ? "ok"
                    : "idle";
            const psInfo = psMap[slot.model];
            const vramBytes =
              psInfo?.size_vram ?? psInfo?.vram_usage ?? psInfo?.size ?? undefined;
            const vramLabel = psInfo?.size_vram || psInfo?.vram_usage ? "VRAM" : "Size";
            return (
              <section className="team-stage-card" key={slot.id}>
                <div className="team-slot-head">
                  <h4>Model</h4>
                  <div className="team-slot-actions">
                    <span className="pill status" data-state={statusState}>
                      {statusLabel}
                    </span>
                    <button className="pill ghost" onClick={() => removeSlot(slot.id)}>
                      Remove
                    </button>
                  </div>
                </div>
                <input
                  className="input"
                  list="team-a-models"
                  placeholder="model:tag"
                  value={slot.model}
                  onChange={(e) => updateSlot(slot.id, { model: e.target.value })}
                />
                <div className="team-slot-meta">
                  {vramLabel}: <span>{formatBytes(vramBytes)}</span>
                </div>
                <div className="label">Response</div>
                <div className="output team-slot-output">{slot.response}</div>
                <div className="team-slot-metrics">
                  <div className="team-slot-metric">
                    <span>total</span>
                    <strong>{formatMs(slot.metrics?.total_ms)}</strong>
                  </div>
                  <div className="team-slot-metric">
                    <span>load</span>
                    <strong>{formatMs(slot.metrics?.load_ms)}</strong>
                  </div>
                  <div className="team-slot-metric">
                    <span>prompt tokens</span>
                    <strong>{formatCount(slot.metrics?.prompt_tokens)}</strong>
                  </div>
                  <div className="team-slot-metric">
                    <span>prompt eval</span>
                    <strong>{formatMs(slot.metrics?.prompt_eval_ms)}</strong>
                  </div>
                  <div className="team-slot-metric">
                    <span>gen tokens</span>
                    <strong>{formatCount(slot.metrics?.gen_tokens)}</strong>
                  </div>
                  <div className="team-slot-metric">
                    <span>gen eval</span>
                    <strong>{formatMs(slot.metrics?.gen_eval_ms)}</strong>
                  </div>
                </div>
                {slot.error ? <div className="team-slot-error">{slot.error}</div> : null}
              </section>
            );
          })}
        </div>
        <datalist id="team-a-models">
          {models.map((model) => (
            <option key={model} value={model} />
          ))}
        </datalist>
      </section>
    </div>
  );
}

export default TeamAPage;
