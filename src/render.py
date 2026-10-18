import datetime as dt, glob, html, json, os

E = html.escape
CSS = """
:root{--bg:#f2f4f3;--ink:#17262b;--mute:#5d6e72;--line:#d5dcdb;--acc:#0e6b6b;--work:#8a5a00;--bar:#fbfcfb}
@media(prefers-color-scheme:dark){:root{--bg:#10191b;--ink:#e6eeee;--mute:#93a5a8;--line:#27373a;--acc:#5fc4c0;--work:#e0b255;--bar:#162124}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.65 -apple-system,"PingFang SC","Noto Sans SC",sans-serif;
padding:env(safe-area-inset-top) 0 calc(76px + env(safe-area-inset-bottom))}
main{max-width:640px;margin:0 auto;padding:0 20px}
h1{font-size:15px;font-weight:500;color:var(--mute);margin:18px 0 6px}
h2{font-size:15px;font-weight:600;margin:26px 0 0;color:var(--mute)}
article{padding:18px 0;border-bottom:1px solid var(--line)}
article.w{border-left:3px solid var(--work);padding-left:14px}
.m{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:13px;color:var(--mute)}
.m .k{color:var(--work);font-weight:600}
h3{font-size:19px;line-height:1.4;margin:4px 0 6px;font-weight:650}
article p{margin:0 0 10px;font-size:16px}
.l{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:14px}
.l a{color:var(--acc);text-decoration:underline;text-underline-offset:3px;padding:4px 0}
.e{color:var(--mute);padding:28px 0}
.panel{display:none}.panel.on{display:block}
nav{position:fixed;left:0;right:0;bottom:0;display:flex;background:var(--bar);border-top:1px solid var(--line);
padding-bottom:env(safe-area-inset-bottom)}
nav button{flex:1;border:0;background:none;color:var(--mute);font:inherit;font-size:15px;padding:16px 0;
border-top:3px solid transparent}
nav button.on{color:var(--ink);font-weight:650;border-top-color:var(--acc)}
nav button:focus-visible,.l a:focus-visible{outline:2px solid var(--acc);outline-offset:-2px}
ul{list-style:none;padding:0;margin:0}li a{display:block;padding:14px 0;border-bottom:1px solid var(--line);color:var(--ink);text-decoration:none}
"""


def when(b):
    return dt.datetime.fromisoformat(b["time"]).strftime("%m月%d日 %H:%M 更新")


def row(x):
    tags = f'<span>{E(x["category"])}</span><span>{x["owners"]} 家独立来源</span>'
    if x.get("work"):
        tags += '<span class="k">工作相关</span>'
    if not x.get("new", True):
        tags += "<span>上次已报</span>"
    links = "".join(f'<a href="{E(l["url"])}" target="_blank" rel="noopener">{E(l["source"])}</a>' for l in x["links"])
    return (f'<article{" class=w" if x.get("work") else ""}><div class="m">{tags}</div>'
            f'<h3>{E(x["title"])}</h3><p>{E(x["summary"])}</p><div class="l">{links}</div></article>')


def rows(items, empty):
    return "".join(row(x) for x in items) or f'<p class="e">{E(empty)}</p>'


def shell(body, nav=""):
    return ('<!doctype html><html lang="zh-Hans"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="每日简报">'
            f'<title>每日简报</title><style>{CSS}</style></head><body><main>{body}</main>{nav}</body></html>')


def render():
    bs = []
    for f in glob.glob("data/*.json"):
        if f.endswith("notify.json"):
            continue
        b = json.load(open(f, encoding="utf-8")); b["name"] = os.path.basename(f)[:-5]; bs.append(b)
    bs.sort(key=lambda b: b["time"], reverse=True)
    os.makedirs("docs", exist_ok=True)
    for b in bs:   # 每一期都有独立页面，方便回看
        if b["kind"] == "daily":
            sub = "".join(f"<h2>{t}</h2>{rows([x for x in b['items'] if x.get('scope') == s], '无')}"
                          for s, t in (("my", "马来西亚"), ("world", "国际")))
        else:
            sub = rows(b["items"], b.get("note", "暂无"))
        open(f"docs/{b['name']}.html", "w", encoding="utf-8").write(shell(f'<h1>{b["name"]}　{when(b)}</h1>{sub}'))
    d = next((b for b in bs if b["kind"] == "daily"), None)
    p = next((b for b in bs if b["kind"] == "parliament"), None)
    mk = lambda s: rows([x for x in d["items"] if x["scope"] == s], "今天暂无符合“至少3家独立来源”的新闻。") if d else '<p class="e">还没有简报。</p>'
    arch = "<ul>" + "".join(f'<li><a href="{b["name"]}.html">{E(b["name"])}</a></li>' for b in bs) + "</ul>"
    panels = [("马来西亚", mk("my"), d), ("国际", mk("world"), d),
              ("国会", rows(p["items"], p.get("note", "")) if p else '<p class="e">每周三傍晚更新。</p>', p), ("往期", arch, None)]
    body = "".join(f'<section class="panel{" on" if i == 0 else ""}" id="p{i}">'
                   f'<h1>{when(b) if b else "全部简报"}</h1>{h}</section>' for i, (_, h, b) in enumerate(panels))
    nav = ("<nav>" + "".join(f'<button class="{"on" if i == 0 else ""}" data-i="{i}">{n}</button>'
                             for i, (n, _, _) in enumerate(panels)) + "</nav>"
           "<script>document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{"
           "document.querySelectorAll('.on').forEach(e=>e.classList.remove('on'));"
           "b.classList.add('on');document.getElementById('p'+b.dataset.i).classList.add('on');scrollTo(0,0)})</script>")
    open("docs/index.html", "w", encoding="utf-8").write(shell(body, nav))
