import { useMemo, useRef, useState } from 'react';

type StageId =
    | 'stage01_normalize'
    | 'stage02_querygen'
    | 'stage03_wiki'
    | 'stage03_web'
    | 'stage03_merge'
    | 'stage04_score'
    | 'stage05_topk'
    | 'stage06_verify_support'
    | 'stage07_verify_skeptic'
    | 'stage08_aggregate'
    | 'stage09_judge';

type StageStatus = 'idle' | 'running' | 'success' | 'error' | 'aborted';

type StageResult = {
    id: StageId;
    label: string;
    description: string;
    status: StageStatus;
    summary?: string;
    prompt?: string;
    detail?: string;
    errorMessage?: string;
    startedAt?: string;
    endedAt?: string;
};

type StreamEvent =
    | { event: 'stage_complete'; stage: StageId; data: Record<string, any> }
    | { event: 'error'; stage?: StageId; data: string }
    | { event: 'complete'; data: Record<string, any> };

const STAGE_META: Array<Omit<StageResult, 'status'>> = [
    { id: 'stage01_normalize', label: '01 정규화', description: '입력 클레임 표준화' },
    { id: 'stage02_querygen', label: '02 쿼리 생성', description: '검색 쿼리 생성' },
    { id: 'stage03_wiki', label: '03-1 위키 수집', description: '위키 기반 증거 수집' },
    { id: 'stage03_web', label: '03-2 웹 수집', description: '웹 기반 증거 수집' },
    { id: 'stage03_merge', label: '03-3 병합', description: '증거 데이터 병합' },
    { id: 'stage04_score', label: '04 점수화', description: '증거 스코어링' },
    { id: 'stage05_topk', label: '05 Top-K', description: '상위 증거 선정' },
    { id: 'stage06_verify_support', label: '06 지지 검증', description: '지지 증거 검증' },
    { id: 'stage07_verify_skeptic', label: '07 반박 검증', description: '반박 증거 검증' },
    { id: 'stage08_aggregate', label: '08 집계', description: '검증 결과 집계' },
    { id: 'stage09_judge', label: '09 판정', description: '최종 판단' },
];

const buildInitialStages = (): StageResult[] =>
    STAGE_META.map((stage) => ({
        ...stage,
        status: 'idle',
    }));

const formatDetail = (data: Record<string, any>) =>
    JSON.stringify(data, null, 2);

const extractPrompt = (stageId: StageId, data?: Record<string, any>) => {
    if (!data) return undefined;
    if (stageId === 'stage01_normalize') return data.prompt_normalize_user;
    if (stageId === 'stage02_querygen') return data.prompt_querygen_user;
    if (stageId === 'stage06_verify_support') return data.prompt_support_user;
    if (stageId === 'stage07_verify_skeptic') return data.prompt_skeptic_user;
    if (stageId === 'stage09_judge') return data.prompt_judge_user;
    return undefined;
};

