# Hekayti implementation audit

## Baseline

The repository is a local Python package plus `demo/server.py` and
`demo/index.html`. It has no database, deployed service, or production queue;
local JSON and image files are the intended persistence mechanism.

Before this implementation, `pytest -q` passed 8 tests. The demo already had
real Bailian text, vision, and image calls, including a direct DashScope
multimodal adapter. Its successful evidence was one three-arm, one-scene run:
`demo/experiments/run_20261023_030024/`.

## Existing architecture

- `hekayti/models.py`: provider-neutral character, scene, reference, and
  strategy models.
- `hekayti/prompting.py`: deterministic provider-neutral prompt compiler.
- `demo/server.py`: local HTTP bridge, photo upload, vision profile call,
  story planning, direct DashScope image-reference calls, artifact persistence,
  and manual rating persistence.
- `demo/index.html`: user/developer tabs, parent flow, manual prompt export,
  provider testing controls, and comparison UI.

## Gaps found

- Approved character identity was not versioned or persisted as a canonical
  record.
- Story source hashes and exact scene-to-source records were not modeled.
- The browser experiment submitted one hardcoded scene instead of the planner's
  complete scene list.
- Generation state transitions and per-attempt manifests were implicit.
- QA was limited to manual ratings; deterministic artifact checks were absent.
- Existing real evidence proved reference acceptance, not cross-scene identity
  consistency.

## Implementation order

1. Add local file-backed character and story version records.
2. Add explicit scene plans, generation manifests, legal state transitions, and
   deterministic QA.
3. Wire the browser experiment to consume validated planner output and preserve
   UTF-8 source text.
4. Add provider-independent semantic QA and multi-scene integration evidence.

## Risks and limitations

- A provider response containing references proves transport, not identity
  quality.
- Deterministic QA can validate metadata and integrity, but identity and scene
  semantics still require a replaceable vision evaluator and human review.
- Existing historical artifacts contain corrupted Arabic text from an earlier
  Windows encoding path and must not be treated as fidelity evidence.
