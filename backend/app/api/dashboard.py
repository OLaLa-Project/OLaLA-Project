import json
import os
import shutil
import socket
import subprocess
from typing import Any, Dict, Generator, Iterable, Optional

import requests
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.settings import settings
from app.core.observability import snapshot_observability

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None

from app.db.session import get_db, SessionLocal
from app.services.wiki_retriever import retrieve_wiki_hits

router = APIRouter(prefix="/api")

OLLAMA_URL = settings.ollama_url
OLLAMA_TIMEOUT = settings.ollama_timeout
NAVER_CLIENT_ID = settings.naver_client_id.strip()
NAVER_CLIENT_SECRET = settings.naver_client_secret.strip()


class TeamAQueryGenRequest(BaseModel):
    model: Optional[str] = None
    user_request: str = ""
    title: str = ""
    article_text: str = Field(..., min_length=1)
    prompt: Optional[str] = None


class TeamAQueryGenResponse(BaseModel):
    ok: bool
    model: str
    prompt: str
    raw: str
    response_json: Optional[Dict[str, Any]] = Field(default=None, alias="json")
    error: Optional[str] = None


class TeamARetrieveRequest(BaseModel):
    claims: list[Dict[str, Any]]
    top_k: int = Field(6, ge=1, le=20)
    page_limit: int = Field(8, ge=1, le=50)
    window: int = Field(2, ge=0, le=5)
    max_chars: int = Field(2000, ge=200, le=20000)
    embed_missing: bool = True
    search_mode: str = "auto"
    news_display: int = Field(5, ge=1, le=20)


