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

const summarizeStageData = (data?: Record<string, any>) => {
    if (!data || Object.keys(data).length === 0) return '요약 준비 중';
    if (typeof data.summary === 'string' && data.summary.trim()) return data.summary.trim();
    if (typeof data.label === 'string') return `label: ${data.label}`;
    if (typeof data.answer === 'string') return data.answer.slice(0, 120);
    const keys = Object.keys(data).slice(0, 3).join(', ');
    return keys ? `keys: ${keys}` : '요약 준비 중';
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
                    summary: data ? summarizeStageData(data) : stage.summary,
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

        try {
            const response = await fetch('/api/truth/check/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    input_type: 'claim',
                    input_payload: claim,
                    normalize_mode: 'soft',
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
        <div className="p-8 max-w-5xl mx-auto text-white">
            <div className="flex items-center justify-between gap-4 mb-6">
                <div>
                    <h1 className="text-2xl font-bold">Truth Check Pipeline</h1>
                    <p className="text-sm text-slate-300">Stage별 진행 상태와 결과를 순차적으로 출력합니다.</p>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs border ${overallBadge}`}>
                    {overallStatus.toUpperCase()}
                </span>
            </div>

            <div className="flex flex-col gap-3 mb-6">
                <input
                    type="text"
                    value={claim}
                    onChange={(e) => setClaim(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-4 py-2 text-white"
                    placeholder="Enter claim to verify..."
                />
                <div className="flex gap-3">
                    <button
                        onClick={runPipeline}
                        disabled={loading}
                        className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-6 py-2 rounded font-bold"
                    >
                        {loading ? 'Running...' : 'Run'}
                    </button>
                    <button
                        onClick={abortRun}
                        disabled={!loading}
                        className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-6 py-2 rounded font-bold"
                    >
                        Abort
                    </button>
                </div>
            </div>

            {generalError ? (
                <div className="mb-6 border border-red-500/40 bg-red-500/10 text-red-200 rounded px-4 py-3">
                    {generalError}
                </div>
            ) : null}

            <div className="grid gap-4">
                {stages.map((stage) => {
                    const statusColor =
                        stage.status === 'success'
                            ? 'border-emerald-500/40 bg-emerald-500/10'
                            : stage.status === 'error'
                            ? 'border-red-500/40 bg-red-500/10'
                            : stage.status === 'running'
                            ? 'border-blue-500/40 bg-blue-500/10'
                            : stage.status === 'aborted'
                            ? 'border-yellow-500/40 bg-yellow-500/10'
                            : 'border-gray-800 bg-gray-900/40';

                    return (
                        <div key={stage.id} className={`rounded-lg border px-4 py-3 ${statusColor}`}>
                            <div className="flex items-center justify-between gap-4">
                                <div>
                                    <div className="font-semibold">{stage.label}</div>
                                    <div className="text-xs text-slate-300">{stage.description}</div>
                                </div>
                                <span className="text-xs uppercase text-slate-200">
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
                            {stage.detail ? (
                                <details className="mt-3 text-xs text-slate-300">
                                    <summary className="cursor-pointer text-slate-200">상세 보기</summary>
                                    <pre className="mt-2 whitespace-pre-wrap break-words">{stage.detail}</pre>
                                </details>
                            ) : null}
                        </div>
                    );
                })}
            </div>

            <div className="mt-8 border border-gray-800 rounded-lg bg-gray-900/60 p-4">
                <h2 className="font-semibold mb-2">최종 결과</h2>
                {finalResult ? (
                    <pre className="text-xs whitespace-pre-wrap break-words text-slate-200">
                        {JSON.stringify(finalResult, null, 2)}
                    </pre>
                ) : (
                    <div className="text-sm text-slate-400">아직 결과가 없습니다.</div>
                )}
            </div>
        </div>
    );
}