const summarizeStageData = (stageId: StageId, data?: Record<string, any>) => {
    if (!data || Object.keys(data).length === 0) return '요약 준비 중';

    switch (stageId) {
        case 'stage01_normalize': {
            const claim = data.claim_text || data.canonical_evidence?.snippet;
            return claim ? `정규화: ${String(claim).slice(0, 140)}` : '정규화 결과 생성';
        }
        case 'stage02_querygen': {
            const variantCount = Array.isArray(data.query_variants) ? data.query_variants.length : 0;
            const hasBundles = data.keyword_bundles ? '키워드 묶음 생성' : '키워드 묶음 없음';
            return `쿼리 ${variantCount}개 · ${hasBundles}`;
        }
        case 'stage03_wiki': {
            const count = Array.isArray(data.wiki_candidates) ? data.wiki_candidates.length : 0;
            return `위키 후보 ${count}개 수집`;
        }
        case 'stage03_web': {
            const count = Array.isArray(data.web_candidates) ? data.web_candidates.length : 0;
            return `웹 후보 ${count}개 수집`;
        }
        case 'stage03_merge': {
            const count = Array.isArray(data.evidence_candidates) ? data.evidence_candidates.length : 0;
            return `증거 후보 ${count}개 병합`;
        }
        case 'stage04_score': {
            const count = Array.isArray(data.scored_evidence) ? data.scored_evidence.length : 0;
            return `스코어링 ${count}개`;
        }
        case 'stage05_topk': {
            const topk = Array.isArray(data.evidence_topk) ? data.evidence_topk.length : 0;
            const citations = Array.isArray(data.citations) ? data.citations.length : 0;
            return `Top-K ${topk}개 · 인용 ${citations}개`;
        }
        case 'stage06_verify_support': {
            const stance = data.verdict_support?.stance || 'UNVERIFIED';
            const conf = data.verdict_support?.confidence ?? 0;
            return `지지: ${stance} (${Number(conf).toFixed(2)})`;
        }
        case 'stage07_verify_skeptic': {
            const stance = data.verdict_skeptic?.stance || 'UNVERIFIED';
            const conf = data.verdict_skeptic?.confidence ?? 0;
            return `반박: ${stance} (${Number(conf).toFixed(2)})`;
        }
        case 'stage08_aggregate': {
            const stance = data.draft_verdict?.stance || 'UNVERIFIED';
            const score = data.quality_score ?? 0;
            return `집계: ${stance} · 품질 ${score}`;
        }
        case 'stage09_judge': {
            const stance = data.final_verdict?.label || data.final_verdict?.stance || 'UNVERIFIED';
            const conf = data.final_verdict?.confidence ?? 0;
            return `판정: ${stance} (${Number(conf).toFixed(2)})`;
        }
        default: {
            const keys = Object.keys(data).slice(0, 3).join(', ');
            return keys ? `keys: ${keys}` : '요약 준비 중';
        }
    }
};

