# Requirements Document

## Introduction

On branch `feat/otel-demo`, abox runs MLflow, Phoenix and an OpenTelemetry (OTel) Collector, but no two backends see the same spans:

- triage-core and the Astronomy Shop send only to MLflow, through the bridge collector.
- Phoenix receives only agentgateway-llm's proxy spans, and that gateway gets no traffic.
- No OTel-native trace UI exists.
- kagent and retrieval-agent emit no spans.

The feature has three goals:

1. Fan one span stream out to three backends: Jaeger v2 (standard OTel), MLflow and Phoenix.
2. Drive the stream with real agent loops plus a volume baseline.
3. Write `OBSERVABILITY.md`, a comparison of the three backends from a GenAI perspective.

The user's three-part assignment maps onto the plan's Definition of Done (DoD) and onto Requirements 1 to 3:

| Assignment part | DoD | Requirement |
|---|---|---|
| Familiarize yourself with the interfaces of OTel, MLflow and Phoenix. | DoD 1 | 1 |
| Obtain traces from the Astronomy Shop agent, your own retrieval/voice agent, or any of the kagents. | DoD 2 | 2 |
| Compare the three observability solutions (standard OTel, MLflow and Phoenix) from a GenAI perspective. | DoD 3 | 3 |

Requirements 4 to 11 carry the plan's guardrails: Cluster access, git and release hygiene, consent, exposure and secrets, evidence and cleanup, pinning, the committed spec copies, and the Phase 0 reconciliation of the root docs with the checked-in manifests.

Source of truth: this spec. The canonical copy lives under `docs/specs/genai-observability-comparison/`, and every exact decision lives in that copy's `requirements.md`, `design.md` and `tasks.md`. The spec carries over the user-approved implementation plan v2 and the plan's DoD, plus the user's clarify answers on kagent exposure, on the spec copies and on the source of truth, and the reviewer roadmap and exit criteria of the Spec_Readme, which the user adopted in full. The plan's scratch file stays out of git, and nothing in this spec depends on that file (criterion 10.12).

### Scope

In scope:

- Phase 0 (Requirement 11): reconciling README.md, CODEBASE.md, REVIEW.md and EVALS.md with the checked-in manifests, committed before Phase A and before any Exercise_Config change. Jaeger's README row and the observed Phoenix app version still come in Task 12 (criteria 3.2 and 3.3).
- Tasks 0 to 12 and DoD sections 1 to 3, carried over from the approved plan unchanged in substance.
- The Kagent_Exposure_Gate: a read-only check in Task 0b, then a User decision in Phase B, before `flux suspend` or any other write to the Cluster. A chosen restriction is the first consented write after the suspend, and is re-probed and live before Task 1's apply.
- Committing the spec's canonical copy under `docs/specs/genai-observability-comparison/` with the landing page `docs/README.md`, and keeping the mirror under `.kiro/specs/genai-observability-comparison/` in sync.

Out of scope:

- The optional extras the user left unanswered: Astronomy agent MCP mode, a real LLM for the Astronomy agent, and chart version bumps.
- Task 9 (the agentgateway-llm route), unless the User accepts Task 9 at Task 7's decision point.
- Porting the custom `k8s-agent` from `feat/llmd-embeddings`.
- Instrumenting `mcp/qdrant-mcp`. If the User picks that option at Task 7, the work becomes new scope and needs a spec update first.

### Repo facts and deltas

- README.md, CODEBASE.md, REVIEW.md and EVALS.md warn that the RSIP sorts tags lexicographically, or cap the patch version at 9. `bootstrap/flux.tf` configures semver sorting, and `make push` bumps the patch with no ceiling, so that guidance is stale; Phase 0 corrects the docs (Requirement 11). The Release flow follows `bootstrap/flux.tf`, and `make push` stays unchanged.
- `make push` tags HEAD and pushes `main` plus the new tag. The feature branch needs a separate push.
- REVIEW.md suggests an HTTPRoute for every UI. Jaeger, MLflow and Phoenix get no HTTPRoute (Requirement 7).
- The header of `releases/mlflow-otel-collector.yaml` says "only these two sources exist today". Tasks 3, 4 and 8 rewrite that header.
- In `releases/kustomization.yaml`, `jaeger.yaml` belongs between `graph-otel-demo.yaml` and `kagent.yaml`, and `model-configs.yaml` between `mlflow-otel-collector.yaml` and `neo4j.yaml`.
- Possible public exposure of kagent (repo facts; live reachability unverified):
  - HTTPRoute `kagent` in namespace `kagent` (`releases/kagent.yaml`) sends `/api` to `kagent-controller:8083` and `/` to `kagent-ui:8080`. The route has no hostnames and attaches to Gateway `agentgateway-external`. ReferenceGrant `kagent` sits in the same file.
  - Gateway `agentgateway-external` (`releases/agentgateway.yaml`) has one listener, `http` on port 80, with no hostname and `allowedRoutes.namespaces.from: All`.
  - AgentEndpoint `triageagent-ngrok-dev` (`releases/ngrok-operator.yaml`) publishes `https://triageagent.ngrok.dev` to `http://agentgateway-external.agentgateway-system:80`. The ngrok operator's auto-created free-domain endpoint may tunnel to the same Gateway.

### Reading the criteria

- Criterion n of Requirement m is cited as m.n.
- "DoD x.y" is row x.y of the DoD traceability table at the end of this document: checkbox y of DoD section x, stated in short form, with the criteria that carry the checkbox's exact content. "DoD Exit" is the table's row for the Reviewer_Exit_Criteria, which the Task 12 DoD walk checks.
- The tag at the end of each criterion names the phase that verifies the criterion (0, A to D, or "all phases" when the check recurs) and whether verification needs the Cluster (`cluster`) or not (`offline`).
- Values that still need confirmation on the Cluster, including values observed before execution, appear only as conditions, recorded findings or decision points, never as facts.

## Glossary

- **abox**: this repository, and the GitOps platform that the repository deploys.
- **Cluster**: the user's running abox Kubernetes cluster.
- **Workstation**: the arm64 Mac that holds this checkout. Phase 0 and Phase A run on the Workstation. The Workstation's kind 0.27.0 is never used: `scripts/setup.sh` installs kind v0.33.0, and `bootstrap/variables.tf` defaults the node image to `kindest/node:v1.37.0`.
- **Executor**: the agent that carries out this spec's tasks, on the Workstation and, from Phase B on, against the Cluster.
- **User**: the abox owner, who approved the plan and answers every Consent_Checkpoint.
- **Task N**: Task N of this spec (Tasks 0 to 12), carried over from the approved plan and detailed in `design.md` and `tasks.md`. Task 0 splits into 0a (Workstation preflight) and 0b (Cluster preflight).
- **Phase 0** (baseline docs reconciliation): Requirement 11. After the add commit of criterion 10.2, and before Phase A and any Exercise_Config change, the Executor reconciles the Root_Docs with the Baseline_Manifests and commits the result as `docs: …`. Offline; nothing is pushed or applied.
- **Phase A** (offline prep): the offline parts of Tasks 0a, 1 to 7 and 11: file changes, scripts, offline validation, local commits and the Decision_Log records, ending at the Phase_A_Review_Gate. Nothing is pushed or applied.
- **Phase B** (access checkpoint): getting Cluster access, the read-only Task 0b preflight, the single checkpoint message, the User's Kagent_Exposure_Gate decision, the consented `flux suspend`, and any restriction that the User chose at the gate (criteria 7.10 to 7.14).
- **Phase C** (on the Cluster): the on-cluster parts of Tasks 1 to 8 and 10, in that order. Task 9 runs only if the User accepts Task 9 at Task 7's decision point.
- **Phase D**: Task 11 (the Observability_Doc) and Task 12 (README.md and CODEBASE.md updates, the Root_Docs re-check, Release, DoD walk with the Reviewer_Exit_Criteria, cleanup).
- **Abox_Kubeconfig**: the Cluster's kubeconfig, kept in a separate file (for example `/tmp/abox-observability/abox.kubeconfig`), outside `~/.kube/config` and outside git.
- **Scratch_Dir**: `/tmp/abox-observability/`, outside git. Holds scripts, script output, pulled charts and raw evidence.
- **Backend**: one of the three compared trace stores: Jaeger, MLflow or Phoenix.
- **Jaeger**: HelmRelease `jaeger` in namespace `jaeger` (chart `jaeger` 4.14.0, image `jaegertracing/jaeger:2.21.0`), added by Task 1 as the Standard_OTel reference Backend.
- **MLflow**: the MLflow tracking server in namespace `mlflow`, Service `mlflow-mlflow` on port 5000 (`releases/mlflow.yaml`, chart 0.1.0).
- **Phoenix**: Arize Phoenix in namespace `phoenix` (`releases/phoenix.yaml`, chart `phoenix-helm` 12.0.14).
- **Bridge_Collector**: HelmRelease `otel-collector` in namespace `mlflow` (`releases/mlflow-otel-collector.yaml`; chart `opentelemetry-collector` 0.173.1; image `otel/opentelemetry-collector-contrib` 0.160.0), Service `otel-collector.mlflow.svc.cluster.local` on ports 4317 (OTLP/gRPC) and 4318 (OTLP/HTTP). The single fan-out point for every Source.
- **Demo_Collector**: the OTel Collector of chart `opentelemetry-demo` 0.41.2 in namespace `otel-demo`. Forwards traces to the Bridge_Collector through exporter `otlp_grpc/mlflow-bridge`.
- **Standard_OTel**: the OTel SDKs, the OTLP protocol, the OTel Collector and the OTel semantic conventions (semconv), with Jaeger v2 as the reference UI.
- **Tenant**: the per-Source bucket inside a Backend. In MLflow, an experiment selected by header `x-mlflow-experiment-id`. In Phoenix, a project selected by header `x-project-name` or by resource attribute `openinference.project.name`. Jaeger has no Tenants and groups traces by `service.name`. "Bucket" is a synonym.
- **Source**: a workload whose spans this spec collects:
  - **GenAI_Source**: retrieval-agent via kagent (primary), and the Astronomy Shop `agent` (second).
  - **Volume_Source**: the Astronomy Shop microservices under Locust load.
  - **Control_Source**: triage-core, which already sends to the Bridge_Collector. Control_Source evidence is useful but not required for done.
