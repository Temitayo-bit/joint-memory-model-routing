# RunPod session runbook

## Before starting a pod

1. Confirm the session has a defined purpose: integration test, planned evaluation condition, rehearsal, or demo.
2. Record the planned GPU, hourly rate shown by RunPod, expected duration, and budget remaining in `gpu-session-log.md`.
3. Confirm the repository is pushed and that required durable memory is in Supabase or another approved store.
4. Do not place secrets in commits, logs, screenshots, or shared experiment artifacts.
5. If using a Network Volume, create or attach it in the same RunPod region as the Pod. It may contain only non-sensitive model weights, container caches, and setup material. Recheck its displayed monthly price before creating it.

## During the session

1. Use a self-hosted model server and record the exact image, model revision, quantization, configuration, and start/end time needed to reproduce the run.
2. Save aggregate, non-sensitive outputs and configuration to the repository or approved durable storage.
3. Keep the pod private; do not expose an unauthenticated model endpoint to the public internet.

## Required shutdown

At the end of active work, rehearsal, or demo:

1. Push code and save approved experiment artifacts.
2. Verify that nothing required remains only on the pod volume.
3. Terminate the pod. Do not merely disconnect from it or leave it stopped with retained storage by default.
4. Delete attached pod storage. A Network Volume may stay only for a documented short-term setup/model-cache reason; it is billed independently after the Pod ends, so record its monthly rate and planned deletion date.
5. Complete the actual cost, retained-volume decision, and termination confirmation in `gpu-session-log.md`.

If termination cannot be verified, report that immediately; do not claim the session is shut down.