export default function TruthCheckPage() {
    const [claim, setClaim] = useState("딥러닝의 아버지 제프리 힌튼은 노벨 물리학상을 수상했다.");
    const [stages, setStages] = useState<StageResult[]>(() => buildInitialStages());
    const [loading, setLoading] = useState(false);
    const [overallStatus, setOverallStatus] = useState<'idle' | 'running' | 'success' | 'error' | 'aborted'>('idle');
    const [generalError, setGeneralError] = useState<string | null>(null);
    const [finalResult, setFinalResult] = useState<Record<string, any> | null>(null);
    const abortControllerRef = useRef<AbortController | null>(null);
    const bufferRef = useRef<string>('');

    const stageIndexMap = useMemo(() => {
        const map = new Map<StageId, number>();
        stages.forEach((stage, index) => {
            map.set(stage.id, index);
        });
        return map;
    }, [stages]);

    const setStageStatus = (stageId: StageId, status: StageStatus, data?: Record<string, any>, errorMessage?: string) => {
        setStages((prev) =>
            prev.map((stage) => {
                if (stage.id !== stageId) return stage;
                return {
                    ...stage,
                    status,
                    summary: data ? summarizeStageData(stageId, data) : stage.summary,
                    prompt: data ? extractPrompt(stageId, data) : stage.prompt,
                    detail: data ? formatDetail(data) : stage.detail,
                    errorMessage: errorMessage ?? stage.errorMessage,
                    endedAt: status === 'success' || status === 'error' || status === 'aborted' ? new Date().toISOString() : stage.endedAt,
                };
            })
        );
    };

    const runPipeline = async () => {
        if (loading) return;
        setLoading(true);
        setStages(() => {
            const initial = buildInitialStages();
            if (initial.length > 0) {
                initial[0] = { ...initial[0], status: 'running', startedAt: new Date().toISOString() };
            }
            return initial;
        });
        setGeneralError(null);
        setFinalResult(null);
        setOverallStatus('running');
        bufferRef.current = '';

        abortControllerRef.current = new AbortController();
        const trimmedClaim = claim.trim();
        const inputType = /^https?:\/\//i.test(trimmedClaim) ? 'url' : 'text';

        try {
            const response = await fetch('/api/truth/check/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    input_type: inputType,
                    input_payload: trimmedClaim,
                    normalize_mode: 'llm',
                    include_full_outputs: true,
                    // Explicitly request full sequence
                    start_stage: 'stage01_normalize',
                    end_stage: 'stage09_judge'
                }),
                signal: abortControllerRef.current.signal,
            });

            if (!response.body) throw new Error("No response body");
            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value, { stream: true });
                bufferRef.current += chunk;
                const lines = bufferRef.current.split('\n');
                bufferRef.current = lines.pop() ?? '';

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const event = JSON.parse(line) as StreamEvent;
                        if (event.event === 'stage_complete') {
                            setStageStatus(event.stage, 'success', event.data);
                            const currentIndex = stageIndexMap.get(event.stage);
                            if (typeof currentIndex === 'number') {
                                setStages((prev) => {
                                    const next = [...prev];
                                    const nextIndex = currentIndex + 1;
                                    if (nextIndex < next.length && next[nextIndex].status === 'idle') {
                                        next[nextIndex] = {
                                            ...next[nextIndex],
                                            status: 'running',
                                            startedAt: new Date().toISOString(),
                                        };
                                    }
                                    return next;
                                });
                            }
                        } else if (event.event === 'error') {
                            if (event.stage) {
                                setStageStatus(event.stage, 'error', undefined, event.data);
                            }
                            setGeneralError(event.data);
                            setOverallStatus('error');
                            setLoading(false);
                        } else if (event.event === 'complete') {
                            setFinalResult(event.data);
                            setOverallStatus('success');
                        }
                    } catch (error: any) {
                        setGeneralError(`JSON parse error: ${error.message}`);
                    }
                }
            }
        } catch (error: any) {
            if (error.name !== 'AbortError') {
                setGeneralError(error.message);
                setOverallStatus('error');
            }
        } finally {
            setLoading(false);
        }
    };

    const abortRun = () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
            setOverallStatus('aborted');
            setLoading(false);
            setStages((prev) =>
                prev.map((stage) =>
                    stage.status === 'running' ? { ...stage, status: 'aborted', endedAt: new Date().toISOString() } : stage
                )
            );
        }
    };

    const overallBadge = (() => {
        if (overallStatus === 'success') return 'bg-emerald-500/20 text-emerald-200 border-emerald-500/40';
        if (overallStatus === 'error') return 'bg-red-500/20 text-red-200 border-red-500/40';
        if (overallStatus === 'aborted') return 'bg-yellow-500/20 text-yellow-100 border-yellow-500/40';
        if (overallStatus === 'running') return 'bg-blue-500/20 text-blue-200 border-blue-500/40';
        return 'bg-slate-600/20 text-slate-200 border-slate-600/40';
    })();

    return (
        <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.18),_transparent_55%),radial-gradient(circle_at_left,_rgba(56,189,248,0.12),_transparent_45%),linear-gradient(180deg,_#0b0f1a_0%,_#121826_45%,_#0b0f1a_100%)] text-white">
            <div className="max-w-6xl mx-auto px-6 py-10">
                <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <p className="text-xs uppercase tracking-[0.2em] text-emerald-200/70">Pipeline Monitor</p>
                        <h1 className="text-3xl font-semibold text-white">Truth Check Pipeline</h1>
                        <p className="text-sm text-slate-300 mt-2">
                            각 stage 완료 시점마다 결과를 순차적으로 출력합니다.
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <span className={`px-3 py-1 rounded-full text-[11px] border ${overallBadge}`}>
                            {overallStatus.toUpperCase()}
                        </span>
                        <div className="text-xs text-slate-400">
                            {loading ? 'Streaming...' : 'Idle'}
                        </div>
                    </div>
                </div>

                <div className="mt-8 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-6 shadow-[0_20px_70px_-40px_rgba(15,118,110,0.8)]">
                        <div className="flex items-center justify-between">
                            <h2 className="text-lg font-semibold">입력</h2>
                            <span className="text-xs text-slate-400">Claim 또는 URL</span>
                        </div>
                        <input
                            type="text"
                            value={claim}
                            onChange={(e) => setClaim(e.target.value)}
                            className="mt-4 w-full rounded-xl border border-white/10 bg-[#0f1424] px-4 py-3 text-sm text-white shadow-inner focus:border-emerald-400/60 focus:outline-none focus:ring-2 focus:ring-emerald-400/20"
                            placeholder="검증할 문장 또는 URL을 입력하세요."
                        />
                        <div className="mt-4 flex flex-wrap gap-3">
                            <button
                                onClick={runPipeline}
                                disabled={loading}
                                className="rounded-xl bg-emerald-500 px-5 py-2 text-sm font-semibold text-emerald-950 shadow-lg shadow-emerald-500/30 transition hover:bg-emerald-400 disabled:opacity-50"
                            >
                                {loading ? 'Running...' : 'Run'}
                            </button>
                            <button
                                onClick={abortRun}
                                disabled={!loading}
                                className="rounded-xl border border-white/10 bg-white/5 px-5 py-2 text-sm font-semibold text-white/90 transition hover:bg-white/10 disabled:opacity-50"
                            >
                                Abort
                            </button>
                        </div>
                        {generalError ? (
                            <div className="mt-4 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                                {generalError}
                            </div>
                        ) : null}
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
                        <h2 className="text-lg font-semibold">요약 상태</h2>
                        <p className="mt-2 text-xs text-slate-400">Stream 상태 요약</p>
                        <div className="mt-4 rounded-xl border border-white/10 bg-[#0f1424] p-4 text-sm text-slate-200">
                            {overallStatus === 'running' && '파이프라인 실행 중'}
                            {overallStatus === 'success' && '전체 완료'}
                            {overallStatus === 'error' && '오류 발생'}
                            {overallStatus === 'aborted' && '중단됨'}
                            {overallStatus === 'idle' && '대기 중'}
                        </div>
                    </div>
                </div>

                <div className="mt-10">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold">Stage Timeline</h2>
                        <span className="text-xs text-slate-400">{stages.length} stages</span>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                        {stages.map((stage) => {
                            const statusColor =
                                stage.status === 'success'
                                    ? 'border-emerald-500/40 bg-emerald-500/10'
                                    : stage.status === 'error'
                                    ? 'border-red-500/40 bg-red-500/10'
                                    : stage.status === 'running'
                                    ? 'border-sky-400/40 bg-sky-400/10'
                                    : stage.status === 'aborted'
                                    ? 'border-amber-400/40 bg-amber-400/10'
                                    : 'border-white/10 bg-white/5';

                            return (
                                <div key={stage.id} className={`rounded-2xl border px-4 py-4 ${statusColor}`}>
                                    <div className="flex items-start justify-between gap-3">
                                        <div>
                                            <div className="text-sm font-semibold">{stage.label}</div>
                                            <div className="text-xs text-slate-300">{stage.description}</div>
                                        </div>
                                        <span className="rounded-full bg-white/10 px-2 py-1 text-[10px] uppercase text-slate-200">
                                            {stage.status}
                                        </span>
                                    </div>
                                    <div className="mt-3 text-sm text-slate-100">
                                        {stage.errorMessage ? (
                                            <span className="text-red-200">{stage.errorMessage}</span>
                                        ) : (
                                            stage.summary || '요약 준비 중'
                                        )}
                                    </div>
                                    {stage.prompt ? (
                                        <details className="mt-3 text-xs text-slate-300">
                                            <summary className="cursor-pointer text-slate-200">Prompt 보기</summary>
                                            <pre className="mt-2 whitespace-pre-wrap break-words">{stage.prompt}</pre>
                                        </details>
                                    ) : null}
                                    {stage.detail ? (
                                        <details className="mt-3 text-xs text-slate-300">
                                            <summary className="cursor-pointer text-slate-200">JSON 보기</summary>
                                            <pre className="mt-2 whitespace-pre-wrap break-words">{stage.detail}</pre>
                                        </details>
                                    ) : null}
                                </div>
                            );
                        })}
                    </div>
                </div>

                <div className="mt-10 rounded-2xl border border-white/10 bg-white/5 p-6">
                    <h2 className="text-lg font-semibold">최종 결과</h2>
                    <p className="mt-2 text-xs text-slate-400">complete 이벤트 기준</p>
                    <div className="mt-4 rounded-xl border border-white/10 bg-[#0f1424] p-4">
                        {finalResult ? (
                            <pre className="text-xs whitespace-pre-wrap break-words text-slate-200">
                                {JSON.stringify(finalResult, null, 2)}
                            </pre>
                        ) : (
                            <div className="text-sm text-slate-500">아직 결과가 없습니다.</div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
