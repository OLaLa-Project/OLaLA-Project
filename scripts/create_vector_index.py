#!/usr/bin/env python3
"""
벡터 인덱스 생성 스크립트

pgvector HNSW 인덱스를 생성하여 검색 성능을 향상시킵니다.
"""
import sys
import os

# Python path 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import text
from app.db.session import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_vector_index():
    """HNSW 벡터 인덱스 생성"""
    
    logger.info("=" * 60)
    logger.info("벡터 인덱스 생성 시작")
    logger.info("=" * 60)
    
    with engine.connect() as conn:
        # 1. 임베딩 통계 확인
        logger.info("임베딩 현황 확인 중...")
        result = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(embedding) as with_embedding,
                COUNT(*) - COUNT(embedding) as without_embedding,
                ROUND(100.0 * COUNT(embedding) / COUNT(*), 2) as percentage
            FROM wiki_chunks;
        """))
        stats = result.fetchone()
        stats_dict = dict(stats._mapping)
        logger.info(f"청크 통계:")
        logger.info(f"  - 전체 청크: {stats_dict['total']:,}")
        logger.info(f"  - 임베딩 있음: {stats_dict['with_embedding']:,} ({stats_dict['percentage']}%)")
        logger.info(f"  - 임베딩 없음: {stats_dict['without_embedding']:,}")
        
        if stats_dict['with_embedding'] == 0:
            logger.warning("임베딩이 하나도 없습니다. 인덱스를 생성하지 않습니다.")
            return
        
        # 2. 기존 인덱스 삭제
        logger.info("\n기존 인덱스 확인 및 삭제 중...")
        try:
            conn.execute(text("DROP INDEX IF EXISTS wiki_chunks_embedding_hnsw_idx;"))
            conn.execute(text("DROP INDEX IF EXISTS wiki_chunks_embedding_ivfflat_idx;"))
            conn.execute(text("DROP INDEX IF EXISTS wiki_chunks_embedding_idx;"))
            conn.commit()
            logger.info("✓ 기존 인덱스 삭제 완료")
        except Exception as e:
            logger.warning(f"인덱스 삭제 중 오류 (인덱스가 없을 수 있음): {e}")
            conn.rollback()
        
        # 3. HNSW 인덱스 생성
        logger.info("\nHNSW 인덱스 생성 중...")
        logger.info("(이 작업은 수 분이 소요될 수 있습니다...)")
        try:
            # HNSW 파라미터:
            # - m: 각 노드의 최대 연결 수 (기본 16, 범위 2-100)
            # - ef_construction: 인덱스 구축 시 탐색 범위 (기본 64, 높을수록 정확하지만 느림)
            #
            # m=16, ef_construction=64는 균형잡힌 설정
            # 더 높은 정확도가 필요하면 m=32, ef_construction=128 사용
            conn.execute(text("""
                CREATE INDEX wiki_chunks_embedding_hnsw_idx 
                ON wiki_chunks 
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """))
            conn.commit()
            logger.info("✓ HNSW 인덱스 생성 완료!")
        except Exception as e:
            logger.error(f"HNSW 인덱스 생성 중 오류: {e}")
            conn.rollback()
            
            # IVFFlat 인덱스 대안 시도
            logger.info("\nIVFFlat 인덱스를 대안으로 시도 중...")
            try:
                # IVFFlat은 HNSW보다 빠르지만 정확도가 약간 낮음
                # lists는 클러스터 수 (일반적으로 rows / 1000)
                conn.execute(text("""
                    CREATE INDEX wiki_chunks_embedding_ivfflat_idx 
                    ON wiki_chunks 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 1000);
                """))
                conn.commit()
                logger.info("✓ IVFFlat 인덱스 생성 완료!")
            except Exception as e2:
                logger.error(f"IVFFlat 인덱스 생성도 실패: {e2}")
                conn.rollback()
                raise
        
        # 4. 인덱스 확인
        logger.info("\n생성된 인덱스 확인 중...")
        result = conn.execute(text("""
            SELECT 
                indexname, 
                indexdef
            FROM pg_indexes
            WHERE tablename = 'wiki_chunks' 
              AND indexname LIKE '%embedding%';
        """))
        indexes = result.fetchall()
        logger.info(f"총 {len(indexes)}개의 임베딩 인덱스 발견:")
        for idx in indexes:
            logger.info(f"  - {idx[0]}")
    
    logger.info("\n" + "=" * 60)
    logger.info("벡터 인덱스 생성 완료!")
    logger.info("=" * 60)


if __name__ == "__main__":
    create_vector_index()
