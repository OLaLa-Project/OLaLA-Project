const $ = (id) => document.getElementById(id);

const traceIdEl = $("traceId");
const timelineEl = $("timeline");
const stageOutputsEl = $("stageOutputs");
const finalResultEl = $("finalResult");
const errorBoxEl = $("errorBox");
const rawLogsEl = $("rawLogs");
const diffBoxEl = $("diffBox");
const compareBtn = $("compareBtn");
const inputErrorEl = $("inputError");

const inputTypeEl = $("inputType");
const urlRowEl = $("urlRow");
const textRowEl = $("textRow");
const urlInputEl = $("urlInput");
const textInputEl = $("textInput");

let lastRun = null;

const STAGES = [
  "stage01_normalize",
  "stage02_querygen",
  "adapter_queries",
  "stage03_collect",
  "stage04_score",
  "stage05_topk",
  "stage06_verify_support",
  "stage07_verify_skeptic",
  "stage08_aggregate",
  "stage09_judge",
];

function syncInputType() {
  const inputType = inputTypeEl.value;
  if (inputType === "url") {
    urlRowEl.classList.remove("hidden");
    textRowEl.classList.add("hidden");
  } else {
    urlRowEl.classList.add("hidden");
    textRowEl.classList.remove("hidden");
  }
}

function buildRequest() {
  const inputType = inputTypeEl.value;
  const url = urlInputEl.value.trim();
  const text = textInputEl.value.trim();
  const requestText = $("requestInput").value.trim();
  const apiBase = $("apiBaseInput").value.trim().replace(/\/$/, "");
  const asOf = $("asOfInput").value.trim();
  const language = $("languageInput").value.trim();
  const normalizeMode = $("normalizeModeInput").value;
  const querygenPrompt = $("querygenPromptInput").value.trim();
  const includeFullOutputs = $("includeFullOutputs").checked;

  if (inputType === "url" && !url) {
    inputErrorEl.textContent = "URL is required for input_type=url.";
    inputErrorEl.classList.remove("hidden");
    return null;
  }
  if (inputType === "text" && !text) {
    inputErrorEl.textContent = "Text input is required for input_type=text.";
    inputErrorEl.classList.remove("hidden");
    return null;
  }
  if (!apiBase) {
    inputErrorEl.textContent = "API Base URL is required.";
    inputErrorEl.classList.remove("hidden");
    return null;
  }

  inputErrorEl.classList.add("hidden");

  const payload = {
    input_type: inputType,
    input_payload: inputType === "url" ? url : text,
    user_request: requestText || null,
    as_of: asOf || null,
    language: language || "ko",
    start_stage: null,
    end_stage: null,
    querygen_prompt: querygenPrompt || null,
    normalize_mode: normalizeMode || null,
    stage_state: {},
    include_full_outputs: includeFullOutputs,
  };

  return { apiBase, payload };
}

function setTraceId(traceId) {
  traceIdEl.textContent = traceId || "-";
}

function renderTimeline(stageLogs) {
  timelineEl.innerHTML = "";
  const latestByStage = {};
  (stageLogs || []).forEach((log) => {
    latestByStage[log.stage] = log;
  });

  STAGES.forEach((stage) => {
    const item = document.createElement("div");
    const log = latestByStage[stage];
    item.className = "timeline-item";
    if (log?.event === "end") item.classList.add("success");
    if (log?.event === "error") item.classList.add("error");
    item.innerHTML = `
      <div>${stage}</div>
      <div>${log?.event || "pending"}</div>
    `;
    timelineEl.appendChild(item);
  });
}

function renderStageOutputs(outputs, fullOutputs, traceId) {
  stageOutputsEl.innerHTML = "";
  STAGES.forEach((stage) => {
    const detail = document.createElement("details");
    detail.open = false;
    const summary = document.createElement("summary");
    summary.textContent = `${stage} (trace: ${traceId || "-"})`;
    detail.appendChild(summary);

    const pre = document.createElement("pre");
    pre.className = "code";
    pre.textContent = JSON.stringify(outputs?.[stage] || {}, null, 2);
    detail.appendChild(pre);

    const full = fullOutputs?.[stage];
    if (full !== undefined) {
      const fullDetail = document.createElement("details");
      fullDetail.open = false;
      const fullSummary = document.createElement("summary");
      fullSummary.textContent = "full_output";
      fullDetail.appendChild(fullSummary);
      const fullPre = document.createElement("pre");
      fullPre.className = "code";
      fullPre.textContent = JSON.stringify(full || {}, null, 2);
      fullDetail.appendChild(fullPre);
      detail.appendChild(fullDetail);
    }

    stageOutputsEl.appendChild(detail);
  });
}

function renderFinalResult(stageOutputs, apiFinalVerdict, apiUserResult) {
  const stage9 = stageOutputs?.stage09_judge || {};
  const finalVerdict = apiFinalVerdict || stage9.final_verdict || {};
  const userResult = apiUserResult || stage9.user_result || {};
  const riskFlags = stage9.risk_flags || finalVerdict.risk_flags || [];

  finalResultEl.innerHTML = "";
  const label = finalVerdict?.label || "UNVERIFIED";
  const confidence = finalVerdict?.confidence ?? 0;
  const summary = finalVerdict?.summary || "";

  finalResultEl.innerHTML = `
    <div><strong>Label:</strong> ${label}</div>
    <div><strong>Confidence:</strong> ${confidence}</div>
    <div><strong>Summary:</strong> ${summary}</div>
    <div><strong>Risk Flags:</strong> ${riskFlags.length ? riskFlags.join(", ") : "-"}</div>
    <details>
      <summary>final_verdict JSON</summary>
      <pre class="code">${JSON.stringify(finalVerdict || {}, null, 2)}</pre>
    </details>
    <details>
      <summary>user_result JSON</summary>
      <pre class="code">${JSON.stringify(userResult || {}, null, 2)}</pre>
    </details>
  `;
}

