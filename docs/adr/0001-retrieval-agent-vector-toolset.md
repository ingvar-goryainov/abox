---
status: Proposed
owner: "Ihor Pysmennyi"
reviewers: []
updated_at: "2026-09-27"
---

# 0001 — Keep our qdrant-mcp over nomic-embed as the retrieval agent's vector toolset

- **Status:** Proposed
- **Date:** 2026-09-27
- **Deciders:** abox maintainers

## Context

`releases/agent-retrieval.yaml` runs two retrieval agents with the same prompt, the
same model and the same graph, differing only in the vector toolset:

- `retrieval-agent`: our Go `qdrant-mcp` (`mcp/qdrant-mcp`), which embeds through the
  cluster's OpenAI-compatible endpoint with nomic-embed-text-v1.5 and chunks long text.
- `retrieval-agent-minilm`: the official `mcp-server-qdrant` 0.8.1, which runs
  all-MiniLM-L6-v2 in-pod through fastembed and stores one vector per text.

The pair was set up to answer one question: should the retrieval agent keep our
server or use the default Qdrant MCP? This ADR records the answer and the
evaluation behind it. [docs/retrieval-toolsets.md](../retrieval-toolsets.md)
shows the setup and how to switch between the two by hand.

## Decision drivers

- **Answer quality on what this repo's manifests actually contain.** Most of the
  rationale lives in comments deep inside long objects, not in the first lines.
- **Robustness as the index grows.** The collection only gets bigger as more objects
  are ingested.
- **Agent context cost.** Every find result is read by the model, on every question,
  and the worst case matters as much as the typical one.
- **Reuse of existing infrastructure.** The cluster already serves embeddings; a
  model inside the MCP pod is a second copy of that capability.

## Considered options

1. **Go qdrant-mcp + nomic-embed-text-v1.5**: the shipped `retrieval-agent`, with 3500-char chunks.
2. **Go qdrant-mcp + all-MiniLM-L6-v2**: our toolset on the official server's default model.
3. **Official mcp-server-qdrant + all-MiniLM-L6-v2**: the default Qdrant MCP, configured as in `releases/mcp-servers.yaml`.

Option 2 is not deployable today, because nothing in the cluster serves MiniLM over
`/v1/embeddings`. It is included because it isolates the toolset: options 2 and 3
write byte-identical MiniLM vectors, so any difference between them comes from the
toolset alone.

## Decision outcome

**Chosen: option 1, and stop it sending each result twice (follow-up 1).**

The results below come from gemini-3.5-flash, the model the cluster runs, on Google
ADK, the framework kagent's agent runtime is built on.

- **Accuracy.** Option 1 answered 30/30 on the base corpus and 27/30 on a corpus
  3.7× larger. The default Qdrant MCP answered 30/30 and 24/30.
- **Retrieval.** Option 1 is the only option that put the answer text in front of
  the agent on every question at both sizes (evidence@5 100%).
- **Worst-case cost.** Option 1's most expensive question took 40k input tokens. The
  default server's took 501k, and it passed 50k on 8 of 32 questions at scale.

Option 1 has one cost problem to fix. Under ADK its typical question costs more than
the default server's: a median of 14.9k input tokens against 10.7k. The reason is that
ADK hands the model both copies of every result our server returns. Removing the
duplicate is therefore part of adopting this option, not an optional follow-up.

## Evaluation

### At a glance

| default (official + MiniLM) against custom (ours + nomic) | default | custom |
|---|---|---|
| share of each manifest actually embedded | 25% | 100% |
| correct answers, 51 objects | 30/30 | 30/30 |
| correct answers, 187 objects | 24/30 | 27/30 |
| answer text reached the agent, 187 objects | 80% | 100% |
| heaviest question, input tokens | 501k | 40k |
| typical question, median input tokens (187 objects) | 10.7k | 14.9k, until follow-up 1 |

The setup diagram, and how to switch toolsets and models by hand, are in
[docs/retrieval-toolsets.md](../retrieval-toolsets.md).

### How it was measured

The run was local, with components matching the cluster: Qdrant 1.19.1, the
official server at 0.8.1 with the env from `releases/mcp-servers.yaml`, and ours
built at `4de8aa2`. Two corpora were used:

- **base:** the 51 objects in `releases/` and `bootstrap/`, as authored.
- **scaled:** 187 objects, adding the other branches' manifests and what the pinned
  charts render.