- **Golden_Probe**: `docs/observability/golden_probe.py`, with exact pins in `docs/observability/requirements.txt`. Sends one synthetic trace with known attributes directly to each Backend.
- **Golden_Trace**: the trace that the Golden_Probe sends.
- **Parity**: for one trace ID, every Backend resolves the trace, and each Backend's span count equals Jaeger's span count or the Observability_Doc explains the difference.
- **Observability_Doc**: `OBSERVABILITY.md` at the repo root.
- **Interface_Matrix**: the Observability_Doc's table of Backend interfaces (DoD 1).
- **Evidence_Dir**: `docs/observability/`. Holds the committed evidence and the Golden_Probe.
- **Exercise_Config**: this spec's GitOps changes under `releases/`: new `jaeger.yaml` and `model-configs.yaml`; edits to `mlflow-otel-collector.yaml`, `agent-retrieval.yaml`, `kagent.yaml` and `kustomization.yaml`; and `agentgateway-llm.yaml` only if Task 9 runs.
- **Exercise_Apply**: `kubectl apply --server-side --force-conflicts --field-manager=abox-exercise -f <manifest>`, run with explicit `--kubeconfig` and `--context`, where `<manifest>` holds changed or new Exercise_Config objects. Exercise_Apply targets Kubernetes manifests only; `kustomization.yaml` is a build file.
- **Consent_Checkpoint**: a message in which the Executor states what an action does, what could go wrong and whether the action is reversible, followed by a wait for the User's explicit yes.
- **Phase_A_Review_Gate**: the stop at the end of Phase A where the Executor asks the User to review the offline work, and waits for the User's explicit approval before Phase B (criterion 6.12).
- **Kagent_Exposure_Gate**: the read-only Task 0b check of whether kagent answers on the public ngrok endpoints, plus the User's decision, made in Phase B before `flux suspend` or any other write to the Cluster. The gate is resolved when the User explicitly accepts the risk, or when the chosen restriction, the first consented write after the suspend, is live and re-probed before Task 1's apply (criterion 7.13).
- **Fixed_Workload**: the recorded prompts and Locust parameters that produce the evidence traces.
- **Load_Run**: one Locust run with fixed users, spawn rate and duration, while every In_Scope_Exporter is live.
- **In_Scope_Exporter**: an exporter covered by the zero-failure check: the Bridge_Collector's `otlp_grpc/jaeger-v2`, every `otlp_http/mlflow-*`, and every `otlp_http/phoenix-*` or the fallback `otlp_grpc/phoenix`, plus the Demo_Collector's `otlp_grpc/mlflow-bridge`. The Demo_Collector's `otlp_grpc/jaeger`, `otlp_http/prometheus` and `opensearch` exporters are excluded, because those exporters deliberately point at removed backends and fail on every send.
- **GenAI_Inventory**: per GenAI_Source, a present-or-absent record of token usage; prompt and completion content; tool arguments and results; retrieval results; session or conversation ID; whether delegation to `k8s-agent` forms one trace or two; and MCP server-side spans (expected absent).
- **Secret_Scan**: a case-sensitive search of the named files for the markers `Bearer`, `AIza`, `sk-` and `API_KEY=`. The scan fails on a credential-shaped hit:
  - `Bearer`, one space, then 16 or more token characters;
  - `AIza` followed by 16 or more token characters;
  - `sk-` at the start of a word, followed by 16 or more token characters;
  - `API_KEY=` followed directly by a character other than whitespace, a quote, a backtick, `<` or `$`.

  Token characters are letters, digits, `.`, `_`, `~`, `+`, `/`, `=` and `-`. A marker named in prose, or followed by a `<placeholder>`, passes, because this spec and the docs name the markers.
- **Port_Map**: the local ports for `kubectl port-forward`: frontend-proxy 8080, kagent-ui 8081, kagent-controller 8083, Astronomy agent 8010, Jaeger UI 16686, Jaeger metrics 18888, MLflow 5000, Phoenix 6006 and Locust 8089. The Golden_Probe also forwards Jaeger OTLP on 4317 (gRPC) or 4318 (HTTP).
- **RSIP**: ResourceSetInputProvider `releases-image` in namespace `flux-system` (`bootstrap/flux.tf`). Polls the configured OCI repository (default `oci://ghcr.io/den-vasyliev/abox/releases-otel-demo`) for the highest semver tag matching `^\d+\.\d+\.\d+$`.
- **Release**: publishing `./releases` as an OCI artifact by pushing a `v*` git tag (workflow `.github/workflows/flux-push.yaml`, target `oci://ghcr.io/<github.repository>/releases-<branch>`), then letting Flux reconcile the artifact.
- **Root_Docs**: `README.md`, `CODEBASE.md`, `REVIEW.md` and `EVALS.md` at the repo root.
- **Baseline_Manifests**: the checked-in `releases/` and `bootstrap/` trees, plus `scripts/setup.sh` and the `Makefile`: the files whose facts the Root_Docs describe. Phase 0 changes none of them.
- **Known_Deviation**: a Baseline_Manifest fact that breaks a rule stated in the Root_Docs, kept as is because manifests stay unchanged, and recorded next to the rule (for example `ref.tag: latest` in `releases/graph-otel-demo.yaml` and `releases/pages-triage.yaml`).
- **Decision_Log**: the decision log section of the Canonical_Spec's `design.md`. Holds the Phoenix routing decision and the expected kagent trace identity, recorded in Phase A before any Cluster work and confirmed or corrected in Phase C (criteria 2.93 to 2.96).
- **Spec_Copies**: the two copies of this spec's `requirements.md`, `design.md` and `tasks.md`:
  - **Canonical_Spec**: `docs/specs/genai-observability-comparison/*.md`, the committed copy and the source of truth. Content edits land here first.
  - **Spec_Mirror**: `.kiro/specs/genai-observability-comparison/*.md`, the copy that the IDE reads and writes, left untracked. Task-status ticks made in the IDE land here first.
- **Spec_Sync**: copying one spec file from one of the Spec_Copies to the other with `cp`, then confirming with `cmp` that the pair is byte-identical. A content edit syncs from the Canonical_Spec to the Spec_Mirror right after the edit (criterion 10.13). The Spec_Mirror's `tasks.md`, which holds the task-status ticks made in the IDE, syncs back to the Canonical_Spec at each phase end, in that phase's sync commit (criteria 10.3 and 10.6).
- **Spec_Readme**: `docs/README.md`, the spec's landing page, committed with the Canonical_Spec. Holds a Status line, a "Read first" list of links to the Canonical_Spec files, a reviewer roadmap whose checkboxes belong to the User, and the Reviewer_Exit_Criteria.
- **Reviewer_Exit_Criteria**: the six conditions under which the User approves completion: the source-of-truth decision is recorded; the Root_Docs match the manifests; all required safety gates are resolved; all release objects are Ready; every required Source has a trace in all three Backends; and published conclusions are reproducible from sanitized evidence. Checked in the Task 12 DoD walk (criteria 5.18 to 5.20).

## Requirements

### Requirement 1: Interfaces (DoD 1)

**User Story:** As the abox owner, I want the Observability_Doc to show how each Backend ingests, buckets and returns spans, proven with one Golden_Trace, so that the Observability_Doc alone tells me how to send a span to each Backend, which Tenant the span lands in, and how to read the span back.

#### Acceptance Criteria

##### Interface_Matrix

1. THE Observability_Doc SHALL contain an Interface_Matrix with one column each for Jaeger (Standard_OTel), MLflow and Phoenix. (DoD 1.1) `[D offline]`
2. THE Interface_Matrix SHALL contain these rows (DoD 1.1) `[D offline]`:
   - ingest: protocol, port, path and encoding;
   - bucketing: how a span selects a Tenant, and what the Backend does when the Tenant header or attribute is missing;
   - native data model;
   - semantic conventions understood natively versus stored as plain attributes, including prompt content sent as attributes versus as span events;
   - read path: the UI plus one programmatic API;
   - storage and retention as deployed in abox;
   - auth, stating explicitly that none of the three Backends has auth as deployed;
   - GenAI features beyond tracing: evals, datasets, prompt management and feedback.
3. THE Interface_Matrix SHALL contain in every cell either a documentation URL for the deployed version, labelled "docs only" when the Cluster did not confirm the cell, or the text "observed in abox YYYY-MM-DD". (DoD 1.2) `[D offline]`
4. WHILE Phase A runs, THE Executor SHALL draft the Interface_Matrix from documentation in an untracked `OBSERVABILITY.md` at the repo root, citing one URL per cell and marking every cell "to verify in abox". `[A offline]`
5. WHEN the Observability_Doc is committed in Phase D, THE Interface_Matrix SHALL contain no "to verify in abox" mark. (DoD 1.2) `[D offline]`

##### Collector as built

6. THE Observability_Doc SHALL document the deployed Bridge_Collector: the `otlp` receiver; each routing row with the row's OTTL condition and target pipelines; the processors that the chart adds; and each exporter with the exporter's endpoint and Tenant header or attribute. (DoD 1.3) `[D cluster]`
7. THE Observability_Doc SHALL include a mermaid diagram of the collector topology that shows every receiver, routing row, pipeline and exporter of the deployed Bridge_Collector config, and no collector element that the deployed config lacks. (DoD 1.3) `[D cluster]`

##### Golden_Probe content

8. THE Golden_Probe SHALL send one Golden_Trace through one TracerProvider with three exporters, each aimed directly at one Backend's own ingest endpoint, bypassing the Bridge_Collector (DoD 1.4) `[C cluster]`:
   - Jaeger: OTLP/gRPC `localhost:4317`, or OTLP/HTTP `localhost:4318/v1/traces`;
   - MLflow: OTLP/HTTP `http://localhost:5000/v1/traces` with header `x-mlflow-experiment-id: <golden-probe experiment ID>`;
   - Phoenix: OTLP/HTTP `http://localhost:6006/v1/traces` with header `x-project-name: golden-probe`.
