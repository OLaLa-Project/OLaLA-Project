#!/usr/bin/env python3
"""
데이터베이스 스키마 마이그레이션: embedding 컬럼 차원 변경
768 -> 1024 (nomic-embed-text -> bona/bge-m3-korean)
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


def migrate_embedding_dimension():
    """임베딩 차원을 768에서 1024로 변경"""
    
    logger.info("=" * 60)
    logger.info("임베딩 차원 마이그레이션 시작")
    logger.info("=" * 60)
    
    with engine.connect() as conn:
        # 1. 현재 스키마 확인
        logger.info("현재 스키마 확인 중...")
        result = conn.execute(text("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'wiki_chunks' AND column_name = 'embedding';
        """))
        current_schema = result.fetchone()
        if current_schema:
            logger.info(f"현재 embedding 컬럼: {dict(current_schema._mapping)}")
        
        # 2. 기존 벡터 인덱스 삭제 (존재하는 경우)
        logger.info("기존 벡터 인덱스 삭제 중...")
        try:
            conn.execute(text("DROP INDEX IF EXISTS wiki_chunks_embedding_idx;"))
            conn.execute(text("DROP INDEX IF EXISTS wiki_chunks_embedding_hnsw_idx;"))
            conn.execute(text("DROP INDEX IF EXISTS wiki_chunks_embedding_ivfflat_idx;"))
            conn.commit()
            logger.info("✓ 기존 인덱스 삭제 완료")
        except Exception as e:
            logger.warning(f"인덱스 삭제 중 오류 (인덱스가 없을 수 있음): {e}")
            conn.rollback()
        
        # 3. embedding 컬럼 차원 변경
        logger.info("embedding 컬럼 차원을 768 -> 1024로 변경 중...")
        try:
            conn.execute(text("""
                ALTER TABLE wiki_chunks 
                ALTER COLUMN embedding TYPE vector(1024);
            """))
            conn.commit()
            logger.info("✓ embedding 컬럼을 vector(1024)로 변경 완료")
        except Exception as e:
            logger.error(f"컬럼 변경 중 오류: {e}")
            conn.rollback()
            raise
        
        # 4. 변경 확인
        logger.info("스키마 변경 확인 중...")
        result = conn.execute(text("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'wiki_chunks' AND column_name = 'embedding';
        """))
        new_schema = result.fetchone()
        logger.info(f"변경된 embedding 컬럼: {dict(new_schema._mapping)}")
        
        # 5. 임베딩 통계 확인
        logger.info("임베딩 통계 확인 중...")
        result = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(embedding) as with_embedding,
                COUNT(*) - COUNT(embedding) as without_embedding
            FROM wiki_chunks;
        """))
        stats = result.fetchone()
        stats_dict = dict(stats._mapping)
        logger.info(f"청크 통계: {stats_dict}")
        logger.info(f"  - 전체 청크: {stats_dict['total']:,}")
        logger.info(f"  - 임베딩 있음: {stats_dict['with_embedding']:,}")
        logger.info(f"  - 임베딩 없음: {stats_dict['without_embedding']:,}")
    
    logger.info("=" * 60)
    logger.info("마이그레이션 성공적으로 완료!")
    logger.info("=" * 60)


if __name__ == "__main__":
    migrate_embedding_dimension()
