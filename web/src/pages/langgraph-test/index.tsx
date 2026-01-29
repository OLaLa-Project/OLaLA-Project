import { useMemo, useRef, useState, useEffect } from "react";

const TEAM_A_PROMPT_TEMPLATE = `너는 단순 요약기가 아니라, 기사 속 의도/논란의 소지를 파헤치는 ‘수석 팩트체커 + QueryGen(Stage2)’이다.
입력으로 주어진 title과 [SENTENCES]를 바탕으로,
(1) 기사 주제와 core_narrative를 작성하고,
(2) 검증이 필요한 핵심 claims 3개를 [SENTENCES]에서 “문장 그대로” 선택하며,
(3) 각 claim마다 verification_reason, time_sensitivity, 그리고 위키피디아 로컬 DB 조회용 쿼리(wiki_db)와 최신 뉴스 검색용 쿼리(news_search)를 생성하라.

[절대 규칙]
1) 출력은 오직 “유효한 JSON”만 허용한다. 마크다운, 주석, 코드펜스(\`\`\`)를 절대 포함하지 마라.
2) 아래 [SENTENCES]는 article_text를 문장 단위로 분해한 것이다.
3) claims[].주장 값은 반드시 [SENTENCES]의 문장 텍스트를 “완전히 동일하게” 그대로 복사해야 한다.
   - 글자 하나라도 바꾸면 실패다(띄어쓰기/따옴표/조사/숫자 포함).
   - 문장 일부만 발췌하지 말고, 반드시 ‘한 문장 전체’를 그대로 사용해라.
4) claims는 정확히 3개만 출력한다. claim_id는 C1, C2, C3 고정.
5) claim_type은 반드시 아래 중 하나로만 선택한다:
   - 사건 | 논리 | 통계 | 인용 | 정책
6) verification_reason는 “왜 이 문장이 핵심 논점/논란 포인트인지”를 맥락적으로 설명하되, 기사 밖의 새로운 사실을 만들어내지 마라.
7) time_sensitivity는 low|mid|high 중 하나로 지정한다.
   - high: 최신 논란/팬 반응/시즌 전망/최근 발언 등 시점 영향이 큰 것
   - low: 인물/팀/리그/제도처럼 시간 영향이 적은 것
8) query_pack 생성 규칙:
   8-1) wiki_db: 정확히 3개를 생성한다. 각 원소는 {"mode":"title|fulltext","q":"string"} 형식의 객체다.
        - 목적: ‘검증’이 아니라 로컬 위키에서 배경/정의/고정 사실(인물·팀·리그·대회·제도)을 찾기 위함.
        - title은 실제 문서 제목으로 존재할 가능성이 높은 엔터티(인물/팀/리그/대회/제도)를 우선한다.
        - fulltext는 개념/동의어/표기 변형을 포함해 검색 폭을 넓힌다.
        - 한국어 타이틀을 우선하고, 영문 표기는 필요 시 fulltext에 보조로 넣어라.
        - 이 기사처럼 위키 검증이 불필요한 claim이어도 wiki_db는 “배경 확보용”으로만 최소한으로 구성해라(예: 인물/팀/리그).
   8-2) news_search: 각 claim마다 정확히 4개 “문자열”을 생성한다. (객체/딕셔너리 금지)
        - 구성: (진위/공식 확인용 2개) + (반대/비교 데이터 탐색용 2개)
        - 필요 시 연도/시점, 공식 출처 키워드(구단 발표, KBO 공식 기록, 인터뷰 원문 등)를 포함한다.
9) JSON 스키마를 반드시 지켜라.

[출력 스키마]
{
  "주제": "string",
  "core_narrative": "string",
  "claims": [
    {
      "claim_id": "C1",
      "주장": "string",
      "claim_type": "사건|논리|통계|인용|정책",
      "verification_reason": "string",
      "time_sensitivity": "low|mid|high",
      "query_pack": {
        "wiki_db": [
          {"mode":"title|fulltext","q":"string"},
          {"mode":"title|fulltext","q":"string"},
          {"mode":"title|fulltext","q":"string"}
        ],
        "news_search": ["string","string","string","string"]
      }
    },
    {
      "claim_id": "C2",
      "주장": "string",
      "claim_type": "사건|논리|통계|인용|정책",
      "verification_reason": "string",
      "time_sensitivity": "low|mid|high",
      "query_pack": {
        "wiki_db": [
          {"mode":"title|fulltext","q":"string"},
          {"mode":"title|fulltext","q":"string"},
          {"mode":"title|fulltext","q":"string"}
        ],
        "news_search": ["string","string","string","string"]
      }
    },
    {
      "claim_id": "C3",
      "주장": "string",
      "claim_type": "사건|논리|통계|인용|정책",
      "verification_reason": "string",
      "time_sensitivity": "low|mid|high",
      "query_pack": {
        "wiki_db": [
          {"mode":"title|fulltext","q":"string"},
          {"mode":"title|fulltext","q":"string"},
          {"mode":"title|fulltext","q":"string"}
        ],
        "news_search": ["string","string","string","string"]
      }
    }
  ]
}

[INPUT]
user_request: "{{user_request}}"
title: "{{title}}"
article_text:
{{article_text}}
[/INPUT]
`;