9. THE Golden_Probe SHALL set resource attribute `service.name` to `golden-probe` and emit a root span named `golden-probe` with no GenAI attributes. (DoD 1.4) `[A offline]`
10. THE Golden_Probe SHALL emit one child subtree per convention (`gen_ai.*`, OpenInference, MLflow-native), each with at least one LLM span and one tool span, plus one retrieval span in every convention that defines a retrieval span kind. (DoD 1.4) `[A offline]`
11. THE Golden_Probe SHALL set, in the `gen_ai.*` subtree, `gen_ai.operation.name` (`chat` on LLM spans, `execute_tool` on the tool span), `gen_ai.provider.name` plus the legacy `gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, and `gen_ai.input.messages` and `gen_ai.output.messages` as JSON attributes. (DoD 1.4) `[A offline]`
12. THE Golden_Probe SHALL add to the `gen_ai.*` subtree one sibling LLM span that carries the prompt and completion content as span events instead of attributes. (DoD 1.4) `[A offline]`
13. THE Golden_Probe SHALL set, on the `gen_ai.*` tool span, `gen_ai.tool.name`, `gen_ai.tool.call.id`, the tool arguments and the tool result. (DoD 1.4) `[A offline]`
14. THE Golden_Probe SHALL set, in the OpenInference subtree, `openinference.span.kind` (`LLM`, `TOOL`, `RETRIEVER`), `llm.model_name`, `llm.token_count.prompt`, `llm.token_count.completion`, `llm.token_count.total`, `input.value` and `output.value` with `input.mime_type` and `output.mime_type`, `llm.input_messages.N.message.role` and `.content`, `llm.output_messages.N.message.role` and `.content`, `tool.name`, `tool.parameters`, and `retrieval.documents.N.document.id`, `.content` and `.score`. (DoD 1.4) `[A offline]`
15. THE Golden_Probe SHALL set, in the MLflow-native subtree, `mlflow.spanType` (`LLM`, `TOOL`, `RETRIEVER`) plus `mlflow.spanInputs` and `mlflow.spanOutputs`, JSON-encoded as the MLflow documentation specifies. (DoD 1.4) `[A offline]`
16. THE Golden_Probe SHALL emit one bare child span with no GenAI attributes. (DoD 1.4) `[A offline]`
17. THE Golden_Probe SHALL print the Golden_Trace's trace ID as 32 lowercase hex characters. (DoD 1.4) `[A offline]`
18. WHERE the `--dry-run` flag is set, THE Golden_Probe SHALL export every span to the console only. `[A offline]`
19. WHERE the no-tenant option is set, THE Golden_Probe SHALL send one extra trace with no Tenant header. `[A offline]`
20. WHEN Phase A validates Task 2, THE Executor SHALL run the Golden_Probe with `--dry-run` in a uv venv built from `docs/observability/requirements.txt` and confirm that the printed span tree satisfies criteria 1.9 to 1.16. `[A offline]`

##### Golden_Probe on the Cluster

21. WHEN Phase C reaches Task 2, THE Executor SHALL create MLflow experiment `golden-probe` with `POST /api/2.0/mlflow/experiments/create` and pass the returned ID to the Golden_Probe at run time, keeping the ID out of `releases/`. `[C cluster]`
22. WHEN the Golden_Trace is sent, THE Executor SHALL find the Golden_Trace by trace ID in Jaeger service `golden-probe`, MLflow experiment `golden-probe` (as `tr-<trace ID>`) and Phoenix project `golden-probe`, through each Backend's UI and through one API per Backend, and save each API response in the Scratch_Dir. (DoD 1.5) `[C cluster]`
23. WHEN the Golden_Trace is read back from Jaeger, THE Executor SHALL call both `/api/v3/traces/<trace ID>` and the legacy `/api/traces/<trace ID>` on port 16686 and record which endpoint returns the trace. (DoD 1.5) `[C cluster]`
24. WHEN the Golden_Trace is read back from MLflow, THE Executor SHALL call `get_trace("tr-<trace ID>")` from `mlflow-tracing` or `mlflow`, pinned per criterion 9.6. (DoD 1.5) `[C cluster]`
25. WHEN the Golden_Trace is read back from Phoenix, THE Executor SHALL query `/graphql` or call `arize-phoenix-client`, pinned per criterion 9.6. (DoD 1.5) `[C cluster]`
26. WHEN the no-tenant trace of criterion 1.19 is sent, THE Executor SHALL record per Backend where the trace landed or how the Backend rejected the trace, and enter the result in the Interface_Matrix bucketing row. (DoD 1.1) `[C cluster]`
27. THE Observability_Doc SHALL record, per Backend and per Golden_Probe convention, which attributes get dedicated UI (span-kind badge, token columns, chat or message view, retrieval documents, tool input and output) and which appear only as raw key/value pairs. (DoD 1.6) `[D offline]`

##### Re-run and leftovers

28. THE Observability_Doc SHALL contain a copy-paste snippet that re-runs the Golden_Probe: venv creation from `docs/observability/requirements.txt`, the port-forwards, the MLflow experiment creation and the probe command. (DoD 1.7) `[D offline]`
29. WHEN a Golden_Probe run finishes, THE Executor SHALL stop the run's port-forwards and remove the run's venv, so that no process from the run remains and `pgrep -f golden_probe.py` prints nothing. (DoD 1.7) `[C cluster]`
30. THE Executor SHALL commit the Golden_Probe and `docs/observability/requirements.txt` in Phase D, together with the Observability_Doc. (DoD 1.7) `[D offline]`

### Requirement 2: Traces (DoD 2)

**User Story:** As the abox owner, I want every Source's spans to reach Jaeger, MLflow and Phoenix through the Bridge_Collector, driven by the Fixed_Workload, so that the three Backends can be compared on the same traces.

#### Acceptance Criteria

##### Jaeger v2 Backend (Task 1)

1. THE Exercise_Config SHALL add `releases/jaeger.yaml` with Namespace `jaeger`, HelmRepository `jaegertracing` in `flux-system` (URL `https://jaegertracing.github.io/helm-charts`), and HelmRelease `jaeger` in namespace `jaeger`, pinned to chart `jaeger` version `4.14.0` through `chart.spec` and `sourceRef` as in `releases/opentelemetry-demo.yaml`. `[A offline]`
2. THE Exercise_Config SHALL set the `jaeger` HelmRelease values to disable ingress and httproute, give the container resource requests and limits under `jaeger.resources`, set `uiconfig` as a map containing `useOpenTelemetryTerms: true`, and set `userconfig` as a complete Jaeger configuration. `[A offline]`
3. THE Exercise_Config SHALL define, in the `jaeger` HelmRelease `userconfig`: an `otlp` receiver on `0.0.0.0:4317` (gRPC) and `0.0.0.0:4318` (HTTP); a memory storage backend bounded by `max_traces` (planned value 5000); `jaeger_query` on that backend with `ui.config_file: /etc/jaeger/ui-config.json`; `healthcheckv2` with `use_v2: true` on `0.0.0.0:13133`; and Prometheus-format internal metrics on port 8888. `[A offline]`
4. THE Exercise_Config SHALL give `releases/jaeger.yaml` a header comment stating that Jaeger is the Standard_OTel reference Backend, that storage is memory-only and bounded by `max_traces`, why `userconfig` is a complete override, why `uiconfig` is a map, that access is port-forward only, why no HTTPRoute exists (no auth, and the store will hold prompts), and why no `dependsOn` is needed (the chart ships no CRDs). `[A offline]`
5. THE Exercise_Config SHALL list `jaeger.yaml` in `releases/kustomization.yaml` between `graph-otel-demo.yaml` and `kagent.yaml`. `[A offline]`
6. WHEN Phase A validates Task 1, THE Executor SHALL render the chart with `helm template` and the HelmRelease's `spec.values`, and confirm that ConfigMaps `user-config` and `ui-config` render, that `ui-config.json` equals `{"useOpenTelemetryTerms":true}`, and that the container has resources and the argument `--config /etc/jaeger/user-config.yaml`. `[A offline]`
7. WHERE a `jaeger` 2.21.0 darwin-arm64 binary is published, THE Executor SHALL validate the rendered `user-config.yaml` with `jaeger validate --config`, using that binary pinned and checksum-verified. `[A offline]`
8. WHEN `releases/jaeger.yaml` is applied, THE Executor SHALL confirm that the Jaeger pod is Ready with a QoS class other than `BestEffort`, that Service `jaeger` exposes ports 4317, 4318 and 16686, and that the UI on local port 16686 lists no services. `[C cluster]`

##### Bridge_Collector fan-out to Jaeger (Task 3)

9. THE Exercise_Config SHALL add exporter `otlp_grpc/jaeger-v2` (endpoint `jaeger.jaeger.svc.cluster.local:4317`, `tls.insecure: true`) to `releases/mlflow-otel-collector.yaml` and list `otlp_grpc/jaeger-v2` in the top-level `traces` pipeline exporters, next to `debug` and `routing`. `[A offline]`
10. THE Exercise_Config SHALL name every exporter that this spec adds with the current component types `otlp_grpc` and `otlp_http`. `[A offline]`
11. THE Exercise_Config SHALL rewrite the header comment of `releases/mlflow-otel-collector.yaml` to describe the fan-out shape and to explain why Jaeger sits before routing (Jaeger holds the reference copy of every span and is the safety net for a routing table with no catch-all), replacing the sentence "only these two sources exist today". `[A offline]`
12. THE Exercise_Config SHALL keep the Demo_Collector's `otlp_grpc/jaeger` exporter on the exporter's original endpoint, so that Jaeger receives each otel-demo span once, through the Bridge_Collector. `[A offline]`
13. WHEN a Bridge_Collector change is validated, THE Executor SHALL render chart `opentelemetry-collector` 0.173.1 with the HelmRelease values, extract the rendered collector config, and confirm that `MY_POD_IP=127.0.0.1 otelcol-contrib validate --config=file:<rendered>` exits 0 with the pinned, checksum-verified contrib 0.160.0 darwin_arm64 binary. `[A offline]` `[C offline]`
14. WHEN Phase A renders the Bridge_Collector chart, THE Executor SHALL record which processors the chart adds to the `traces` pipeline. `[A offline]`
15. WHEN the Task 3 change is applied, THE Executor SHALL confirm that the new Bridge_Collector pod reaches Ready with zero restarts and that the pod log holds no exporter error entries. `[C cluster]`
16. WHEN the Bridge_Collector fans out to Jaeger, THE Executor SHALL find one new Astronomy Shop trace ID in both Jaeger and MLflow experiment `3`. `[C cluster]`
17. WHILE triage-core emits spans, THE Executor SHALL confirm after each applied Bridge_Collector change that MLflow experiment `2` keeps receiving triage-core traces. `[C cluster]`

##### Phoenix as the third sink (Task 4)

18. WHEN Phase A starts Task 4, THE Executor SHALL read the Phoenix app version from `helm show chart oci://registry-1.docker.io/arizephoenix/phoenix-helm --version 12.0.14` with anonymous registry access, and render the chart to confirm the Service name (expected `phoenix-svc`) and ports 6006 and 4317. `[A offline]`
19. WHEN the Phoenix app version is 15.5.0 or later, THE Exercise_Config SHALL add exporters `otlp_http/phoenix-triage-core` and `otlp_http/phoenix-otel-demo` (endpoint `http://phoenix-svc.phoenix.svc.cluster.local:6006` with the Service name confirmed in criterion 2.18, `tls.insecure: true`, headers `x-project-name: triage-core` and `x-project-name: otel-demo`), each attached to the matching per-Source pipeline next to that pipeline's MLflow exporter. `[A offline]`
20. IF the Phoenix app version is below 15.5.0, THEN THE Exercise_Config SHALL implement the fallback: Phoenix-only pipelines `traces/<source>-phoenix`, each with a `resource/phoenix-<source>` processor that upserts `openinference.project.name`; one `otlp_grpc/phoenix` exporter to Phoenix port 4317; and routing rows that list both the MLflow pipeline and the Phoenix pipeline, so that the MLflow copy stays unmodified. `[A offline]`
21. THE Exercise_Config SHALL extend the header comment of `releases/mlflow-otel-collector.yaml` with the Phoenix mechanism in use, why the header mechanism needs OTLP/HTTP (`x-project-name` applies only to OTLP/HTTP), and the Phoenix 15.5.0 version requirement. `[A offline]`
22. WHEN the Task 4 change is applied, THE Executor SHALL record the running Phoenix image tag. `[C cluster]`
23. IF the running Phoenix image tag and the Phase A app version fall on different sides of 15.5.0, THEN THE Executor SHALL switch to the matching Phoenix mechanism in a new commit before Task 5 starts. `[C cluster]`
24. WHEN the Phoenix exporters are live, THE Executor SHALL find one new Astronomy Shop trace ID in Jaeger, MLflow experiment `3` and Phoenix project `otel-demo`. `[C cluster]`
25. WHILE triage-core emits spans, THE Executor SHALL find triage-core spans in Phoenix project `triage-core`. `[C cluster]`
26. IF Phoenix ignores the `x-project-name` header, so that spans land in the Phoenix default project, THEN THE Executor SHALL switch to the fallback of criterion 2.20 in a new commit. `[C cluster]`
27. IF Phoenix rejects gzip-compressed requests, THEN THE Exercise_Config SHALL set `compression: none` on every Phoenix exporter. `[C cluster]`
28. WHEN the Phoenix exporters are live, THE Executor SHALL record the capacity and used bytes of the Phoenix Postgres PVC, and propose bounded retention at a Consent_Checkpoint: `PHOENIX_DEFAULT_RETENTION_POLICY_DAYS` if the chart exposes that setting, otherwise per-project retention in the Phoenix UI. `[C cluster]`

