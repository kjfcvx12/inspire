"""한국어 위키백과 문서를 .txt로 내려받아 검색 평가용 코퍼스를 만든다(해커톤식 '주제 하나' 시나리오 재현용).
사용: python scripts/fetch_wiki_corpus.py data/hackathon_food 김치 비빔밥 불고기 ...   (제목 생략 시 한식 기본 10개)
위키백과 본문은 CC BY-SA 라이선스다. 저장소에는 커밋하지 않고(data/hackathon_* 는 gitignore)
필요할 때 이 스크립트로 받는다."""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT = ["김치", "비빔밥", "불고기", "떡볶이", "삼계탕", "냉면", "된장", "김밥", "잡채", "갈비탕"]
API = "https://ko.wikipedia.org/w/api.php"


def fetch(title: str) -> str:
    q = urllib.parse.urlencode({"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
                                "titles": title, "format": "json"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": "interview-kit-retrieval-eval/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    page = next(iter(data["query"]["pages"].values()))
    return page.get("extract", "")


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/hackathon_food")
    titles = sys.argv[2:] or DEFAULT
    out.mkdir(parents=True, exist_ok=True)
    for t in titles:
        text = fetch(t)
        if len(text) < 200:
            print(f"건너뜀: {t} (본문 {len(text)}자)")
            continue
        (out / f"{t}.txt").write_text(f"# {t}\n\n{text}\n", encoding="utf-8")
        print(f"{t}: {len(text):,}자")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
