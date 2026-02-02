#!/bin/bash
FILE="backend/app/stages/stage09_judge/node.py"

# Line 680 (8 spaces)
sed -i '680c\        "explanation": "자동 분석 시스템을 통해 검증되었습니다." if stance != "UNVERIFIED" else "충분한 근거를 확보하지 못해 확인 불가합니다.",' $FILE

# Line 682 (8 spaces)
sed -i '682c\        "cautions": ["자동 분석 결과이므로 참고용으로만 사용해 주세요."],' $FILE

# Line 683 (8 spaces)
sed -i '683c\        "recommendation": "추가 검증을 위해 공식 출처를 직접 확인해 보시기 바랍니다.",' $FILE

# Line 697 (8 spaces)
sed -i '697c\        "verdict_korean": "확인불가",' $FILE

# Line 700 (8 spaces)
sed -i '700c\        "explanation": f"시스템 오류로 인해 검증을 완료할 수 없습니다. ({error_msg[:50]})",' $FILE

# Line 702 (8 spaces)
sed -i '702c\        "cautions": ["시스템 오류 발생"],' $FILE

# Line 703 (8 spaces)
sed -i '703c\        "recommendation": "잠시 후 다시 시도하거나 직접 출처를 확인해 주세요.",' $FILE

# Line 728 (8 spaces)
sed -i '728c\        "verdict_korean": "확인불가",' $FILE

# Line 739 (12 spaces)
sed -i '739c\            "korean": "확인불가",' $FILE

