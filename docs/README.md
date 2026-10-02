# GenAI observability comparison

**Status:** Planned. This work will compare Jaeger (standard OpenTelemetry), MLflow, and Phoenix using the same GenAI and workload traces.

## Scope and source of truth

The Bridge Collector sends every bridged span to Jaeger before routing tenant-specific copies to MLflow and Phoenix. The Golden Probe bypasses that collector and sends a known trace directly to all three backends. The study then evaluates parity, GenAI visibility, operational behavior, and reproducibility.

- [Requirements](specs/genai-observability-comparison/requirements.md) — acceptance criteria, safety constraints, and evidence requirements.
- [Design](specs/genai-observability-comparison/design.md) — canonical implementation, decision, validation, and release plan.

`docs/specs/genai-observability-comparison/` is canonical. The matching `.kiro/specs/genai-observability-comparison/` files are an untracked IDE mirror: synchronize content edits from `docs/specs/` to `.kiro/specs/`, and synchronize IDE task ticks back at phase boundaries.

## Reviewer roadmap

### Phase 0 — reconcile baseline documentation
**Offline; Root_Docs only; required before implementation.**

- [ ] Compare every version, path, tool, and release-behavior claim in `README.md`, `CODEBASE.md`, `REVIEW.md`, and `EVALS.md` with the baseline manifests.
- [ ] Record each mismatch with file and line; correct only root documentation and record any unavoidable manifest/document conflict as a `Known_Deviation`.
- [ ] Re-check corrected facts, run the secret and publish-safety scans, and confirm no files under `releases/`, `bootstrap/`, or `scripts/` changed.
- [ ] Commit the verified Phase 0 documentation changes before Phase A begins.

### Phase A — build and validate offline
**No cluster access or writes. End with the Phase A review gate.**

- [ ] Render and validate Jaeger, the Bridge Collector, Phoenix, and kagent with pinned versions and verified checksums where required.
- [ ] Build the Golden Probe and verify its dry-run trace tree; keep its packages pinned.
- [ ] Record the Phoenix routing decision, expected kagent trace identity, chart-added collector processors, and all other applicable decisions in the Decision Log.
- [ ] Prove the rendered configuration has no public UI route for Jaeger, MLflow, or Phoenix; run the Secret_Scan over all changed files and scratch scripts.
- [ ] Review the Phase A evidence bundle: pins, renders, collector validation, Golden Probe output, exposure check, scan results, and Decision Log. **Explicit reviewer approval is required before Phase B.**

### Phase B — read-only preflight and consent
**Read-only cluster access only until approvals are granted.**

- [ ] Use an isolated kubeconfig and confirm the target cluster identity, deployed versions, existing experiments, secrets by name, and release source.
- [ ] Review the live-versus-planned diff, exact task order, raw-evidence locations, rollback plan, cleanup plan, and potential release pruning.
- [ ] Decide the Kagent Exposure Gate: restrict the public route or explicitly accept the risk. An unresolved gate blocks every cluster write.
- [ ] Separately approve suspension of `flux-system/releases`. No cluster write occurs while either the exposure decision or suspend consent is pending.

### Phase C — apply, verify, and capture evidence
**Apply one task document at a time, in recorded commit order; verify each task before continuing.**

- [ ] Apply any approved kagent-route restriction first, then Jaeger, Golden Probe checks, collector fan-out, Phoenix routing, Astronomy Shop trace exercises, kagent model/tracing changes, tenant routing, and fixed workloads.
- [ ] Run optional Task 9 only after the Task 7 decision and time-box it to 60 minutes.
- [ ] Before every write, confirm the target cluster and that Flux remains suspended; use only the task-specific manifest document.
- [ ] Prove Golden Trace parity, then capture each required source in Jaeger, MLflow, and Phoenix with span counts and explained differences.
- [ ] Record exporter failures, queues, restarts, resource usage, PVC growth, retention findings, and the fixed-workload/load-run results. Export evidence before Jaeger's bounded memory store evicts it.

### Phase D — publish, release, and close out

- [ ] Publish `OBSERVABILITY.md`, the Golden Probe, pinned requirements, and sanitized evidence under `docs/observability/`.
- [ ] Label every claim as **observed in abox** or **docs only**; include trace/API/screenshot evidence, reproduction commands, version pins, unverified items, and outstanding risks.
- [ ] Synchronize the canonical spec and IDE mirror, update the root documentation required by Task 12, then repeat the Phase 0 reconciliation against final manifests.
- [ ] Release only with explicit consent; confirm Flux readiness, inspect remaining `abox-exercise` field ownership, and complete the documented cleanup.

## Key decision gates

| Decision | Reviewer expectation |
|---|---|
| Phoenix routing | Use OTLP/HTTP headers only when the observed version supports them; otherwise approve the resource-attribute fallback. |
| Kagent trace identity | Base the final routing row on Task 7 observations, not offline expectations alone. |
| Kagent exposure | Resolve before suspension or any cluster write; re-probe a chosen restriction before Task 1. |
| Optional Task 9 | Do not begin unless explicitly accepted after Task 7; stop at the 60-minute limit if no viable route exists. |

## Required deliverables

- `docs/observability/golden_probe.py` and pinned `requirements.txt`
- Sanitized evidence in `docs/observability/`
- Root-level `OBSERVABILITY.md` with the interface matrix, collector topology, parity/coverage tables, GenAI inventory, load results, verdict, and reproduction steps
- Updated Decision Log and synchronized canonical specifications

## Reviewer exit criteria

Approve completion only when all six conditions hold:

- [ ] The source-of-truth decision is recorded in the canonical specification.
- [ ] Root documentation matches manifests, apart from recorded `Known_Deviations`.
- [ ] The Phase A review gate, Kagent Exposure Gate, and every consent checkpoint are resolved and recorded.
- [ ] All release objects report Ready in the captured Flux status.
- [ ] Every required GenAI and volume source has an evidence trace in Jaeger, MLflow, and Phoenix.
- [ ] Conclusions can be reproduced from sanitized evidence and a passing Secret_Scan.
