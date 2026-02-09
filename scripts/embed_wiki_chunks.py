#!/usr/bin/env python3
"""
위키 청크 임베딩 생성 스크립트

약 100만 개의 청크에 대해 bona/bge-m3-korean 모델로 임베딩을 생성합니다.
배치 처리 및 중단/재개를지원합니다.
"""
import sys
import os
import time
import argparse
from typing import List, Tuple

# Python path 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import text
from app.db.session import SessionLocal
from app.orchestrator.embedding.client import embed_texts, vec_to_pgvector_literal
from app.core.settings import settings
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_chunks_without_embedding(db, limit: int = 1000) -> List[Tuple[int, str]]:
    """임베딩이 없는 청크를 가져옴"""
    sql = text("""
        SELECT chunk_id, content
        FROM wiki_chunks
        WHERE embedding IS NULL
        ORDER BY chunk_id
        LIMIT :limit
    """)
    result = db.execute(sql, {"limit": limit})
    return [(int(row[0]), str(row[1])) for row in result.fetchall()]


def update_embeddings(db, chunk_embeddings: dict[int, str]) -> int:
    """청크 임베딩 업데이트"""
    if not chunk_embeddings:
        return 0
    
    sql = text("""
        UPDATE wiki_chunks
        SET embedding = (:vec)::vector
        WHERE chunk_id = :chunk_id
    """)
    
    updated = 0
    for chunk_id, vec_literal in chunk_embeddings.items():
        db.execute(sql, {"chunk_id": chunk_id, "vec": vec_literal})
        updated += 1
    
    db.commit()
    return updated


def embed_wiki_chunks(
    batch_size: int = 100,
    limit: int = None,
    max_batches: int = None,
    verbose: bool = True
):
    """
    위키 청크 임베딩 생성
    
    Args:
        batch_size: 한 번에 처리할 청크 수
        limit: 가져올 최대 청크 수 (각 배치마다)
        max_batches: 최대 배치 수 (테스트용)
        verbose: 상세 로그 출력
    """
    logger.info("=" * 70)
    logger.info("위키 청크 임베딩 생성 시작")
    logger.info(f"모델: {settings.embed_model}")
    logger.info(f"차원: {settings.embed_dim}")
    logger.info(f"배치 크기: {batch_size}")
    logger.info(f"Ollama URL: {settings.ollama_url}")
    logger.info("=" * 70)
    
    db = SessionLocal()
    total_processed = 0
    batch_count = 0
    start_time = time.time()
    
    try:
        while True:
            # 최대 배치 수 제한 확인
            if max_batches and batch_count >= max_batches:
                logger.info(f"최대 배치 수({max_batches}) 도달. 종료합니다.")
                break
            
            # 임베딩이 없는 청크 가져오기
            fetch_limit = limit or batch_size * 10
            chunks = get_chunks_without_embedding(db, limit=fetch_limit)
            
            if not chunks:
                logger.info("✓ 모든 청크에 임베딩이 생성되었습니다!")
                break
            
            logger.info(f"\n배치 #{batch_count + 1}: {len(chunks):,}개 청크 발견")
            
            # 배치 단위로 처리
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                chunk_ids = [cid for cid, _ in batch]
                contents = [content for _, content in batch]
                
                try:
                    # 임베딩 생성
                    batch_start = time.time()
                    embeddings = embed_texts(
                        contents,
                        model=settings.embed_model,
                        timeout=120
                    )
                    batch_elapsed = time.time() - batch_start
                    
                    # pgvector 형식으로 변환
                    chunk_embeddings = {
                        chunk_id: vec_to_pgvector_literal(emb, ndigits=settings.embed_ndigits)
                        for chunk_id, emb in zip(chunk_ids, embeddings)
                    }
                    
                    # DB 업데이트
                    updated = update_embeddings(db, chunk_embeddings)
                    total_processed += updated
                    
                    if verbose:
                        avg_time = batch_elapsed / len(batch)
                        logger.info(
                            f"  ✓ {updated:3}개 업데이트 완료 "
                            f"(배치: {batch_elapsed:5.2f}s, "
                            f"평균: {avg_time:.3f}s/chunk)"
                        )
                    
                except Exception as e:
                    logger.error(f"배치 처리 중 오류: {e}", exc_info=True)
                    logger.warning("다음 배치로 계속 진행합니다...")
                    continue
            
            batch_count += 1
            
            # 진행 상황 요약
            elapsed = time.time() - start_time
            rate = total_processed / elapsed if elapsed > 0 else 0
            remaining = 1002975 - total_processed  # 대략적인 전체 청크 수
            eta = remaining / rate if rate > 0 else 0
            
            logger.info(
                f"\n[진행 상황] "
                f"총 {total_processed:,}개 처리 완료 | "
                f"경과: {elapsed/60:.1f}분 | "
                f"속도: {rate:.1f} chunks/s | "
                f"예상 남은 시간: {eta/60:.1f}분"
            )
            
            # 잠시 대기 (Ollama 부하 분산)
            if len(chunks) >= fetch_limit:
                time.sleep(0.5)
    
    finally:
        db.close()
    
    total_elapsed = time.time() - start_time
    logger.info("\n" + "=" * 70)
    logger.info(f"임베딩 생성 완료!")
    logger.info(f"총 처리: {total_processed:,}개 청크")
    logger.info(f"총 소요 시간: {total_elapsed/60:.1f}분 ({total_elapsed/3600:.2f}시간)")
    if total_processed > 0:
        logger.info(f"평균 처리 속도: {total_processed/total_elapsed:.2f} chunks/s")
    logger.info("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="위키 청크 임베딩 생성")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="배치 크기 (기본값: 100)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="한 번에 가져올 최대 청크 수 (기본값: batch_size * 10)"
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="최대 배치 수 (테스트용, 기본값: 무제한)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="테스트 모드 (100개만 처리)"
    )
    
    args = parser.parse_args()
    
    if args.test:
        logger.info("테스트 모드: 100개 청크만 처리합니다.")
        embed_wiki_chunks(
            batch_size=10,
            limit=100,
            max_batches=1,
            verbose=True
        )
    else:
        embed_wiki_chunks(
            batch_size=args.batch_size,
            limit=args.limit,
            max_batches=args.max_batches,
            verbose=True
        )
