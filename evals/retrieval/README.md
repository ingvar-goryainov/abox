# Retrieval eval: vector toolsets for the retrieval agent

The harness behind [ADR 0001](../../docs/adr/0001-retrieval-agent-vector-toolset.md).
It indexes this repo's manifests through each vector toolset's own MCP store
tool and asks the same 32 questions two ways: the retrieval layer alone, then
through an LLM agent that has only that toolset's find tool. The same comparison
by hand, in the cluster, is [docs/retrieval-toolsets.md](../../docs/retrieval-toolsets.md).

| arm | server | model | chunking |
|---|---|---|---|
| `official-minilm` | `mcp-server-qdrant==0.8.1`, configured as in `releases/mcp-servers.yaml` | all-MiniLM-L6-v2 (fastembed) | none: one vector per object |
| `go-minilm` | `mcp/qdrant-mcp` | all-MiniLM-L6-v2, **same fastembed weights** | 450 chars |
| `go-nomic` | `mcp/qdrant-mcp`, as shipped | nomic-embed-text-v1.5 | 3500 chars |

`embed_shim.py` serves `/v1/embeddings` from fastembed, so the two MiniLM arms
write identical vectors (cos = 1.000000 on the same text). Between them the
only variable is the toolset.

## Method

**Components.** Everything runs locally and matches the cluster wherever it can:

- **Qdrant 1.19.1**, as in `releases/qdrant.yaml`.
- **The official server** from PyPI `mcp-server-qdrant==0.8.1`, with the env from
  `releases/mcp-servers.yaml` verbatim: collection, `QDRANT_SEARCH_LIMIT=5` and both
  tool descriptions.
- **Ours** built from `mcp/qdrant-mcp`.
- **nomic** runs in the shim as fastembed ONNX f32 at a 2048-token window, where
  the cluster runs llama.cpp GGUF.

**Ingest** goes through each server's own store tool over MCP stdio: one call per
Kubernetes object, with `kind`, `name`, `namespace` and `path` as metadata.

**Corpora.** One document per object, as authored, comments included:

| corpus | objects | chars | contents |
|---|---|---|---|
| base | 51 | 65,235 | every object in `releases/` and `bootstrap/flux-instance.yaml` |
| scaled | 187 | 301,363 | base + 37 objects from the other branches + 99 from `helm template` of the 8 pinned charts with their HelmRelease values (CRDs excluded) |

The scaled corpus adds only objects whose kind and name differ from every base
object, so each question keeps exactly the targets it was written for.

**Questions.** 32: 26 in English, 4 in Ukrainian and 2 with no answer in the
corpus. Each answerable question names its target objects, a verbatim evidence
string and the facts a correct answer must contain. `corpus.py --check` computes
each question's depth from token offsets: "head" if the evidence ends inside
MiniLM's 128-token window, "deep" otherwise. 23 of the 30 are deep.

**Retrieval layer.** `harness.py find` runs the two queries the retrieval prompt
mandates, both fixed per question: the question as asked, then an English kind +
name + key-term query. No model is involved.

**Agentic layer.** `agent_run.py` gives each question to a fresh agent. It uses
`retrieval-agent`'s Retrieve section verbatim minus the graph lines, has the arm's
find tool as its only tool, and never sees the ground truth. `grade.py` scores the
answer against the required facts, and records two more things:

- whether the evidence reached the agent in any tool result, which separates a
  retrieval miss from a reading miss;
- any numbers in the answer that no tool result contains, as a hallucination screen.

Every non-correct answer was read by hand, as was every correct answer whose
evidence never reached the agent. Verdicts changed by hand are in
`overrides.json`, each with its reason. A run that hits the 12-model-call cap
counts as no answer, and is scored on its first attempt.

## Running it

Needs Python 3.12, Go, `helm` and a Qdrant 1.19.1 on `:6333`. The agentic step
needs `GOOGLE_API_KEY`, read from the repo's `.env` like `make run` does.

```bash
cd evals/retrieval
python3.12 -m venv .work/venv && .work/venv/bin/pip install mcp-server-qdrant==0.8.1 pyyaml
# ADK wants mcp 2.x, the official server pins 1.x: a venv of its own.
python3.12 -m venv .work/venv-adk && .work/venv-adk/bin/pip install google-adk mcp
go build -o .work/bin/qdrant-mcp ../../mcp/qdrant-mcp/cmd/server
docker run -d -p 6333:6333 qdrant/qdrant:v1.19.1
.work/venv/bin/python embed_shim.py &            # downloads MiniLM + nomic once

PY=.work/venv/bin/python ADK=.work/venv-adk/bin/python
export EVAL_OFFICIAL_SERVER=$PWD/.work/venv/bin/mcp-server-qdrant
$PY corpus.py --scaled --check                   # corpora + question sanity
for c in base scaled; do
  $PY harness.py ingest $c && $PY harness.py find $c && $PY metrics.py $c
  $ADK agent_run.py $c && $PY grade.py $c --detail
done
```

`agent_run.py` runs 96 agents per corpus, six at a time, on `gemini-3.5-flash`
(as in `releases/model-configs.yaml`) through Google ADK's `LlmAgent` and
`McpToolset`, the framework kagent's runtime builds on. It retries on 429/503,
stops an agent at 12 model calls and records that as no answer, and skips any
run already on disk. Transcripts go to `.work/agent_runs/`.

| env | default | |
|---|---|---|
| `EVAL_WORK` | `.work` | corpora, collections' outputs, agent transcripts |
| `EVAL_QDRANT_URL` | `http://127.0.0.1:6333` | |
| `EVAL_SHIM_URL` | `http://127.0.0.1:8091` | |
| `EVAL_GO_SERVER` | `.work/bin/qdrant-mcp` | |
| `EVAL_OFFICIAL_SERVER` | the venv's `mcp-server-qdrant` | |
| `EVAL_GEMINI_MODEL` | `gemini-3.5-flash` | the agent's model |
| `FASTEMBED_CACHE_PATH` | `.work/fastembed` | |

## Files

| file | |
|---|---|
| `corpus.py` | base corpus: every object in `releases/` and `bootstrap/`; scaled: plus other branches' manifests and `helm template` of the pinned charts |
| `questions.json` | 30 answerable questions with target objects, a verbatim evidence string and required facts; 2 with no answer in the corpus |
| `harness.py` | ingest and fixed-query find over MCP stdio |
| `metrics.py` | hit@k, evidence@5, MRR, result shape, index coverage |
| `agent_run.py` | the agent: `retrieval-agent`'s Retrieve prompt and one find tool |
| `grade.py` | regex facts, evidence-seen, unbacked-number screen |
| `overrides.json` | hand-audited verdicts, each with its reason |
| `results/` | the outputs the ADR quotes |

The regenerated scaled corpus differs from the evaluated one only in the
random `PHOENIX_SECRET` the phoenix chart generates on each render.