##### Astronomy Shop agent traces (Task 5)

29. WHEN Phase A runs the offline part of Task 5, THE Executor SHALL search the VCR cassettes in the pulled `opentelemetry-demo` chart 0.41.2 (the files behind ConfigMap `agent-fixtures`) for each README canned prompt ("Show all available products in the store.", "What currencies are supported by the Astronomy Shop?", "What current promotions are available on binoculars?"), without dumping the files, and record the exact matching strings. `[A offline]`
30. IF a README prompt differs from the cassette text, THEN THE Executor SHALL use the cassette text in the Fixed_Workload and record the difference. `[A offline]`
31. WHEN Phase C reaches Task 5, THE Executor SHALL confirm that the `agent` and `chatbot` pods in namespace `otel-demo` are Running, send each canned prompt as `POST localhost:8010/prompt` with body `{"message":"<prompt>","history":[]}` through a port-forward to `svc/agent`, send one prompt through `/chatbot/` via frontend-proxy on local port 8080, and record every resulting trace ID. `[C cluster]`
32. IF a canned prompt returns HTTP 500, THEN THE Executor SHALL record the response, re-check the prompt text against the cassettes, and resend corrected text only. `[C cluster]`
33. WHEN an Astronomy agent trace is found, THE Executor SHALL record from Jaeger's raw span view which `gen_ai.*` attributes are present after the Demo_Collector's `gen_ai_normalizer` processor. `[C cluster]`
34. IF Jaeger evicts an evidence trace before the JSON export, THEN THE Executor SHALL announce and stop Locust from the Locust UI during GenAI runs, and restart Locust before the Load_Run. `[C cluster]`

##### Gemini model for retrieval-agent (Task 6)

35. THE Exercise_Config SHALL add `releases/model-configs.yaml` byte-identical to `feat/llmd-embeddings:releases/model-configs.yaml` (ModelConfig `gemini-3-5-flash` in namespace `kagent`: provider `Gemini`, model `gemini-3.5-flash`, `apiKeySecret: kagent-gemini`, `apiKeySecretKey: GOOGLE_API_KEY`), so that `git show feat/llmd-embeddings:releases/model-configs.yaml | cmp - releases/model-configs.yaml` exits 0. `[A offline]`
36. THE Exercise_Config SHALL list `model-configs.yaml` in `releases/kustomization.yaml` between `mlflow-otel-collector.yaml` and `neo4j.yaml`. `[A offline]`
37. THE Exercise_Config SHALL set `modelConfig: gemini-3-5-flash` on retrieval-agent in `releases/agent-retrieval.yaml`, with a rewritten comment that explains why `default-model-config` fails (the chart points the default at OpenAI with a Secret nobody fills) and that the ModelConfig comes from `feat/llmd-embeddings`. `[A offline]`
38. THE Exercise_Config SHALL add `k8s-agent: {modelConfigRef: gemini-3-5-flash}` to the kagent HelmRelease values in `releases/kagent.yaml`. `[A offline]`
39. WHEN Phase A validates Task 6, THE Executor SHALL render kagent chart 0.10.1 (`oci://ghcr.io/kagent-dev/kagent/helm/kagent`, anonymous access) with the HelmRelease values and confirm that the `k8s-agent` Agent renders `modelConfig: gemini-3-5-flash`. `[A offline]`
40. WHEN Phase C reaches Task 6, THE Executor SHALL confirm by name that Secret `kagent/kagent-gemini` exists, then apply the Task 6 changes to `releases/model-configs.yaml`, `releases/agent-retrieval.yaml` and `releases/kagent.yaml` with Exercise_Apply. `[C cluster]`
41. IF Secret `kagent/kagent-gemini` is missing, THEN THE Executor SHALL ask the User to run `kubectl -n kagent create secret generic kagent-gemini --from-literal=GOOGLE_API_KEY=<key>` and wait. `[C cluster]`
42. WHEN the Task 6 changes are applied, THE Executor SHALL confirm that ModelConfig `gemini-3-5-flash` and Agents `retrieval-agent` and `k8s-agent` report Ready or Accepted, that the agent logs hold no HTTP 401 or 404 from the model provider, and that retrieval-agent returns a non-error answer to one recorded question in the kagent UI. `[C cluster]`
43. IF model `gemini-3.5-flash` returns HTTP 404, THEN THE Executor SHALL report the error and ask the User how to proceed. `[C cluster]`
44. WHEN retrieval-agent delegates ingest to `k8s-agent`, THE Executor SHALL record the content lost to the "Response Format" section of the chart `k8s-agent` prompt, and leave the custom `k8s-agent` unported. `[C cluster]`

##### kagent tracing (Task 7)

