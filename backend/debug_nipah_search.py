"""
Debug script to test why '니파바이러스' is not appearing in search results.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal
from app.gateway.database.repos.wiki_repo import WikiRepository

def test_nipah_search():
    with SessionLocal() as db:
        repo = WikiRepository(db)
        
        print("=" * 80)
        print("Testing '니파바이러스' Search")
        print("=" * 80)
        
        # Test 1: Title Match (ILIKE)
        print("\n[Test 1] Title Match (ILIKE)")
        results = repo.find_pages_by_title_ilike("니파바이러스", limit=5)
        print(f"Results: {len(results)}")
        for r in results:
            print(f"  - page_id={r[0]}, title='{r[1]}'")
        
        # Test 2: Title Match (Exact)
        print("\n[Test 2] Title Match (Exact)")
        results = repo.find_pages_by_title_ilike("니파바이러스", limit=5)
        print(f"Results: {len(results)}")
        
        # Test 3: FTS Search
        print("\n[Test 3] FTS Search")
        results = repo.find_pages_by_fts("니파바이러스", limit=5)
        print(f"Results: {len(results)}")
        for r in results:
            print(f"  - page_id={r[0]}, title='{r[1]}'")
        
        # Test 4: Keyword Search (Any)
        print("\n[Test 4] Keyword Search (Any)")
        results = repo.find_pages_by_any_keyword(["니파바이러스"], limit=5)
        print(f"Results: {len(results)}")
        for r in results:
            print(f"  - page_id={r[0]}, title='{r[1]}'")
        
        # Test 5: Check if page exists
        print("\n[Test 5] Direct Page Query")
        from sqlalchemy import text
        result = db.execute(text("SELECT page_id, title FROM wiki_pages WHERE page_id = 4096300")).fetchone()
        if result:
            print(f"  ✅ Page exists: page_id={result[0]}, title='{result[1]}'")
        else:
            print(f"  ❌ Page NOT found")
        
        # Test 6: Check chunks
        print("\n[Test 6] Chunk Count")
        result = db.execute(text("SELECT COUNT(*) FROM wiki_chunks WHERE page_id = 4096300")).fetchone()
        print(f"  Chunks: {result[0]}")
        
        # Test 7: Check embeddings
        print("\n[Test 7] Embedding Status")
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embedding
            FROM wiki_chunks 
            WHERE page_id = 4096300
        """)).fetchone()
        print(f"  Total chunks: {result[0]}, With embedding: {result[1]}")

if __name__ == "__main__":
    test_nipah_search()
