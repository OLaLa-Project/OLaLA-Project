# Git 사용법 (초보자용)

이 레포는 **브랜치 2개(main, sub)**만 사용합니다.

## 원칙
- `main`에는 **절대 직접 작업하지 않습니다.**
- 모든 작업은 `sub`에 반영합니다.
- `sub → main` 머지는 리더가 합니다.
- force push 금지

## 1) 처음 받을 때
```bash
git clone <레포주소>
cd <레포폴더>
```

## 2) 항상 sub에서 시작
```bash
git checkout sub
git pull origin sub
```

## 3) 작업 후 커밋
```bash
git add .
git commit -m "feat: 작업 내용 요약"
```

## 4) sub로 푸시
```bash
git push origin sub
```

## 5) (리더만) sub → main 머지
```bash
git checkout main
git pull origin main
git merge sub
git push origin main
```

## 실수 방지 체크리스트
- 지금 내가 `sub`에 있는지 확인했나요? → `git branch`
- `main`에 직접 push 하지 않았나요?
- 커밋 메시지를 간단히 적었나요?

## GitHub Desktop 사용 시
- Branch를 **sub**로 바꾼 뒤 작업하세요.
- Commit → Push 하면 됩니다.