def _build_team_a_prompt(user_request: str, title: str, article_text: str) -> str:
    return (
        "너는 단순 요약기가 아니라, 기사 속 의도/논란의 소지를 파헤치는 ‘수석 팩트체커 + QueryGen(Stage2)’이다.\n"
        "입력으로 주어진 title과 [SENTENCES]를 바탕으로,\n"
        "(1) 기사 주제와 core_narrative를 작성하고,\n"
        "(2) 검증이 필요한 핵심 claims 3개를 [SENTENCES]에서 “문장 그대로” 선택하며,\n"
        "(3) 각 claim마다 verification_reason, time_sensitivity, 그리고 위키피디아 로컬 DB 조회용 쿼리(wiki_db)와 최신 뉴스 검색용 쿼리(news_search)를 생성하라.\n\n"
        "[절대 규칙]\n"
        "1) 출력은 오직 “유효한 JSON”만 허용한다. 마크다운, 주석, 코드펜스(```)를 절대 포함하지 마라.\n"
        "2) 아래 [SENTENCES]는 article_text를 문장 단위로 분해한 것이다.\n"
        "3) claims[].주장 값은 반드시 [SENTENCES]의 문장 텍스트를 “완전히 동일하게” 그대로 복사해야 한다.\n"
        "   - 글자 하나라도 바꾸면 실패다(띄어쓰기/따옴표/조사/숫자 포함).\n"
        "   - 문장 일부만 발췌하지 말고, 반드시 ‘한 문장 전체’를 그대로 사용해라.\n"
        "4) claims는 정확히 3개만 출력한다. claim_id는 C1, C2, C3 고정.\n"
        "5) claim_type은 반드시 아래 중 하나로만 선택한다:\n"
        "   - 사건 | 논리 | 통계 | 인용 | 정책\n"
        "6) verification_reason는 “왜 이 문장이 핵심 논점/논란 포인트인지”를 맥락적으로 설명하되, 기사 밖의 새로운 사실을 만들어내지 마라.\n"
        "7) time_sensitivity는 low|mid|high 중 하나로 지정한다.\n"
        "   - high: 최신 논란/팬 반응/시즌 전망/최근 발언 등 시점 영향이 큰 것\n"
        "   - low: 인물/팀/리그/제도처럼 시간 영향이 적은 것\n"
        "8) query_pack 생성 규칙:\n"
        "   8-1) wiki_db: 정확히 3개를 생성한다. 각 원소는 {\"mode\":\"title|fulltext\",\"q\":\"string\"} 형식의 객체다.\n"
        "        - 목적: ‘검증’이 아니라 로컬 위키에서 배경/정의/고정 사실(인물·팀·리그·대회·제도)을 찾기 위함.\n"
        "        - title은 실제 문서 제목으로 존재할 가능성이 높은 엔터티(인물/팀/리그/대회/제도)를 우선한다.\n"
        "        - fulltext는 개념/동의어/표기 변형을 포함해 검색 폭을 넓힌다.\n"
        "        - 한국어 타이틀을 우선하고, 영문 표기는 필요 시 fulltext에 보조로 넣어라.\n"
        "        - 이 기사처럼 위키 검증이 불필요한 claim이어도 wiki_db는 “배경 확보용”으로만 최소한으로 구성해라(예: 인물/팀/리그).\n"
        "   8-2) news_search: 각 claim마다 정확히 4개 “문자열”을 생성한다. (객체/딕셔너리 금지)\n"
        "        - 구성: (진위/공식 확인용 2개) + (반대/비교 데이터 탐색용 2개)\n"
        "        - 필요 시 연도/시점, 공식 출처 키워드(구단 발표, KBO 공식 기록, 인터뷰 원문 등)를 포함한다.\n"
        "9) JSON 스키마를 반드시 지켜라.\n\n"
        "[출력 스키마]\n"
        "{\n"
        "  \"주제\": \"string\",\n"
        "  \"core_narrative\": \"string\",\n"
        "  \"claims\": [\n"
        "    {\n"
        "      \"claim_id\": \"C1\",\n"
        "      \"주장\": \"string\",\n"
        "      \"claim_type\": \"사건|논리|통계|인용|정책\",\n"
        "      \"verification_reason\": \"string\",\n"
        "      \"time_sensitivity\": \"low|mid|high\",\n"
        "      \"query_pack\": {\n"
        "        \"wiki_db\": [\n"
        "          {\"mode\":\"title|fulltext\",\"q\":\"string\"},\n"
        "          {\"mode\":\"title|fulltext\",\"q\":\"string\"},\n"
        "          {\"mode\":\"title|fulltext\",\"q\":\"string\"}\n"
        "        ],\n"
        "        \"news_search\": [\"string\",\"string\",\"string\",\"string\"]\n"
        "      }\n"
        "    },\n"
        "    {\n"
        "      \"claim_id\": \"C2\",\n"
        "      \"주장\": \"string\",\n"
        "      \"claim_type\": \"사건|논리|통계|인용|정책\",\n"
        "      \"verification_reason\": \"string\",\n"
        "      \"time_sensitivity\": \"low|mid|high\",\n"
        "      \"query_pack\": {\n"
        "        \"wiki_db\": [\n"
        "          {\"mode\":\"title|fulltext\",\"q\":\"string\"},\n"
        "          {\"mode\":\"title|fulltext\",\"q\":\"string\"},\n"
        "          {\"mode\":\"title|fulltext\",\"q\":\"string\"}\n"
        "        ],\n"
        "        \"news_search\": [\"string\",\"string\",\"string\",\"string\"]\n"
        "      }\n"
        "    },\n"
        "    {\n"
        "      \"claim_id\": \"C3\",\n"
        "      \"주장\": \"string\",\n"
        "      \"claim_type\": \"사건|논리|통계|인용|정책\",\n"
        "      \"verification_reason\": \"string\",\n"
        "      \"time_sensitivity\": \"low|mid|high\",\n"
        "      \"query_pack\": {\n"
        "        \"wiki_db\": [\n"
        "          {\"mode\":\"title|fulltext\",\"q\":\"string\"},\n"
        "          {\"mode\":\"title|fulltext\",\"q\":\"string\"},\n"
        "          {\"mode\":\"title|fulltext\",\"q\":\"string\"}\n"
        "        ],\n"
        "        \"news_search\": [\"string\",\"string\",\"string\",\"string\"]\n"
        "      }\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "[INPUT]\n"
        f"user_request: \"{user_request}\"\n"
        f"title: \"{title}\"\n"
        "SENTENCES:\n"
        f"{article_text}\n"
        "[/INPUT]\n\n"
        "[최종 점검(출력 금지)]\n"
        "- JSON만 출력했는가? (첫 글자 {, 마지막 글자 })\n"
        "- claims 3개인가? claim_id가 C1~C3인가?\n"
        "- 각 주장 문장이 [SENTENCES] 중 하나와 완전히 동일한가?\n"
        "- news_search가 문자열 4개인가? (객체 금지)\n"
        "- wiki_db가 객체 3개인가? mode가 title|fulltext 중 하나인가?\n\n"
        "이제 JSON만 출력하라.\n"
    )


