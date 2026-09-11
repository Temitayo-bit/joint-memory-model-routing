"""Command-line entry for mock, export-requests, and import-responses."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict

from experiments.text_baseline.fixtures import DATA_DIR
from experiments.text_baseline.hashing import canonical_json
from experiments.text_baseline.import_responses import import_responses, load_json
from experiments.text_baseline.io_guard import prepare_output_dir, refuse_existing
from experiments.text_baseline.run_builder import build_requests, mock_record


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