There were 32 questions. 23 of the 30 answerable ones have their answer past
MiniLM's first 128 tokens, which reflects this repo: the "why" sits in comments
further down.

Two layers were measured. The first is retrieval alone: the prompt's two mandated
queries, with no model involved. The second is an agent per question on
gemini-3.5-flash in Google ADK, the framework kagent's runtime is built on, with
`retrieval-agent`'s prompt and the arm's find tool as its only tool. That makes 192
agent runs, each graded against the required facts and audited by hand where they
failed.

The full method, the questions and the raw results are in
[evals/retrieval/](../../evals/retrieval/README.md).

### Finding 1: the default Qdrant MCP embeds a quarter of each manifest

fastembed's all-MiniLM-L6-v2 truncates at **128 tokens**, not the 256 that
sentence-transformers uses for this model. Qdrant's ONNX export sets `max_length: 128`
in `tokenizer_config.json`, and fastembed takes the stricter of that and
`model_max_length`. Two texts that differ only after token 128 embed to identical
vectors. The official server has no setting for this, and it does not chunk.

| | points (base / scaled) | corpus inside an embedded window |
|---|---|---|
| official + MiniLM | 51 / 187 | **24.9%** / 21.7% |
| Go + MiniLM | 284 / 1,270 | 99.9% / 99.7% |
| Go + nomic | 58 / 223 | 100% / 100% |

26 of the 51 base objects are longer than 128 tokens; the median is 131 and the
longest is 2,101. The comment in `releases/agent-retrieval.yaml` said 256 and is
corrected in this change.

### Finding 2: returning whole manifests hides the truncation, until the corpus grows

The official server returns each hit's full stored text, so the agent sees the whole
manifest even though only its head was embedded. On 51 objects, 5 hits × 2 queries
covers so much of the corpus that the answer text almost always reaches the agent
anyway. At 187 objects it no longer does:

| retrieval, both queries | evidence@5 base | evidence@5 scaled | MRR base | MRR scaled | hit@5, question as asked (scaled) |
|---|---|---|---|---|---|
| official + MiniLM | 100% | **80.0%** | 0.812 | **0.621** | 50.0% |
| Go + MiniLM | 93.3% | 83.3% | 0.928 | 0.858 | 83.3% |
| Go + nomic | 100% | **100%** | 0.967 | 0.961 | 83.3% |

evidence@5 means some returned text contains the answer's evidence string. MRR uses
the better of the two queries.

The agent layer follows the retrieval layer:

| agentic | correct, base | correct, scaled | deep answers correct, scaled | evidence reached the agent, scaled |
|---|---|---|---|---|
| official + MiniLM | 30/30 | **24/30** | 78.3% | 80.0% |
| Go + MiniLM | 28/30 | 28/30 | 95.7% | 83.3% |
| Go + nomic | **30/30** | 27/30 | 91.3% | 90.0% |

- On the 7 questions answered in the first 128 tokens, all three arms score the
  same: 7/7 on base and 6/7 on scaled. The official server's losses are all on deep
  answers.
- Options 1 and 2 are within one question of each other. That is noise, and
  option 2 used more searches to get there (Finding 3).
- All 12 no-answer runs abstained correctly: every arm, both corpora.
- There were 13 non-correct answers:

  | kind | count | cases |
  |---|---|---|
  | ambiguous question | 3 | q20 (below) |
  | honest miss or stated gap | 3 | |
  | no answer (hit the 12-call cap) | 2 | both official |
  | inferred instead of retrieved | 1 | official q13 |
  | contains a false claim | 1 | Go + MiniLM, base q14: "no memory request is specified", though `128Mi` is |
  | confidently wrong | 3 | official q10, Go + nomic q10, Go + nomic q12 |

- The confidently wrong answers:
  - **q10, on both arms that got it wrong.** The deep rationale in
    `HelmRelease/llm-d-embedding` (vLLM's CPU backend crashes on the first forward
    pass) was never retrieved. The agents answered "resource efficiency" instead,
    quoting the standalone llama.cpp Deployment's comments.
  - **q12 on Go + nomic.** It misread the llm-d-pool comment, because the HTTPRoute
    that holds the real reason was not retrieved.
- q20 ("which LLM do the agents use") became ambiguous in the scaled corpus, because
  the triage branch's agentgateway-llm is a second valid answer. All three arms
  answered from it and scored partial.

### Finding 3: the default server's cost has a long tail