function renderError(errorMessage, logs, traceId) {
  if (!errorMessage) {
    errorBoxEl.classList.add("hidden");
    return;
  }
  errorBoxEl.classList.remove("hidden");
  errorBoxEl.innerHTML = `
    <div><strong>Error:</strong> ${errorMessage}</div>
    <div><strong>Trace:</strong> ${traceId}</div>
  `;
  rawLogsEl.textContent = JSON.stringify(logs || [], null, 2);
}

function persistRun(key, data) {
  localStorage.setItem(key, JSON.stringify(data));
}

function loadRun(key) {
  const raw = localStorage.getItem(key);
  return raw ? JSON.parse(raw) : null;
}

function normalizeCitations(citations) {
  return (citations || []).map((c) => ({
    evid_id: c.evid_id ?? c.id ?? null,
    title: c.title ?? null,
    url: c.url ?? null,
    score: c.score ?? null,
  }));
}

function pickStage5(stageOutputs) {
  const stage5 = stageOutputs?.stage05_topk || {};
  return {
    citations: normalizeCitations(stage5.citations || []),
  };
}

function pickStage8(stageOutputs) {
  const stage8 = stageOutputs?.stage08_aggregate || {};
  const draft = stage8.draft_verdict || {};
  return {
    stance: draft.stance ?? null,
    confidence: draft.confidence ?? null,
    quality_score: stage8.quality_score ?? null,
    citations_len: (draft.citations || []).length,
  };
}

function pickStage9(stageOutputs, apiFinalVerdict) {
  const stage9 = stageOutputs?.stage09_judge || {};
  const finalVerdict = apiFinalVerdict || stage9.final_verdict || {};
  return {
    label: finalVerdict.label ?? null,
    confidence: finalVerdict.confidence ?? null,
    risk_flags: finalVerdict.risk_flags ?? stage9.risk_flags ?? [],
    summary: finalVerdict.summary ?? null,
  };
}

function renderDiff(current, previous) {
  diffBoxEl.innerHTML = "";
  if (!previous) {
    diffBoxEl.textContent = "No previous run for this input.";
    return;
  }

  const diffs = [];

  const stage5Prev = pickStage5(previous.stage_outputs);
  const stage5Curr = pickStage5(current.stage_outputs);
  if (JSON.stringify(stage5Prev) !== JSON.stringify(stage5Curr)) {
    diffs.push({ stage: "stage05_topk", before: stage5Prev, after: stage5Curr });
  }

  const stage8Prev = pickStage8(previous.stage_outputs);
  const stage8Curr = pickStage8(current.stage_outputs);
  if (JSON.stringify(stage8Prev) !== JSON.stringify(stage8Curr)) {
    diffs.push({ stage: "stage08_aggregate", before: stage8Prev, after: stage8Curr });
  }

  const stage9Prev = pickStage9(previous.stage_outputs, previous.final_verdict);
  const stage9Curr = pickStage9(current.stage_outputs, current.final_verdict);
  if (JSON.stringify(stage9Prev) !== JSON.stringify(stage9Curr)) {
    diffs.push({ stage: "stage09_judge", before: stage9Prev, after: stage9Curr });
  }

  if (diffs.length === 0) {
    diffBoxEl.textContent = "No changes detected.";
    return;
  }

  diffs.forEach((item) => {
    const row = document.createElement("div");
    row.className = "diff-item";
    row.textContent = `${item.stage}: ${JSON.stringify(item.before)} -> ${JSON.stringify(item.after)}`;
    diffBoxEl.appendChild(row);
  });
}

async function run() {
  const req = buildRequest();
  if (!req) return;

  const key = [
    req.payload.input_type,
    req.payload.input_payload,
    req.payload.user_request || "",
    req.payload.as_of || "",
    req.payload.language || "",
    req.payload.normalize_mode || "",
    req.payload.querygen_prompt || "",
  ].join("||");

  const previous = loadRun(key);

  compareBtn.disabled = true;
  diffBoxEl.textContent = "";
  setTraceId("-");
  timelineEl.innerHTML = "";
  stageOutputsEl.innerHTML = "";
  finalResultEl.innerHTML = "";
  errorBoxEl.classList.add("hidden");
  rawLogsEl.textContent = "";

  try {
    const res = await fetch(`${req.apiBase}/truth/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.payload),
    });
    const data = await res.json();
    lastRun = data;

    const traceId = data.analysis_id || data.trace_id || "-";
    setTraceId(traceId);
    renderTimeline(data.stage_logs);
    renderStageOutputs(data.stage_outputs || {}, data.stage_full_outputs || {}, traceId);
    renderFinalResult(data.stage_outputs || {}, data.final_verdict, data.user_result);
    renderError(res.ok ? "" : data.message || "API error", data.stage_logs, traceId);

    persistRun(key, {
      stage_outputs: data.stage_outputs || {},
      final_verdict: data.final_verdict || null,
    });

    compareBtn.disabled = false;
    compareBtn.onclick = () => renderDiff(
      { stage_outputs: data.stage_outputs || {}, final_verdict: data.final_verdict || null },
      previous
    );
  } catch (err) {
    renderError(err.message, [], "-");
  }
}

inputTypeEl.addEventListener("change", syncInputType);
$("runBtn").addEventListener("click", run);

syncInputType();
