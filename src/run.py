"""每日简报：抓取 -> 聚类 -> 程序统计“至少N家独立来源” -> 中文摘要 -> 页面 + 通知。
用法：python src/run.py noon|evening|parliament|check"""
import datetime as dt, json, os, re, sys, urllib.parse
from zoneinfo import ZoneInfo
import anthropic, feedparser, yaml
from render import render

MYT = ZoneInfo("Asia/Kuala_Lumpur")
MODEL = os.getenv("MODEL", "claude-sonnet-5-5")
MIN_OWNERS = {"daily": 3, "parliament": 2}   # 日常 ≥3 家；国会周报 ≥2 家（可自行改）
LIMITS = {"my": 15, "world": 10}             # 上限；达标的不够就宁缺毋滥
KW = re.compile(r"国会|下议院|上议院|议员|Dewan Rakyat|Dewan Negara|Parlimen|Parliament|Hansard", re.I)
client = anthropic.Anthropic()


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
        try:
            feed = feedparser.parse(feed_url(s, days))
        except Exception as e:
            print("FAIL", s["name"], e); continue
        n = 0
        for e in feed.entries[:30]:
            t = e.get("published_parsed")
            if t and dt.datetime(*t[:6], tzinfo=dt.timezone.utc) < cutoff:
                continue
            title = e.title if s.get("url") else re.sub(r"\s+[-–|]\s+[^-–|]+$", "", e.title)
            arts.append(dict(id=len(arts), source=s["name"], owner=s["owner"], official=s.get("official", False),
                             title=title, link=e.link, summary=re.sub("<[^>]+>", "", e.get("summary", ""))[:200]))
            n += 1
        print(f"{s['name']}: {n} 条")
    return arts


def ask(prompt, max_tokens=16000):
    r = client.messages.create(model=MODEL, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
    return json.loads(re.search(r"[\[{].*[\]}]", r.content[0].text, re.S).group(0))


def cluster(arts):
    lines = "\n".join(f"{a['id']}|{a['source']}|{a['title']}" for a in arts)
    return ask("下面是多家媒体的新闻标题（id|媒体|标题），语言含中文、马来文、英文。\n"
               "把报道【同一具体事件】的标题归为一组，只输出含2条以上的组，无关的忽略。\n"
               "只输出JSON：[[id,id,...],...]，不要任何解释。\n" + lines)


def qualify(groups, arts, need):
    out = []
    for g in groups:
        items = [arts[i] for i in g if isinstance(i, int) and 0 <= i < len(arts)]
        if len({a["owner"] for a in items}) >= need:   # 由程序统计，不交给AI
            out.append(items)
    return sorted(out, key=lambda c: -len({a["owner"] for a in c}))[:45]


def summarise(clusters, parl=False):
    blocks = ["[%d]\n" % i + "\n".join(f"- {a['source']}: {a['title']} {a['summary']}" for a in c[:8])
              for i, c in enumerate(clusters)]
    cat = "议题类型（法案/质询/预算/争议/其他）" if parl else "类别（政治/经济/社会/司法/国际/科技/其他）"
    res = ask("你是新闻编辑。下面每个编号是一个事件，含多家媒体的报道标题与摘要。\n"
              "只能依据所给内容，不得补充任何未提供的事实、数字或链接。逐个输出：\n"
              "same_event：这些报道确实是同一事件吗(true/false)；title：中文标题，30字内；"
              "summary：中文摘要2-3句，只陈述事实不加评论；scope：\"my\"(马来西亚是主要主体或直接受影响)或\"world\"；"
              f"category：{cat}；importance：1-10(影响范围、政策与法律后果、官方行动)；"
              "work：是否与资本市场/监管/行业政策(Bursa、SC、BNM、建筑、地产、F&B、O&G等)相关(true/false)。\n"
              '只输出JSON数组：[{"i":0,"same_event":true,"title":"","summary":"","scope":"","category":"","importance":0,"work":false}]\n'
              + "\n".join(blocks))
    items = []
    for r in res:
        if not r.get("same_event") or not 0 <= r["i"] < len(clusters):
            continue
        c, seen, links = clusters[r["i"]], set(), []
        for a in c:   # 链接只来自抓取到的真实文章，每家媒体一条
            if a["source"] not in seen:
                seen.add(a["source"]); links.append({"source": a["source"], "url": a["link"]})
        items.append({k: r[k] for k in ("title", "summary", "scope", "category", "importance", "work")}
                     | {"owners": len({a["owner"] for a in c}), "links": links})
    return items


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
    arts = fetch(1)
    items = summarise(qualify(cluster(arts), arts, MIN_OWNERS["daily"]))
    prev = set()
    f = f"data/{now:%Y-%m-%d}-noon.json"
    if slot == "evening" and os.path.exists(f):
        prev = {l["url"] for x in json.load(open(f, encoding="utf-8"))["items"] for l in x["links"]}
    for x in items:
        x["new"] = not any(l["url"] in prev for l in x["links"])
    chosen = []
    for scope, hi in LIMITS.items():
        pool = sorted((x for x in items if x["scope"] == scope), key=lambda x: (-x["importance"], -x["owners"]))
        chosen += pool[:hi]
    save({"name": f"{now:%Y-%m-%d}-{slot}", "kind": "daily", "slot": slot, "time": now.isoformat(), "items": chosen})
    top = sorted((x for x in chosen if x["new"]), key=lambda x: -x["importance"])[:3] or chosen[:3]
    label = "午间要闻" if slot == "noon" else "傍晚要闻"
    write_notify(f"📰 {label}（共{len(chosen)}条）", [f"{i+1}. {x['title']}" for i, x in enumerate(top)])
    return now


def parliament(now, after_daily):
    arts = [a for a in fetch(7) if KW.search(a["title"] + a["summary"])]
    arts = [{**a, "id": i} for i, a in enumerate(arts)]
    b = {"name": f"{now:%Y-%m-%d}-parliament", "kind": "parliament", "time": now.isoformat(), "items": []}
    if len(arts) < 5:
        b["note"] = "本周国会相关报道不足，可能处于休会期。"
    else:
        b["items"] = sorted(summarise(qualify(cluster(arts), arts, MIN_OWNERS["parliament"]), True),
                            key=lambda x: -x["importance"])[:10]
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
