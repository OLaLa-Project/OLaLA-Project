import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.wiki_usecase import calculate_hybrid_score

def test_scoring():
    print("--- Testing Hybrid Scoring ---")
    
    # Case 1: Strong Vector Match (dist=0.3), No FTS
    # Old logic: 1/(1+0.3) = 0.76 * 0.5 (weight) = 0.38 (Fail)
    # New logic: 1/(1+0.3) = 0.76. Base=0.76. Final=0.76. (Pass > 0.7)
    hit_vec = {"dist": 0.3, "title": "Random", "chunk_idx": 0}
    score_vec = calculate_hybrid_score(hit_vec, keywords=["Target"], fts_rank=0.0)
    print(f"Case 1 (Dist 0.3, No FTS): {score_vec:.4f} (Expected > 0.7)")

    # Case 2: Medium Vector (dist=0.5), Strong FTS
    # Target > 0.7
    # Vector: 1/1.5 = 0.66
    # FTS Rank: 0.5 -> Boost 0.5*2.0 = 1.0 * 0.3(W_FTS) = 0.3
    # Final = 0.66 + 0.3 = 0.96
    hit_fts = {"dist": 0.5, "title": "Random", "chunk_idx": 0}
    score_fts = calculate_hybrid_score(hit_fts, keywords=["Target"], fts_rank=0.5)
    print(f"Case 2 (Dist 0.5, Low FTS): {score_fts:.4f} (Expected > 0.7)")

    # Case 3: Exact Title Match
    hit_title = {"dist": 1.0, "title": "Target Keyword", "chunk_idx": 0}
    # Vector: 0.5
    # Title: 1.0 * 0.2 = 0.2
    # Final = 0.7
    score_title = calculate_hybrid_score(hit_title, keywords=["Target"], fts_rank=0.0)
    print(f"Case 3 (Dist 1.0, Exact Title): {score_title:.4f} (Expected >= 0.7)")

    # Case 4: Weak everything
    hit_weak = {"dist": 1.5, "title": "Nothing", "chunk_idx": 0}
    # Vector: 1/2.5 = 0.4
    # Final = 0.4
    score_weak = calculate_hybrid_score(hit_weak, keywords=["Target"], fts_rank=0.0)
    print(f"Case 4 (Dist 1.5, No FTS): {score_weak:.4f} (Expected < 0.7)")

if __name__ == "__main__":
    test_scoring()
