# Local text-baseline harness

This package runs **fixed** conditions S0, S1, L0, and L1 on twelve synthetic questions. It does not implement a controller and does not claim experimental results.

Local lexical overlap retrieval is **plumbing validation**, not the semantic retrieval system.

## Modes

```sh
PYTHONPATH=. python3 -m experiments.text_baseline mock --output /tmp/text-baseline-mock --seed 0 --repeats 1
PYTHONPATH=. python3 -m experiments.text_baseline export-requests --output /tmp/text-baseline-export --seed 0 --repeats 1
PYTHONPATH=. python3 -m experiments.text_baseline import-responses --requests /tmp/text-baseline-export/requests.json --responses /path/to/measured.json --output /tmp/text-baseline-import
```

Mock mode writes placeholder answers and leaves latency, tokens, quality, and all three cost fields null. Existing output directories are refused.

Scoring anchors in `data/scoring_anchors.json` are not loaded when prompts are built.

The supervised live client in `live_client.py` only constructs the allow-listed JSON body. It does not call Supabase or a model server.
