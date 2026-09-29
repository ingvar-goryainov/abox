"""Paths, endpoints and the three arms under test. Everything is overridable
from the environment; see README.md."""
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORK = Path(os.environ.get("EVAL_WORK", HERE / ".work"))

QDRANT_URL = os.environ.get("EVAL_QDRANT_URL", "http://127.0.0.1:6333")
SHIM_URL = os.environ.get("EVAL_SHIM_URL", "http://127.0.0.1:8091")
FASTEMBED_CACHE = os.environ.get("FASTEMBED_CACHE_PATH", str(WORK / "fastembed"))
GO_SERVER = os.environ.get("EVAL_GO_SERVER", str(WORK / "bin" / "qdrant-mcp"))
# The venv's own copy first, so running its python without activating it works.
_venv_official = Path(sys.executable).parent / "mcp-server-qdrant"
OFFICIAL_SERVER = os.environ.get("EVAL_OFFICIAL_SERVER", str(_venv_official) if _venv_official.exists()
                                 else shutil.which("mcp-server-qdrant") or "mcp-server-qdrant")

MINILM = "sentence-transformers/all-MiniLM-L6-v2"
NOMIC = "nomic-ai/nomic-embed-text-v1.5"
ARM_NAMES = ["official-minilm", "go-minilm", "go-nomic"]
CORPORA = ["base", "scaled"]

# Verbatim from releases/mcp-servers.yaml.
OFFICIAL_STORE_DESC = ("Index a Kubernetes manifest or a note for later semantic search. Pass "
    "the full text as `information` and put path, kind, name and namespace "
    "in `metadata` so a hit can be traced back to its source.")
OFFICIAL_FIND_DESC = ("Semantic search over what qdrant-store has indexed: Kubernetes "
    "manifests, OpenTofu, scripts and docs. Use it for questions about the "
    "content of an object -- what it configures, which file does X, where "
    "something is set. Returns the stored text with its metadata, best "
    "match first.")


def arms(corpus):
    """The three arms, each writing to its own collection per corpus."""
    sfx = "" if corpus == "base" else f"-{corpus}"
    return {
        # Toolset B: the official server as releases/mcp-servers.yaml configures it.
        "official-minilm": {
            "cmd": OFFICIAL_SERVER, "store": "qdrant-store", "find": "qdrant-find",
            "collection": f"abox-minilm{sfx}",
            "env": {"QDRANT_URL": QDRANT_URL, "COLLECTION_NAME": f"abox-minilm{sfx}", "EMBEDDING_PROVIDER": "fastembed",
                    "EMBEDDING_MODEL": MINILM, "FASTEMBED_CACHE_PATH": FASTEMBED_CACHE, "QDRANT_SEARCH_LIMIT": "5",
                    "TOOL_STORE_DESCRIPTION": OFFICIAL_STORE_DESC, "TOOL_FIND_DESCRIPTION": OFFICIAL_FIND_DESC},
        },
        # Toolset A on the same model through the same fastembed weights (see
        # embed_shim.py): against official-minilm the only variable is the
        # toolset. MiniLM takes no instruction prefix. 450 chars is fastembed's
        # 128-token window less [CLS]/[SEP], at the 3.86 chars/token measured on
        # this corpus, less a margin -- the derivation mcp-servers.yaml uses for
        # nomic's 3500.
        "go-minilm": {
            "cmd": GO_SERVER, "store": "vector_store", "find": "vector_find",
            "collection": f"abox-minilm-go{sfx}",
            "env": {"QDRANT_URL": QDRANT_URL, "QDRANT_COLLECTION": f"abox-minilm-go{sfx}", "EMBEDDINGS_BASE_URL": SHIM_URL,
                    "EMBEDDINGS_MODEL": MINILM, "EMBEDDINGS_DOCUMENT_PREFIX": "", "EMBEDDINGS_QUERY_PREFIX": "",
                    "EMBEDDING_MAX_INPUT_CHARS": "450"},
        },
        # Toolset A as shipped: nomic-embed-text-v1.5, 3500-char chunks, nomic's
        # search_document:/search_query: prefixes (the server's defaults).
        "go-nomic": {
            "cmd": GO_SERVER, "store": "vector_store", "find": "vector_find",
            "collection": f"abox-nomic{sfx}",
            "env": {"QDRANT_URL": QDRANT_URL, "QDRANT_COLLECTION": f"abox-nomic{sfx}", "EMBEDDINGS_BASE_URL": SHIM_URL,
                    "EMBEDDINGS_MODEL": NOMIC, "EMBEDDING_MAX_INPUT_CHARS": "3500"},
        },
    }


def server_env(arm_cfg):
    return {"PATH": os.environ["PATH"], "HOME": os.environ["HOME"], "HF_HUB_OFFLINE": "1", **arm_cfg["env"]}


def corpus_path(corpus):
    return WORK / ("corpus.json" if corpus == "base" else f"corpus_{corpus}.json")


def load_json(path):
    return json.loads(Path(path).read_text())


def dump_json(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False))


def questions():
    return load_json(HERE / "questions.json")
