# Text benchmark v2 implementation plan

Date: 2026-09-13  
Status: executable once; do not run a live experiment from this plan  
Spec: `docs/specs/2026-09-13-text-benchmark-v2-design.md`

## Objective

Add a versioned synthetic text benchmark that can test both long-term-memory retrieval and small-versus-large model selection without replacing the recorded twelve-question pilot. The implementation creates a sixteen-question development split and a forty-eight-question held-out split, records three pre-registered generation seeds, and makes the harness validate named datasets safely. It does not create a controller or report experimental results.

## File map

- Create: `docs/specs/2026-09-13-text-benchmark-v2-design.md`
- Create: `docs/plans/2026-09-13-text-benchmark-v2.md` (this file)
- Create: dataset manifests, memory fixtures, question fixtures, and scoring anchors for `benchmark-v2-dev` and `benchmark-v2-eval`
- Modify: fixture loading, schedule/request construction, CLI plumbing, live request validation, and import manifest handling as required for named datasets and generation seeds
- Modify: Python and Deno tests plus the text-baseline verification script only where necessary to enforce the new contract
- Modify: harness/operator documentation and the evaluation protocol to distinguish the legacy pilot, development split, and held-out benchmark-v2 split

## Tasks

1. Inspect the current `origin/main` working tree and retain the legacy fixture directory exactly as it is. Add an explicit named-dataset layout for benchmark v2; do not move, rename, or rehash the pilot files.
2. Add dataset manifests that declare identifier, version, split, question count, four-stratum balance, and allowed generation seeds. The development split has 16 questions; the held-out split has 48, with 12 questions in each stratum.
3. Author all synthetic fixtures, required-evidence mappings, binary anchors, and diagnostic scoring rubrics before any benchmark-v2 model request. Keep anchors and diagnostic-only fields out of question/prompt loading.
4. Refactor fixture validation so the legacy twelve-question contract stays enforced for the legacy dataset while benchmark v2 is checked against its manifest. Reject duplicate question IDs, duplicate evidence IDs, split overlap, unknown strata/tags, missing anchors, and any anchor-bearing prompt fixture.
5. Extend schedule/request construction with a request-level `generation_seed`. Preserve the existing schedule shuffle seed separately. Permit only benchmark-v2 seeds 42, 43, and 44, and calculate expected cells from question count × four conditions × generation-seed count.
6. Ensure prompts, Edge allow-lists, evidence hashes, manifests, response checkpoints, and imports preserve the dataset identifier/version/split and generation seed. Do not send scoring anchors, required evidence, or diagnostic labels to a model.
7. Add tests covering legacy compatibility; 16/48 fixture counts; 12-per-stratum evaluation balance; split disjointness; deterministic schedule ordering; all three generation seeds; 576 held-out cells; prompt leakage protection; import rejection for a mismatched dataset or generation seed; and unchanged S0/L0 retrieval behavior.
8. Update the harness README, evaluation protocol, and operator runbook. Clearly label the development split as non-reportable and benchmark-v2 evaluation as held-out. State that the current retriever remains `pilot_hybrid_v2_1` and that a controller is not part of this change.
9. Run `make test`, `make build`, and `git diff --check`. The complete Python and Deno suites must run; if Deno is unavailable, install or make it available before claiming the gates pass.
10. Submit the implementation through a feature-branch pull request. Do not merge it, apply a Supabase migration, load a snapshot, deploy an Edge Function, provision RunPod, or run live inference in that pull request.

## Live evaluation follows only after the implementation is merged

1. Verify the merged code, all checks, current RunPod availability/rate, budget remaining, and no active paid resource.
2. Build fresh embeddings and a new owner-scoped synthetic benchmark-v2 snapshot. Verify fixture and embedding hashes before any request.
3. Run a non-scored model readiness check on the same Secure Cloud GPU class for both models; record server and model identity.
4. Export development requests, collect development-only results, and preserve them separately. Do not alter held-out fixtures in response.
5. Export the 576 held-out requests. Run S0/S1 and L0/L1 with the same GPU class and fixed configuration except for model identity; collect all three pre-registered generation seeds.
6. Import only complete successful evidence, score against the frozen anchors, and report quality, retrieval, latency, cost, failures, durable artifacts, and confirmed teardown.
7. Terminate every pod and delete attached temporary storage immediately after its session. Do not design or evaluate the controller until the fixed text and voice baseline requirements are met.

## Constraints

- Preserve v1 and retrieval-v2.1 code, data, migrations, settings, and artifacts.
- Treat benchmark v2 as a new dataset condition, not as evidence that the large model is superior.
- Use synthetic data only; no real conversations, personal data, credentials, or audio recordings enter the repository.
- Keep RLS/JWT, `SECURITY INVOKER`, empty search path, Edge request allow-list, and top-four retrieval limit unchanged.
- Do not report development results as held-out findings.
- Do not perform a code review unless explicitly requested.
