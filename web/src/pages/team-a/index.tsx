import { useEffect, useMemo, useRef, useState } from "react";

type SearchMode = "fts" | "lexical" | "vector";

type QueryGenResult = {
  ok: boolean;
  model: string;
  prompt: string;
  raw: string;
  json?: any;
  error?: string | null;
};

type RetrieveResult = {
  ok: boolean;
  results: Array<{
    claim_id: string;
    skipped: boolean;
    wiki: Array<{
      query: string;
      candidates: Array<{ page_id: number; title: string; score?: number }>;
      hits: Array<{
        title: string;
        page_id: number;
        chunk_id: number;
        chunk_idx: number;
        snippet: string;
      }>;
      debug?: any;
    }>;
    news?: Array<{
      query: string;
      items: Array<{
        title?: string;
        link?: string;
        originallink?: string;
        pubDate?: string;
        description?: string;
      }>;
      error?: string | null;
    }>;
  }>;
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function apiGet(path: string) {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} failed`);
  return res.json();
}

async function apiPost(path: string, payload: unknown, signal?: AbortSignal) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) throw new Error(`POST ${path} failed`);
  return res.json();
}

function buildPrompt(userRequest: string, title: string, articleText: string) {
  return (
    "너는 단순 요약기가 아니라, 기사 속 의도/논란의 소지를 파헤치는 ‘수석 팩트체커 + QueryGen(Stage2)’이다.\n" +
    "입력으로 주어진 title과 [SENTENCES]를 바탕으로,\n" +
    "(1) 기사 주제와 core_narrative를 작성하고,\n" +
    "(2) 검증이 필요한 핵심 claims 3개를 [SENTENCES]에서 “문장 그대로” 선택하며,\n" +
    "(3) 각 claim마다 verification_reason, time_sensitivity, 그리고 위키피디아 로컬 DB 조회용 쿼리(wiki_db)와 최신 뉴스 검색용 쿼리(news_search)를 생성하라.\n\n" +
    "[절대 규칙]\n" +
    "1) 출력은 오직 “유효한 JSON”만 허용한다. 마크다운, 주석, 코드펜스(```)를 절대 포함하지 마라.\n" +
    "2) 아래 [SENTENCES]는 article_text를 문장 단위로 분해한 것이다.\n" +
    "3) claims[].주장 값은 반드시 [SENTENCES]의 문장 텍스트를 “완전히 동일하게” 그대로 복사해야 한다.\n" +
    "   - 글자 하나라도 바꾸면 실패다(띄어쓰기/따옴표/조사/숫자 포함).\n" +
    "   - 문장 일부만 발췌하지 말고, 반드시 ‘한 문장 전체’를 그대로 사용해라.\n" +
    "4) claims는 정확히 3개만 출력한다. claim_id는 C1, C2, C3 고정.\n" +
    "5) claim_type은 반드시 아래 중 하나로만 선택한다:\n" +
    "   - 사건 | 논리 | 통계 | 인용 | 정책\n" +
    "6) verification_reason는 “왜 이 문장이 핵심 논점/논란 포인트인지”를 맥락적으로 설명하되, 기사 밖의 새로운 사실을 만들어내지 마라.\n" +
    "7) time_sensitivity는 low|mid|high 중 하나로 지정한다.\n" +
    "   - high: 최신 논란/팬 반응/시즌 전망/최근 발언 등 시점 영향이 큰 것\n" +
    "   - low: 인물/팀/리그/제도처럼 시간 영향이 적은 것\n" +
    "8) query_pack 생성 규칙:\n" +
    "   8-1) wiki_db: 정확히 3개를 생성한다. 각 원소는 {\"mode\":\"title|fulltext\",\"q\":\"string\"} 형식의 객체다.\n" +
    "        - 목적: ‘검증’이 아니라 로컬 위키에서 배경/정의/고정 사실(인물·팀·리그·대회·제도)을 찾기 위함.\n" +
    "        - title은 실제 문서 제목으로 존재할 가능성이 높은 엔터티(인물/팀/리그/대회/제도)를 우선한다.\n" +
    "        - fulltext는 개념/동의어/표기 변형을 포함해 검색 폭을 넓힌다.\n" +
    "        - 한국어 타이틀을 우선하고, 영문 표기는 필요 시 fulltext에 보조로 넣어라.\n" +
    "        - 이 기사처럼 위키 검증이 불필요한 claim이어도 wiki_db는 “배경 확보용”으로만 최소한으로 구성해라(예: 인물/팀/리그).\n" +
    "   8-2) news_search: 각 claim마다 정확히 4개 “문자열”을 생성한다. (객체/딕셔너리 금지)\n" +
    "        - 구성: (진위/공식 확인용 2개) + (반대/비교 데이터 탐색용 2개)\n" +
    "        - 필요 시 연도/시점, 공식 출처 키워드(구단 발표, KBO 공식 기록, 인터뷰 원문 등)를 포함한다.\n" +
    "9) JSON 스키마를 반드시 지켜라.\n\n" +
    "[출력 스키마]\n" +
    "{\n" +
    "  \"주제\": \"string\",\n" +
    "  \"core_narrative\": \"string\",\n" +
    "  \"claims\": [\n" +
    "    {\n" +
    "      \"claim_id\": \"C1\",\n" +
    "      \"주장\": \"string\",\n" +
    "      \"claim_type\": \"사건|논리|통계|인용|정책\",\n" +
    "      \"verification_reason\": \"string\",\n" +
    "      \"time_sensitivity\": \"low|mid|high\",\n" +
    "      \"query_pack\": {\n" +
    "        \"wiki_db\": [\n" +
    "          {\"mode\":\"title|fulltext\",\"q\":\"string\"},\n" +
    "          {\"mode\":\"title|fulltext\",\"q\":\"string\"},\n" +
    "          {\"mode\":\"title|fulltext\",\"q\":\"string\"}\n" +
    "        ],\n" +
    "        \"news_search\": [\"string\",\"string\",\"string\",\"string\"]\n" +
    "      }\n" +
    "    },\n" +
    "    {\n" +
    "      \"claim_id\": \"C2\",\n" +
    "      \"주장\": \"string\",\n" +
    "      \"claim_type\": \"사건|논리|통계|인용|정책\",\n" +
    "      \"verification_reason\": \"string\",\n" +
    "      \"time_sensitivity\": \"low|mid|high\",\n" +
    "      \"query_pack\": {\n" +
    "        \"wiki_db\": [\n" +
    "          {\"mode\":\"title|fulltext\",\"q\":\"string\"},\n" +
    "          {\"mode\":\"title|fulltext\",\"q\":\"string\"},\n" +
    "          {\"mode\":\"title|fulltext\",\"q\":\"string\"}\n" +
    "        ],\n" +
    "        \"news_search\": [\"string\",\"string\",\"string\",\"string\"]\n" +
    "      }\n" +
    "    },\n" +
    "    {\n" +
    "      \"claim_id\": \"C3\",\n" +
    "      \"주장\": \"string\",\n" +
    "      \"claim_type\": \"사건|논리|통계|인용|정책\",\n" +
    "      \"verification_reason\": \"string\",\n" +
    "      \"time_sensitivity\": \"low|mid|high\",\n" +
    "      \"query_pack\": {\n" +
    "        \"wiki_db\": [\n" +
    "          {\"mode\":\"title|fulltext\",\"q\":\"string\"},\n" +
    "          {\"mode\":\"title|fulltext\",\"q\":\"string\"},\n" +
    "          {\"mode\":\"title|fulltext\",\"q\":\"string\"}\n" +
    "        ],\n" +
    "        \"news_search\": [\"string\",\"string\",\"string\",\"string\"]\n" +
    "      }\n" +
    "    }\n" +
    "  ]\n" +
    "}\n\n" +
    "[INPUT]\n" +
    `user_request: \"${userRequest}\"\n` +
    `title: \"${title}\"\n` +
    "SENTENCES:\n" +
    `${articleText}\n` +
    "[/INPUT]\n\n" +
    "[최종 점검(출력 금지)]\n" +
    "- JSON만 출력했는가? (첫 글자 {, 마지막 글자 })\n" +
    "- claims 3개인가? claim_id가 C1~C3인가?\n" +
    "- 각 주장 문장이 [SENTENCES] 중 하나와 완전히 동일한가?\n" +
    "- news_search가 문자열 4개인가? (객체 금지)\n" +
    "- wiki_db가 객체 3개인가? mode가 title|fulltext 중 하나인가?\n\n" +
    "이제 JSON만 출력하라.\n"
  );
}

