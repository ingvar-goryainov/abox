"""Agentic retrieval: one agent per (corpus, arm, question).

The agent runs on gemini-3.5-flash -- the model releases/model-configs.yaml pins
-- in Google ADK, the agent framework kagent's runtime is built on. It gets
retrieval-agent's Retrieve instructions from releases/agent-retrieval.yaml,
verbatim apart from the graph lines (the graph is a constant in the cluster and
is not wired up here), and exactly one tool: the arm's find tool. It never sees
the ground truth.

Needs google-adk and GOOGLE_API_KEY, read from the repo's .env if unset.

  python agent_run.py <base|scaled> [arm ...] [--only q01,q02] [--parallel 6]
"""
import argparse
import asyncio
import concurrent.futures as cf
import json
import os
import random
import time

from common import ARM_NAMES, REPO, WORK, arms, dump_json, questions, server_env

MODEL = os.environ.get("EVAL_GEMINI_MODEL", "gemini-3.5-flash")
# The prompt allows three searches; twelve model turns is far past any agent
# that is converging. Hitting it is recorded as no answer.
MAX_LLM_CALLS = 12

PROMPT = """You are a retrieval agent over a vector store in this cluster. Which product backs it is not your concern and can change; the tool is the contract.

- A vector store, via {find}. Free text in, semantic search out. The collection is chosen by the server, not by you.

## Retrieve

Always search twice before answering, in the same turn. First call {find} with the user's question as the query, in the user's language. Then call {find} again with a keyword query in English: the kind of object likely to hold the answer, the name the question mentions, and the key term it asks about -- for "Why does kagent need a postRenderer?" that is "HelmRelease kagent postRenderers". The two find different things. A manifest may be stored as a single vector whose beginning is all the embedding model reads, so a question about a field deep inside it matches poorly while the kind and the name match the top. Read every text both calls returned; the best match is first but not always the right one. If neither holds the key term, one more reworded call is allowed. Do not offer to search again, and do not reason from a text that lacks the term -- answer from a text that has it, or say nothing relevant is stored.

Retrieval reads what is already stored. Do not fetch manifests, do not delegate to another agent, and do not write. If the collection is missing something, say so and stop.

Answer from what you retrieved and nothing else. Quote the relevant lines and cite each fact with the source metadata -- kind, name, namespace -- of the hit it came from. Report a similarity score only when the tool returned one; never invent or estimate one. Never present a guess as retrieved."""


async def _run(corpus, arm, q):
    from google.adk.agents import LlmAgent
    from google.adk.agents.invocation_context import LlmCallsLimitExceededError
    from google.adk.agents.run_config import RunConfig
    from google.adk.runners import InMemoryRunner
    from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
    from google.genai import types
    from mcp import StdioServerParameters

    a = arms(corpus)[arm]
    # 120s, as both MCPServers set spec.timeout.
    toolset = McpToolset(connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(command=a["cmd"], args=[], env=server_env(a)), timeout=120),
        tool_filter=[a["find"]])
    agent = LlmAgent(name="retrieval_agent", model=MODEL, instruction=PROMPT.format(find=a["find"]), tools=[toolset])
    runner = InMemoryRunner(agent=agent, app_name="eval")
    session = await runner.session_service.create_session(app_name="eval", user_id="eval")
    calls, answer, usage, visible = {}, [], [], sorted(t.name for t in await toolset.get_tools())
    stopped = None
    try:
        async for ev in runner.run_async(user_id="eval", session_id=session.id,
                                         new_message=types.Content(role="user", parts=[types.Part(text=q["q"])]),
                                         run_config=RunConfig(max_llm_calls=MAX_LLM_CALLS)):
            if ev.usage_metadata:
                usage.append(ev.usage_metadata.model_dump(exclude_none=True))
            for p in (ev.content.parts or []) if ev.content else []:
                if p.function_call:
                    calls[p.function_call.id] = {"id": p.function_call.id, "name": p.function_call.name,
                                                 "input": dict(p.function_call.args or {}), "result": None}
                elif p.function_response:
                    # What the model is handed: ADK passes the whole dumped
                    # CallToolResult, content and structuredContent both.
                    text = json.dumps(p.function_response.response, ensure_ascii=False)
                    if p.function_response.id in calls:
                        calls[p.function_response.id]["result"] = {"chars": len(text), "text": text,
                                                                   "is_error": bool((p.function_response.response or {}).get("isError"))}
                elif p.text and not p.thought and ev.is_final_response():
                    answer.append(p.text)
    except LlmCallsLimitExceededError:
        # The agent kept searching and never answered: an outcome, not an
        # error. Keep the transcript so far; it grades as no answer.
        stopped = f"llm_calls_limit_{MAX_LLM_CALLS}"
    finally:
        await toolset.close()
    total = lambda k: sum(u.get(k) or 0 for u in usage)
    return {"answer": "".join(answer) or None, "stopped": stopped, "calls": list(calls.values()), "tools_visible": visible,
            "usage": {"input_tokens": total("prompt_token_count"), "output_tokens": total("candidates_token_count"),
                      "thoughts_tokens": total("thoughts_token_count"), "llm_calls": len(usage)}}


def run_one(corpus, arm, q, out_path):
    from google.genai import errors
    for attempt in range(6):
        t0 = time.time()
        try:
            rec = asyncio.run(_run(corpus, arm, q))
            break
        except errors.APIError as e:
            # Rate limits and overload: back off and rerun the whole question.
            if e.code not in (429, 500, 503) or attempt == 5:
                raise
            time.sleep(min(90, 5 * 2 ** attempt) + random.random() * 3)
    dump_json({"corpus": corpus, "arm": arm, "id": q["id"], "question": q["q"], "model": MODEL,
               "runtime": "google-adk", "wall_seconds": time.time() - t0, "attempts": attempt + 1,
               "num_turns": rec["usage"]["llm_calls"], **rec}, out_path)
    return "ok" if rec["answer"] else "NO ANSWER"


def load_dotenv():
    """GOOGLE_API_KEY from the repo's .env, the file bootstrap/secrets.tf reads."""
    env = REPO / ".env"
    if os.environ.get("GOOGLE_API_KEY") or not env.exists():
        return
    for line in env.read_text().splitlines():
        k, sep, v = line.strip().partition("=")
        if sep and k and not k.startswith("#"):
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", choices=["base", "scaled"])
    ap.add_argument("arms", nargs="*", default=ARM_NAMES)
    ap.add_argument("--only")
    ap.add_argument("--parallel", type=int, default=6)
    a = ap.parse_args()
    load_dotenv()
    qs = questions()
    if a.only:
        qs = [q for q in qs if q["id"] in set(a.only.split(","))]
    jobs = []
    for arm in a.arms:
        outdir = WORK / "agent_runs" / a.corpus / arm
        outdir.mkdir(parents=True, exist_ok=True)
        jobs += [(a.corpus, arm, q, outdir / f"{q['id']}.json") for q in qs]

    def one(corpus, arm, q, out_path):
        if out_path.exists():
            return out_path, "cached"
        try:
            return out_path, run_one(corpus, arm, q, out_path)
        except Exception as e:  # one failed question must not sink the batch
            return out_path, f"FAILED {type(e).__name__}: {str(e)[:200]}"

    with cf.ThreadPoolExecutor(a.parallel) as ex:
        for f in cf.as_completed([ex.submit(one, *j) for j in jobs]):
            path, status = f.result()
            print(status, path.relative_to(WORK), flush=True)


if __name__ == "__main__":
    main()