45. THE Exercise_Config SHALL add to the kagent HelmRelease values `otel.tracing.enabled: true` and `otel.tracing.exporter.otlp` with endpoint `http://otel-collector.mlflow.svc.cluster.local:4317`, protocol `grpc`, timeout `15000` and `insecure: true`; keep `otel.logging` disabled with an empty endpoint; and add a comment that explains the URL form and the controller's propagation of `OTEL_*` env vars into agent pods. `[A offline]`
46. WHEN Phase A validates Task 7, THE Executor SHALL render kagent chart 0.10.1 and confirm that the controller ConfigMap carries `OTEL_TRACING_ENABLED: "true"`, `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, `OTEL_EXPORTER_OTLP_TRACES_INSECURE`, `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL` and `OTEL_EXPORTER_OTLP_TRACES_TIMEOUT`, and lacks `OTEL_EXPORTER_OTLP_ENDPOINT`. `[A offline]`
47. THE Executor SHALL commit the Task 7 change separately from the Task 6 change. `[A offline]`
48. WHEN the Task 7 change is applied, THE Executor SHALL restart the kagent controller if the controller pod did not roll, confirm by name that the `OTEL_*` env vars exist on the controller and on the `retrieval-agent` and `k8s-agent` Deployments, and restart any agent pod whose Deployment lacks the names. `[C cluster]`
49. IF no kagent span reaches Jaeger after a retrieval-agent question, THEN THE Executor SHALL check the controller and agent logs, then try the bare `host:port` endpoint form in a new commit. `[C cluster]`
50. WHEN kagent spans reach Jaeger, THE Executor SHALL record: the resource attributes (`service.name`, `service.namespace` and the rest); whether spans come from the controller only or from agent pods too; the span names; LLM spans with model, token counts and content presence; tool spans with MCP calls, arguments and results; whether delegation to `k8s-agent` joins the same trace; A2A spans; and the runtime image that retrieval-agent runs. (DoD 2.6) `[C cluster]`
51. IF the kagent spans include no LLM span or no tool span, THEN THE Executor SHALL document the evidence and ask the User to choose among Task 9 (LLM spans through agentgateway-llm), instrumenting `mcp/qdrant-mcp` (new scope that needs a spec update) and neither, starting no option before the User chooses. (DoD 2.5) `[C cluster]`

##### kagent Tenant (Task 8)

52. WHEN Phase C reaches Task 8, THE Executor SHALL create MLflow experiment `kagent` through the MLflow API and record the returned ID. `[C cluster]`
53. THE Exercise_Config SHALL add exporter `otlp_http/mlflow-kagent` with header `x-mlflow-experiment-id` set to the recorded `kagent` experiment ID. `[C offline]`
54. THE Exercise_Config SHALL extend the header comment's experiment-ID note to experiments `2`, `3` and `kagent`, including how to recreate the three experiments if the MLflow PVC is wiped. `[C offline]`
55. THE Exercise_Config SHALL add a routing row that sends spans from every kagent-side service observed in Task 7 (the controller, retrieval-agent, `k8s-agent`, and agentgateway-llm only if Task 9 runs) to pipeline `traces/kagent`. `[C offline]`
56. WHERE the kagent-side spans share one resource attribute value (for example `service.namespace == "kagent"`), THE Exercise_Config SHALL match the kagent routing row on that attribute. `[C offline]`
57. IF the kagent-side spans share no resource attribute value, THEN THE Exercise_Config SHALL match the kagent routing row with `IsMatch(resource.attributes["service.name"], "<observed pattern>")`. `[C offline]`
58. THE Exercise_Config SHALL keep every routing row in `statement` style and order the rows from specific to broad, because each row's default `move` action removes matched data from later rows. `[C offline]`
59. THE Exercise_Config SHALL define pipeline `traces/kagent` with exporter `otlp_http/mlflow-kagent` and the Phoenix exporter for project `kagent`, using the Phoenix mechanism that Task 4 settled. `[C offline]`
60. WHEN the Task 8 change passes the validation of criterion 2.13, THE Executor SHALL commit the change, then apply the change with Exercise_Apply. `[C cluster]`
61. WHEN the kagent routing row is live, THE Executor SHALL show one retrieval-agent trace, including the `k8s-agent` delegation when the delegation joins the trace, with matching span counts in Jaeger, MLflow experiment `kagent` and Phoenix project `kagent`. (DoD 2.4) `[C cluster]`

##### agentgateway-llm route (Task 9, optional)

62. WHERE the User accepts Task 9 at Task 7's decision point, THE Executor SHALL time-box Task 9 to 60 minutes and first check whether an agentgateway release fixes the Gemini AI-Studio key bug or a provider config can reach Gemini's OpenAI-compatible endpoint with a bearer key, and what `randomSampling` means, aiming for 100% or parent-based sampling. `[C cluster]`
63. WHERE Task 9 runs and the first checks show a viable route, THE Executor SHALL add a second ModelConfig that goes through agentgateway-llm, repoint `frontendPolicies.tracing.host` at the Bridge_Collector, route agentgateway-llm spans into `traces/kagent`, and change both the seed ConfigMap in git and the live config through the agentgateway-llm admin UI. `[C cluster]`
64. IF the Task 9 time-box ends without a viable route, THEN THE Executor SHALL stop Task 9, record the findings and report to the User. `[C cluster]`

##### Reconciliation, coverage, Tenants and Parity

65. THE Exercise_Config SHALL hold every Cluster configuration change of this spec, with the manual steps of criterion 2.67 as the only exceptions. (DoD 2.1) `[D offline]`
66. WHEN the Release completes, THE Executor SHALL capture `flux get all -A` output in which every object reports Ready and OCIRepository `releases` reports the revision of the pushed tag. (DoD 2.1) `[D cluster]`
67. THE Observability_Doc SHALL list every manual step outside `releases/`: MLflow experiment creation (`golden-probe`, `kagent`, and recreation of `2` and `3`), each Secret by name with a create command that uses placeholders, any Locust stop or restart, and any agentgateway-llm reseed. (DoD 2.1) `[D offline]`
68. THE Observability_Doc SHALL contain a coverage table with at least one recorded trace ID per Source (retrieval-agent via kagent, the Astronomy Shop agent, the Astronomy Shop microservices) in each Backend, plus an optional triage-core control row. (DoD 2.2) `[D offline]`
69. THE Exercise_Config SHALL route triage-core, otel-demo and kagent spans to three distinct MLflow experiments and three distinct Phoenix projects, with the Astronomy Shop agent routed by the otel-demo namespace row, because agent traces cross into frontend, product-catalog and other otel-demo services. (DoD 2.3) `[C offline]`
70. THE Observability_Doc SHALL list every service present in Jaeger but absent from MLflow or Phoenix, with the reason (for example, the Golden_Probe sends directly, or the service matches no routing row). (DoD 2.3) `[D offline]`
71. WHEN a GenAI_Source evidence trace is captured, THE Executor SHALL resolve the same OTel trace ID in Jaeger, in MLflow (as `tr-<trace ID>`) and in Phoenix, and record each Backend's span count. (DoD 2.4) `[C cluster]`
72. IF a Backend's span count for an evidence trace differs from Jaeger's span count, THEN THE Observability_Doc SHALL explain the difference. (DoD 2.4) `[D offline]`

##### GenAI minimum and GenAI_Inventory

73. THE Observability_Doc SHALL show, per GenAI_Source, at least one trace ID whose trace holds an LLM call span with the model name present and a tool-call span. (DoD 2.5) `[D offline]`
74. IF kagent 0.10.1 emits no LLM span or no tool span, THEN THE Observability_Doc SHALL document the gap with evidence and record the User's follow-up decision from criterion 2.51. (DoD 2.5) `[D offline]`
75. THE Observability_Doc SHALL record the GenAI_Inventory for each GenAI_Source, marking each item present or absent. (DoD 2.6) `[D offline]`

##### Fixed_Workload and Load_Run (Task 10)

76. THE Fixed_Workload SHALL contain retrieval-agent's four prompts, word for word (DoD 2.7) `[C cluster]`:
    1. Ingest: "Ingest the kagent.dev Agent and ModelConfig objects in namespace kagent."
    2. Vector: "What does the retrieval-agent's system message say about choosing between the vector store and the graph?"
    3. Graph: "Which agents use the ModelConfig gemini-3-5-flash?"
    4. Unanswerable: "Which agent uses the ModelConfig named does-not-exist?"
77. WHERE Task 9 ran, THE Fixed_Workload SHALL add one guardrail-tripping prompt, recorded word for word. (DoD 2.7) `[C cluster]`
78. THE Fixed_Workload SHALL contain the Astronomy agent prompts word for word, as checked against the demo 3.0.0 cassettes in criteria 2.29 and 2.30. (DoD 2.7) `[A offline]`
79. WHEN the retrieval-agent prompts run, THE Executor SHALL verify the A2A path on the kagent controller (expected: JSON-RPC `message/send` to `POST /api/a2a/kagent/retrieval-agent/`) and send the four prompts through that path. `[C cluster]`
80. IF the A2A path fails, THEN THE Executor SHALL send the four prompts through the kagent UI and record that the run was manual. `[C cluster]`
81. WHEN a GenAI run completes, THE Executor SHALL export the run's evidence traces from Jaeger as JSON before the next run and before the Load_Run starts. (DoD 2.9) `[C cluster]`
82. THE Load_Run SHALL use fixed Locust users, spawn rate and duration (planned: 10 users, spawn rate 1, 10 minutes), with the values used recorded in the Observability_Doc. (DoD 2.7) `[C cluster]`
83. WHEN the Load_Run starts, reaches the halfway point and ends, THE Executor SHALL record `otelcol_exporter_sent_spans`, `otelcol_exporter_send_failed_spans` and `otelcol_exporter_queue_size` per exporter for both collectors (series names can carry a `_total` suffix), plus `kubectl top pod` CPU and memory for Jaeger, MLflow, Phoenix and the Bridge_Collector. (DoD 2.8) `[C cluster]`
84. WHEN the Load_Run ends, THE Executor SHALL confirm that `otelcol_exporter_send_failed_spans` increased by zero over the run for every In_Scope_Exporter. (DoD 2.8) `[C cluster]`
85. IF an In_Scope_Exporter's `otelcol_exporter_send_failed_spans` increases during the Load_Run, THEN THE Observability_Doc SHALL quantify the loss for that exporter in spans and as a share of sent spans. (DoD 2.8) `[D offline]`
86. THE Observability_Doc SHALL name the Demo_Collector's `otlp_grpc/jaeger`, `otlp_http/prometheus` and `opensearch` exporters as excluded from the zero-failure check, with the reason from the In_Scope_Exporter definition. (DoD 2.8) `[D offline]`
87. WHEN the Load_Run ends, THE Executor SHALL confirm that the restart counts of the Jaeger, MLflow, Phoenix and Bridge_Collector pods equal the counts recorded at the start, and record any MLflow probe-failure events. (DoD 2.8) `[C cluster]`
88. WHEN the Load_Run ends, THE Executor SHALL confirm that MLflow experiment `3` received traces during the run, and experiment `2` too while triage-core emits spans, and record the used bytes of the Phoenix and MLflow PVCs at the start and the end. (DoD 2.8) `[C cluster]`
89. WHERE the Executor measures the time until a fresh trace becomes visible, THE Observability_Doc SHALL report the measured seconds per Backend. `[D offline]`

##### Evidence and exposure

90. THE Executor SHALL commit under the Evidence_Dir the Jaeger JSON exports of the evidence traces, plus the trimmed excerpts and screenshots that the Observability_Doc references. (DoD 2.9) `[D offline]`
91. WHEN Phase D starts, THE Executor SHALL record the backendRefs of every HTTPRoute (`kubectl get httproute -A -o yaml`) and the upstream of every ngrok endpoint, and confirm that none references a Service in namespace `jaeger`, `mlflow` or `phoenix`. (DoD 2.10) `[D cluster]`
92. WHEN evidence is committed, THE Executor SHALL pass the Secret_Scan over the committed Evidence_Dir files and the Observability_Doc. (DoD 2.10) `[D offline]`

##### Phase A decision records

93. WHEN Phase A has read the Phoenix app version per criterion 2.18, THE Executor SHALL record the Phoenix routing decision in the Decision_Log before any Cluster work: the app version read from chart 12.0.14, the outcome of the 15.5.0 version gate, and the Phoenix mechanism that the Exercise_Config uses (criterion 2.19 or 2.20). `[A offline]`
94. WHILE Phase A runs, THE Executor SHALL derive the expected kagent trace identity from the kagent 0.10.1 source without Cluster access, and record the expected identity in the Decision_Log before any Cluster work: per emitter (the controller and the agent pods), the `service.name`, `service.namespace` and any other resource attribute that the Task 8 routing row could match, with the source files and tag read. `[A offline]`
95. WHEN kagent spans reach Jaeger in Task 7, THE Executor SHALL compare the resource attributes recorded under criterion 2.50 with the expected identity of criterion 2.94, and record in the Decision_Log whether Task 7 confirmed or corrected the expectation, with the observed values. `[C cluster]`
96. IF Phase C switches the Phoenix mechanism under criterion 2.23 or 2.26, THEN THE Executor SHALL update the Phoenix routing decision in the Decision_Log with the new mechanism and the reason. `[C offline]`

### Requirement 3: Comparison (DoD 3)

**User Story:** As the abox owner, I want the Observability_Doc to compare the three Backends on the same traces from a GenAI perspective, with every claim backed by evidence, so that I can choose a default observability setup for abox.

#### Acceptance Criteria

##### Placement and links

1. THE Observability_Doc SHALL be the file `OBSERVABILITY.md` at the repo root. (DoD 3.1) `[D offline]`
2. WHEN Task 12 updates README.md, THE Executor SHALL add a link to the Observability_Doc, add a Jaeger row to the component table next to the MLflow row that Phase 0 added (criterion 11.3), and add the Port_Map port-forward commands. (DoD 3.1) `[D offline]`
3. WHEN Task 12 updates README.md and CODEBASE.md, THE Executor SHALL add the Phoenix app version observed on the Cluster next to each Phoenix chart 12.0.14 mention that Phase 0 set (criterion 11.3). (DoD 3.1) `[D offline]`

##### Framing and views

4. THE Observability_Doc SHALL open with the framing that Standard_OTel means the OTel SDKs, OTLP, the OTel Collector and semconv, with Jaeger v2 as the reference UI, and that all three Backends ingest the same OTLP, so the comparison covers data model, semconv handling and GenAI tooling rather than transport. (DoD 3.2) `[D offline]`
5. THE Observability_Doc SHALL show, per GenAI_Source, one trace ID in all three Backend views (screenshots or API excerpts), with the differences between the views called out. (DoD 3.3) `[D offline]`

##### Comparison dimensions

6. THE Observability_Doc SHALL give each dimension in criteria 3.7 to 3.17 a verdict per Backend plus at least one evidence link (trace ID, screenshot or versioned doc URL). (DoD 3.4) `[D offline]`
7. THE Observability_Doc SHALL compare prompt and completion display (dimension 1). (DoD 3.4) `[D offline]`
8. THE Observability_Doc SHALL compare token usage and cost (dimension 2). (DoD 3.4) `[D offline]`
9. THE Observability_Doc SHALL compare agent structure: tool calls, ReAct loops, delegation and span-kind recognition (dimension 3). (DoD 3.4) `[D offline]`
10. THE Observability_Doc SHALL compare retrieval results (dimension 4). (DoD 3.4) `[D offline]`
11. THE Observability_Doc SHALL compare the handling of each emitter's conventions: `gen_ai.*` from the Astronomy agent and from agentgateway, kagent's own spans, and triage-core (dimension 5). (DoD 3.4) `[D offline]`
12. THE Observability_Doc SHALL compare failure visibility: tool errors, empty retrievals and guardrail rejections (dimension 6). (DoD 3.4) `[D offline]`
13. THE Observability_Doc SHALL compare session and conversation grouping (dimension 7). (DoD 3.4) `[D offline]`
14. THE Observability_Doc SHALL compare search and filter, including finding agent traces in the mixed otel-demo stream (dimension 8). (DoD 3.4) `[D offline]`
15. THE Observability_Doc SHALL compare evals and feedback: evals, annotations, datasets built from traces, and prompt management (dimension 9). (DoD 3.4) `[D offline]`
16. THE Observability_Doc SHALL compare operations: ingest limits, cost under load, stability, retention and auth (dimension 10). (DoD 3.4) `[D offline]`
17. THE Observability_Doc SHALL compare portability: plain OTLP versus a vendor SDK, export options and license (dimension 11). (DoD 3.4) `[D offline]`
18. IF the Fixed_Workload did not exercise an emitter or failure type named in dimensions 5 and 6 (for example agentgateway spans without Task 9, or guardrail rejections), THEN THE Observability_Doc SHALL mark that item "not exercised" with the reason. (DoD 3.4) `[D offline]`

##### Load results and verdict

19. THE Observability_Doc SHALL report the Load_Run results as numbers: Locust parameters, sent and failed spans and queue size per exporter, CPU and memory per Backend, restarts, MLflow probe events and PVC growth. (DoD 3.5) `[D offline]`
20. THE Observability_Doc SHALL state that the Astronomy agent's LLM latency comes from VCR cassette replay and does not represent a live LLM. (DoD 3.5) `[D offline]`
21. THE Observability_Doc SHALL state which Backend fits infra tracing, which fits GenAI debugging and which fits eval and regression work, and recommend a default observability setup for abox. (DoD 3.6) `[D offline]`

##### Claims, pins and Reproduce

22. THE Observability_Doc SHALL link every claim to a trace ID, a screenshot or a versioned doc URL. (DoD 3.7) `[D offline]`
23. THE Observability_Doc SHALL label every claim taken from documentation and not checked on the Cluster as "docs only". (DoD 3.7) `[D offline]`
24. THE Observability_Doc SHALL list unverified items in a dedicated section. (DoD 3.7) `[D offline]`
25. THE Observability_Doc SHALL pin every component version: Jaeger chart 4.14.0 and app 2.21.0; Bridge_Collector chart 0.173.1 and contrib 0.160.0; the observed MLflow server version; Phoenix chart 12.0.14 and the observed app version; kagent 0.10.1 and the observed agent runtime image; demo chart 0.41.2, demo app 3.0.0 and the observed Demo_Collector version. (DoD 3.7) `[D offline]`
26. THE Observability_Doc SHALL contain a Reproduce section with the port-forward commands, the Golden_Probe commands, the Fixed_Workload prompts and the Locust parameters. (DoD 3.8) `[D offline]`
27. WHEN the Reproduce section is written, THE Executor SHALL follow the section's steps verbatim against the Cluster and confirm that one new trace appears in all three UIs. (DoD 3.8) `[D cluster]`
28. THE Observability_Doc SHALL contain an "Outstanding risks" section, next to the unverified-items, version-pin and Reproduce sections of criteria 3.24 to 3.26, that lists each risk still open at publication with the evidence or User decision behind the risk (for example Backends without auth, retention left unbounded, or an exposure risk accepted under criterion 7.15). `[D offline]`

### Requirement 4: Access gate and kubeconfig isolation

**User Story:** As the abox owner, I want the Executor to reach only my abox cluster, through an isolated kubeconfig, and to inspect the cluster read-only before changing anything, so that no other cluster is touched and every later step starts from recorded facts.

#### Acceptance Criteria

1. IF the User has supplied no Cluster access by the end of Phase A, THEN THE Executor SHALL send one access request, asking for either (a) a Codespace name after the User runs `gh auth refresh -h github.com -s codespace`, or (b) a kubeconfig path, context name and any VPN or tunnel, stating that offline prep is committed locally with nothing pushed or applied, and wait for the answer. `[B offline]`
2. WHERE the Cluster runs in a GitHub Codespace, THE Executor SHALL either copy the kind kubeconfig with `gh codespace cp -e 'remote:~/.kube/config' /tmp/abox-observability/abox.kubeconfig -c <name>` and forward the API port in the background with `gh codespace ports forward <port>:<port> -c <name>`, or run kubectl inside the Codespace with `gh codespace ssh -c <name> -- <cmd>`. `[B cluster]`
3. WHERE the Cluster runs on another host, THE Executor SHALL use the kubeconfig path, context name and VPN or tunnel details that the User supplies. `[B cluster]`
4. THE Executor SHALL keep the Abox_Kubeconfig in a separate file, unmerged into `~/.kube/config`, with no current-context set. `[all phases]`
5. THE Executor SHALL pass `--kubeconfig` with the Abox_Kubeconfig and `--context` with the abox context name on every kubectl, helm and flux command. `[all phases]`
6. THE Executor SHALL leave the unrelated EKS context in `~/.kube/config` unused and unchanged. `[all phases]`
7. WHEN the Executor first connects, and before every write to the Cluster, THE Executor SHALL confirm that the target is abox: node names start with `abox-` and Kustomization `flux-system/releases` exists. `[all phases]`
8. IF the abox identity check fails, THEN THE Executor SHALL stop, run no further command against that context, and report to the User. `[all phases]`
9. THE Executor SHALL keep the content of a copied kubeconfig out of every message and log. `[all phases]`
10. WHILE the Task 0b preflight runs, THE Executor SHALL run read-only commands only. `[B cluster]`
11. WHEN Cluster access works, THE Executor SHALL record in the Task 0b preflight `[B cluster]`:
    - `kubectl top nodes`, allocatable versus requested resources, and PVCs with capacity;
    - `flux get all -A`;
    - the RSIP URL from `kubectl get resourcesetinputprovider releases-image -n flux-system -o jsonpath='{.spec.url}'`;
    - the live OCIRepository `releases` revision, mapped to a tag and a commit;
    - pod status in namespaces `mlflow`, `phoenix`, `otel-demo` (including `agent`, `chatbot`, `mcp` and `load-generator`), `kagent` and `triage`;
    - the MLflow server version, the Phoenix app version, the kagent agent images and runtime, and the Demo_Collector version;
    - whether Locust generates load (the repo sets `LOCUST_HEADLESS: "false"` and a Service on port 8089; autostart is unknown);
    - through the MLflow API on local port 5000, whether experiments `2` and `3` exist and receive traces;
    - `kubectl get modelconfig,agents -n kagent` with statuses, and the ModelConfig that retrieval-agent uses live.
12. IF the live OCIRepository revision is upstream `0.11.36` at commit `49db8b6`, THEN THE Executor SHALL run `git fetch upstream` (local refs only) and identify the branch that holds that commit. `[B cluster]`
13. IF the MLflow server version is below 3.6, THEN THE Executor SHALL stop and report, because MLflow OTLP ingest needs 3.6 or later. `[B cluster]`
14. IF the MLflow server version is below 3.7, THEN THE Exercise_Config SHALL set `compression: none` on every MLflow exporter, because MLflow accepts gzip from 3.7 on. `[C offline]`
15. WHEN the preflight finishes, THE Executor SHALL send one checkpoint message with the findings, the diff lists of criterion 6.3, the missing Secrets with exact create commands, the Kagent_Exposure_Gate findings with the decision request, the review items of criterion 6.11, and the request to confirm `flux suspend kustomization releases -n flux-system`. `[B offline]`

### Requirement 5: Git and release hygiene

**User Story:** As the abox owner, I want every change committed as small, reviewable commits on `feat/otel-demo`, and every push and Release done only with my confirmation, so that the history stays clean and the live cluster changes only when I say so.

#### Acceptance Criteria

1. WHEN a batch of edits starts, and before every commit, THE Executor SHALL confirm that `git branch --show-current` prints `feat/otel-demo`. `[all phases]`
2. IF the current branch is not `feat/otel-demo`, THEN THE Executor SHALL stop and ask the User. `[all phases]`
3. WHEN execution starts, THE Executor SHALL ask the User to keep this checkout on `feat/otel-demo` until execution ends. `[0 offline]`
4. WHEN Phase 0 starts, after the add commit of criterion 10.2, and again when Phase A starts, THE Executor SHALL confirm that `git status --porcelain` prints no line other than `?? .kiro/`. `[0 offline]` `[A offline]`
5. THE Executor SHALL stage files by name, leaving `.env`, `.kiro/` and every secret-bearing file unstaged. `[all phases]`
6. THE Executor SHALL write each commit message as `<area>: <summary>` (for example `releases: add Jaeger v2 as the OTel-native trace backend`), with a body that explains why. `[all phases]`
7. THE Executor SHALL keep one logical change per commit. `[all phases]`
8. THE Executor SHALL push without force, leave pushed commits unamended, and keep git hooks active (no `--no-verify`). `[all phases]`
9. WHEN an Exercise_Config change passes offline validation, including `kubectl kustomize releases` exiting 0, THE Executor SHALL commit the change locally, with nothing pushed or applied during Phase A. `[A offline]`
10. WHEN Cluster testing finds a defect in a committed change, THE Executor SHALL fix the defect in a new commit. `[C offline]`
11. THE Executor SHALL push a branch or a tag only after the User's explicit confirmation of that push. `[all phases]`
12. WHEN Task 12 starts the Release, THE Executor SHALL choose the Release path from the RSIP URL and the live OCIRepository revision recorded in Task 0b. `[D cluster]`
13. WHERE the RSIP polls the fork registry `oci://ghcr.io/ingvar-goryainov/abox/releases-otel-demo`, THE Executor SHALL run these steps, each confirmed by the User (DoD 2.1) `[D cluster]`:
    1. push `feat/otel-demo` before the tag, because CI maps the tag to a branch with `git branch -r --contains`;
    2. push a tag above the highest semver tag in that registry, with `make push` (which also pushes `main`) or a manual tag;
    3. wait for CI to publish the artifact;
    4. have the User make the new package public or provide a pull secret;
    5. run `flux resume kustomization releases -n flux-system`, and remove the ResourceSet reconcile annotation if one was added;
    6. confirm that `flux get all -A` reports Ready.
