"""
Phase 1 Step 1 — RSS 화이트리스트 50개 빌드 및 검증.

후보 RSS 50개 + 예비를 feedparser로 검증.
통과한 것만 data/rss_whitelist.json에 저장.

실행:
    cd /Users/jtmini/claude_github/pigeonbrief
    python scripts/build_rss_whitelist.py
"""
import json
import socket
import sys
import time
from pathlib import Path

import feedparser

socket.setdefaulttimeout(20)
RETRY_COUNT = 3

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "rss_whitelist.json"

# 카테고리별 후보 (target 50개, 실패 대비 여유 추가)
# (name, url, language, country, categories)
CANDIDATES = [
    # ===== Tech / AI (target 10) =====
    ("TechCrunch", "https://techcrunch.com/feed/", "en", "US", ["tech", "ai", "startup"]),
    ("The Verge", "https://www.theverge.com/rss/index.xml", "en", "US", ["tech", "ai"]),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "en", "US", ["tech", "science"]),
    ("Wired", "https://www.wired.com/feed/rss", "en", "US", ["tech", "ai", "science"]),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/", "en", "US", ["tech", "ai", "science"]),
    ("VentureBeat", "https://venturebeat.com/feed/", "en", "US", ["tech", "ai", "business"]),
    ("Engadget", "https://www.engadget.com/rss.xml", "en", "US", ["tech"]),
    ("IEEE Spectrum", "https://spectrum.ieee.org/feeds/feed.rss", "en", "US", ["tech", "science"]),
    ("AI News", "https://www.artificialintelligence-news.com/feed/", "en", "UK", ["ai", "tech"]),
    ("The Information", "https://www.theinformation.com/feed", "en", "US", ["tech", "business"]),
    ("Hacker News Frontpage", "https://hnrss.org/frontpage", "en", "US", ["tech", "startup"]),
    ("ZDNet", "https://www.zdnet.com/news/rss.xml", "en", "US", ["tech", "business"]),

    # ===== Business / Finance (target 10) =====
    ("Reuters Business", "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best", "en", "US", ["business", "finance"]),
    ("CNBC Top News", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "en", "US", ["business", "finance"]),
    ("CNBC Markets", "https://www.cnbc.com/id/15839069/device/rss/rss.html", "en", "US", ["finance"]),
    ("Financial Times", "https://www.ft.com/?format=rss", "en", "UK", ["business", "finance"]),
    ("Forbes Business", "https://www.forbes.com/business/feed/", "en", "US", ["business", "finance"]),
    ("Fortune", "https://fortune.com/feed/fortune-feeds/", "en", "US", ["business"]),
    ("Business Insider", "https://www.businessinsider.com/rss", "en", "US", ["business", "finance"]),
    ("Axios Business", "https://api.axios.com/feed/business", "en", "US", ["business"]),
    ("Quartz", "https://qz.com/rss", "en", "US", ["business", "tech"]),
    ("MarketWatch Top Stories", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "en", "US", ["finance"]),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex", "en", "US", ["finance"]),
    ("Seeking Alpha Market News", "https://seekingalpha.com/market_currents.xml", "en", "US", ["finance"]),
    ("Investing.com News", "https://www.investing.com/rss/news.rss", "en", "GLOBAL", ["finance"]),

    # ===== Healthcare / Bio (target 6) =====
    ("STAT News", "https://www.statnews.com/feed/", "en", "US", ["healthcare", "bio"]),
    ("Healthcare IT News", "https://www.healthcareitnews.com/rss.xml", "en", "US", ["healthcare", "tech"]),
    ("Fierce Healthcare", "https://www.fiercehealthcare.com/rss/xml", "en", "US", ["healthcare"]),
    ("Endpoints News", "https://endpts.com/feed/", "en", "US", ["bio", "pharma"]),
    ("MedCity News", "https://medcitynews.com/feed/", "en", "US", ["healthcare", "bio"]),
    ("BioPharma Dive", "https://www.biopharmadive.com/feeds/news/", "en", "US", ["bio", "pharma"]),
    ("FierceBiotech", "https://www.fiercebiotech.com/rss/xml", "en", "US", ["bio"]),
    ("Modern Healthcare", "https://www.modernhealthcare.com/rss.xml", "en", "US", ["healthcare"]),

    # ===== Science (target 5) =====
    ("Nature News", "https://www.nature.com/nature.rss", "en", "GLOBAL", ["science"]),
    ("Science Daily Top", "https://www.sciencedaily.com/rss/top.xml", "en", "US", ["science"]),
    ("Phys.org", "https://phys.org/rss-feed/", "en", "GLOBAL", ["science"]),
    ("New Scientist", "https://www.newscientist.com/feed/home/", "en", "UK", ["science"]),
    ("Quanta Magazine", "https://www.quantamagazine.org/feed/", "en", "US", ["science"]),
    ("Scientific American", "https://rss.sciam.com/ScientificAmerican-Global", "en", "US", ["science"]),

    # ===== Startup / VC (target 4) =====
    ("TechCrunch Startups", "https://techcrunch.com/category/startups/feed/", "en", "US", ["startup", "vc"]),
    ("Crunchbase News", "https://news.crunchbase.com/feed/", "en", "US", ["startup", "vc"]),
    ("Sifted", "https://sifted.eu/feed", "en", "EU", ["startup", "vc"]),
    ("StrictlyVC", "https://www.strictlyvc.com/feed/", "en", "US", ["vc"]),

    # ===== Geopolitics / Policy (target 4) =====
    ("Foreign Policy", "https://foreignpolicy.com/feed/", "en", "US", ["geopolitics", "policy"]),
    ("The Diplomat", "https://thediplomat.com/feed/", "en", "ASIA", ["geopolitics"]),
    ("Politico", "https://www.politico.com/rss/politicopicks.xml", "en", "US", ["politics", "policy"]),
    ("Council on Foreign Relations", "https://www.cfr.org/rss.xml", "en", "US", ["geopolitics"]),
    ("War on the Rocks", "https://warontherocks.com/feed/", "en", "US", ["geopolitics", "defense"]),

    # ===== Korean (target 8) =====
    ("연합뉴스 경제", "https://www.yna.co.kr/rss/economy.xml", "ko", "KR", ["business", "finance"]),
    ("연합뉴스 IT/과학", "https://www.yna.co.kr/rss/it.xml", "ko", "KR", ["tech"]),
    ("한겨레 경제", "https://www.hani.co.kr/rss/economy/", "ko", "KR", ["business"]),
    ("매일경제 헤드라인", "https://www.mk.co.kr/rss/30000001/", "ko", "KR", ["business", "finance"]),
    ("매일경제 IT/과학", "https://www.mk.co.kr/rss/50400012/", "ko", "KR", ["tech"]),
    ("한국경제 헤드라인", "https://www.hankyung.com/feed/all-news", "ko", "KR", ["business"]),
    ("조선일보 경제", "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml", "ko", "KR", ["business"]),
    ("전자신문", "https://rss.etnews.com/Section901.xml", "ko", "KR", ["tech"]),
    ("머니투데이 헤드라인", "https://rss.mt.co.kr/mt_news.xml", "ko", "KR", ["business", "finance"]),
    ("IT조선", "https://it.chosun.com/rss/all.xml", "ko", "KR", ["tech"]),
    ("ZDNet Korea", "https://feeds.feedburner.com/zdkorea", "ko", "KR", ["tech"]),
    ("디지털타임스", "https://www.dt.co.kr/rss/economy.xml", "ko", "KR", ["business", "tech"]),

    # ===== General (target 3) =====
    ("BBC News World", "https://feeds.bbci.co.uk/news/world/rss.xml", "en", "UK", ["general"]),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml", "en", "US", ["general"]),
    ("AP Top News", "https://feeds.apnews.com/rss/apf-topnews", "en", "US", ["general"]),
    ("Reuters World", "https://feeds.reuters.com/reuters/worldNews", "en", "GLOBAL", ["general"]),
    ("Al Jazeera English", "https://www.aljazeera.com/xml/rss/all.xml", "en", "GLOBAL", ["general"]),

    # ===== 보충 (A안: healthcare/geopolitics 강화) =====
    ("KFF Health News", "https://kffhealthnews.org/feed/", "en", "US", ["healthcare", "policy"]),
    ("Just Security", "https://www.justsecurity.org/feed/", "en", "US", ["geopolitics", "security", "policy"]),
    ("The Guardian World", "https://www.theguardian.com/world/rss", "en", "UK", ["geopolitics", "general"]),
    ("Atlantic Council", "https://www.atlanticcouncil.org/feed/", "en", "US", ["geopolitics", "policy"]),
]


