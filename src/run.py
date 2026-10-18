"""完全免费版（不使用任何AI）：抓取 -> 按标题相似度归类 -> 程序统计“至少N家独立来源” -> 页面 + 通知。
用法：python src/run.py noon|evening|parliament|check"""
import datetime as dt, json, os, re, sys, urllib.parse
from zoneinfo import ZoneInfo
import feedparser, yaml
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from render import render

MYT = ZoneInfo("Asia/Kuala_Lumpur")
MIN_OWNERS = {"daily": 3, "parliament": 2}   # 日常 ≥3 家；国会周报 ≥2 家（可自行改）
LIMITS = {"my": 15, "world": 10}             # 上限；达标的不够就宁缺毋滥
THRESHOLD = 0.8                              # 标题相似度门槛：调小=更严格，调大=更宽松
INTL = {"bbc", "reuters", "ap", "aljazeera", "cna", "guardian", "dw"}   # 国际媒体
KW = re.compile(r"国会|下议院|上议院|议员|Dewan Rakyat|Dewan Negara|Parlimen|Parliament|Hansard", re.I)
WORK = re.compile(r"Bursa|Securities Commission|Bank Negara|\bBNM\b|\bOPR\b|ringgit|\bIPO\b|\bGDP\b|inflation|tariff|"
                  r"property|hartanah|construction|pembinaan|Petronas|oil and gas|minyak|budget|belanjawan|policy|polisi|"
                  r"令吉|证券委员会|国家银行|交易所|上市|房地产|建筑|工程|国油|石油|统计局|通胀|关税|财政预算|预算案|政策", re.I)
CATS = [("经济", r"ringgit|economy|ekonomi|GDP|inflation|OPR|Bursa|budget|belanjawan|令吉|经济|通胀|股|预算|利率|油价"),
        ("司法", r"court|mahkamah|MACC|SPRM|charge|didakwa|法庭|反贪|控状|判"),
        ("政治", r"Anwar|Parliament|minister|menteri|election|PRN|PRU|首相|部长|国会|选举|政党|安华"),
        ("社会", r"police|polis|flood|banjir|accident|kemalangan|school|sekolah|警方|水灾|意外|学校|命案")]
CJK = re.compile(r"[\u4e00-\u9fff]")


def feed_url(s, days):
    if s.get("url"):
        return s["url"]
    hl, ceid = {"zh": ("zh-MY", "MY:zh-Hans"), "ms": ("ms", "MY:ms"), "en": ("en-MY", "MY:en")}[s["lang"]]
    q = urllib.parse.quote(f"site:{s['site']} when:{days}d")
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl=MY&ceid={ceid}"


def fetch(days):
    cfg = yaml.safe_load(open("config/sources.yml", encoding="utf-8"))
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    arts = []
    for s in cfg["sources"]:
        urls = [feed_url(s, days)]
        if s.get("site") and not s.get("official"):   # 备用：媒体网站自己的 RSS（Google 抓得少时补充）
            urls.append(f"https://www.{s['site']}/feed/")
        n, seen = 0, set()
        for u in urls:
            if n >= 10:
                break
            try:
                feed = feedparser.parse(u)
            except Exception as e:
                print("FAIL", s["name"], e); continue
            google = "news.google.com" in u
            for e in feed.entries[:30]:
                t = e.get("published_parsed")
                if t and dt.datetime(*t[:6], tzinfo=dt.timezone.utc) < cutoff:
                    continue
                title = re.sub(r"\s+[-–|]\s+[^-–|]+$", "", e.title) if google else e.title
                if title in seen:
                    continue
                seen.add(title)
                arts.append(dict(id=len(arts), source=s["name"], owner=s["owner"], title=title.strip(), link=e.link))
                n += 1
        print(f"{s['name']}: {n} 条")
    return arts


