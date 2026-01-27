import json
import os
import shutil
import socket
import subprocess
from typing import Any, Dict, Generator, Iterable, Optional

import requests
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    psutil = None


router = APIRouter(prefix="/api")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "60"))


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
        except requests.HTTPError as err:
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
        except requests.HTTPError as err:
            message = str(err)
            yield json.dumps({"error": message}).encode("utf-8") + b"\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")