14. WHERE the RSIP polls the upstream registry under `ghcr.io/den-vasyliev/abox`, THE Executor SHALL present these options and wait for the User's choice `[D cluster]`:
    - (a) the User repoints the RSIP and ResourceSet at the fork, with `tofu apply -var oci_registry=oci://ghcr.io/ingvar-goryainov/abox` wherever the Cluster was bootstrapped, or with a kubectl patch that drifts from tofu state;
    - (b) an upstream PR, after which the maintainer tags a Release;
    - (c) resume Flux without a Release, with the warning that resuming reverts the Cluster to upstream's bundle and tears down the exercise setup.
15. IF the Cluster ran upstream `0.11.36`, THEN THE Executor SHALL warn the User that a Release from this branch prunes the objects of upstream's `graph-triage.yaml` and `triage-ui.yaml`, and offer to merge upstream's newer state first. `[D cluster]`
16. THE Executor SHALL leave the `Makefile`, including `make push`, unchanged. `[all phases]`
17. WHEN Task 12 closes out, THE Executor SHALL walk every DoD checkbox and report each unmet item with the reason (for example "not reconciled from a pushed tag" when the User chose not to release). `[D cluster]`
18. WHEN Task 12 walks the DoD, THE Executor SHALL check each Reviewer_Exit_Criterion against this evidence and record whether the criterion holds (DoD Exit) `[D cluster]`:
    - source-of-truth decision recorded: the "Source of truth" paragraph of the committed Canonical_Spec (criterion 10.2);
    - Root_Docs match the manifests: the Phase 0 commit and the Task 12 re-check (criteria 11.6 and 11.9), with only recorded Known_Deviations left;
    - required safety gates resolved: the Phase_A_Review_Gate approval (criterion 6.12), the Kagent_Exposure_Gate (criteria 7.9 to 7.16), and every Consent_Checkpoint answered and recorded (criteria 6.1 and 6.10);
    - release objects Ready: the `flux get all -A` capture of criterion 2.66;
    - every required Source traced in all three Backends: the coverage table of criterion 2.68, with a trace ID in Jaeger, MLflow and Phoenix for each GenAI_Source and the Volume_Source;
    - conclusions reproducible from sanitized evidence: the Reproduce run of criterion 3.27, plus a passing Secret_Scan over the committed Evidence_Dir files and the Observability_Doc (criteria 2.92 and 8.3).
