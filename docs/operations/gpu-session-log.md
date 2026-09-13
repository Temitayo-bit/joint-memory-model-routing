# GPU session log

Record one row per GPU session. Amounts are estimates until confirmed by the provider billing view.

| Date | Purpose | GPU / hourly rate | Start–end | Estimated cost | Durable outputs saved | Shutdown / teardown status |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-09-11 | Provisioning attempt for S0 smoke; replaced before inference after the user requested a lower-memory option | RTX PRO 6000 MIG 24GB secure / $0.59 per hour | About 10:49-10:51 EDT | Provider line item pending (do not use the combined balance delta here) | No inference output | Yes; Pod `i7x2g39782kytg` deleted and the subsequent Pod list was empty |
| 2026-09-11 | Paired Q10 S0/S1 smoke on the small model; deployment and importer validation only | RTX 3090 secure / $0.50 per hour | 10:52:53-about 11:06 EDT | Provider line item pending (do not use the combined balance delta here) | Reproducibility summary in `2026-09-11-text-s0-s1-smoke.md`; raw local artifacts under ignored `artifacts/smoke/2026-09-11-s0-s1/` | Yes; Pod `izkvn8qqesqdls` deleted, Pod list empty, and current spend $0/hour |
| 2026-09-12 | Retrieval v2.1 S1 setup and failed Edge retries; no research score reported | PRO 6000 MIG 24GB secure / $0.60 per hour all-in while running | Multiple short windows before 23:51 EDT | About $0.19 observed from the dashboard balance across the setup windows; provider line items pending | Failed-attempt evidence under `artifacts/live/2026-09-12-text-small-edge-v2-1*`; preserved as setup failures, not research findings | Stopped at $0.00/hour; Pod `8699cfotscmsyb` retained temporarily for the corrected retry |
| 2026-09-12 to 2026-09-13 | Corrected retrieval v2.1 S1, 12/12 successful responses | PRO 6000 MIG 24GB secure / $0.60 per hour all-in while running | About 23:51-00:03 EDT | About $0.12 from elapsed-time estimate and delayed dashboard balance movement; provider line item pending | Raw successful responses under `artifacts/live/2026-09-13-text-small-edge-v2-1-combined/`; validated import under `artifacts/live/2026-09-13-text-small-edge-v2-1-import/` | Yes; Pod `8699cfotscmsyb` stopped and verified at $0.00/hour |
| 2026-09-13 | Retrieval v2.1 L1, 12/12 successful responses | RTX A6000 48GB secure / $0.54 per hour all-in while running | About 00:05-00:10 EDT | About $0.04 observed from the dashboard balance; provider line item pending | Raw responses under `artifacts/live/2026-09-13-text-large-edge-v2-1-final/`; validated import under `artifacts/live/2026-09-13-text-large-edge-v2-1-import/` | Yes; Pod `k8n6yeti0pf3be` stopped and verified at $0.00/hour |

Aggregate note (recorded once): observed all-in RunPod balance delta for both 2026-09-11 pods together was **$0.1292403981**. That combined amount is not allocated across the two rows until provider line items are available.

Semester cap: **$75**. Do not start an unplanned session that could exceed the remaining budget.
