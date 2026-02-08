# Stage 9 - llm judge

Owner: TODO

Input:
- claim_text
- support_pack
- skeptic_pack
- evidence_index
- language

Output:
- final_verdict
- user_result
- risk_flags
- judge_retrieval

Notes:
- Stage6/7 결과를 직접 비교해 TRUE/FALSE 판결만 수행.
- 별도 retrieval 근거를 함께 사용.