function TeamAPage() {
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState("gemma2:2b");
  const [searchMode, setSearchMode] = useState<SearchMode>("fts");

  const [userRequest, setUserRequest] = useState("");
  const [title, setTitle] = useState("");
  const [articleText, setArticleText] = useState("");

  const [promptText, setPromptText] = useState("");
  const [querygen, setQuerygen] = useState<QueryGenResult | null>(null);
  const [retrieve, setRetrieve] = useState<RetrieveResult | null>(null);
  const [loadingStage2, setLoadingStage2] = useState(false);
  const [loadingStage3, setLoadingStage3] = useState(false);
  const [stage3Error, setStage3Error] = useState<string | null>(null);
  const [manualJson, setManualJson] = useState("");

  const stage2Controller = useRef<AbortController | null>(null);
  const stage3Controller = useRef<AbortController | null>(null);

  const canRunStage2 = articleText.trim().length > 0 && !loadingStage2;
  const claims = useMemo(() => {
    const list = querygen?.json?.["claims"] || querygen?.json?.["주장들"];
    return Array.isArray(list) ? list : [];
  }, [querygen]);

  const manualParse = useMemo(() => {
    if (!manualJson.trim()) return { claims: [] as any[], error: null as string | null };
    try {
      const parsed = JSON.parse(manualJson);
      const list = parsed?.["claims"] || parsed?.["주장들"];
      return { claims: Array.isArray(list) ? list : [], error: null };
    } catch (err: any) {
      return { claims: [], error: err?.message || "invalid JSON" };
    }
  }, [manualJson]);

  const stage3Queries = useMemo(() => {
    const rows: Array<{ claim_id: string; wiki: string[]; news: string[] }> = [];
    const sourceClaims = claims.length ? claims : manualParse.claims;
    sourceClaims.forEach((claim: any) => {
      const claimId = claim?.claim_id || claim?.claimId || "-";
      const pack = claim?.query_pack || {};
      const wikiItems = Array.isArray(pack?.wiki_db) ? pack.wiki_db : [];
      const newsItems = Array.isArray(pack?.news_search) ? pack.news_search : [];
      const wikiQs = wikiItems
        .map((w: any) => (typeof w === "string" ? w : w?.q))
        .filter((q: any) => typeof q === "string" && q.trim())
        .map((q: string) => q.trim());
      const newsQs = newsItems
        .filter((q: any) => typeof q === "string" && q.trim())
        .map((q: string) => q.trim());
      rows.push({ claim_id: claimId, wiki: wikiQs, news: newsQs });
    });
    return rows;
  }, [claims, manualParse.claims]);

  useEffect(() => {
    loadModels();
  }, []);

  useEffect(() => {
    setPromptText(buildPrompt(userRequest, title, articleText));
  }, [userRequest, title, articleText]);

  async function loadModels() {
    try {
      const data = await apiGet("/api/models");
      if (data.ok) {
        const list = (data.models || []).map((item: any) => item.name).filter(Boolean);
        setModels(list);
        if (!model && list.length) setModel(list[0]);
      }
    } catch (err) {
      setModels([]);
    }
  }

  async function runStage2() {
    if (!canRunStage2) return;
    if (stage2Controller.current) stage2Controller.current.abort();
    stage2Controller.current = new AbortController();
    setLoadingStage2(true);
    setQuerygen(null);
    setRetrieve(null);
    setStage3Error(null);
    try {
      const data = await apiPost(
        "/api/team-a/querygen",
        {
          model,
          user_request: userRequest,
          title,
          article_text: articleText,
          prompt: promptText,
        },
        stage2Controller.current.signal
      );
      setQuerygen(data as QueryGenResult);
    } catch (err: any) {
      setQuerygen({
        ok: false,
        model,
        prompt: promptText,
        raw: "",
        error: err.message || "failed",
      });
    } finally {
      setLoadingStage2(false);
      stage2Controller.current = null;
    }
  }

  async function runStage3() {
    const sourceClaims = claims.length ? claims : manualParse.claims;
    if (!sourceClaims.length || loadingStage3) return;
    if (stage3Controller.current) stage3Controller.current.abort();
    stage3Controller.current = new AbortController();
    setLoadingStage3(true);
    setRetrieve(null);
    setStage3Error(null);
    try {
      const data = await apiPost(
        "/api/team-a/retrieve",
        {
          claims: sourceClaims,
          top_k: 6,
          page_limit: 8,
          window: 2,
          max_chars: 2000,
          embed_missing: true,
          search_mode: searchMode,
        },
        stage3Controller.current.signal
      );
      setRetrieve(data as RetrieveResult);
    } catch (err: any) {
      setRetrieve({ ok: false, results: [] } as RetrieveResult);
      setStage3Error(err.message || "stage3 failed");
    } finally {
      setLoadingStage3(false);
      stage3Controller.current = null;
    }
  }

  function stopAll() {
    if (stage2Controller.current) stage2Controller.current.abort();
    if (stage3Controller.current) stage3Controller.current.abort();
    setLoadingStage2(false);
    setLoadingStage3(false);
  }

  return (
    <div className="team">
      <div className="team-header">
        <h2>Team A</h2>
        <p>Stage1~3 실험 UI (dashboard.py + web UI only)</p>
      </div>

      <section className="team-stage">
        <div className="team-stage-header">
          <div>
            <h3>Stage 1. 입력 (직접 제목/본문)</h3>
            <p>URL 대신 직접 기사 제목/본문을 입력한다.</p>
          </div>
        </div>
        <div className="team-stage-grid">
          <section className="team-stage-card team-stage-controls">
            <div className="label">user_request (optional)</div>
            <input
              className="input"
              placeholder="사용자 요청"
              value={userRequest}
              onChange={(e) => setUserRequest(e.target.value)}
            />
            <div className="label">title</div>
            <input
              className="input"
              placeholder="기사 제목"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <div className="label">article_text</div>
            <textarea
              className="textarea"
              placeholder="기사 본문"
              value={articleText}
              onChange={(e) => setArticleText(e.target.value)}
              style={{ minHeight: 220 }}
            />
          </section>
        </div>
      </section>

      <section className="team-stage">
        <div className="team-stage-header">
          <div>
            <h3>Stage 2. QueryGen (JSON)</h3>
            <p>프롬프트를 직접 수정하고 JSON 출력만 받는다.</p>
          </div>
          <div className="row">
            <input
              className="input"
              list="team-a-models"
              placeholder="model:tag"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              style={{ width: 220 }}
            />
            <button className="pill ghost" onClick={loadModels}>
              Refresh models
            </button>
            <button className="pill ghost stop" onClick={stopAll}>
              Stop
            </button>
            <button className="pill" onClick={runStage2} disabled={!canRunStage2}>
              {loadingStage2 ? "Running..." : "Run Stage2"}
            </button>
          </div>
        </div>
        <div className="team-stage-grid">
          <section className="team-stage-card">
            <div className="label">Prompt (editable)</div>
            <textarea
              className="textarea"
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              style={{ minHeight: 240 }}
            />
          </section>
          <section className="team-stage-card">
            <div className="label">Output (raw)</div>
            <div className="output" style={{ whiteSpace: "pre-wrap", minHeight: 220 }}>
              {querygen?.raw || querygen?.error || "-"}
            </div>
            <div className="label">Output (parsed JSON)</div>
            <pre className="output" style={{ whiteSpace: "pre-wrap", minHeight: 220 }}>
              {querygen?.json ? JSON.stringify(querygen.json, null, 2) : "-"}
            </pre>
          </section>
        </div>
        <datalist id="team-a-models">
          {models.map((m) => (
            <option key={m} value={m} />
          ))}
        </datalist>
      </section>

      <section className="team-stage">
        <div className="team-stage-header">
          <div>
            <h3>Stage 3. Retrieve (DB only)</h3>
            <p>Stage2 결과의 위키피디아 쿼리로 DB 검색만 수행.</p>
          </div>
          <div className="row">
            <div className="row">
              <button
                className={`pill ${searchMode === "vector" ? "" : "ghost"}`}
                onClick={() => setSearchMode("vector")}
              >
                Vector
              </button>
              <button
                className={`pill ${searchMode === "fts" ? "" : "ghost"}`}
                onClick={() => setSearchMode("fts")}
              >
                FTS
              </button>
              <button
                className={`pill ${searchMode === "lexical" ? "" : "ghost"}`}
                onClick={() => setSearchMode("lexical")}
              >
                Lexical
              </button>
              <div className="hint">mode: {searchMode}</div>
            </div>
            <button
              className="pill"
              onClick={runStage3}
              disabled={(!claims.length && !manualParse.claims.length) || loadingStage3}
            >
              {loadingStage3 ? "Running..." : "Run Stage3"}
            </button>
          </div>
        </div>
        <div className="team-stage-grid">
          <section className="team-stage-card">
            <div className="label">Claims</div>
            <pre className="output" style={{ whiteSpace: "pre-wrap", minHeight: 180 }}>
              {claims.length ? JSON.stringify(claims, null, 2) : "-"}
            </pre>
            <div className="label">Stage3 queries</div>
            <div className="output" style={{ whiteSpace: "pre-wrap", minHeight: 180 }}>
              {stage3Queries.length
                ? stage3Queries.map((row) => (
                    <div key={`q-${row.claim_id}`} style={{ marginBottom: 12 }}>
                      <div>
                        <strong>{row.claim_id}</strong>
                      </div>
                      <div>news:</div>
                      {(row.news || []).map((q, idx) => (
                        <div key={`n-${row.claim_id}-${idx}`}>- {q}</div>
                      ))}
                      <div>wiki:</div>
                      {(row.wiki || []).map((q, idx) => (
                        <div key={`w-${row.claim_id}-${idx}`}>- {q}</div>
                      ))}
                    </div>
                  ))
                : "-"}
            </div>
            <div className="label">Manual JSON (paste)</div>
            <textarea
              className="textarea"
              placeholder="Stage2 raw JSON을 여기에 붙여넣으면 Stage3 실행 가능"
              value={manualJson}
              onChange={(e) => setManualJson(e.target.value)}
              style={{ minHeight: 160 }}
            />
            {manualJson.trim() ? (
              <div className="hint">
                {manualParse.error
                  ? `parse error: ${manualParse.error}`
                  : `claims: ${manualParse.claims.length}`}
              </div>
            ) : null}
          </section>
          <section className="team-stage-card">
            <div className="label">Retrieve results</div>
            <div className="team-stage-grid">
              <section className="team-stage-card">
                <div className="label">News search</div>
                <div className="output" style={{ whiteSpace: "pre-wrap", minHeight: 180 }}>
                  {stage3Error && <div className="hint">error: {stage3Error}</div>}
                  {retrieve?.ok === false && "Retrieve failed"}
                  {!retrieve && "-"}
                  {retrieve?.ok &&
                    retrieve.results.map((res) => (
                      <div key={`news-${res.claim_id}`} style={{ marginBottom: 16 }}>
                        <div>
                          <strong>{res.claim_id}</strong> {res.skipped ? "(skipped)" : ""}
                        </div>
                        {(res.news || []).length ? (
                          (res.news || []).map((n) => (
                            <div key={`${res.claim_id}-news-${n.query}`} style={{ marginTop: 8 }}>
                              <div>query: {n.query}</div>
                              {n.error ? (
                                <div className="hint">error: {n.error}</div>
                              ) : (
                                (n.items || []).map((item, idx) => (
                                  <div key={`${res.claim_id}-news-${n.query}-${idx}`}>
                                    - {item.title || "-"} ({item.pubDate || "-"})
                                  </div>
                                ))
                              )}
                            </div>
                          ))
                        ) : (
                          <div className="hint">no news queries</div>
                        )}
                      </div>
                    ))}
                </div>
              </section>
              <section className="team-stage-card">
                <div className="label">Wiki DB</div>
                <div className="output" style={{ whiteSpace: "pre-wrap", minHeight: 180 }}>
                  {retrieve?.ok === false && "Retrieve failed"}
                  {!retrieve && "-"}
                  {retrieve?.ok &&
                    retrieve.results.map((res) => (
                      <div key={`wiki-${res.claim_id}`} style={{ marginBottom: 16 }}>
                        <div>
                          <strong>{res.claim_id}</strong> {res.skipped ? "(skipped)" : ""}
                        </div>
                        {res.wiki.map((w) => (
                          <div key={w.query} style={{ marginTop: 8 }}>
                            <div>query: {w.query}</div>
                            <div>candidates: {w.candidates.length}</div>
                            <div>hits: {w.hits.length}</div>
                          </div>
                        ))}
                      </div>
                    ))}
                </div>
              </section>
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}

export default TeamAPage;