def _proxy_json(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> requests.Response:
    url = f"{OLLAMA_URL}{path}"
    return requests.request(
        method,
        url,
        json=payload,
        timeout=OLLAMA_TIMEOUT,
    )


def _stream_ollama(path: str, payload: Dict[str, Any]) -> Iterable[bytes]:
    url = f"{OLLAMA_URL}{path}"
    with requests.post(url, json=payload, stream=True, timeout=OLLAMA_TIMEOUT) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                yield line + b"\n"


def _naver_news_search(query: str, display: int = 5) -> Dict[str, Any]:
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return {"query": query, "items": [], "error": "naver credentials missing"}
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params: Dict[str, str | int] = {"query": query, "display": display, "sort": "date"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if not resp.ok:
            return {"query": query, "items": [], "error": f"naver http {resp.status_code}"}
        data = resp.json()
        items = []
        for item in data.get("items", []):
            items.append(
                {
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "originallink": item.get("originallink"),
                    "pubDate": item.get("pubDate"),
                    "description": item.get("description"),
                }
            )
        return {"query": query, "items": items, "error": None}
    except Exception as err:
        return {"query": query, "items": [], "error": str(err)}


def _get_system_stats() -> Dict[str, Any]:
    if not psutil:
        return {
            "total": None,
            "used": None,
            "available": None,
            "percent": None,
            "cpu_percent": None,
        }
    mem = psutil.virtual_memory()
    return {
        "total": mem.total,
        "used": mem.total - mem.available,
        "available": mem.available,
        "percent": mem.percent,
        "cpu_percent": psutil.cpu_percent(interval=None),
    }


def _get_api_stats() -> Dict[str, Any]:
    pid = os.getpid()
    if not psutil:
        return {"pid": pid, "cpu": None, "rss": None}
    proc = psutil.Process(pid)
    try:
        rss = proc.memory_info().rss
        cpu = proc.cpu_percent(interval=None)
    except Exception:
        rss = None
        cpu = None
    return {"pid": pid, "cpu": cpu, "rss": rss}


def _get_ollama_stats() -> Dict[str, Any]:
    if not psutil:
        return {"rss": None, "pids": []}
    rss_total = 0
    pids = []
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            name = proc.info.get("name") or ""
            if "ollama" not in name.lower():
                continue
            mem = proc.info.get("memory_info")
            if mem:
                rss_total += mem.rss
            pids.append(proc.info.get("pid"))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {"rss": rss_total if pids else None, "pids": pids}


def _get_gpu_stats() -> Dict[str, Any]:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return {"ok": False, "note": "nvidia-smi not found"}
    cmd = [
        smi,
        "--query-gpu=utilization.gpu,memory.used,memory.total,name",
        "--format=csv,noheader,nounits",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        note = proc.stderr.strip() or "nvidia-smi failed"
        return {"ok": False, "note": note}
    line = (proc.stdout or "").strip().splitlines()[0:1]
    if not line:
        return {"ok": False, "note": "nvidia-smi returned no data"}
    parts = [p.strip() for p in line[0].split(",")]
    if len(parts) < 4:
        return {"ok": False, "note": "unexpected nvidia-smi output"}
    try:
        util = int(parts[0])
    except ValueError:
        util = None
    try:
        mem_used = int(parts[1])
        mem_total = int(parts[2])
    except ValueError:
        mem_used = None
        mem_total = None
    name = parts[3]
    return {
        "ok": True,
        "util": util,
        "mem_used": mem_used,
        "mem_total": mem_total,
        "name": name,
    }


def _docker_ctl(action: str) -> Dict[str, Any]:
    if action not in {"start", "stop"}:
        return {"ok": False, "error": "invalid action"}
    path = f"/containers/olala-ollama/{'start' if action == 'start' else 'stop'}"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect("/var/run/docker.sock")
            req = f"POST {path} HTTP/1.1\r\nHost: docker\r\nContent-Length: 0\r\n\r\n"
            sock.sendall(req.encode("utf-8"))
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\r\n\r\n" in data:
                    break
    except FileNotFoundError:
        return {"ok": False, "error": "docker socket not available"}
    except socket.timeout:
        return {"ok": False, "error": "docker socket timeout"}
    except OSError as err:
        return {"ok": False, "error": str(err)}

    header, _, body = data.partition(b"\r\n\r\n")
    status_line = header.splitlines()[0].decode("utf-8", "replace") if header else ""
    parts = status_line.split()
    status_code = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
    if status_code in {204, 304}:
        return {"ok": True}
    message = body.decode("utf-8", "replace").strip()
    return {"ok": False, "error": message or status_line or "docker api failed"}


@router.post("/team-a/querygen")
def team_a_querygen(req: TeamAQueryGenRequest) -> JSONResponse:
    model = (req.model or "").strip() or "gemma2:2b"
    prompt = req.prompt or _build_team_a_prompt(req.user_request, req.title, req.article_text)
    try:
        resp = _proxy_json(
            "POST",
            "/api/generate",
            {"model": model, "prompt": prompt, "stream": False},
        )
        if not resp.ok:
            return JSONResponse(
                TeamAQueryGenResponse(
                    ok=False,
                    model=model,
                    prompt=prompt,
                    raw="",
                    error=f"ollama error: {resp.status_code}",
                ).model_dump(),
                status_code=502,
            )
        data = resp.json()
        raw = (data.get("response") or "").strip()
        parsed = None
        error = None
        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as err:
                error = f"json_parse_error: {err}"
        return JSONResponse(
            TeamAQueryGenResponse(
                ok=True,
                model=model,
                prompt=prompt,
                raw=raw,
                json=parsed,
                error=error,
            ).model_dump()
        )
    except Exception as err:
        return JSONResponse(
            TeamAQueryGenResponse(
                ok=False,
                model=model,
                prompt=prompt,
                raw="",
                error=str(err),
            ).model_dump(),
            status_code=502,
        )


@router.post("/team-a/retrieve")
def team_a_retrieve(req: TeamARetrieveRequest, db: Session = Depends(get_db)) -> JSONResponse:
    results: list[Dict[str, Any]] = []
    for item in req.claims:
        claim_id = item.get("claim_id") or item.get("claimId") or item.get("id") or "-"
        query_pack = item.get("query_pack") or {}
        wiki_items = query_pack.get("wiki_db") if isinstance(query_pack, dict) else None
        news_queries = query_pack.get("news_search") if isinstance(query_pack, dict) else None
        if isinstance(news_queries, str):
            news_queries = [news_queries]
        news_queries = [str(q).strip() for q in (news_queries or []) if str(q).strip()]
        if isinstance(wiki_items, dict):
            wiki_items = [wiki_items]
        queries: list[str] = []
        for item_q in wiki_items or []:
            if isinstance(item_q, dict):
                q = str(item_q.get("q") or "").strip()
            else:
                q = str(item_q or "").strip()
            if q:
                queries.append(q)

        def run_query(query: str) -> Dict[str, Any]:
            local_db = SessionLocal()
            try:
                pack = retrieve_wiki_hits(
                    local_db,
                    question=query,
                    top_k=req.top_k,
                    window=req.window,
                    page_limit=req.page_limit,
                    embed_missing=req.embed_missing,
                    max_chars=req.max_chars,
                    search_mode=req.search_mode,
                )
                return {
                    "query": query,
                    "candidates": pack.get("candidates", []),
                    "hits": pack.get("hits", []),
                    "debug": pack.get("debug"),
                }
            finally:
                local_db.close()

        wiki_results: list[Dict[str, Any]] = []
        news_results: list[Dict[str, Any]] = []
        if queries or news_queries:
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures: Dict[str, Any] = {}
                if queries:
                    futures["wiki"] = pool.submit(lambda: list(map(run_query, queries)))
                if news_queries:
                    futures["news"] = pool.submit(
                        lambda: list(
                            map(lambda q: _naver_news_search(q, req.news_display), news_queries)
                        )
                    )
                if "wiki" in futures:
                    wiki_results = futures["wiki"].result()
                if "news" in futures:
                    news_results = futures["news"].result()
        results.append(
            {
                "claim_id": claim_id,
                "wiki": wiki_results,
                "news": news_results,
                "skipped": not wiki_results and not news_results,
            }
        )
    return JSONResponse({"ok": True, "results": results})


@router.get("/health")
def api_health() -> JSONResponse:
    ok = True
    version = None
    ollama_ok = False
    try:
        resp = _proxy_json("GET", "/api/version")
        if resp.ok:
            data = resp.json()
            version = data.get("version")
            ollama_ok = True
    except Exception:
        ollama_ok = False
    return JSONResponse({"ok": ok, "status": "healthy", "ollama_ok": ollama_ok, "version": version})


@router.get("/models")
def api_models() -> JSONResponse:
    try:
        resp = _proxy_json("GET", "/api/tags")
        if not resp.ok:
            return JSONResponse({"ok": False, "error": "ollama tags failed"}, status_code=502)
        data = resp.json()
        return JSONResponse({"ok": True, "models": data.get("models", [])})
    except Exception as err:
        return JSONResponse({"ok": False, "error": str(err)}, status_code=502)


@router.get("/ps")
def api_ps() -> JSONResponse:
    try:
        resp = _proxy_json("GET", "/api/ps")
        if not resp.ok:
            return JSONResponse({"ok": False, "error": "ollama ps failed"}, status_code=502)
        data = resp.json()
        return JSONResponse({"ok": True, "models": data.get("models", [])})
    except Exception as err:
        return JSONResponse({"ok": False, "error": str(err)}, status_code=502)


@router.get("/metrics")
def api_metrics() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "system": _get_system_stats(),
            "api": _get_api_stats(),
            "ollama": _get_ollama_stats(),
            "gpu": _get_gpu_stats(),
            "pipeline": snapshot_observability(),
        }
    )


@router.post("/generate-stream")
async def api_generate_stream(request: Request) -> StreamingResponse:
    payload = await request.json()
    model = (payload.get("model") or "").strip()
    prompt = payload.get("prompt") or ""
    options = payload.get("options") or None
    if not model:
        return StreamingResponse(
            (b'{"error":"model is required"}\n',),
            status_code=400,
            media_type="application/x-ndjson",
        )
    req = {"model": model, "prompt": prompt, "stream": True}
    if options:
        req["options"] = options

    def gen() -> Generator[bytes, None, None]:
        try:
            for line in _stream_ollama("/api/generate", req):
                yield line
        except requests.RequestException as err:
            message = str(err)
            yield json.dumps({"error": message}).encode("utf-8") + b"\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@router.post("/pull-stream")
async def api_pull_stream(request: Request) -> StreamingResponse:
    payload = await request.json()
    name = (payload.get("name") or payload.get("model") or "").strip()
    if not name:
        return StreamingResponse(
            (b'{"error":"name is required"}\n',),
            status_code=400,
            media_type="application/x-ndjson",
        )
    req = {"name": name, "stream": True}

    def gen() -> Generator[bytes, None, None]:
        try:
            for line in _stream_ollama("/api/pull", req):
                yield line
        except requests.HTTPError as err:
            message = str(err)
            yield json.dumps({"error": message}).encode("utf-8") + b"\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@router.post("/warm")
async def api_warm(request: Request) -> JSONResponse:
    payload = await request.json()
    model = (payload.get("model") or "").strip()
    if not model:
        return JSONResponse({"ok": False, "error": "model is required"}, status_code=400)
    req = {
        "model": model,
        "prompt": "hello",
        "stream": False,
        "keep_alive": "5m",
    }
    try:
        resp = _proxy_json("POST", "/api/generate", req)
        return JSONResponse({"ok": resp.ok})
    except Exception as err:
        return JSONResponse({"ok": False, "error": str(err)}, status_code=502)


@router.post("/ollama/down")
def api_ollama_down() -> JSONResponse:
    data = _docker_ctl("stop")
    status = 200 if data.get("ok") else 500
    return JSONResponse(data, status_code=status)


@router.post("/ollama/up")
def api_ollama_up() -> JSONResponse:
    data = _docker_ctl("start")
    status = 200 if data.get("ok") else 500
    return JSONResponse(data, status_code=status)


@router.post("/rag-stream")
async def api_rag_stream(request: Request) -> StreamingResponse:
    payload = await request.json()
    model = (payload.get("model") or "").strip()
    question = (payload.get("question") or payload.get("prompt") or "").strip()
    options = payload.get("options") or None
    top_k = payload.get("top_k") or 6
    max_chars = payload.get("max_chars") or 4200
    if not model:
        return StreamingResponse(
            (b'{"error":"model is required"}\n',),
            status_code=400,
            media_type="application/x-ndjson",
        )
    if not question:
        return StreamingResponse(
            (b'{"error":"question is required"}\n',),
            status_code=400,
            media_type="application/x-ndjson",
        )
    req = {"model": model, "prompt": question, "stream": True}
    if options:
        req["options"] = options

    def gen() -> Generator[bytes, None, None]:
        meta_line = {
            "type": "sources",
            "sources": [],
            "meta": {"mode": "proxy", "hits": 0, "top_k": top_k, "max_chars": max_chars},
        }
        yield json.dumps(meta_line).encode("utf-8") + b"\n"
        try:
            for line in _stream_ollama("/api/generate", req):
                yield line
        except requests.RequestException as err:
            message = str(err)
            yield json.dumps({"error": message}).encode("utf-8") + b"\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")