type TruthCheckRequest = {
  input_type: "text" | "url";
  input_payload: string;
  user_request: string;
  language: string;
  start_stage?: string;
  end_stage?: string;
  querygen_prompt?: string;
  normalize_mode?: "llm" | "basic";
  stage_state?: Record<string, any>;
  include_full_outputs?: boolean;
};

const envBase = (import.meta.env.VITE_API_BASE_URL || "").trim();
const inferredBase = `${window.location.protocol}//${window.location.hostname}:8000`;
const shouldOverride =
  envBase &&
  /(localhost|127\\.0\\.0\\.1)/.test(envBase) &&
  !/(localhost|127\\.0\\.0\\.1)/.test(window.location.hostname);
const API_BASE = (shouldOverride ? inferredBase : envBase || inferredBase).replace(/\/$/, "");

async function apiPost(path: string, payload: unknown) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const text = await res.text();
  return { ok: res.ok, status: res.status, text };
}

export default function LangGraphTestPage() {
  const [inputType, setInputType] = useState<"text" | "url">("text");
  const [inputPayload, setInputPayload] = useState(
    "인텔이 18A 공정 기반 AI PC를 공개했다."
  );
  const [userRequest, setUserRequest] = useState("");
  const [language, setLanguage] = useState("ko");
  const [startStage, setStartStage] = useState("stage01_normalize");
  const [endStage, setEndStage] = useState("stage05_topk");
  const [useQuerygenPrompt, setUseQuerygenPrompt] = useState(false);
  const [querygenPrompt, setQuerygenPrompt] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [raw, setRaw] = useState("");
  const [parsed, setParsed] = useState<any | null>(null);
  const [status, setStatus] = useState<number | null>(null);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const [stage1InputType, setStage1InputType] = useState<"text" | "url">("text");
  const [stage1Input, setStage1Input] = useState("");
  const [stage1NormalizeMode, setStage1NormalizeMode] = useState<"llm" | "basic">("llm");
  const [stage1Raw, setStage1Raw] = useState("");
  const [stage1Parsed, setStage1Parsed] = useState<any | null>(null);
  const [stage1Status, setStage1Status] = useState<number | null>(null);
  const [stage1Error, setStage1Error] = useState("");
  const [stage2Input, setStage2Input] = useState("");
  const [stage2NormalizeMode, setStage2NormalizeMode] = useState<"llm" | "basic">("llm");
  const [stage2UsePrompt, setStage2UsePrompt] = useState(false);
  const [stage2Prompt, setStage2Prompt] = useState("");
  const [stage2AutoFromStage1, setStage2AutoFromStage1] = useState(true);
  const [stage2Raw, setStage2Raw] = useState("");
  const [stage2Parsed, setStage2Parsed] = useState<any | null>(null);
  const [stage2Status, setStage2Status] = useState<number | null>(null);
  const [stage2Error, setStage2Error] = useState("");
  const [stage3Raw, setStage3Raw] = useState("");
  const [stage3Parsed, setStage3Parsed] = useState<any | null>(null);
  const [stage3Status, setStage3Status] = useState<number | null>(null);
  const [stage3Error, setStage3Error] = useState("");
  const [stage4Raw, setStage4Raw] = useState("");
  const [stage4Parsed, setStage4Parsed] = useState<any | null>(null);
  const [stage4Status, setStage4Status] = useState<number | null>(null);
  const [stage4Error, setStage4Error] = useState("");
  const [stage5Raw, setStage5Raw] = useState("");
  const [stage5Parsed, setStage5Parsed] = useState<any | null>(null);
  const [stage5Status, setStage5Status] = useState<number | null>(null);
  const [stage5Error, setStage5Error] = useState("");

  const stage1OutputText = useMemo(() => {
    const out = stage1Parsed?.stage_outputs?.stage01_normalize;
    if (out?.claim_text) return String(out.claim_text);
    if (out?.canonical_evidence?.snippet) return String(out.canonical_evidence.snippet);
    return stage1Input;
  }, [stage1Parsed, stage1Input]);

  useEffect(() => {
    if (!stage2AutoFromStage1) return;
    if (!stage2Input.trim() && stage1OutputText.trim()) {
      setStage2Input(stage1OutputText);
    }
  }, [stage2AutoFromStage1, stage1OutputText, stage2Input]);

  const payload = useMemo<TruthCheckRequest>(
    () => ({
      input_type: inputType,
      input_payload: inputPayload,
      user_request: userRequest,
      language,
      start_stage: startStage,
      end_stage: endStage,
      querygen_prompt: useQuerygenPrompt ? querygenPrompt : undefined,
    }),
    [
      inputType,
      inputPayload,
      userRequest,
      language,
      startStage,
      endStage,
      useQuerygenPrompt,
      querygenPrompt,
    ]
  );

  const prettyPayload = useMemo(() => JSON.stringify(payload, null, 2), [payload]);
  const displayPayload = useMemo(() => {
    const { querygen_prompt, ...rest } = payload;
    return JSON.stringify(rest, null, 2);
  }, [payload]);
  const prettyParsed = useMemo(
    () => (parsed ? JSON.stringify(parsed, null, 2) : ""),
    [parsed]
  );
  const prettyLogs = useMemo(() => {
    if (!parsed || !parsed.stage_logs) return "";
    return JSON.stringify(parsed.stage_logs, null, 2);
  }, [parsed]);

  const stageOutputKeys = useMemo(() => {
    if (!parsed || !parsed.stage_outputs) return [];
    return Object.keys(parsed.stage_outputs);
  }, [parsed]);
  const [selectedStage, setSelectedStage] = useState<string>("");
  const prettyStageOutput = useMemo(() => {
    if (!parsed || !parsed.stage_outputs) return "";
    const key = selectedStage || stageOutputKeys[stageOutputKeys.length - 1];
    if (!key) return "";
    return JSON.stringify(parsed.stage_outputs[key], null, 2);
  }, [parsed, selectedStage, stageOutputKeys]);

  const stage2WikiQueries = useMemo(() => {
    if (!stage2Parsed?.stage_outputs?.stage02_querygen) return [];
    const s2 = stage2Parsed.stage_outputs.stage02_querygen;
    const queries: string[] = [];
    if (Array.isArray(s2.querygen_claims)) {
      for (const claim of s2.querygen_claims) {
        const wikiDb = claim?.query_pack?.wiki_db;
        if (Array.isArray(wikiDb)) {
          for (const item of wikiDb) {
            if (item?.q) queries.push(String(item.q));
          }
        }
      }
    }
    if (queries.length) return Array.from(new Set(queries));
    const samples = s2?.query_variants?.sample;
    if (Array.isArray(samples)) {
      for (const v of samples) {
        if (v?.type === "wiki" && v?.text) queries.push(String(v.text));
      }
    }
    return Array.from(new Set(queries));
  }, [stage2Parsed]);

  async function runTest() {
    setRunning(true);
    setStreaming(true);
    setError("");
    setRaw("");
    setParsed(null);
    setStatus(null);
    try {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const res = await fetch(`${API_BASE}/truth/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      setStatus(res.status);

      const reader = res.body?.getReader();
      if (!reader) {
        const text = await res.text();
        setRaw(text);
        try {
          setParsed(JSON.parse(text));
        } catch {
          setParsed(null);
        }
        if (!res.ok) setError(`HTTP ${res.status}`);
        return;
      }

      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        setRaw(buffer);
        try {
          setParsed(JSON.parse(buffer));
        } catch {
          // keep streaming until valid JSON
        }
      }
      if (!res.ok) setError(`HTTP ${res.status}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
      setStreaming(false);
    }
  }

  function clearAll() {
    abortRef.current?.abort();
    setInputPayload("");
    setUserRequest("");
    setRaw("");
    setParsed(null);
    setError("");
    setStatus(null);
    setStreaming(false);
  }

  async function runStage1() {
    setStage1Error("");
    setStage1Raw("");
    setStage1Parsed(null);
    setStage1Status(null);
    try {
      const res = await fetch(`${API_BASE}/truth/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_type: stage1InputType,
          input_payload: stage1Input,
          user_request: "",
          language: "ko",
          start_stage: "stage01_normalize",
          end_stage: "stage01_normalize",
          normalize_mode: stage1NormalizeMode,
        }),
      });
      setStage1Status(res.status);
      const text = await res.text();
      setStage1Raw(text);
      try {
        setStage1Parsed(JSON.parse(text));
      } catch {
        setStage1Parsed(null);
      }
      if (!res.ok) setStage1Error(`HTTP ${res.status}`);
    } catch (err) {
      setStage1Error(err instanceof Error ? err.message : String(err));
    }
  }

  async function runStage2() {
    setStage2Error("");
    setStage2Raw("");
    setStage2Parsed(null);
    setStage2Status(null);
    try {
      const stage1Out = stage1Parsed?.stage_outputs?.stage01_normalize;
      const inputPayload = stage2AutoFromStage1 && stage1OutputText.trim()
        ? stage1OutputText
        : stage2Input.trim()
          ? stage2Input
          : stage1Input;
      if (!inputPayload.trim() && !(stage2AutoFromStage1 && stage1Out)) {
        setStage2Error("Stage2 input이 비어있습니다. Stage1 실행 또는 입력값을 넣어주세요.");
        return;
      }
      const res = await fetch(`${API_BASE}/truth/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_type: "text",
          input_payload: inputPayload,
          user_request: "",
          language: "ko",
          start_stage: "stage01_normalize",
          end_stage: "stage02_querygen",
          querygen_prompt: stage2UsePrompt ? stage2Prompt : undefined,
          normalize_mode: stage2NormalizeMode,
          stage_state: stage2AutoFromStage1 && stage1Out ? stage1Out : undefined,
        }),
      });
      setStage2Status(res.status);
      const text = await res.text();
      setStage2Raw(text);
      try {
        setStage2Parsed(JSON.parse(text));
      } catch {
        setStage2Parsed(null);
      }
      if (!res.ok) setStage2Error(`HTTP ${res.status}`);
    } catch (err) {
      setStage2Error(err instanceof Error ? err.message : String(err));
    }
  }

  async function runStage3() {
    setStage3Error("");
    setStage3Raw("");
    setStage3Parsed(null);
    setStage3Status(null);
    try {
      const stage2Out = stage2Parsed?.stage_outputs?.stage02_querygen;
      const adapterOut = stage2Parsed?.stage_outputs?.adapter_queries;
      const stageState: Record<string, any> = {};
      if (adapterOut?.search_queries) {
        stageState.search_queries = adapterOut.search_queries;
      } else if (stage2Out?.query_variants?.sample) {
        stageState.search_queries = stage2Out.query_variants.sample.map((v: any) => v.text).filter(Boolean);
      }
      const res = await fetch(`${API_BASE}/truth/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_type: "text",
          input_payload: stage2Input || stage1Input,
          user_request: "",
          language: "ko",
          start_stage: "stage03_collect",
          end_stage: "stage03_collect",
          stage_state: stageState,
          include_full_outputs: true,
        }),
      });
      setStage3Status(res.status);
      const text = await res.text();
      setStage3Raw(text);
      try {
        setStage3Parsed(JSON.parse(text));
      } catch {
        setStage3Parsed(null);
      }
      if (!res.ok) setStage3Error(`HTTP ${res.status}`);
    } catch (err) {
      setStage3Error(err instanceof Error ? err.message : String(err));
    }
  }

  async function runStage4() {
    setStage4Error("");
    setStage4Raw("");
    setStage4Parsed(null);
    setStage4Status(null);
    try {
      const stage3Out =
        stage3Parsed?.stage_full_outputs?.stage03_collect ||
        stage3Parsed?.stage_outputs?.stage03_collect;
      const stageState: Record<string, any> = {};
      if (stage3Out?.evidence_candidates) {
        stageState.evidence_candidates = stage3Out.evidence_candidates;
      }
      const res = await fetch(`${API_BASE}/truth/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_type: "text",
          input_payload: stage2Input || stage1Input,
          user_request: "",
          language: "ko",
          start_stage: "stage04_score",
          end_stage: "stage04_score",
          stage_state: stageState,
          include_full_outputs: true,
        }),
      });
      setStage4Status(res.status);
      const text = await res.text();
      setStage4Raw(text);
      try {
        setStage4Parsed(JSON.parse(text));
      } catch {
        setStage4Parsed(null);
      }
      if (!res.ok) setStage4Error(`HTTP ${res.status}`);
    } catch (err) {
      setStage4Error(err instanceof Error ? err.message : String(err));
    }
  }

  async function runStage5() {
    setStage5Error("");
    setStage5Raw("");
    setStage5Parsed(null);
    setStage5Status(null);
    try {
      const stage4Out =
        stage4Parsed?.stage_full_outputs?.stage04_score ||
        stage4Parsed?.stage_outputs?.stage04_score;
      const stageState: Record<string, any> = {};
      if (stage4Out?.scored_evidence) {
        stageState.scored_evidence = stage4Out.scored_evidence;
      }
      const res = await fetch(`${API_BASE}/truth/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_type: "text",
          input_payload: stage2Input || stage1Input,
          user_request: "",
          language: "ko",
          start_stage: "stage05_topk",
          end_stage: "stage05_topk",
          stage_state: stageState,
          include_full_outputs: true,
        }),
      });
      setStage5Status(res.status);
      const text = await res.text();
      setStage5Raw(text);
      try {
        setStage5Parsed(JSON.parse(text));
      } catch {
        setStage5Parsed(null);
      }
      if (!res.ok) setStage5Error(`HTTP ${res.status}`);
    } catch (err) {
      setStage5Error(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <>
      <section className="team-stage" style={{ maxHeight: "calc(100vh - 140px)", overflow: "auto" }}>
      <div className="team-stage-header">
        <div>
          <h3>LangGraph Test</h3>
          <p>/truth/check 파이프라인 테스트 전용 페이지</p>
        </div>
        <div className="row">
          <button className="pill ghost" onClick={clearAll} disabled={running}>
            Clear
          </button>
          <button className="pill" onClick={runTest} disabled={running}>
            {running ? (streaming ? "Streaming" : "Running") : "Run"}
          </button>
        </div>
      </div>

      <div className="team-stage-grid" style={{ gridTemplateColumns: "1fr" }}>
        <section className="team-stage-card">
          <div className="label">input_type</div>
          <div className="row">
            <button
              className={`pill ${inputType === "text" ? "" : "ghost"}`}
              onClick={() => setInputType("text")}
            >
              text
            </button>
            <button
              className={`pill ${inputType === "url" ? "" : "ghost"}`}
              onClick={() => setInputType("url")}
            >
              url
            </button>
          </div>
          <div className="label">input_payload</div>
          <textarea
            className="textarea"
            placeholder="문장 또는 URL"
            value={inputPayload}
            onChange={(e) => setInputPayload(e.target.value)}
            style={{ minHeight: 160 }}
          />
          <div className="label">user_request (optional)</div>
          <input
            className="input"
            placeholder="사용자 요청"
            value={userRequest}
            onChange={(e) => setUserRequest(e.target.value)}
          />
          <div className="label">language</div>
          <input
            className="input"
            placeholder="ko"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            style={{ width: 120 }}
          />
          <div className="label">stage range</div>
          <div className="row">
            <select
              className="input"
              value={startStage}
              onChange={(e) => setStartStage(e.target.value)}
              style={{ width: 200 }}
            >
              <option value="stage01_normalize">stage01_normalize</option>
              <option value="stage02_querygen">stage02_querygen</option>
              <option value="adapter_queries">adapter_queries</option>
              <option value="stage03_collect">stage03_collect</option>
              <option value="stage04_score">stage04_score</option>
              <option value="stage05_topk">stage05_topk</option>
            </select>
            <select
              className="input"
              value={endStage}
              onChange={(e) => setEndStage(e.target.value)}
              style={{ width: 200 }}
            >
              <option value="stage01_normalize">stage01_normalize</option>
              <option value="stage02_querygen">stage02_querygen</option>
              <option value="adapter_queries">adapter_queries</option>
              <option value="stage03_collect">stage03_collect</option>
              <option value="stage04_score">stage04_score</option>
              <option value="stage05_topk">stage05_topk</option>
            </select>
          </div>
          <div className="label">stage02 prompt (optional)</div>
          <div className="row" style={{ marginBottom: 8 }}>
            <button
              className={`pill ${useQuerygenPrompt ? "" : "ghost"}`}
              onClick={() => setUseQuerygenPrompt((prev) => !prev)}
            >
              use prompt override
            </button>
            <button
              className="pill ghost"
              onClick={() => setQuerygenPrompt(TEAM_A_PROMPT_TEMPLATE)}
            >
              load Team A prompt
            </button>
          </div>
          {useQuerygenPrompt ? (
            <textarea
              className="textarea"
              placeholder="Stage2 QueryGen prompt"
              value={querygenPrompt}
              onChange={(e) => setQuerygenPrompt(e.target.value)}
              style={{ minHeight: 180 }}
            />
          ) : null}
          <div className="label">Request JSON (prompt 제외)</div>
          <pre
            className="output"
            style={{ whiteSpace: "pre-wrap", minHeight: 140, maxHeight: 220, overflow: "auto" }}
          >
            {displayPayload}
          </pre>
          {useQuerygenPrompt ? (
            <>
              <div className="label">QueryGen prompt (separate)</div>
              <pre
                className="output"
                style={{ whiteSpace: "pre-wrap", minHeight: 120, maxHeight: 200, overflow: "auto" }}
              >
                {querygenPrompt || "-"}
              </pre>
            </>
          ) : null}
        </section>

        <section className="team-stage-card">
          <div className="label">Response</div>
          <div className="row" style={{ marginBottom: 8 }}>
            <div className="pill ghost">status: {status ?? "-"}</div>
            {error ? <div className="pill stop">{error}</div> : null}
          </div>
          <div className="label">Parsed JSON</div>
          <pre
            className="output"
            style={{ whiteSpace: "pre-wrap", minHeight: 200, maxHeight: 260, overflow: "auto" }}
          >
            {prettyParsed || "-"}
          </pre>
          <div className="label">Raw</div>
          <pre
            className="output"
            style={{ whiteSpace: "pre-wrap", minHeight: 140, maxHeight: 200, overflow: "auto" }}
          >
            {raw || "-"}
          </pre>
          <div className="label">Stage output</div>
          <div className="row" style={{ marginBottom: 8 }}>
            <select
              className="input"
              value={selectedStage}
              onChange={(e) => setSelectedStage(e.target.value)}
              style={{ width: 220 }}
            >
              <option value="">latest</option>
              {stageOutputKeys.map((key) => (
                <option key={key} value={key}>
                  {key}
                </option>
              ))}
            </select>
          </div>
          <pre
            className="output"
            style={{ whiteSpace: "pre-wrap", minHeight: 140, maxHeight: 220, overflow: "auto" }}
          >
            {prettyStageOutput || "-"}
          </pre>
          <div className="label">Stage logs</div>
          <pre
            className="output"
            style={{ whiteSpace: "pre-wrap", minHeight: 140, maxHeight: 220, overflow: "auto" }}
          >
            {prettyLogs || "-"}
          </pre>
        </section>
      </div>
      </section>

      <section className="team-stage">
      <div className="team-stage-header">
        <div>
          <h3>Stage 1. Normalize (test)</h3>
          <p>입력 → claim_text/metadata 확인</p>
        </div>
        <div className="row">
          <button className="pill" onClick={runStage1}>
            Run Stage1
          </button>
        </div>
      </div>
      <div className="team-stage-grid" style={{ gridTemplateColumns: "1fr" }}>
        <section className="team-stage-card">
          <div className="label">input</div>
          <div className="row" style={{ marginBottom: 8 }}>
            <button
              className={`pill ${stage1InputType === "text" ? "" : "ghost"}`}
              onClick={() => setStage1InputType("text")}
            >
              text
            </button>
            <button
              className={`pill ${stage1InputType === "url" ? "" : "ghost"}`}
              onClick={() => setStage1InputType("url")}
            >
              url
            </button>
          </div>
          <textarea
            className="textarea"
            placeholder="Stage1 input"
            value={stage1Input}
            onChange={(e) => setStage1Input(e.target.value)}
            style={{ minHeight: 160 }}
          />
          <div className="label">normalize mode</div>
          <div className="row">
            <button
              className={`pill ${stage1NormalizeMode === "llm" ? "" : "ghost"}`}
              onClick={() => setStage1NormalizeMode("llm")}
            >
              llm
            </button>
            <button
              className={`pill ${stage1NormalizeMode === "basic" ? "" : "ghost"}`}
              onClick={() => setStage1NormalizeMode("basic")}
            >
              basic
            </button>
          </div>
        </section>
        <section className="team-stage-card">
          <div className="label">output</div>
          <div className="row" style={{ marginBottom: 8 }}>
            <div className="pill ghost">status: {stage1Status ?? "-"}</div>
            {stage1Error ? <div className="pill stop">{stage1Error}</div> : null}
          </div>
          <pre className="output" style={{ whiteSpace: "pre-wrap", minHeight: 160, maxHeight: 260, overflow: "auto" }}>
            {stage1Parsed
              ? JSON.stringify(stage1Parsed.stage_outputs?.stage01_normalize || {}, null, 2)
              : stage1Raw || "-"}
          </pre>
        </section>
      </div>
      </section>

    <section className="team-stage">
      <div className="team-stage-header">
        <div>
          <h3>Stage 2. QueryGen (test)</h3>
          <p>Stage1→Stage2 실행, query_variants 확인</p>
        </div>
        <div className="row">
          <button
            className={`pill ${stage2AutoFromStage1 ? "" : "ghost"}`}
            onClick={() => {
              setStage2AutoFromStage1((prev) => {
                const next = !prev;
                if (next && stage1OutputText.trim()) {
                  setStage2Input(stage1OutputText);
                }
                return next;
              });
            }}
          >
            auto inject stage1 output
          </button>
          <button className="pill" onClick={runStage2}>
            Run Stage2
          </button>
        </div>
      </div>
      <div className="team-stage-grid" style={{ gridTemplateColumns: "1fr" }}>
        <section className="team-stage-card">
          <div className="label">input</div>
          <textarea
            className="textarea"
            placeholder="Stage2 input"
            value={stage2Input}
            onChange={(e) => setStage2Input(e.target.value)}
            style={{ minHeight: 160 }}
          />
          <div className="label">normalize mode</div>
          <div className="row">
            <button
              className={`pill ${stage2NormalizeMode === "llm" ? "" : "ghost"}`}
              onClick={() => setStage2NormalizeMode("llm")}
            >
              llm
            </button>
            <button
              className={`pill ${stage2NormalizeMode === "basic" ? "" : "ghost"}`}
              onClick={() => setStage2NormalizeMode("basic")}
            >
              basic
            </button>
          </div>
          <div className="label">QueryGen prompt (optional)</div>
          <div className="row" style={{ marginBottom: 8 }}>
            <button
              className={`pill ${stage2UsePrompt ? "" : "ghost"}`}
              onClick={() => setStage2UsePrompt((prev) => !prev)}
            >
              use prompt override
            </button>
            <button className="pill ghost" onClick={() => setStage2Prompt(TEAM_A_PROMPT_TEMPLATE)}>
              load Team A prompt
            </button>
          </div>
          {stage2UsePrompt ? (
            <textarea
              className="textarea"
              placeholder="Stage2 prompt override"
              value={stage2Prompt}
              onChange={(e) => setStage2Prompt(e.target.value)}
              style={{ minHeight: 140 }}
            />
          ) : null}
        </section>
        <section className="team-stage-card">
          <div className="label">output</div>
          <div className="row" style={{ marginBottom: 8 }}>
            <div className="pill ghost">status: {stage2Status ?? "-"}</div>
            {stage2Error ? <div className="pill stop">{stage2Error}</div> : null}
          </div>
          <pre className="output" style={{ whiteSpace: "pre-wrap", minHeight: 160, maxHeight: 260, overflow: "auto" }}>
            {stage2Parsed
              ? JSON.stringify(stage2Parsed.stage_outputs?.stage02_querygen || {}, null, 2)
              : stage2Raw || "-"}
          </pre>
          <div className="label">wiki queries</div>
          <pre className="output" style={{ whiteSpace: "pre-wrap", minHeight: 80, maxHeight: 180, overflow: "auto" }}>
            {stage2WikiQueries.length ? stage2WikiQueries.map((q) => `- ${q}`).join("\n") : "-"}
          </pre>
        </section>
      </div>
    </section>

    <section className="team-stage">
      <div className="team-stage-header">
        <div>
          <h3>Stage 3. Collect (test)</h3>
          <p>search_queries 기반 수집 결과 확인</p>
        </div>
        <div className="row">
          <button className="pill" onClick={runStage3}>
            Run Stage3
          </button>
        </div>
      </div>
      <div className="team-stage-grid" style={{ gridTemplateColumns: "1fr" }}>
        <section className="team-stage-card">
          <div className="label">input (from Stage2)</div>
          <pre className="output" style={{ whiteSpace: "pre-wrap", minHeight: 160, maxHeight: 220, overflow: "auto" }}>
            {stage2Parsed ? JSON.stringify(stage2Parsed.stage_outputs?.adapter_queries || {}, null, 2) : "-"}
          </pre>
        </section>
        <section className="team-stage-card">
          <div className="label">output</div>
          <div className="row" style={{ marginBottom: 8 }}>
            <div className="pill ghost">status: {stage3Status ?? "-"}</div>
            {stage3Error ? <div className="pill stop">{stage3Error}</div> : null}
          </div>
          <pre className="output" style={{ whiteSpace: "pre-wrap", minHeight: 160, maxHeight: 260, overflow: "auto" }}>
            {stage3Parsed
              ? JSON.stringify(stage3Parsed.stage_outputs?.stage03_collect || {}, null, 2)
              : stage3Raw || "-"}
          </pre>
        </section>
      </div>
    </section>

    <section className="team-stage">
      <div className="team-stage-header">
        <div>
          <h3>Stage 4. Score (test)</h3>
          <p>stage03 evidence_candidates → scoring</p>
        </div>
        <div className="row">
          <button className="pill" onClick={runStage4}>
            Run Stage4
          </button>
        </div>
      </div>
      <div className="team-stage-grid" style={{ gridTemplateColumns: "1fr" }}>
        <section className="team-stage-card">
          <div className="label">input (from Stage3)</div>
          <pre className="output" style={{ whiteSpace: "pre-wrap", minHeight: 160, maxHeight: 220, overflow: "auto" }}>
            {stage3Parsed
              ? JSON.stringify(
                  stage3Parsed.stage_full_outputs?.stage03_collect ||
                    stage3Parsed.stage_outputs?.stage03_collect ||
                    {},
                  null,
                  2
                )
              : "-"}
          </pre>
        </section>
        <section className="team-stage-card">
          <div className="label">output</div>
          <div className="row" style={{ marginBottom: 8 }}>
            <div className="pill ghost">status: {stage4Status ?? "-"}</div>
            {stage4Error ? <div className="pill stop">{stage4Error}</div> : null}
          </div>
          <pre className="output" style={{ whiteSpace: "pre-wrap", minHeight: 160, maxHeight: 260, overflow: "auto" }}>
            {stage4Parsed
              ? JSON.stringify(stage4Parsed.stage_outputs?.stage04_score || {}, null, 2)
              : stage4Raw || "-"}
          </pre>
        </section>
      </div>
    </section>

    <section className="team-stage">
      <div className="team-stage-header">
        <div>
          <h3>Stage 5. TopK (test)</h3>
          <p>stage04 scored_evidence → top-k</p>
        </div>
        <div className="row">
          <button className="pill" onClick={runStage5}>
            Run Stage5
          </button>
        </div>
      </div>
      <div className="team-stage-grid" style={{ gridTemplateColumns: "1fr" }}>
        <section className="team-stage-card">
          <div className="label">input (from Stage4)</div>
          <pre className="output" style={{ whiteSpace: "pre-wrap", minHeight: 160, maxHeight: 220, overflow: "auto" }}>
            {stage4Parsed
              ? JSON.stringify(
                  stage4Parsed.stage_full_outputs?.stage04_score ||
                    stage4Parsed.stage_outputs?.stage04_score ||
                    {},
                  null,
                  2
                )
              : "-"}
          </pre>
        </section>
        <section className="team-stage-card">
          <div className="label">output</div>
          <div className="row" style={{ marginBottom: 8 }}>
            <div className="pill ghost">status: {stage5Status ?? "-"}</div>
            {stage5Error ? <div className="pill stop">{stage5Error}</div> : null}
          </div>
          <pre className="output" style={{ whiteSpace: "pre-wrap", minHeight: 160, maxHeight: 260, overflow: "auto" }}>
            {stage5Parsed
              ? JSON.stringify(stage5Parsed.stage_outputs?.stage05_topk || {}, null, 2)
              : stage5Raw || "-"}
          </pre>
        </section>
      </div>
    </section>
    </>
  );
}
