"""Index the corpus through each toolset's own store tool, then run the two
queries the retrieval prompt mandates -- the question as asked, then an English
keyword query -- through its find tool. Everything goes over MCP stdio, the way
kagent's kmcp adapter drives these servers.

  python harness.py ingest <base|scaled> [arm ...]   # recreate collections, store every object
  python harness.py find   <base|scaled> [arm ...]   # fixed-query retrieval for every question
"""
import asyncio
import json
import re
import sys
import time
import urllib.error
import urllib.request

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from common import ARM_NAMES, QDRANT_URL, WORK, arms, corpus_path, dump_json, load_json, questions, server_env


def http(method, url, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def text_of(res):
    return "\n".join(c.text for c in res.content if getattr(c, "type", "") == "text")


ENTRY = re.compile(r"<entry><content>(.*?)</content><metadata>(.*?)</metadata></entry>", re.S)


def parse_hits(arm, raw):
    """Normalise both tools' output to [{kind, name, text, score}]."""
    if arm.startswith("go-"):
        return [{"kind": h["payload"].get("kind"), "name": h["payload"].get("name"), "text": h["payload"].get("document", ""),
                 "score": h["score"], "chunk": h["payload"].get("chunk"), "chunks": h["payload"].get("chunks")}
                for h in json.loads(raw or "[]")]
    # FastMCP serialises the list[str] qdrant-find returns into one JSON text
    # block, so the entries arrive as escaped strings inside a JSON array.
    try:
        raw = "\n".join(json.loads(raw)) if raw.strip() else ""
    except json.JSONDecodeError:
        pass
    out = []
    for content, md in ENTRY.findall(raw):
        m = json.loads(md) if md else {}
        out.append({"kind": m.get("kind"), "name": m.get("name"), "text": content, "score": None})
    return out


async def ingest(corpus, arm):
    a = arms(corpus)[arm]
    http("DELETE", f"{QDRANT_URL}/collections/{a['collection']}")
    docs = load_json(corpus_path(corpus))
    log = []
    params = StdioServerParameters(command=a["cmd"], args=[], env=server_env(a))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for d in docs:
                md = {"kind": d["kind"], "name": d["name"], "namespace": d["namespace"], "path": d["path"]}
                t0 = time.perf_counter()
                res = await s.call_tool(a["store"], {"information": d["text"], "metadata": md})
                out = text_of(res)
                if res.isError:
                    raise RuntimeError(f"{arm} store {d['id']}: {out[:300]}")
                log.append({"id": d["id"], "seconds": time.perf_counter() - t0, "response_chars": len(out)})
    _, c = http("GET", f"{QDRANT_URL}/collections/{a['collection']}")
    return {"arm": arm, "objects": len(docs), "points": c["result"]["points_count"],
            "ingest_seconds": sum(x["seconds"] for x in log),
            "store_response_chars": sum(x["response_chars"] for x in log), "per_doc": log}


async def find(corpus, arm):
    a = arms(corpus)[arm]
    out = []
    params = StdioServerParameters(command=a["cmd"], args=[], env=server_env(a))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for q in questions():
                row = {"id": q["id"]}
                for key in ("q", "kw"):
                    t0 = time.perf_counter()
                    raw = text_of(await s.call_tool(a["find"], {"query": q[key]}))
                    row[key] = {"seconds": time.perf_counter() - t0, "response_chars": len(raw), "hits": parse_hits(arm, raw)}
                out.append(row)
    return out


async def main():
    mode, corpus, *sel = sys.argv[1:]
    sel = sel or ARM_NAMES
    path = WORK / f"{mode}_{corpus}.json"
    prev = load_json(path) if path.exists() else {}
    for arm in sel:
        prev[arm] = await (ingest if mode == "ingest" else find)(corpus, arm)
        if mode == "ingest":
            r = prev[arm]
            print(f"{arm:16} objects={r['objects']} points={r['points']} ingest={r['ingest_seconds']:.1f}s "
                  f"store_response_chars={r['store_response_chars']}", flush=True)
        else:
            print(f"{arm:16} done", flush=True)
    dump_json(prev, path)


asyncio.run(main())
