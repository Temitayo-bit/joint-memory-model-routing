"""Reproducible RunPod/vLLM launch command generator. Does not execute anything."""

from __future__ import annotations

import shlex
from typing import Any, Dict, List, Mapping

from experiments.text_baseline.constants import FIXED_GENERATION

VLLM_IMAGE_NAME = "vllm/vllm-openai"
VLLM_VERSION = "v0.29.0"
# Digested from the 2026-09-11 smoke session; prefer digest over a mutable tag.
VLLM_IMAGE_DIGEST = "sha256:c2914767605584b6d8f45686b82de173ecc99e781897aa3d0a66dacd72c51ae1"
VLLM_IMAGE = "%s@%s" % (VLLM_IMAGE_NAME, VLLM_IMAGE_DIGEST)
VLLM_IMAGE_TAG = "%s:%s" % (VLLM_IMAGE_NAME, VLLM_VERSION)

PINNED_MODELS: Dict[str, Dict[str, str]] = {
    "small": {
        "alias": "small",
        "model_id": "Qwen/Qwen3-4B-AWQ",
        "revision": "74d4bd2bd4bff9cafc9345221320bffb08b406a3",
        "quantization": "awq",
    },
    "large": {
        "alias": "large",
        "model_id": "Qwen/Qwen3-14B-AWQ",
        "revision": "31c69efc29464b6bb0aee1398b5a7b50a99340c3",
        "quantization": "awq",
    },
}


class LaunchSpecError(ValueError):
    """Invalid launch generation request."""


def build_vllm_args(model_key: str, *, host: str = "0.0.0.0", port: int = 8000) -> List[str]:
    if model_key not in PINNED_MODELS:
        raise LaunchSpecError("model_key must be small or large")
    pinned = PINNED_MODELS[model_key]
    # Fixed sampling remains a per-request body; --generation-config vllm avoids
    # silently substituting a Hugging Face generation_config.json for defaults.
    return [
        "--host",
        host,
        "--port",
        str(port),
        "--model",
        pinned["model_id"],
        "--revision",
        pinned["revision"],
        "--quantization",
        pinned["quantization"],
        "--generation-config",
        "vllm",
        "--dtype",
        "auto",
        "--max-model-len",
        "8192",
    ]


def render_docker_command(model_key: str, *, host: str = "0.0.0.0", port: int = 8000) -> str:
    args = build_vllm_args(model_key, host=host, port=port)
    tokens = [
        "docker",
        "run",
        "--rm",
        "--gpus",
        "all",
        "-p",
        "%s:%s" % (port, port),
        VLLM_IMAGE,
        *args,
    ]
    return " ".join(shlex.quote(part) for part in tokens)


def render_runpod_start_command(model_key: str, *, host: str = "0.0.0.0", port: int = 8000) -> str:
    """Docker CMD / RunPod start command for the pinned vLLM image."""
    return " ".join(shlex.quote(part) for part in build_vllm_args(model_key, host=host, port=port))


def launch_bundle(model_key: str, *, host: str = "0.0.0.0", port: int = 8000) -> Dict[str, Any]:
    pinned = dict(PINNED_MODELS[model_key])
    return {
        "not_executed": True,
        "note": (
            "Command generator only. Codex/user must provision RunPod, start the pod, "
            "record costs, and terminate it. This tool never launches remote compute."
        ),
        "image": VLLM_IMAGE,
        "image_tag": VLLM_IMAGE_TAG,
        "image_digest": VLLM_IMAGE_DIGEST,
        "vllm_version": VLLM_VERSION,
        "model": pinned,
        "fixed_generation": dict(FIXED_GENERATION),
        "runpod_start_command": render_runpod_start_command(model_key, host=host, port=port),
        "docker_run_command": render_docker_command(model_key, host=host, port=port),
        "client_env": {
            "TEXT_BASELINE_SMALL_MODEL_ID": PINNED_MODELS["small"]["model_id"],
            "TEXT_BASELINE_LARGE_MODEL_ID": PINNED_MODELS["large"]["model_id"],
            "TEXT_BASELINE_MODEL_BASE_URL": "<pod-proxy-base-url>",
            "TEXT_BASELINE_MODEL_BEARER": "<inference-bearer-from-env-only>",
        },
    }


def launch_bundle_both(*, host: str = "0.0.0.0", port: int = 8000) -> Mapping[str, Any]:
    return {
        "not_executed": True,
        "vllm_version": VLLM_VERSION,
        "image": VLLM_IMAGE,
        "image_digest": VLLM_IMAGE_DIGEST,
        "fixed_generation": dict(FIXED_GENERATION),
        "small": launch_bundle("small", host=host, port=port),
        "large": launch_bundle("large", host=host, port=port),
    }
