"""OpenAI-compatible /v1/embeddings over fastembed, for the Go qdrant-mcp.

Uses the same library and the same ONNX weights as mcp-server-qdrant, so a
MiniLM vector written by either toolset is the same vector. The only thing that
differs between the two MiniLM arms is then the toolset itself.

`model` selects the model; the Go server sends it when EMBEDDINGS_MODEL is set.
No instruction prefix is added here -- the Go server adds nomic's itself.
"""
import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastembed import TextEmbedding

from common import FASTEMBED_CACHE as CACHE, MINILM, NOMIC
# The cluster serves nomic from llama.cpp at 2048 tokens per slot; match that
# window rather than whatever the ONNX export's tokenizer config says.
NOMIC_MAX_TOKENS = int(os.environ.get("NOMIC_MAX_TOKENS", "2048"))

_models, _lock = {}, threading.Lock()


def model(name):
    with _lock:
        if name not in _models:
            m = TextEmbedding(name, cache_dir=CACHE)
            if name == NOMIC:
                m.model.tokenizer.enable_truncation(max_length=NOMIC_MAX_TOKENS)
            _models[name] = (m, threading.Lock())
            t = m.model.tokenizer.truncation
            print(f"loaded {name}: truncation={t}", file=sys.stderr, flush=True)
        return _models[name]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "ok"})
        if self.path == "/v1/models":
            return self._send(200, {"data": [{"id": MINILM}, {"id": NOMIC}]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/v1/embeddings":
            return self._send(404, {"error": "not found"})
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        name = req.get("model") or MINILM
        if name not in (MINILM, NOMIC):
            return self._send(400, {"error": f"unknown model {name}"})
        inputs = req["input"] if isinstance(req["input"], list) else [req["input"]]
        m, lk = model(name)
        with lk:
            vecs = [v.tolist() for v in m.embed(inputs)]
        self._send(200, {"object": "list", "model": name,
                         "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vecs)]})


if __name__ == "__main__":
    for n in (MINILM, NOMIC):
        model(n)
    port = int(os.environ.get("PORT", "8091"))
    print(f"listening on :{port}", file=sys.stderr, flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
