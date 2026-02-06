import logging
import asyncio
import numpy as np
from typing import List, Optional
import trafilatura
from app.gateway.embedding.client import embed_texts

logger = logging.getLogger(__name__)

# Constants
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
MAX_CONTENT_FETCH_TIMEOUT = 5.0  # seconds per URL
SNIPPET_LENGTH_LIMIT = 500

class WebRAGService:
    @staticmethod
    async def fetch_url_content(url: str) -> Optional[str]:
        """Fetch and extract main text from URL."""
        if not url:
            return None
            
        try:
            # Run blocking trafilatura.fetch_url in thread
            downloaded = await asyncio.to_thread(
                trafilatura.fetch_url, 
                url
            )
            
            if not downloaded:
                logger.warning(f"Failed to download/empty: {url}")
                return None
                
            # Extract text
            text = await asyncio.to_thread(
                trafilatura.extract,
                downloaded,
                include_comments=False,
                include_tables=False,
                no_fallback=False
            )
            
            if not text:
                logger.warning(f"Failed to extract text: {url}")
                return None
                
            return text.strip()
            
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    @staticmethod
    def chunk_text(text: str) -> List[str]:
        """Split text into overlapping chunks."""
        if not text:
            return []
            
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + CHUNK_SIZE
            chunk = text[start:end]
            
            # If chunk is too short compared to overlap (tail end), just take it if meaningful
            if len(chunk) < 50: 
                pass # merge with previous? for now just append if not empty
            
            if chunk.strip():
                chunks.append(chunk)
            
            start += (CHUNK_SIZE - CHUNK_OVERLAP)
            
        return chunks

    @staticmethod
    def find_best_snippet(query: str, content: str) -> Optional[str]:
        """
        RAG: Chunk content -> Embed -> Cosine Similarity -> Top 1 Chunk
        """
        chunks = WebRAGService.chunk_text(content)
        if not chunks:
            return None
            
        if len(chunks) == 1:
            return chunks[0][:SNIPPET_LENGTH_LIMIT]

        try:
            # 1. Embed Query
            # embed_texts returns List[List[float]]
            q_vecs = embed_texts([query])
            if not q_vecs:
                return chunks[0][:SNIPPET_LENGTH_LIMIT]
            q_vec = np.array(q_vecs[0])

            # 2. Embed Chunks (Batch)
            # Limit number of chunks to avoid OOM or timeout (e.g. max 20 chunks = ~10k chars)
            MAX_CHUNKS = 20
            process_chunks = chunks[:MAX_CHUNKS]
            
            c_vecs_list = embed_texts(process_chunks)
            if not c_vecs_list:
                return chunks[0][:SNIPPET_LENGTH_LIMIT]
                
            c_vecs = np.array(c_vecs_list)

            # 3. Cosine Similarity
            # (A . B) / (|A| * |B|)
            norm_q = np.linalg.norm(q_vec)
            norm_c = np.linalg.norm(c_vecs, axis=1)
            
            # Avoid divide by zero
            if norm_q == 0:
                return chunks[0][:SNIPPET_LENGTH_LIMIT]
            
            # Similarity scores
            sims = np.dot(c_vecs, q_vec) / (norm_c * norm_q + 1e-10)
            
            # 4. Argmax
            best_idx = int(np.argmax(sims))
            best_chunk = process_chunks[best_idx]
            
            # Truncate to limit
            return best_chunk[:SNIPPET_LENGTH_LIMIT]

        except Exception as e:
            logger.error(f"RAG Error: {e}")
            # Fallback to first chunk
            return chunks[0][:SNIPPET_LENGTH_LIMIT]

    @staticmethod
    async def enrich_citation(citation: dict, query: str) -> dict:
        """
        Fetch content and update snippet using RAG.
        Returns the modified citation (in-place update).
        """
        url = citation.get("url")
        if not url:
            return citation

        logger.info(f"RAG Fetching: {url}")
        try:
            # Timeout for the whole fetch operation
            content = await asyncio.wait_for(
                WebRAGService.fetch_url_content(url), 
                timeout=MAX_CONTENT_FETCH_TIMEOUT
            )
            
            if content:
                # Find best snippet
                # Note: find_best_snippet calls embed_texts which is sync (urllib), 
                # so we should wrap it in to_thread to avoid blocking event loop
                best_snippet = await asyncio.to_thread(
                    WebRAGService.find_best_snippet, 
                    query, 
                    content
                )
                
                if best_snippet:
                    citation["snippet"] = best_snippet
                    # citation["content"] = best_snippet # User requested to KEEP original content (summary)
                    logger.info(f"RAG Success: {url} -> {len(best_snippet)} chars")
                else:
                    logger.warning(f"RAG Snippet not found: {url}")
            else:
                logger.warning(f"RAG Empty content: {url}")

        except asyncio.TimeoutError:
            logger.warning(f"RAG Timeout: {url}")
        except Exception as e:
            logger.error(f"RAG Failed: {url} - {e}")
            
        return citation