def validate(url: str) -> tuple[bool, str, int]:
    last_reason = ""
    for attempt in range(RETRY_COUNT):
        try:
            f = feedparser.parse(url)
            n = len(f.entries)
            status = getattr(f, "status", None)
            if n > 0 and (status is None or status < 400):
                return True, f"status={status}, entries={n} (attempt {attempt+1})", n
            last_reason = f"status={status}, entries={n}"
        except Exception as e:
            last_reason = f"{type(e).__name__}: {e}"
        time.sleep(1)
    return False, f"{last_reason} (after {RETRY_COUNT} attempts)", 0


def main() -> int:
    print(f"검증할 후보: {len(CANDIDATES)}개\n")
    passed = []
    failed = []
    for name, url, lang, country, cats in CANDIDATES:
        ok, reason, n = validate(url)
        if ok:
            print(f"  ✅ {name} ({n} entries)")
            passed.append({
                "name": name,
                "url": url,
                "language": lang,
                "country": country,
                "categories": cats,
            })
        else:
            print(f"  ❌ {name}: {reason}")
            failed.append({"name": name, "url": url, "reason": reason})

    print(f"\n통과: {len(passed)}/{len(CANDIDATES)}")
    print(f"실패: {len(failed)}")

    # 카테고리별 분포
    from collections import Counter
    cat_counter = Counter()
    for p in passed:
        for c in p["categories"]:
            cat_counter[c] += 1
    print("\n통과 항목의 카테고리 분포:")
    for c, n in sorted(cat_counter.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "version": 1,
        "feeds": passed,
        "failed_candidates": failed,
    }, ensure_ascii=False, indent=2))
    print(f"\n저장: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
