"""AI news aggregator: fetch -> clean -> dedupe -> rank -> web/public/news.json"""
import hashlib, html, json, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser, httpx, numpy as np, yaml

ROOT = Path(__file__).parent
ITEMS, OUT = ROOT / "data" / "items.json", ROOT / "web" / "public" / "news.json"
KEEP_DAYS, THRESH, PER_FEED, UA = 30, 0.85, 40, "ai-news-bot/1.0"


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def summarize(text, n=2, cap=400):
    return " ".join(re.split(r"(?<=[.!?])\s+", clean(text))[:n])[:cap]


def item(source, title, url, ts, text="", score=0):
    return {"id": hashlib.sha1(url.encode()).hexdigest()[:16], "source": source,
            "title": clean(title), "url": url, "published": ts.isoformat(),
            "summary": summarize(text), "score": score}


def fetch_feeds(feeds, client):
    out = []
    for f in feeds:
        try:
            r = client.get(f["url"]); r.raise_for_status()
            for e in feedparser.parse(r.content).entries[:PER_FEED]:
                t = e.get("published_parsed") or e.get("updated_parsed")
                ts = datetime(*t[:6], tzinfo=timezone.utc) if t else datetime.now(timezone.utc)
                if e.get("link") and e.get("title"):
                    out.append(item(f["name"], e["title"], e["link"], ts, e.get("summary", "")))
        except Exception as ex:
            print(f"[skip] {f['name']}: {ex}", file=sys.stderr)
    return out


def fetch_hn(queries, client):
    out = []
    for q in queries:
        try:
            r = client.get("https://hn.algolia.com/api/v1/search_by_date", params={
                "tags": "story", "query": q, "numericFilters": "points>30", "hitsPerPage": 30})
            r.raise_for_status()
            for h in r.json()["hits"]:
                url = h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}"
                ts = datetime.fromisoformat(h["created_at"].replace("Z", "+00:00"))
                out.append(item("Hacker News", h["title"], url, ts, "", h.get("points", 0)))
        except Exception as ex:
            print(f"[skip] HN {q}: {ex}", file=sys.stderr)
    return out


def merge(old, new, now):
    d = {i["id"]: i for i in old}
    for i in new:
        i["score"] = max(i["score"], d.get(i["id"], {}).get("score", 0))
        d[i["id"]] = i
    cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
    return [i for i in d.values() if i["published"] >= cutoff]


def embed(items):
    """[N, 384] L2-normalised bge-small vectors, or None if fastembed is missing."""
    try:
        from fastembed import TextEmbedding
    except ImportError:
        return None
    texts = [f"{i['title']}. {i['summary'][:200]}" for i in items]
    v = np.array(list(TextEmbedding("BAAI/bge-small-en-v1.5").embed(texts)), dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def cluster(vecs, thresh=THRESH):
    reps, labels = [], []
    for i, v in enumerate(vecs):
        sims = [float(v @ vecs[r]) for r in reps]
        j = int(np.argmax(sims)) if sims and max(sims) >= thresh else -1
        if j < 0:
            reps.append(i); j = len(reps) - 1
        labels.append(j)
    return labels


def build_stories(items, labels):
    groups = {}
    for it, l in zip(items, labels):
        groups.setdefault(l, []).append(it)
    stories = []
    for g in groups.values():
        g.sort(key=lambda x: x["published"])
        lead, seen, srcs = g[0], set(), []
        for x in g:
            if x["url"] not in seen:
                seen.add(x["url"])
                srcs.append({"name": x["source"], "url": x["url"], "published": x["published"]})
        stories.append({"id": lead["id"], "title": lead["title"],
                        "summary": next((x["summary"] for x in g if x["summary"]), ""),
                        "published": g[-1]["published"], "sources": srcs,
                        "score": 2 * len(srcs) + sum(x["score"] for x in g) / 50})
    return sorted(stories, key=lambda s: s["published"], reverse=True)


def main():
    cfg = yaml.safe_load((ROOT / "sources.yaml").read_text())
    now = datetime.now(timezone.utc)
    old = json.loads(ITEMS.read_text()) if ITEMS.exists() else []
    with httpx.Client(headers={"User-Agent": UA}, timeout=20, follow_redirects=True) as c:
        new = fetch_feeds(cfg["feeds"], c) + fetch_hn(cfg.get("hn_queries", []), c)
    items = sorted(merge(old, new, now), key=lambda i: i["published"])
    vecs = embed(items) if items else None
    labels = cluster(vecs) if vecs is not None else list(range(len(items)))
    stories = build_stories(items, labels)
    ITEMS.parent.mkdir(exist_ok=True)
    ITEMS.write_text(json.dumps(items, indent=1))
    OUT.write_text(json.dumps({"generated": now.isoformat(), "stories": stories}, indent=1))
    print(f"fetched={len(new)} items={len(items)} stories={len(stories)}")
    if not new:
        print("WARNING: nothing fetched", file=sys.stderr)


if __name__ == "__main__":
    main()