19. WHEN all six Reviewer_Exit_Criteria hold, THE Executor SHALL ask the User to approve completion. (DoD Exit) `[D offline]`
20. IF a Reviewer_Exit_Criterion does not hold, THEN THE Executor SHALL report completion as unapproved and name each unmet Reviewer_Exit_Criterion with the reason. (DoD Exit) `[D offline]`

### Requirement 6: Consent and blast radius

**User Story:** As the abox owner, I want to see what will change on my cluster and approve every risky action in advance, so that nothing irreversible or unexpected reaches the cluster.

#### Acceptance Criteria

1. THE Executor SHALL hold a Consent_Checkpoint before each of these actions `[all phases]`:
   - deleting a PVC;
   - deleting an MLflow experiment or a Phoenix project;
   - bumping a chart version;
   - running `flux suspend`, or adding a ResourceSet reconcile annotation;
   - changing Phoenix retention;
   - LLM spend beyond the prompts this spec plans (Task 6's test question, Task 7's observation question and the Fixed_Workload);
   - running `kubectl delete` on a live object.
2. WHEN the Task 0b inventory is recorded, THE Executor SHALL diff the live Cluster against this branch with `flux diff kustomization releases --path ./releases` (explicit kubeconfig and context), or by comparing objects by hand if that command fails. `[B cluster]`
3. WHEN the diff completes, THE Executor SHALL list everything that applying the Exercise_Config would add or change, and everything that a final Release from this branch would add, change or prune (for example the objects of `graph-triage.yaml` and `triage-ui.yaml`). `[B cluster]`
4. WHEN the diff lists are ready, THE Executor SHALL show the lists to the User in the Task 0b checkpoint message and wait for an explicit go-ahead before the first apply. `[B offline]`
5. WHEN the User has made the Kagent_Exposure_Gate decision and confirmed the suspend, THE Executor SHALL run `flux suspend kustomization releases -n flux-system` with explicit kubeconfig and context. `[B cluster]`
6. WHEN at least 6 minutes have passed since the suspend, THE Executor SHALL read `spec.suspend` of Kustomization `flux-system/releases` and confirm that the value is `true`. `[B cluster]`
7. IF the ResourceSet has reset `spec.suspend`, THEN THE Executor SHALL propose `kubectl annotate resourceset releases -n flux-system fluxcd.controlplane.io/reconcile=disabled` (reversible) at a Consent_Checkpoint. `[B cluster]`
8. WHILE Kustomization `releases` is suspended, THE Executor SHALL apply manifests to the Cluster only with Exercise_Apply, and only for changed or new Exercise_Config objects. `[C cluster]`
9. THE Executor SHALL bring each Phase C task's committed change to the Cluster in task order, so that a file holding changes from several tasks (for example `releases/kagent.yaml` with Tasks 6 and 7, or `releases/mlflow-otel-collector.yaml` with Tasks 3 and 4) reaches the Cluster one task at a time. `[C cluster]`
10. IF the User declines a Consent_Checkpoint, THEN THE Executor SHALL skip the action, record the decision, and report which DoD items the decision affects. `[all phases]`
11. THE Executor SHALL include in the Task 0b checkpoint message, for the User's review before approval `[B offline]`:
    - the exact diff: the `git diff` of `releases/` that Phase A committed, and the `flux diff` output of criterion 6.2 or the comparison by hand;
    - the task order: every planned Cluster write in sequence, starting with any restriction chosen at the Kagent_Exposure_Gate, then Tasks 1 to 8 and 10, with Task 9 only if the User accepts Task 9;
    - a rollback and cleanup plan: for each planned write, how the write is undone and what the undo leaves behind, plus how Flux resumes and what the cleanup of Requirement 8 removes;
    - the evidence locations: the Scratch_Dir paths for raw evidence and the Evidence_Dir paths for committed evidence.
12. WHEN the Phase A work is committed locally, THE Executor SHALL stop at the Phase_A_Review_Gate, ask the User to review the items below, and start Phase B only after the User's explicit approval `[A offline]`:
    - the version pins of criteria 9.1 to 9.5;
    - the chart renderings of criteria 2.6, 2.14, 2.18, 2.39 and 2.46;
    - the collector validation of criterion 2.13;
    - the Golden_Probe dry run of criterion 1.20;
    - proof that no HTTPRoute, Ingress or ngrok endpoint in the Exercise_Config or its chart renderings exposes a UI of Jaeger, MLflow or Phoenix;
    - a passing Secret_Scan over every file that Phase A changed or created;
    - the Decision_Log records of criteria 2.93 and 2.94.
13. IF the User requests changes at the Phase_A_Review_Gate, THEN THE Executor SHALL make the changes in new commits and present the Phase_A_Review_Gate again. `[A offline]`

### Requirement 7: Exposure and secrets

**User Story:** As the abox owner, I want the three unauthenticated Backends and kagent kept off the public internet, and Secret values kept out of every output, so that prompts, tool output, manifests and keys stay private.

#### Acceptance Criteria

