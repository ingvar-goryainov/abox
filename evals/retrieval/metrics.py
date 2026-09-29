"""Deterministic retrieval metrics over harness.py's find output, plus index
coverage. No LLM involved: this measures the toolset alone.

  python metrics.py <base|scaled>

hit@k      the question's target object is among the first k distinct objects
ev@5       some returned text contains the evidence string -- the answer is
           actually in front of the agent, not just its object's name
any        either of the two mandated queries
coverage   share of corpus characters that fall inside some vector's token
           window; the rest is stored but was never embedded
"""
import glob
import json
import re
import statistics
import sys
import urllib.request
from collections import defaultdict

from tokenizers import Tokenizer

from common import ARM_NAMES, FASTEMBED_CACHE, QDRANT_URL, WORK, arms, corpus_path, dump_json, load_json, questions

corpus = sys.argv[1]
qs = {q["id"]: q for q in questions()}
ret = load_json(WORK / f"find_{corpus}.json")
docs = load_json(corpus_path(corpus))


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def objs(hits):
    seen, out = set(), []
    for h in hits:
        k = f'{h["kind"]}/{h["name"]}'
        if k not in seen:
            seen.add(k); out.append(k)
    return out


def rank(hits, targets):
    return next((i for i, k in enumerate(objs(hits), 1) if k in targets), None)


rows = defaultdict(list)
for arm in ARM_NAMES:
    for r in ret[arm]:
        q = qs[r["id"]]
        row = {"id": q["id"], "depth": q.get("depth", "neg"), "lang": q["lang"],
               "distinct": [len(objs(r[k]["hits"])) for k in ("q", "kw")],
               "chars": [r[k]["response_chars"] for k in ("q", "kw")],
               "top_score": [r[k]["hits"][0]["score"] if r[k]["hits"] else None for k in ("q", "kw")]}
        if not q.get("negative"):
            t, ev = set(q["targets"]), norm(q["evidence"])
            row["rank_q"], row["rank_kw"] = rank(r["q"]["hits"], t), rank(r["kw"]["hits"], t)
            row["ev_q"] = any(ev in norm(h["text"]) for h in r["q"]["hits"])
            row["ev_kw"] = any(ev in norm(h["text"]) for h in r["kw"]["hits"])
        rows[arm].append(row)
dump_json(rows, WORK / f"metrics_rows_{corpus}.json")


def pct(xs):
    return f"{100 * sum(xs) / len(xs):5.1f}%" if xs else "   -  "


def summary(sel, label):
    print(f"\n### {label}")
    print(f"{'arm':16} {'n':>3} | {'hit@1 q':>8} {'hit@5 q':>8} {'hit@1 kw':>8} {'hit@5 kw':>8} {'hit@5 any':>9} | "
          f"{'ev@5 q':>7} {'ev@5 kw':>7} {'ev@5 any':>8} | {'MRR best':>8}")
    for arm in ARM_NAMES:
        rs = [r for r in rows[arm] if sel(r) and "rank_q" in r]
        if not rs:
            continue
        h5q = [r["rank_q"] is not None for r in rs]; h5k = [r["rank_kw"] is not None for r in rs]
        eq = [r["ev_q"] for r in rs]; ek = [r["ev_kw"] for r in rs]
        mrr = statistics.mean(max(1 / r["rank_q"] if r["rank_q"] else 0, 1 / r["rank_kw"] if r["rank_kw"] else 0) for r in rs)
        print(f"{arm:16} {len(rs):3} | {pct([r['rank_q'] == 1 for r in rs]):>8} {pct(h5q):>8} "
              f"{pct([r['rank_kw'] == 1 for r in rs]):>8} {pct(h5k):>8} {pct([a or b for a, b in zip(h5q, h5k)]):>9} | "
              f"{pct(eq):>7} {pct(ek):>7} {pct([a or b for a, b in zip(eq, ek)]):>8} | {mrr:8.3f}")


print(f"# corpus: {corpus} ({len(docs)} objects, {sum(len(d['text']) for d in docs)} chars)")
summary(lambda r: True, "all answerable")
summary(lambda r: r["depth"] == "head", "answer within the first 128 tokens of its object")
summary(lambda r: r["depth"] == "deep", "answer past the first 128 tokens")
summary(lambda r: r["lang"] == "uk", "Ukrainian questions (first query in Ukrainian)")

print("\n### result shape per find call")
for arm in ARM_NAMES:
    d = [x for r in rows[arm] for x in r["distinct"]]
    c = [x for r in rows[arm] for x in r["chars"]]
    print(f"{arm:16} distinct objects in top-5: mean {statistics.mean(d):.2f}  | response chars: "
          f"median {statistics.median(c):.0f}  mean {statistics.mean(c):.0f}  max {max(c)}")

print("\n### top-1 similarity, answerable vs negative (official returns no score)")
for arm in ARM_NAMES[1:]:
    pos = [r["top_score"][0] for r in rows[arm] if r["depth"] != "neg"]
    neg = [r["top_score"][0] for r in rows[arm] if r["depth"] == "neg"]
    print(f"{arm:16} answerable min {min(pos):.3f} median {statistics.median(pos):.3f} | negatives {', '.join(f'{x:.3f}' for x in neg)}")

tj = glob.glob(f"{FASTEMBED_CACHE}/models--qdrant--all-MiniLM-L6-v2-onnx/snapshots/*/tokenizer.json")[0]
tok = Tokenizer.from_file(tj); tok.no_truncation(); tok.no_padding()


def window_chars(text, max_tokens):
    offs = [o for o in tok.encode(text).offsets if o != (0, 0)]
    return len(text) if len(offs) <= max_tokens else offs[max_tokens - 1][1]


def scroll(coll):
    pts, off = [], None
    while True:
        body = {"limit": 256, "with_payload": True, "with_vector": False, **({"offset": off} if off is not None else {})}
        req = urllib.request.Request(f"{QDRANT_URL}/collections/{coll}/points/scroll", method="POST",
                                     data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        res = json.load(urllib.request.urlopen(req))["result"]
        pts += res["points"]; off = res.get("next_page_offset")
        if off is None:
            return pts


print("\n### index coverage (share of corpus characters inside an embedded token window)")
total = sum(len(d["text"]) for d in docs)
print(f"{'official-minilm':16} {sum(window_chars(d['text'], 126) for d in docs) / total:6.1%}  "
      f"({len(docs)} points: one per object, 128-token window incl. [CLS]/[SEP])")
cfg = arms(corpus)
for arm, cap in (("go-minilm", 126), ("go-nomic", 2046)):
    by_doc = defaultdict(list)
    for p in scroll(cfg[arm]["collection"]):
        pl = p["payload"]; by_doc[(pl["kind"], pl["name"], pl["path"])].append((pl["chunk"], pl["document"]))
    cov = 0
    for d in docs:
        ranges, pos = [], 0
        for _, text in sorted(by_doc[(d["kind"], d["name"], d["path"])]):
            start = d["text"].find(text, max(0, pos - 400))
            ranges.append((start, start + window_chars(text, cap))); pos = start + 1
        merged = []
        for a, b in sorted(ranges):
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        cov += sum(b - a for a, b in merged)
    print(f"{arm:16} {cov / total:6.1%}  ({sum(len(v) for v in by_doc.values())} points)")
