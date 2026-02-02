#!/bin/bash
FILE="backend/app/stages/stage09_judge/node.py"

# Line 289 (12 spaces) - Use single quotes for inner string
sed -i "289c\            f\"검증 결과: {confidence_percent}% 확률로 {verdict_korean_map.get(verdict_label, '확인불가')}\"," $FILE