def cluster(arts):
    """按标题字符相似度归类（中、英、马来文均可，但不同语言之间不会合并）。"""
    if len(arts) < 2:
        return []
    X = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True).fit_transform([a["title"] for a in arts]).toarray()
    labels = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average",
                                     distance_threshold=THRESHOLD).fit_predict(X)
    groups = {}
    for i, l in enumerate(labels):
        groups.setdefault(l, []).append(arts[i])
    return [g for g in groups.values() if len(g) >= 2]


def make_item(group, need):
    owners = {a["owner"] for a in group}
    if len(owners) < need:   # 由程序统计独立来源数
        return None
    seen, links = set(), []
    for a in group:          # 每家媒体只列一条，链接都来自抓取到的真实文章
        if a["source"] not in seen:
            seen.add(a["source"]); links.append({"source": a["source"], "url": a["link"], "title": a["title"]})
    head = next((a for a in group if CJK.search(a["title"])), group[0])["title"]   # 优先显示中文标题
    text = " ".join(a["title"] for a in group)
    intl = len(owners & INTL)
    return {"title": head, "summary": "", "scope": "world" if intl >= len(owners) - intl else "my",
            "category": next((c for c, p in CATS if re.search(p, text, re.I)), "要闻"),
            "importance": len(owners), "owners": len(owners), "work": bool(WORK.search(text)), "links": links}


def build(arts, need):
    items = [x for x in (make_item(g, need) for g in cluster(arts)) if x]
    return sorted(items, key=lambda x: (-x["owners"], -len(x["links"])))


def save(b):
    os.makedirs("data", exist_ok=True)
    json.dump(b, open(f"data/{b['name']}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def write_notify(title, lines, extra=False):
    f = "data/notify.json"
    if extra and os.path.exists(f):
        n = json.load(open(f, encoding="utf-8")); n["lines"] += lines
    else:
        n = {"title": title, "lines": lines}
    json.dump(n, open(f, "w", encoding="utf-8"), ensure_ascii=False)


def daily(slot):
    now = dt.datetime.now(MYT)
    items = build(fetch(1), MIN_OWNERS["daily"])
    prev = set()
    f = f"data/{now:%Y-%m-%d}-noon.json"
    if slot == "evening" and os.path.exists(f):
        prev = {l["url"] for x in json.load(open(f, encoding="utf-8"))["items"] for l in x["links"]}
    for x in items:
        x["new"] = not any(l["url"] in prev for l in x["links"])
    chosen = [x for scope, hi in LIMITS.items() for x in [i for i in items if i["scope"] == scope][:hi]]
    save({"name": f"{now:%Y-%m-%d}-{slot}", "kind": "daily", "slot": slot, "time": now.isoformat(), "items": chosen})
    top = [x for x in chosen if x["new"]][:3] or chosen[:3]
    label = "午间要闻" if slot == "noon" else "傍晚要闻"
    write_notify(f"📰 {label}（共{len(chosen)}条）", [f"{i+1}. {x['title']}" for i, x in enumerate(top)])
    return now


def parliament(now, after_daily):
    arts = [a for a in fetch(7) if KW.search(a["title"])]
    b = {"name": f"{now:%Y-%m-%d}-parliament", "kind": "parliament", "time": now.isoformat(), "items": []}
    if len(arts) < 5:
        b["note"] = "本周国会相关报道不足，可能处于休会期。"
    else:
        b["items"] = build(arts, MIN_OWNERS["parliament"])[:10]
    save(b)
    lines = [f"🏛 国会周报：{len(b['items'])}个重要议题" if b["items"] else "🏛 国会周报：本周无足够内容"]
    write_notify("🏛 国会周报", lines, extra=after_daily)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "check":
        fetch(1)
    elif mode == "parliament":
        parliament(dt.datetime.now(MYT), False); render()
    else:
        now = daily(mode)
        if mode == "evening" and now.weekday() == 2:   # 周三傍晚加发国会周报
            parliament(now, True)
        render()