1. THE Executor SHALL reach Jaeger, MLflow and Phoenix only through `kubectl port-forward`, adding no HTTPRoute and no ngrok endpoint for any Backend. (DoD 2.10) `[all phases]`
2. THE Executor SHALL bind every port-forward to the local port that the Port_Map assigns. `[all phases]`
3. THE Executor SHALL read collector internal metrics on port 8888 through the API-server pod proxy, `kubectl get --raw "/api/v1/namespaces/<namespace>/pods/<pod>:8888/proxy/metrics"`, for the Bridge_Collector (namespace `mlflow`) and the Demo_Collector (namespace `otel-demo`). `[C cluster]`
4. THE Executor SHALL check Secrets by name only, without reading or printing values: `kagent/kagent-gemini`, `flux-system/ghcr-credentials`, `triage/triage-ghcr-pull`, `triage/triage-gemini-key` and `agentgateway-system/agentgateway-llm-secrets`. `[B cluster]`
5. IF a Secret from criterion 7.4 is missing, THEN THE Executor SHALL list the Secret in the Task 0b checkpoint message with the exact create command using `<placeholder>` values, and wait for the User before the first task that needs the Secret. `[B offline]`
6. WHEN Task 0b runs, THE Executor SHALL list, read-only, the ngrok AgentEndpoint and Domain objects (including the operator's auto-created free-domain pair), every HTTPRoute attached to Gateway `agentgateway-external`, and the Gateway's listeners. `[B cluster]`
7. WHEN the public ngrok URLs are known, THE Executor SHALL send unauthenticated HTTP GET requests to read-only paths only on each public URL, with no prompt and no LLM call, and record the HTTP status and whether kagent served the response. `[B cluster]`
8. WHEN the Task 0b checkpoint message is sent, THE Executor SHALL include the Kagent_Exposure_Gate findings and ask the User to decide, before `flux suspend` or any other write to the Cluster, whether to restrict the kagent route or explicitly accept the risk. `[B offline]`
9. WHILE the Kagent_Exposure_Gate is unresolved, THE Executor SHALL keep Task 1's on-cluster apply, and every later Phase C write, blocked. `[C cluster]`
10. WHERE the User chooses to restrict the kagent route, THE Executor SHALL commit a `releases/kagent.yaml` change that removes HTTPRoute `kagent` and ReferenceGrant `kagent`, or adds hostnames to HTTPRoute `kagent`, as the User picks, and update the kagent route mentions in CODEBASE.md and README.md. `[B offline]`
11. WHERE the User chooses removal, THE Executor SHALL delete the live HTTPRoute `kagent` and ReferenceGrant `kagent` with `kubectl delete` after a Consent_Checkpoint, as the first write after the suspend of criteria 6.5 to 6.7, because Exercise_Apply leaves removed objects in place and Flux is suspended. `[B cluster]`
12. WHERE the User chooses hostnames, THE Executor SHALL apply only the changed HTTPRoute `kagent` with Exercise_Apply after a Consent_Checkpoint, as the first write after the suspend of criteria 6.5 to 6.7. `[B cluster]`
13. WHEN a restriction is live, THE Executor SHALL repeat the GET requests of criterion 7.7 and confirm, before Task 1's apply, that kagent no longer answers on the public URLs. `[B cluster]`
14. IF kagent still answers on a public URL after the restriction, THEN THE Executor SHALL keep Task 1's apply blocked and report to the User. `[B cluster]`
15. WHERE the User accepts the kagent exposure risk, THE Executor SHALL record the acceptance, with the date, in the design document's risks, in the Interface_Matrix auth row and in dimension 10 of the Observability_Doc. `[D offline]`
16. WHILE the Kagent_Exposure_Gate decision is pending, THE Executor SHALL keep `flux suspend` and every other write to the Cluster blocked. `[B cluster]`

### Requirement 8: Evidence and cleanup

**User Story:** As the abox owner, I want raw evidence kept out of git, only trimmed and scanned evidence committed, and every temporary resource removed at the end, so that the repo stays clean and nothing from the exercise keeps running.

#### Acceptance Criteria

1. THE Executor SHALL keep raw evidence (API dumps, logs, metrics scrapes and full exports) in the Scratch_Dir, outside git. `[all phases]`
2. THE Executor SHALL commit to the Evidence_Dir only files that the Observability_Doc references. `[D offline]`
3. WHEN files are about to be committed to the Evidence_Dir or the Observability_Doc, THE Executor SHALL run the Secret_Scan over the staged files. `[D offline]`
4. IF the Secret_Scan fails, THEN THE Executor SHALL stop the commit and report the file names and line numbers without printing the matched values. `[all phases]`
5. IF UI screenshots cannot be captured, THEN THE Executor SHALL give the User an exact list of views and URLs to capture, and use API exports as primary evidence. `[D offline]`
6. WHEN the DoD walk ends, THE Executor SHALL remove probe pods, port-forwards, venvs, temporary scripts and script output, and the copied kubeconfig unless the User asks to keep the kubeconfig. `[D cluster]`
7. WHEN the DoD walk ends, THE Executor SHALL return Locust to the run state recorded in Task 0b. `[D cluster]`
8. WHEN cleanup ends, THE Executor SHALL report each removed item, and each kept item with the reason. `[D offline]`

### Requirement 9: Pinning and repeated failures

**User Story:** As the abox owner, I want every package, binary and chart pinned to an exact, recorded version, and repeated failures stopped and diagnosed, so that results can be reproduced and no time goes into blind retries.

#### Acceptance Criteria

1. THE Executor SHALL install Python packages only into uv venvs, pinned with `==`, and record the versions. `[all phases]`
2. THE Golden_Probe SHALL pin `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http` and `opentelemetry-exporter-otlp-proto-grpc` to exact versions in `docs/observability/requirements.txt`. `[A offline]`
3. THE Executor SHALL download the `otelcol-contrib` 0.160.0 darwin_arm64 release from `github.com/open-telemetry/opentelemetry-collector-releases`, and any `jaeger` 2.21.0 binary, by exact release, verify each published checksum before first use, and record version and checksum. `[A offline]`
4. IF a downloaded binary's checksum differs from the published checksum, THEN THE Executor SHALL delete the binary and stop. `[A offline]`
5. THE Exercise_Config SHALL pin each added chart to an exact version, with chart `jaeger` at `4.14.0`. `[A offline]`
6. THE Executor SHALL pin the MLflow and Phoenix read-back clients to the server versions recorded in Task 0b. `[C cluster]`
7. IF the same approach fails twice, THEN THE Executor SHALL stop, diagnose the root cause, and report to the User before switching approach. `[all phases]`

### Requirement 10: Spec copies and sync

**User Story:** As the abox owner, I want this spec's canonical, publish-safe copy committed under `docs/specs/` with a landing page in `docs/README.md`, mirrored byte-identically to `.kiro/specs/` for the IDE and re-synced at each phase end, so that every exact decision behind the exercise is reviewable in git.

#### Acceptance Criteria

1. WHEN a sync commit is prepared, THE Executor SHALL confirm, before committing, that the Spec_Copies are byte-identical, with `cmp` exiting 0 for each pair. `[all phases]`
2. WHEN the User approves the spec, THE Executor SHALL stage `docs/README.md` plus `docs/specs/genai-observability-comparison/*.md` (`requirements.md`, `design.md` and `tasks.md`) by name and commit only those four files as `docs: add genai-observability-comparison spec`, before any Phase A change. `[A offline]`
3. WHEN Phase A, B or C ends, THE Executor SHALL run the Spec_Sync of the Spec_Mirror's `tasks.md` back to the Canonical_Spec, carrying the task-status ticks made in the IDE, and commit the result as `docs: sync genai-observability-comparison spec (Phase <X>)`. `[all phases]`
4. IF the phase-end Spec_Sync leaves no uncommitted change in the Canonical_Spec or the Spec_Readme, THEN THE Executor SHALL skip that phase's sync commit and record that no change was needed. `[all phases]`
5. THE Executor SHALL stage only `docs/README.md` and `docs/specs/genai-observability-comparison/*.md` in each spec commit, leaving `.kiro/` unstaged. `[all phases]`
6. WHEN Task 12 is ready to push `feat/otel-demo`, THE Executor SHALL land the Phase D Spec_Sync, committed as `docs: sync genai-observability-comparison spec (Phase D)`, before the push. `[D offline]`
7. WHEN the DoD walk ends, THE Executor SHALL put the close-out ticks into one final local sync commit and push that commit only after the User's explicit confirmation. `[D offline]`
8. THE Spec_Copies SHALL refer to Workstation files only by repo-relative paths, by paths under `/tmp/abox-observability/`, or by the generic name `~/.kube/config`. `[all phases]`
9. THE Spec_Copies SHALL name the EKS context only as "an unrelated EKS context in `~/.kube/config`", with no AWS account ID, no EKS ARN and no Secret value. `[all phases]`
10. WHEN a spec commit is prepared, THE Executor SHALL run the Secret_Scan over `docs/README.md` and `docs/specs/genai-observability-comparison/`, and search the same files for home-directory paths (regex `/Users/[A-Za-z0-9._-]+/`), ARNs (regex `arn:aws:[a-z0-9-]+:`) and 12-digit numbers (regex `\b[0-9]{12}\b`). `[all phases]`
11. IF a check of criterion 10.10 finds a hit, THEN THE Executor SHALL stop the spec commit and report the file and line without printing the matched value. `[all phases]`
12. THE Executor SHALL leave the scratch plan file `/tmp/abox-observability/approved-plan-v2.md` out of every commit, because the file contains an AWS account ID and home-directory paths, and keep the Spec_Copies free of any dependency on that file. `[all phases]`
13. WHEN the Executor edits a spec file for any change other than a task-status tick, THE Executor SHALL make the edit in the Canonical_Spec, then run the Spec_Sync to the Spec_Mirror (`cp`, then `cmp`) before any other edit or commit. `[all phases]`
14. THE Spec_Readme SHALL link the Canonical_Spec's `requirements.md`, `design.md` and `tasks.md` in the "Read first" list. `[A offline]`
15. WHILE Phases A to D run, THE Executor SHALL edit only the Status line of the Spec_Readme, leaving the reviewer roadmap checkboxes to the User. `[all phases]`

### Requirement 11: Baseline docs reconciliation (Phase 0)

**User Story:** As the abox owner, I want the Root_Docs reconciled with the checked-in manifests before the exercise changes anything, so that every later phase, and the Phase D doc updates, start from docs that describe the repo as built.

#### Acceptance Criteria

1. WHEN the add commit of criterion 10.2 has landed, THE Executor SHALL complete Phase 0 before Phase A starts and before any Exercise_Config change. `[0 offline]`
2. WHILE Phase 0 runs, THE Executor SHALL compare every version, path, tool and release-behavior statement in the Root_Docs with the Baseline_Manifests at the commit of criterion 10.2, and list each mismatch with file and line. `[0 offline]`
3. WHILE Phase 0 runs, THE Executor SHALL correct at least these known mismatches in the Root_Docs `[0 offline]`:
   - kagent: chart 0.10.1 (`releases/kagent.yaml`, `releases/crds/kagent-crds.yaml`), where CODEBASE.md says kagent is pinned to 0.7.23 and REVIEW.md and EVALS.md treat 0.7.23 as the pin; `releases/kagent.yaml` handles the `+` build-metadata problem with a postRenderer and explicit image tags;
   - Phoenix: chart `phoenix-helm` 12.0.14 (`releases/phoenix.yaml`), where README.md and CODEBASE.md say 12.0.10;
   - agentgateway: chart 1.5.0 (`releases/agentgateway.yaml`), where README.md says v2.2.1;
   - MLflow: a row for MLflow (`releases/mlflow.yaml`) in README.md's component table, which lacks one;
   - RSIP path: this branch polls `releases-otel-demo` under the configured registry (`bootstrap/variables.tf`, `bootstrap/flux.tf`), where README.md names `oci://ghcr.io/den-vasyliev/abox/releases`;
   - release guidance: the RSIP picks the highest semver tag (`bootstrap/flux.tf`) and `make push` bumps the patch with no ceiling (`Makefile`), so the lexicographic-sort warning and the patch-version ceiling go from every Root_Doc that states them;
   - kind: every kind or node-image version that a Root_Doc states, set to kind v0.33.0 (`scripts/setup.sh`) and node image `kindest/node:v1.37.0` (`bootstrap/variables.tf`).
4. WHILE Phase 0 runs, THE Executor SHALL change only the Root_Docs, leaving every Baseline_Manifest unchanged. `[0 offline]`
5. IF a Baseline_Manifest breaks a rule that a Root_Doc states, THEN THE Executor SHALL keep the manifest unchanged and record the case as a Known_Deviation next to the rule, naming the file and field (for example `ref.tag: latest` in `releases/graph-otel-demo.yaml` and `releases/pages-triage.yaml`). `[0 offline]`
6. WHEN the changed Root_Docs pass the checks of criterion 10.10, THE Executor SHALL stage the changed Root_Docs by name and commit only those files as `docs: <summary>`, with the mismatch list of criterion 11.2 in the body, before any Exercise_Config change. `[0 offline]`
7. WHEN the Phase 0 commit lands, THE Executor SHALL repeat the comparison of criterion 11.2 and confirm that no mismatch remains other than the recorded Known_Deviations. `[0 offline]`
8. THE Canonical_Spec SHALL state that `scripts/setup.sh` installs kind v0.33.0 for node image `kindest/node:v1.37.0` (`bootstrap/variables.tf`), and that the Workstation's kind 0.27.0 is never used. `[0 offline]`
9. WHEN Task 12 updates README.md and CODEBASE.md, THE Executor SHALL repeat the comparison of criterion 11.2 against the final Baseline_Manifests, Exercise_Config included, and correct any new mismatch in a `docs: …` commit, so that only recorded Known_Deviations remain. `[D offline]`

## DoD traceability

| DoD | Checkbox (short form) | Criteria |
|---|---|---|
| 1.1 | Interface_Matrix with three columns and the listed rows | 1.1, 1.2, 1.4, 1.26 |
| 1.2 | Every cell cites a versioned doc URL or "observed in abox" with a date | 1.3, 1.5 |
| 1.3 | Collector documented as built; diagram matches the deployed config | 1.6, 1.7 |
| 1.4 | Golden-span probe sent directly to each Backend, known trace ID, one convention per child span | 1.8 to 1.20 |
| 1.5 | Each copy found in the named Tenant and read back by ID through UI and API | 1.21 to 1.25 |
| 1.6 | Dedicated UI versus raw attributes recorded per Backend | 1.27 |
| 1.7 | Probe re-runnable from a doc snippet; nothing left running | 1.28 to 1.30, 8.6 |
| 2.1 | All config in `releases/`, reconciled from a pushed tag, `flux get all` Ready; manual steps written down | 2.1 to 2.64, 2.65 to 2.67, 5.13 |
| 2.2 | Coverage: every Source has a trace ID in each Backend | 2.68 |
| 2.3 | Tenants per Source; Astronomy agent shares otel-demo; Jaeger-only spans explained | 2.69, 2.70 |
| 2.4 | Parity per GenAI_Source | 2.61, 2.71, 2.72 |
| 2.5 | GenAI minimum: LLM span with model name and tool-call span, or documented gap and User decision | 2.51, 2.73, 2.74 |
| 2.6 | GenAI_Inventory per Source | 2.50, 2.75 |
| 2.7 | Fixed, documented workload | 2.29, 2.30, 2.76 to 2.78, 2.82 |
| 2.8 | Load run with all exporters live | 2.83 to 2.88 |
| 2.9 | Evidence saved durably, Jaeger traces as JSON | 2.81, 2.90 |
| 2.10 | No Backend exposed; committed evidence passes the Secret_Scan | 2.91, 2.92, 7.1 |
| 3.1 | `OBSERVABILITY.md` at the root, README link and table rows, Phoenix version fixed | 3.1 to 3.3, 11.3 |
| 3.2 | Opening framing | 3.4 |
| 3.3 | One trace, three views, per GenAI_Source | 3.5 |
| 3.4 | Eleven dimensions with per-Backend verdicts and evidence | 3.6 to 3.18 |
| 3.5 | Load results as numbers, cassette-latency caveat | 3.19, 3.20 |
| 3.6 | Verdict per use case and recommended default setup | 3.21 |
| 3.7 | Claims linked, docs-only claims labelled, versions pinned | 3.22 to 3.25 |
| 3.8 | Reproduce section that works without questions | 3.26, 3.27 |
| Exit | Reviewer_Exit_Criteria: source-of-truth decision recorded, Root_Docs match the manifests, safety gates resolved, release objects Ready, every required Source traced in all three Backends, conclusions reproducible from sanitized evidence | 5.18 to 5.20, with evidence from 10.2, 11.1 to 11.9, 6.12, 7.9 to 7.16, 2.66, 2.68, 3.27, 2.92 and 8.3 |
