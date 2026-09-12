"""Command-line entry for mock, export, import, live run, embeddings, and launch specs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from experiments.text_baseline.embeddings import DEFAULT_MODEL_REVISION, build_embedding_bundle
from experiments.text_baseline.fixtures import DATA_DIR
from experiments.text_baseline.hashing import canonical_json
from experiments.text_baseline.import_responses import import_responses, load_json
from experiments.text_baseline.io_guard import prepare_output_dir, refuse_existing
from experiments.text_baseline.live_runner import run_live
from experiments.text_baseline.run_builder import build_requests, mock_record
from experiments.text_baseline.runpod_launch import launch_bundle, launch_bundle_both


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    refuse_existing(path)
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")


def cmd_mock(args: argparse.Namespace) -> int:
    bundle = build_requests(Path(args.data_dir), repeats=args.repeats, seed=args.seed)
    records = [mock_record(request) for request in bundle["requests"]]
    output = prepare_output_dir(Path(args.output))
    _write_json(output / "manifest.json", bundle["manifest"])
    _write_json(output / "requests.json", {"requests": bundle["requests"]})
    _write_json(
        output / "records.json",
        {
            "not_a_research_result": True,
            "records": records,
        },
    )
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    bundle = build_requests(Path(args.data_dir), repeats=args.repeats, seed=args.seed)
    output = prepare_output_dir(Path(args.output))
    _write_json(output / "manifest.json", bundle["manifest"])
    _write_json(output / "requests.json", {"requests": bundle["requests"]})
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    requests_payload = load_json(Path(args.requests))
    if "requests" not in requests_payload:
        raise ValueError("requests JSON must contain a requests array")
    manifest_path = Path(args.manifest) if args.manifest else Path(args.requests).with_name("manifest.json")
    bundle = {"manifest": load_json(manifest_path), "requests": requests_payload["requests"]}
    responses = load_json(Path(args.responses))
    rates = load_json(Path(args.market_rates)) if args.market_rates else None
    imported = import_responses(
        bundle,
        responses,
        market_rates=rates,
        session_processing_total=args.session_processing_total,
    )
    output = prepare_output_dir(Path(args.output))
    _write_json(output / "manifest.json", imported["manifest"])
    _write_json(output / "records.json", {"not_a_research_result": True, "records": imported["records"]})
    return 0


def cmd_run_live(args: argparse.Namespace) -> int:
    requests_payload = load_json(Path(args.requests))
    requests = requests_payload.get("requests")
    if not isinstance(requests, list):
        raise ValueError("requests JSON must contain a requests array")
    result = run_live(
        requests,
        Path(args.output),
        transport=args.transport,
        conditions=args.condition,
        question_ids=args.question_id,
        repeats=args.repeat,
        max_requests=args.max_requests,
        hourly_rate_usd=args.hourly_rate,
        timeout_s=args.timeout_s,
        max_response_bytes=args.max_response_bytes,
        session_id=args.session_id,
        pod_id=args.pod_id,
        gpu_type=args.gpu_type,
        model_revision=args.model_revision,
        small_model_revision=args.small_model_revision,
        large_model_revision=args.large_model_revision,
        quantization=args.quantization,
        server_version=args.server_version,
        snapshot_id=args.snapshot_id,
        embeddings_path=Path(args.embeddings) if args.embeddings else None,
        resume=not args.no_resume,
    )
    print(
        "Wrote %s responses to %s"
        % (len(result["responses"]), result["checkpoint"])
    )
    return 0


def cmd_prepare_embeddings(args: argparse.Namespace) -> int:
    bundle = build_embedding_bundle(
        Path(args.data_dir),
        model_id=args.model_id,
        model_revision=args.model_revision,
    )
    output = Path(args.output)
    if output.exists() and output.is_dir():
        path = output / "embeddings-bundle.json"
    else:
        path = output
        path.parent.mkdir(parents=True, exist_ok=True)
    refuse_existing(path)
    path.write_text(canonical_json(bundle) + "\n", encoding="utf-8")
    print("Wrote embedding bundle to %s" % path)
    return 0


def cmd_print_runpod_launch(args: argparse.Namespace) -> int:
    if args.model == "both":
        payload = launch_bundle_both(host=args.host, port=args.port)
    else:
        payload = launch_bundle(args.model, host=args.host, port=args.port)
    text = canonical_json(payload)
    if args.output:
        path = Path(args.output)
        refuse_existing(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print("Wrote launch spec to %s" % path)
    else:
        print(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fixed text-baseline harness. Mock output is not a research result.",
    )
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    sub = parser.add_subparsers(dest="command", required=True)

    mock = sub.add_parser("mock")
    mock.add_argument("--output", required=True)
    mock.add_argument("--seed", type=int, default=0)
    mock.add_argument("--repeats", type=int, default=1)
    mock.set_defaults(func=cmd_mock)

    export = sub.add_parser("export-requests")
    export.add_argument("--output", required=True)
    export.add_argument("--seed", type=int, default=0)
    export.add_argument("--repeats", type=int, default=1)
    export.set_defaults(func=cmd_export)

    imported = sub.add_parser("import-responses")
    imported.add_argument("--output", required=True)
    imported.add_argument("--requests", required=True)
    imported.add_argument("--responses", required=True)
    imported.add_argument("--manifest")
    imported.add_argument("--market-rates")
    imported.add_argument("--session-processing-total", type=float)
    imported.set_defaults(func=cmd_import)

    live = sub.add_parser(
        "run-live",
        help="Execute exported requests against a model endpoint or Edge Function.",
    )
    live.add_argument("--requests", required=True, help="Exported requests.json path")
    live.add_argument("--output", required=True, help="Output directory; resumes if responses.json exists")
    live.add_argument("--transport", choices=("direct", "edge"), default="direct")
    live.add_argument("--condition", action="append", dest="condition")
    live.add_argument("--question-id", action="append", dest="question_id")
    live.add_argument("--repeat", action="append", dest="repeat", type=int)
    live.add_argument("--max-requests", type=int)
    live.add_argument("--hourly-rate", type=float, help="USD/hour used for active-inference processing cost")
    live.add_argument("--timeout-s", type=float, default=70.0)
    live.add_argument("--max-response-bytes", type=int, default=65536)
    live.add_argument("--session-id")
    live.add_argument("--pod-id")
    live.add_argument("--gpu-type")
    live.add_argument("--model-revision", help="Deprecated single revision; prefer --small/--large-model-revision")
    live.add_argument("--small-model-revision")
    live.add_argument("--large-model-revision")
    live.add_argument("--quantization")
    live.add_argument("--server-version")
    live.add_argument("--snapshot-id", help="Required for --transport edge")
    live.add_argument("--embeddings", help="Local embedding bundle for S1/L1 edge calls")
    live.add_argument("--no-resume", action="store_true")
    live.set_defaults(func=cmd_run_live)

    embeds = sub.add_parser(
        "prepare-embeddings",
        help="Generate a local MiniLM embedding JSON bundle. Does not write to Supabase.",
    )
    embeds.add_argument("--output", required=True)
    embeds.add_argument("--model-id", default="sentence-transformers/all-MiniLM-L6-v2")
    embeds.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    embeds.set_defaults(func=cmd_prepare_embeddings)

    launch = sub.add_parser(
        "print-runpod-launch",
        help="Print a pinned vLLM launch command. Does not execute or provision RunPod.",
    )
    launch.add_argument("--model", choices=("small", "large", "both"), default="both")
    launch.add_argument("--host", default="0.0.0.0")
    launch.add_argument("--port", type=int, default=8000)
    launch.add_argument("--output")
    launch.set_defaults(func=cmd_print_runpod_launch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
