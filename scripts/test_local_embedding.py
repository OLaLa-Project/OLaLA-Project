
import sys
import os

# Add project root to path
sys.path.append("/home/edu09/workspace/slm2")

from backend.app.gateway.embedding.client import embed_texts, _get_local_model
import torch
import numpy as np

# Force model for test
os.environ["EMBED_MODEL"] = "dragonkue/multilingual-e5-small-ko-v2"

def main():
    print("Testing local embedding fallback...")
    
    # Check GPU
    try:
        if torch.cuda.is_available():
            print(f"CUDA Available: {torch.cuda.get_device_name(0)}")
        else:
            print("CUDA NOT Available (Running on CPU)")
    except Exception as e:
        print(f"Error checking CUDA: {e}")

    test_text = "테스트 문장입니다."
    print(f"Input text: {test_text}")
    
    # Generate embedding
    try:
        embeddings = embed_texts([test_text], model="dragonkue/multilingual-e5-small-ko-v2")
        print(f"Generated embedding shape: {len(embeddings)}x{len(embeddings[0])}")
        
        # Verify model loaded on correct device
        local_model = _get_local_model("dragonkue/multilingual-e5-small-ko-v2")
        print(f"Model device: {local_model.device}")
        
        print("Success! Local embedding generation works.")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
