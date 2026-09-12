# GPU session log

Record one row per GPU session. Amounts are estimates until confirmed by the provider billing view.

| Date | Purpose | GPU / hourly rate | Start–end | Estimated cost | Durable outputs saved | Pod terminated confirmed? |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-09-11 | Provisioning attempt for S0 smoke; replaced before inference after the user requested a lower-memory option | RTX PRO 6000 MIG 24GB secure / $0.59 per hour | About 10:49-10:51 EDT | Provider line item pending (do not use the combined balance delta here) | No inference output | Yes; Pod `i7x2g39782kytg` deleted and the subsequent Pod list was empty |
| 2026-09-11 | Paired Q10 S0/S1 smoke on the small model; deployment and importer validation only | RTX 3090 secure / $0.50 per hour | 10:52:53-about 11:06 EDT | Provider line item pending (do not use the combined balance delta here) | Reproducibility summary in `2026-09-11-text-s0-s1-smoke.md`; raw local artifacts under ignored `artifacts/smoke/2026-09-11-s0-s1/` | Yes; Pod `izkvn8qqesqdls` deleted, Pod list empty, and current spend $0/hour |

Aggregate note (recorded once): observed all-in RunPod balance delta for both 2026-09-11 pods together was **$0.1292403981**. That combined amount is not allocated across the two rows until provider line items are available.

Semester cap: **$75**. Do not start an unplanned session that could exceed the remaining budget.
