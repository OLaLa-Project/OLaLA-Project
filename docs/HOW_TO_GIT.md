# 팀원용 Git A to Z (main/sub/feature)

이 문서는 **Git 초보자 기준**으로 작성했습니다. 그대로 따라 하면 됩니다.

## 0) 기본 규칙 (가장 중요)
- `main` = 최종 데모용 (절대 직접 작업하지 않음)
- `sub` = 팀 작업 통합 브랜치 (기본 작업 대상)
- `feature/*` = 개인 작업 브랜치 (권장)
- force push 금지
- rebase 금지 (모르면 하지 말 것)

## 1) 최초 1회 설정
```bash
git clone <레포주소>
cd <레포폴더>
```

## 2) 매일 시작할 때 (최신화)
```bash
git checkout sub
git pull origin sub
```

## 3) 작업 방법 (권장: feature 브랜치)
**이 방법이 제일 안전합니다.**

### 3-1) 내 작업 브랜치 만들기
```bash
git checkout sub
git pull origin sub
git checkout -b feature/<내작업>
```
예시:
- `feature/stage3-collect`
- `feature/frontend-result-card`

### 3-2) 작업 후 커밋
```bash
git add .
git commit -m "feat: 작업 요약"
```

### 3-3) 원격에 푸시
```bash
git push -u origin feature/<내작업>
```

### 3-4) PR 만들기
- GitHub에서 **feature → sub** 방향으로 PR 생성
- 리뷰 1명 이상 받은 뒤 머지

## 4) 가장 단순한 방법 (feature 생략)
정말 어렵다면 아래처럼 **sub만** 써도 됩니다.

```bash
git checkout sub
git pull origin sub
# 작업
 git add .
 git commit -m "feat: 작업 요약"
 git push origin sub
```

## 5) main으로 머지 (리더만)
```bash
git checkout main
git pull origin main
git merge sub
git push origin main
```

## 6) 충돌이 나면?
- **혼자 해결하지 말고 리더에게 바로 공유**
- 강제로 해결하지 말 것

## 7) GitHub Desktop으로 할 경우
1) Branch를 `sub`로 변경
2) “Create Branch”로 `feature/...` 만들기
3) Commit → Push
4) GitHub 웹에서 PR 만들기

## 8) 자주 하는 실수 방지 체크리스트
- 지금 브랜치가 `sub` 또는 `feature/...`인가?
- `main`에 직접 push 하지 않았나?
- 커밋 메시지가 너무 긴가? (한 줄 요약만)
