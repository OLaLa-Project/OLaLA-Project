#!/bin/bash
FILE="backend/app/stages/stage09_judge/node.py"

# Line 285
sed -i '285s/parsed.get.*/parsed.get("verdict_korean", verdict_korean_map.get(verdict_label, "확인불가")),/' $FILE

# Line 289
sed -i '289s/parsed.get.*/parsed.get("headline", f"검증 결과: {confidence_percent}% 확률로 {verdict_korean_map.get(verdict_label, "확인불가")}"),/' $FILE

# Line 490
sed -i '490s/judge_result.get.*/judge_result.get("verdict_korean", "확인불가"),/' $FILE

# Line 532
sed -i '532s/judge_result.get.*/judge_result.get("verdict_korean", "확인불가"),/' $FILE

# Line 653
sed -i '653s/verdict_korean_map.get.*/verdict_korean_map.get(stance, "확인불가")/' $FILE

# Line 679
sed -i '679s/headline.*/"headline": f"검증 결과: {confidence_percent}% 확률로 {verdict_korean}" if stance != "UNVERIFIED" else "현재 확인 불가",/' $FILE

# Line 680
sed -i '680s/explanation.*/"explanation": "자동 분석 시스템을 통해 검증되었습니다." if stance != "UNVERIFIED" else "충분한 근거를 확보하지 못해 확인 불가합니다.",/' $FILE

# Line 682
sed -i '682s/cautions.*/"cautions": ["자동 분석 결과이므로 참고용으로만 사용해 주세요."],/' $FILE

# Line 683
sed -i '683s/recommendation.*/"recommendation": "추가 검증을 위해 공식 출처를 직접 확인해 보시기 바랍니다.",/' $FILE

# Line 697
sed -i '697s/verdict_korean.*/"verdict_korean": "확인불가",/' $FILE

# Line 699
sed -i '699s/headline.*/"headline": "현재 확인 불가",/' $FILE

# Line 700
sed -i '700s/explanation.*/"explanation": f"시스템 오류로 인해 검증을 완료할 수 없습니다. ({error_msg[:50]})",/' $FILE

# Line 702
sed -i '702s/cautions.*/"cautions": ["시스템 오류 발생"],/' $FILE

# Line 703
sed -i '703s/recommendation.*/"recommendation": "잠시 후 다시 시도하거나 직접 출처를 확인해 주세요.",/' $FILE

# Line 728
sed -i '728s/verdict_korean.*/"verdict_korean": "확인불가",/' $FILE

# Line 739
sed -i '739s/korean.*/"korean": "확인불가",/' $FILE

