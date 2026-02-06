# Team Roles (Stage-based)

Team A (Evidence Pipeline)
- Stages 1-5: normalize, querygen, collect, score, topk
- Work here: backend/app/stages/stage01_normalize ~ stage05_topk

Team B (Verification)
- Stages 6-7: supportive verify, skeptical verify
- Stage 8: aggregate
- Work here: backend/app/stages/stage06_verify_support ~ stage07_verify_skeptic, stage08_aggregate

Common/Platform
- Stages 9-10: llm judge, policy guard
- Shared schemas, graph orchestration, eval/observability
- Work here: backend/app/stages/stage09_judge, stage10_policy, backend/app/graph/, shared/

Canonical stage path: `backend/app/stages/`