| scaled, gemini-3.5-flash | find calls / q | runs over the 3-call budget | runs over 50k input tokens | input tokens median | mean | max |
|---|---|---|---|---|---|---|
| official + MiniLM | 4.41 | 9/32 | 8/32 | 10.7k | **55.0k** | **501k** |
| Go + MiniLM | 2.81 | 5/32 | 3/32 | 7.4k | 16.6k | 94k |
| Go + nomic | 2.09 | **0/32** | **0/32** | 14.9k | 16.9k | 40k |

- **Gemini keeps searching when the answer isn't surfacing.** On the official server
  each extra search returns five more whole manifests, so the cost compounds:
  - u04 ran 24 searches and 501k tokens without answering. Its first attempt hit the
    cap too.
  - n02 spent 327k tokens before abstaining.
  - q23 spent 290k before answering correctly.
- **The same persistence buys part of the official server's 24/30.** Three of its
  correct answers at scale (q06, q17, q23) took 8 to 12 searches each.
- **Per correct answer at scale,** option 1 used about 20k input tokens and the
  default server about 73k.
- **Whole manifests have no size cap.** The largest single official find response
  was 51k characters, and the scaled corpus excluded CRDs, which run to 100k+ each.
- **`qdrant-store` echoes each stored text back** as "Remembered: …", which is 67k
  characters over the 65k-character base ingest. During agentic ingest, every
  manifest re-enters the model's context once more.

### Finding 4: chunking alone is not enough on a small window

On MiniLM, our toolset beats the official one at scale (28 against 24 correct), but
it loses answers of its own:

- **Identity loss.** A 450-char chunk carries no kind or name. The chunk holding
  neo4j's `memory: "2Gi"` never mentions neo4j, so it cannot rank for "Neo4j memory".
  The agent missed q04 on the base corpus.
- **Crowding.** Neighbouring chunks of one manifest share the five slots: only 2.98
  distinct objects per result on base and 3.42 on scaled, against 4.75–5.0 for the
  other arms.
- **Split blocks.** A chunk boundary cut the EPP's `resources` block, so the agent
  saw the CPU value but not the memory value. Gemini then asserted that no memory
  request was set.

nomic's 3500-char chunks rarely hit any of these.

### Finding 5: our toolset sends each result twice under ADK

`text()` in `mcp/qdrant-mcp/internal/tools/embeddings.go` returns the hits JSON
twice: as text `content`, and as `StructuredContent: Raw{Body: s}`, a string inside
JSON. ADK passes the model the whole MCP result, `content` and `structuredContent`
both, so every hit reaches Gemini twice. Measured over every find call in the runs:

| share of each tool result that is the `structuredContent` copy | base | scaled |
|---|---|---|
| official + MiniLM | 0% | 0% |
| Go + MiniLM | **50%** | **50%** |
| Go + nomic | **50%** | **50%** |

The official server returns its list as `content` only. Half of everything our
server hands the model is therefore a repeat, and that is why option 1's median
question costs more than the default server's. kagent's runtime is built on ADK.
Whether its ADK version passes `structuredContent` the same way was not checked in
the cluster.

