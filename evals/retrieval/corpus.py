"""Build the corpora and check the questions against them.

  python corpus.py            # .work/corpus.json: every object in releases/ and bootstrap/
  python corpus.py --scaled   # also .work/corpus_scaled.json: + other branches + `helm template`
  python corpus.py --check    # every evidence string exists; recompute answer depth

One document per Kubernetes object, as authored: the raw YAML segment with its
comments, which is where most of the "why" in this repo lives.

The scaled corpus adds distractors that share no kind/name with a base object,
so every question keeps exactly the targets it was written for: manifests from
the other branches, and what the pinned charts render with the values from
their HelmReleases (CRDs excluded -- 100KB+ schemas nobody asks about).
"""
import argparse
import glob
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from common import HERE, REPO, WORK, corpus_path, dump_json, load_json

SEP = re.compile(r"(?m)^---\s*$")

BRANCHES = ["origin/feat/triage", "origin/feat/otel-demo", "origin/feat/xray-memory",
            "origin/feat/flux-operator-bootstrap-module", "upstream/main"]

# HelmRelease name -> (namespace, chart args), pinned as in releases/.
CHARTS = {
    "qdrant": ("qdrant", ["qdrant", "--repo", "https://qdrant.github.io/qdrant-helm", "--version", "1.19.1"]),
    "neo4j": ("neo4j", ["neo4j", "--repo", "https://helm.neo4j.com/neo4j", "--version", "2026.7.1"]),
    "phoenix": ("phoenix", ["oci://registry-1.docker.io/arizephoenix/phoenix-helm", "--version", "12.0.10"]),
    "kagent": ("kagent", ["oci://ghcr.io/kagent-dev/kagent/helm/kagent", "--version", "0.10.1"]),
    "agentgateway": ("agentgateway-system", ["oci://cr.agentgateway.dev/charts/agentgateway", "--version", "1.5.0"]),
    "agentregistry-inventory": ("agentregistry", ["oci://ghcr.io/den-vasyliev/charts/agentregistry", "--version", "0.5.16"]),
    "llm-d-pool": ("llm-d", ["oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool", "--version", "v1.5.0"]),
    "llm-d-embedding": ("llm-d", ["llm-d-modelservice", "--repo", "https://llm-d-incubation.github.io/llm-d-modelservice/", "--version", "v0.3.17"]),
}


def split(raw, path):
    for seg in SEP.split(raw):
        if not seg.strip():
            continue
        try:
            obj = yaml.safe_load(seg)
        except yaml.YAMLError:
            continue
        if not isinstance(obj, dict) or "kind" not in obj or not (obj.get("metadata") or {}).get("name"):
            continue
        md = obj["metadata"]
        ns = md.get("namespace", "cluster")
        yield {"id": f'{obj["kind"]}/{ns}/{md["name"]}@{path}', "kind": obj["kind"], "name": md["name"],
               "namespace": ns, "path": path, "text": seg.strip("\n") + "\n", "obj": obj}


def base():
    files = sorted(glob.glob(str(REPO / "releases/**/*.yaml"), recursive=True)) + [str(REPO / "bootstrap/flux-instance.yaml")]
    docs = [d for f in files for d in split(Path(f).read_text(), str(Path(f).relative_to(REPO)))]
    ids = [d["id"] for d in docs]
    assert len(ids) == len(set(ids)), "duplicate object ids"
    return docs


def scaled(base_docs):
    taken = {(d["kind"], d["name"]) for d in base_docs}
    seen = {(d["kind"], d["namespace"], d["name"]) for d in base_docs}
    extra = []

    def add(d):
        key = (d["kind"], d["namespace"], d["name"])
        if (d["kind"], d["name"]) in taken or key in seen or d["kind"] == "CustomResourceDefinition":
            return
        seen.add(key)
        extra.append(d)

    for b in BRANCHES:
        try:
            files = subprocess.check_output(["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", b], text=True).split()
        except subprocess.CalledProcessError:
            print(f"skip {b}: not found", file=sys.stderr)
            continue
        for f in files:
            if re.search(r"\.ya?ml$", f) and not f.startswith(".github/"):
                raw = subprocess.check_output(["git", "-C", str(REPO), "show", f"{b}:{f}"], text=True)
                for d in split(raw, f"{b.split('/')[-1]}:{f}"):
                    add(d)

    values = {d["name"]: (d["obj"]["spec"].get("values") or {}) for d in base_docs if d["kind"] == "HelmRelease"}
    with tempfile.TemporaryDirectory() as tmp:
        for name, (ns, chart) in CHARTS.items():
            vf = Path(tmp) / f"{name}.yaml"
            vf.write_text(yaml.safe_dump(values.get(name, {})))
            out = subprocess.run(["helm", "template", name, *chart, "--namespace", ns, "--values", str(vf), "--skip-crds"],
                                 capture_output=True, text=True)
            if out.returncode:
                print(f"helm template {name} failed: {out.stderr[-300:]}", file=sys.stderr)
                continue
            for d in split(out.stdout, f"helm template {name}"):
                add(d)
    return base_docs + extra


def check(docs):
    """Every evidence string must be in one of its question's targets. Depth is
    where the evidence starts, in MiniLM tokens: "head" if it ends inside the
    128-token window fastembed embeds, "deep" otherwise."""
    from tokenizers import Tokenizer
    from common import FASTEMBED_CACHE
    tj = glob.glob(f"{FASTEMBED_CACHE}/models--qdrant--all-MiniLM-L6-v2-onnx/snapshots/*/tokenizer.json")
    assert tj, "run embed_shim.py once so fastembed downloads MiniLM"
    tok = Tokenizer.from_file(tj[0]); tok.no_truncation(); tok.no_padding()
    by = {}
    for d in docs:
        by.setdefault(f'{d["kind"]}/{d["name"]}', []).append(d)
    qs = load_json(HERE / "questions.json")
    bad = 0
    for q in qs:
        missing = [t for t in q["targets"] if t not in by]
        if missing:
            print("no such target", q["id"], missing); bad += 1
        if q.get("negative"):
            continue
        hits = [d for t in q["targets"] for d in by.get(t, []) if q["evidence"] in d["text"]]
        if not hits:
            print("evidence not found", q["id"], repr(q["evidence"])); bad += 1
            continue
        d = hits[0]
        enc = tok.encode(d["text"])
        at = d["text"].index(q["evidence"])
        start = next((i for i, (a, _) in enumerate(enc.offsets) if a >= at), len(enc.ids))
        q["depth_tokens"], q["doc_tokens"] = start, len(enc.ids)
        q["depth"] = "head" if start + len(tok.encode(q["evidence"]).ids) <= 126 else "deep"
    dump_json(qs, HERE / "questions.json")
    print(f"{len(qs)} questions, {bad} problems")
    return bad == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scaled", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    docs = base()
    strip = lambda ds: [{k: v for k, v in d.items() if k != "obj"} for d in ds]
    dump_json(strip(docs), corpus_path("base"))
    print(f"base: {len(docs)} objects, {sum(len(d['text']) for d in docs)} chars")
    if a.scaled:
        big = scaled(docs)
        dump_json(strip(big), corpus_path("scaled"))
        print(f"scaled: {len(big)} objects, {sum(len(d['text']) for d in big)} chars")
    if a.check:
        sys.exit(0 if check(docs) else 1)
