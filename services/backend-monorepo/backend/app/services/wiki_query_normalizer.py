import re

_PARTICLE_RE = re.compile(
    r"(은|는|이|가|을|를|의|에|에서|으로|로|과|와|도|만|부터|까지|랑|이나|나|께|에게|한테|조차|마저|밖에)$"
)

_ENDING_RE = re.compile(
    r"(인가요|인가|나요|니|냐|지|죠|야|요|까|습니다|습니까|입니까|했어|했니|했냐|됐어|되었어|되었니|되었냐)$"
)

_STOPWORDS = {
    "현재",
    "지금",
    "요즘",
    "오늘",
    "이번",
    "최근",
    "그냥",
    "무엇",
    "뭐",
    "어떻게",
    "왜",
    "언제",
    "누구",
    "어느",
    "어떤",
}

_PUNCT_RE = re.compile(r"[^\wㄱ-ㆎ가-힣]+")


def _strip_suffix(token: str) -> str:
    t = token
    for _ in range(2):
        t2 = _ENDING_RE.sub("", t)
        t2 = _PARTICLE_RE.sub("", t2)
        if t2 == t:
            break
        t = t2
    return t


def normalize_question_to_query(text: str) -> str:
    if not text:
        return ""

    raw = text.strip()
    cleaned = _PUNCT_RE.sub(" ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        return ""

    tokens = []
    for tok in cleaned.split(" "):
        base = _strip_suffix(tok.strip())
        if not base:
            continue
        if base in _STOPWORDS:
            continue
        if len(base) == 1 and not base.isdigit():
            continue
        tokens.append(base)

    return " ".join(tokens) if tokens else cleaned
