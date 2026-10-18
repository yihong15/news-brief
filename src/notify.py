import json, os, requests

n = json.load(open("data/notify.json", encoding="utf-8"))
site = os.getenv("SITE_URL", "")
topic = os.getenv("NTFY_TOPIC")
if topic:
    msg = {"topic": topic, "title": n["title"], "message": "\n".join(n["lines"]), "tags": ["newspaper"]}
    if site:
        msg["click"] = site
    requests.post("https://ntfy.sh/", json=msg, timeout=20).raise_for_status()
tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
if tok and chat:
    text = n["title"] + "\n\n" + "\n".join(n["lines"]) + ("\n\n" + site if site else "")
    requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", json={"chat_id": chat, "text": text}, timeout=20)