The copy is there for a reason. Every tool is registered as `MCPTool[_, Raw]`, so
the Go SDK declares an output schema of `{"body": string}` and always sends
`structuredContent`. Before [upstream PR #10](https://github.com/den-vasyliev/abox/pull/10)
that was `{"body": ""}` next to the full text, and kagent agents read the empty body
and reported an empty store ([#9](https://github.com/den-vasyliev/abox/issues/9)).

### Similarity scores do not detect "not stored"

On the scaled corpus, both no-answer questions scored a top hit of 0.610–0.648 on
nomic, against a minimum of 0.630 for answerable ones. On MiniLM, answerable top
hits went as low as 0.213. No threshold separates them. The prompt's abstention rule
is what worked: 12/12 runs.

## Consequences

**Positive**

- Answers deep in a manifest stay reachable as the index grows. The prompt's
  two-search rule becomes a safety margin rather than the only way to reach them.
- Cost per question stays bounded: no run went past 40k input tokens or broke the
  3-search budget.
- No model inside the MCP pod. Vectors come from the embeddings endpoint the cluster
  already runs. Running nomic in-pod is what OOMKilled the official server at 2Gi.

**Negative**

- Until follow-up 1 lands, a typical question costs about 40% more input tokens than
  on the default server under ADK (median 14.9k against 10.7k).
- Retrieval depends on the embeddings Deployment being up, a second moving part
  that fastembed's in-pod model does not have.
- Ingest is slower: 15.4 s against 1.2 s for the 51 base objects on the laptop CPU
  used here. On the cluster the llama.cpp endpoint sets that rate.
- We own `qdrant-mcp`: its chunking, its output format and its upgrades.
- Confident wrong answers are not eliminated. Option 1 gave 2 of the 3, both on
  rationale that sits in one object while a similar-sounding rationale sits in
  another.

**Neutral**

- `retrieval-agent-minilm` and `qdrant-mcp-official` are not adopted. They can stay
  as the baseline for `evals/retrieval`, or be removed; nothing else depends on them.
  As shipped, their image tag is still the `0.8.1-<sha>` placeholder.
- Moving `EMBEDDINGS_BASE_URL` between llama.cpp and llm-d remains a re-embed, as
  `mcp/qdrant-mcp/README.md` describes. This decision does not change that.

### Follow-ups

1. **Part of this decision.** `qdrant-mcp` should send each result once. Leaving
   `StructuredContent` unfilled is not the fix: with the output schema still
   declared, the SDK sends `{"body": ""}` and brings back #9. Register the tools
   without an output schema instead, so a result is `content` only, as the
   official server's is. Then check both that #9's `tools/call` repro still
   returns the hits and, by re-running `evals/retrieval`, that the median cost
   drops (Finding 5).
2. `qdrant-mcp`: group `vector_find` hits by the `doc` payload field, so five hits
   are five objects (Finding 4, crowding).
3. `qdrant-mcp`: embed each chunk with a kind/name header, so a chunk keeps its
   object's identity (Finding 4, identity loss).
4. Re-run the harness on the in-cluster ingest shape. `kubectl get -o yaml` output
   has no comments and carries status, which makes objects longer and removes most
   of the "why".

## Threats to validity

- **Agent runtime.** ADK on gemini-3.5-flash reproduces kagent's model and agent
  framework, not kagent itself. Its ADK version, the kmcp streamable-HTTP adapter
  (stdio here) and its session handling were not reproduced.
- **One model, one run per question and arm.** A difference of one or two questions
  is noise, and the scaled accuracy gap between the default server and option 1 is
  3 questions (24 vs 27). On its own that would be weak evidence. What carries it is
  that every answer the default server lost was deep, and that the deterministic
  layer, which involves no model, shows 6 evidence misses against 0. The cost tail
  (8/32 runs over 50k tokens against 0/32) is not close.
- **Capped runs.** Two official runs hit the 12-call cap and are scored as no
  answer. Their transcripts on disk are re-runs kept for their queries: q01's re-run
  abstained after 6 searches, and u04's hit the cap again. Scoring the first
  attempt keeps every arm at one attempt per question. The first attempts' token
  counts were not recorded, so the official arm's token figures are lower bounds.
- **nomic runtime.** nomic ran as fastembed ONNX f32, not the cluster's llama.cpp
  GGUF. The vectors are close but not identical, and this difference was not
  measured.
- **Question authorship.** The evaluator wrote the questions from the corpus. Their
  depth is measured and head-only results are reported separately; the three arms
  are equal there.
- **Ingest and data shape.** Scripted ingest of authored manifests, not the agentic
  k8s-agent path over live objects.
- **Scale.** Two corpus sizes give a trend, not a curve.
- **Chunk size.** 450 chars for Go + MiniLM was derived from the measured 3.86
  chars/token, not tuned.
- **Prompt example.** The prompt's worked example is q01's keyword query. It is the
  same for every arm.

## Links

- Setup diagram and switching walkthrough: [docs/retrieval-toolsets.md](../retrieval-toolsets.md)
- Harness, method, questions and raw results: [evals/retrieval/](../../evals/retrieval/README.md)
  - [retrieval, base](../../evals/retrieval/results/retrieval_base.txt) · [retrieval, scaled](../../evals/retrieval/results/retrieval_scaled.txt)
  - [agentic, base](../../evals/retrieval/results/agentic_base.txt) · [agentic, scaled](../../evals/retrieval/results/agentic_scaled.txt), per question
- The two agents: [releases/agent-retrieval.yaml](../../releases/agent-retrieval.yaml)
- The two servers: [releases/mcp-servers.yaml](../../releases/mcp-servers.yaml), [mcp/qdrant-mcp/README.md](../../mcp/qdrant-mcp/README.md)
