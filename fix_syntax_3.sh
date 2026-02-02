#!/bin/bash
FILE="backend/app/stages/stage09_judge/node.py"

# Line 741 (12 spaces)
sed -i '741c\            "icon": "❓",' $FILE

# Line 743 (12 spaces)
sed -i '743c\            "badge": "검증 불가",' $FILE
