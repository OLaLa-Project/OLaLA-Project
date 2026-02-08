from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from sqlalchemy import text

from app.core.settings import settings
from app.db.session import SessionLocal
from app.orchestrator.embedding.client import embed_texts, vec_to_pgvector_literal


FETCH_SQL = text(
    """
    SELECT chunk_id, content
    FROM public.wiki_chunks
    WHERE embedding IS NULL
      AND chunk_id > :cursor
    ORDER BY chunk_id ASC
    LIMIT :limit
    """
)

UPDATE_SQL = text(
    """
    UPDATE public.wiki_chunks
    SET embedding = (:vec)::vector
    WHERE chunk_id = :cid
    """
)

COUNT_SQL = text(
    """
    SELECT
      COUNT(*) AS total,
      COUNT(*) FILTER (WHERE embedding IS NULL) AS missing
    FROM public.wiki_chunks
    """
)


@dataclass
class Counters:
    processed: int = 0
    failed: int = 0
    batches: int = 0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(event: str, **payload: object) -> None:
    line = {"ts": _utc_now(), "event": event, **payload}
    print(json.dumps(line, ensure_ascii=True), flush=True)


def _append_failure_log(path: Path, chunk_id: int, reason: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(
            json.dumps(
                {"ts": _utc_now(), "chunk_id": chunk_id, "reason": reason},
                ensure_ascii=False,
            )
            + "\n"
        )


def _fetch_batch(cursor: int, limit: int) -> list[tuple[int, str]]:
    with SessionLocal() as db:
        rows = db.execute(FETCH_SQL, {"cursor": cursor, "limit": limit}).all()
    return [(int(row[0]), str(row[1])) for row in rows]


def _write_vectors(pairs: Sequence[tuple[int, list[float]]], ndigits: int) -> int:
    if not pairs:
        return 0

    with SessionLocal() as db:
        for chunk_id, vector in pairs:
            db.execute(
                UPDATE_SQL,
                {"cid": int(chunk_id), "vec": vec_to_pgvector_literal(vector, ndigits=ndigits)},
            )
        db.commit()
    return len(pairs)


def _embed_and_store_rows(
    rows: list[tuple[int, str]],
    *,
    model: str | None,
    ollama_url: str | None,
    timeout: int,
    ndigits: int,
    max_chars: int,
    failure_log: Path,
) -> tuple[int, int]:
    """
    Try batch embedding first.
    If batch fails, recursively split rows to isolate failing chunks.
    """
    if not rows:
        return 0, 0

    texts = [content[:max_chars] if max_chars > 0 else content for _, content in rows]

    try:
        vectors = embed_texts(
            texts,
            model=model,
            ollama_url=ollama_url,
            timeout=timeout,
        )
        if len(vectors) != len(rows):
            raise ValueError(
                f"embedding count mismatch: vectors={len(vectors)} rows={len(rows)}"
            )

        pairs = list(zip([chunk_id for chunk_id, _ in rows], vectors))
        written = _write_vectors(pairs, ndigits=ndigits)
        return written, 0

    except Exception as exc:
        if len(rows) == 1:
            chunk_id = rows[0][0]
            reason = str(exc)
            _append_failure_log(failure_log, chunk_id, reason)
            _log("chunk_failed", chunk_id=chunk_id, reason=reason)
            return 0, 1

        mid = len(rows) // 2
        left_ok, left_fail = _embed_and_store_rows(
            rows[:mid],
            model=model,
            ollama_url=ollama_url,
            timeout=timeout,
            ndigits=ndigits,
            max_chars=max_chars,
            failure_log=failure_log,
        )
        right_ok, right_fail = _embed_and_store_rows(
            rows[mid:],
            model=model,
            ollama_url=ollama_url,
            timeout=timeout,
            ndigits=ndigits,
            max_chars=max_chars,
            failure_log=failure_log,
        )
        return left_ok + right_ok, left_fail + right_fail


def _count_total_and_missing() -> tuple[int, int]:
    with SessionLocal() as db:
        row = db.execute(COUNT_SQL).one()
    total = int(row[0])
    missing = int(row[1])
    return total, missing


def _should_stop(stop_file: str) -> bool:
    return bool(stop_file) and os.path.exists(stop_file)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill embeddings for public.wiki_chunks in controlled batches."
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-chunks", type=int, default=0)
    parser.add_argument("--report-every", type=int, default=20)
    parser.add_argument("--sleep-ms", type=int, default=0)
    parser.add_argument("--timeout-sec", type=int, default=60)
    parser.add_argument("--max-chars", type=int, default=2000)
    parser.add_argument("--start-cursor", type=int, default=0)
    parser.add_argument("--model", type=str, default="")
    parser.add_argument("--ollama-url", type=str, default="")
    parser.add_argument("--ndigits", type=int, default=settings.embed_ndigits)
    parser.add_argument("--stop-file", type=str, default=(settings.embed_stop_file or "/tmp/wiki-embed.stop"))
    parser.add_argument(
        "--failure-log",
        type=str,
        default="/tmp/wiki-embed-failures.jsonl",
        help="JSONL log for failed chunk_ids",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.batch_size <= 0:
        _log("fatal", reason="batch-size must be > 0")
        return 1
    if args.max_chunks < 0:
        _log("fatal", reason="max-chunks must be >= 0")
        return 1
    if args.report_every <= 0:
        _log("fatal", reason="report-every must be > 0")
        return 1
    if args.max_chars < 0:
        _log("fatal", reason="max-chars must be >= 0")
        return 1

    model = args.model.strip() or None
    ollama_url = args.ollama_url.strip() or None
    failure_log = Path(args.failure_log)

    total, missing = _count_total_and_missing()
    if missing == 0:
        _log("done", message="no missing embeddings", total=total, missing=missing)
        return 0

    _log(
        "start",
        total=total,
        missing=missing,
        batch_size=args.batch_size,
        max_chunks=args.max_chunks,
        timeout_sec=args.timeout_sec,
        max_chars=args.max_chars,
        dry_run=args.dry_run,
        stop_file=args.stop_file,
        model=(model or settings.embed_model),
        ollama_url=(ollama_url or settings.ollama_url),
    )

    started = time.time()
    counters = Counters()
    cursor = max(0, int(args.start_cursor))

    while True:
        if _should_stop(args.stop_file):
            _log("stop_requested", stop_file=args.stop_file)
            break

        if args.max_chunks and counters.processed >= args.max_chunks:
            _log("limit_reached", max_chunks=args.max_chunks, processed=counters.processed)
            break

        batch = _fetch_batch(cursor=cursor, limit=args.batch_size)
        if not batch:
            _log("scan_complete", cursor=cursor)
            break

        if args.max_chunks:
            remain = args.max_chunks - counters.processed
            if remain <= 0:
                _log("limit_reached", max_chunks=args.max_chunks, processed=counters.processed)
                break
            if len(batch) > remain:
                batch = batch[:remain]

        cursor = batch[-1][0]
        counters.batches += 1

        if args.dry_run:
            counters.processed += len(batch)
            _log(
                "dry_run_batch",
                batch_index=counters.batches,
                batch_size=len(batch),
                cursor=cursor,
                processed=counters.processed,
            )
        else:
            ok_count, fail_count = _embed_and_store_rows(
                batch,
                model=model,
                ollama_url=ollama_url,
                timeout=args.timeout_sec,
                ndigits=args.ndigits,
                max_chars=args.max_chars,
                failure_log=failure_log,
            )
            counters.processed += ok_count
            counters.failed += fail_count

        if args.sleep_ms > 0:
            time.sleep(args.sleep_ms / 1000.0)

        if counters.batches % args.report_every == 0:
            _, missing_now = _count_total_and_missing()
            elapsed = max(0.001, time.time() - started)
            throughput = counters.processed / elapsed
            _log(
                "progress",
                batches=counters.batches,
                processed=counters.processed,
                failed=counters.failed,
                missing=missing_now,
                throughput_chunks_per_sec=round(throughput, 3),
                cursor=cursor,
            )

    total_end, missing_end = _count_total_and_missing()
    elapsed = max(0.001, time.time() - started)
    throughput = counters.processed / elapsed
    _log(
        "summary",
        total=total_end,
        missing=missing_end,
        embedded=counters.processed,
        failed=counters.failed,
        batches=counters.batches,
        elapsed_sec=round(elapsed, 3),
        throughput_chunks_per_sec=round(throughput, 3),
        failure_log=str(failure_log),
    )

    if counters.failed > 0:
        _log("warning", message="some chunks failed to embed; inspect failure_log and rerun")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

