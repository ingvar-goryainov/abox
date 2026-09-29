"""Grade agent_run.py's output against questions.json.

  python grade.py <base|scaled> [--detail]

verdict   correct  every required fact group matched in the answer
          partial  some matched
          wrong    none matched, or no answer
          abstain  negative question, and the agent said nothing relevant is stored
          halluc   negative question, and the agent answered anyway
seen      the evidence string was in some tool result the agent received:
          separates a retrieval miss from a reading miss
unbacked  numbers and versions in the answer that appear in no tool result --
          a cheap hallucination screen, each hit read by hand

overrides.json holds hand-audited verdicts keyed "<corpus>/<arm>/<id>", each
with its reason. They replace the regex verdict and the report says so.
"""
import json
import re
import statistics
import sys

from common import ARM_NAMES, HERE, WORK, load_json, questions

qs = {q["id"]: q for q in questions()}
OVERRIDES = load_json(HERE / "overrides.json") if (HERE / "overrides.json").exists() else {}

ABSTAIN = re.compile(r"(nothing relevant|not (stored|found|present|in the (vector )?store|in the (retrieved|stored)|indexed)|"
                     r"no (relevant|information|results?|data|mention|redis|prometheus|configuration|manifests?|records?|entries|matching)|"
                     r"there (is|are) no |(isn't|is not|aren't|are not) (stored|indexed|present|in)|does(n't| not) (contain|include|appear|exist|have)|"
                     r"(couldn't|could not|unable to|did not|didn't) find|none of the (retrieved|results|returned))", re.I)
NUMBER = re.compile(r"(?<![\w.])v?\d+(?:\.\d+)*(?:m|Mi|Gi|s)?(?![\w.])")


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def leaves(v):
    """Every string in a tool result, however many times it was JSON-encoded:
    the Go server's structuredContent is {"body": "<JSON string>"}, and the
    official server's is a JSON array of strings."""
    if isinstance(v, str):
        t = v.strip()
        if t[:1] in "[{":
            try:
                return leaves(json.loads(t))
            except json.JSONDecodeError:
                pass
        return [v]
    if isinstance(v, dict):
        return [x for val in v.values() for x in leaves(val)]
    if isinstance(v, list):
        return [x for val in v for x in leaves(val)]
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return [str(v)]  # scores: an answer may quote them
    return []


def grade(rec):
    q = qs[rec["id"]]
    ans = rec.get("answer") or ""
    seen_text = norm(" ".join(x for c in rec["calls"] for x in leaves((c.get("result") or {}).get("text", ""))))
    usage = rec.get("usage") or {}
    g = {"calls": len(rec["calls"]), "result_chars": sum((c.get("result") or {}).get("chars", 0) for c in rec["calls"]),
         "wall": rec.get("wall_seconds"), "depth": q.get("depth", "neg"), "lang": q["lang"],
         "input_tokens": sum(usage.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")),
         "unbacked": sorted({n for n in NUMBER.findall(ans) if n.lstrip("v") not in seen_text and len(n.lstrip("v")) > 1})}
    if q.get("negative"):
        g["verdict"], g["seen"] = ("abstain" if ABSTAIN.search(ans) else "halluc"), None
    else:
        matched = [any(re.search(p, ans, re.I) for p in grp) for grp in q["facts"]]
        g["verdict"] = "correct" if ans and all(matched) else "partial" if any(matched) else "wrong"
        g["seen"] = norm(q["evidence"]) in seen_text
    key = f'{rec["corpus"]}/{rec["arm"]}/{rec["id"]}'
    if key in OVERRIDES:
        g["regex_verdict"], g["verdict"], g["override"] = g["verdict"], OVERRIDES[key]["verdict"], OVERRIDES[key]["reason"]
    return g


def load(corpus):
    out = {}
    for arm in ARM_NAMES:
        out[arm] = {}
        for f in sorted((WORK / "agent_runs" / corpus / arm).glob("*.json")):
            rec = load_json(f)
            out[arm][rec["id"]] = (rec, grade(rec))
    return out


def pct(n, d):
    return f"{100 * n / d:5.1f}%" if d else "  -  "


def report(corpus):
    runs = load(corpus)
    model = next((r.get("model") for d in runs.values() for r, _ in d.values()), "?")
    print(f"\n## corpus: {corpus}  ({model})")
    print(f"{'arm':16} {'n':>3} | {'correct':>8} {'partial':>8} {'wrong':>7} | {'deep ok':>8} {'head ok':>8} {'uk ok':>6} | "
          f"{'neg abst':>8} | {'seen':>6} {'miss|seen':>9} | {'>3 calls':>8} {'calls':>5} {'res kch':>7} {'in ktok':>7} {'s/q':>5}")
    for arm in ARM_NAMES:
        gs = [g for _, g in runs[arm].values()]
        if not gs:
            continue
        ans = [g for g in gs if g["depth"] != "neg"]; neg = [g for g in gs if g["depth"] == "neg"]
        ok = lambda xs: sum(g["verdict"] == "correct" for g in xs)
        deep = [g for g in ans if g["depth"] == "deep"]; head = [g for g in ans if g["depth"] == "head"]
        uk = [g for g in ans if g["lang"] == "uk"]
        print(f"{arm:16} {len(ans):3} | {pct(ok(ans), len(ans)):>8} {pct(sum(g['verdict'] == 'partial' for g in ans), len(ans)):>8} "
              f"{pct(sum(g['verdict'] == 'wrong' for g in ans), len(ans)):>7} | {pct(ok(deep), len(deep)):>8} {pct(ok(head), len(head)):>8} "
              f"{pct(ok(uk), len(uk)):>6} | {sum(g['verdict'] == 'abstain' for g in neg)}/{len(neg):<6} | "
              f"{pct(sum(bool(g['seen']) for g in ans), len(ans)):>6} {sum(bool(g['seen']) and g['verdict'] != 'correct' for g in ans):>9} | "
              f"{sum(g['calls'] > 3 for g in gs):>8} {statistics.mean(g['calls'] for g in gs):5.2f} "
              f"{statistics.mean(g['result_chars'] for g in gs) / 1000:7.1f} {statistics.mean(g['input_tokens'] for g in gs) / 1000:7.1f} "
              f"{statistics.mean(g['wall'] for g in gs):5.1f}")
    return runs


if __name__ == "__main__":
    corpus = sys.argv[1]
    runs = report(corpus)
    if "--detail" in sys.argv:
        print(f"\n### per question ({corpus})  C=correct P=partial W=wrong A=abstain H=halluc; lower-case = evidence never reached the agent")
        print(f"{'id':4} {'depth':5} " + " ".join(f"{a:>16}" for a in ARM_NAMES))
        for qid, q in qs.items():
            cells = []
            for arm in ARM_NAMES:
                if qid not in runs[arm]:
                    cells.append("-"); continue
                g = runs[arm][qid][1]
                v = g["verdict"][0].upper()
                if g["seen"] is False:
                    v = v.lower()
                cells.append(f"{v}{'*' if 'override' in g else ''} {g['calls']}c")
            print(f"{qid:4} {q.get('depth', 'neg'):5} " + " ".join(f"{c:>16}" for c in cells))
        print("\n* hand-audited, see overrides.json")
        flagged = [(arm, qid, g["unbacked"]) for arm in ARM_NAMES for qid, (_, g) in runs[arm].items() if g["unbacked"]]
        print(f"\n### numbers in answers that no tool result contains ({len(flagged)} answers)")
        for arm, qid, u in flagged:
            print(f"{arm:16} {qid}: {', '.join(u)}")
