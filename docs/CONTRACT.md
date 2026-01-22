# FinalResult Contract (MVP)

This contract is the only required API shape for frontend rendering.

Fields (minimum):
- analysis_id
- label (TRUE|FALSE|MIXED|UNVERIFIED|REFUSED)
- confidence (0..1)
- summary
- citations[]
- limitations[]
- recommended_next_steps[]

Frontend should only depend on this contract.
