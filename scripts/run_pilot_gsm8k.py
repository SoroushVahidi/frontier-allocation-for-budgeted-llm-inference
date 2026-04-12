#!/usr/bin/env python3
"""Run the lightweight GSM8K pilot experiment."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.branching import APIBranchGenerator, SimulatedBranchGenerator
from experiments.controllers import AdaptiveController, BeamController, BestOfNController, GreedyController
from experiments.data import load_pilot_examples
from experiments.scoring import ScoreConfig, SimpleBranchScorer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pilot GSM8K controller experiment")
    parser.add_argument("--config", default="configs/pilot_gsm8k.yaml", help="Path to YAML config")
    parser.add_argument("--output-dir", default=None, help="Optional override for output directory")
    return parser.parse_args()


def _parse_scalar(raw: str) -> Any:
    if raw == "null":
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw.startswith(("\"", "'")) and raw.endswith(("\"", "'")):
        return raw[1:-1]
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _minimal_yaml_parse(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(0, root)]
    for line in text.splitlines():
        content = line.split("#", 1)[0].rstrip()
        if not content.strip():
            continue
        indent = len(content) - len(content.lstrip(" "))
        content = content.strip()
        if ":" not in content:
            raise ValueError(f"Unsupported YAML line: {line}")
        key, raw_value = content.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        while stack and indent < stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if raw_value == "":
            node: dict[str, Any] = {}
            parent[key] = node
            stack.append((indent + 2, node))
        else:
            parent[key] = _parse_scalar(raw_value)
    return root


def load_config(path: str) -> dict[str, Any]:
    content = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        config = yaml.safe_load(content)
    except Exception:
        config = _minimal_yaml_parse(content)
    if not isinstance(config, dict):
        raise ValueError("Top-level config must be a mapping.")
    return config


def _build_generator_factory(config: dict[str, Any], rng: random.Random) -> tuple[Any, dict[str, Any]]:
    model_cfg = config.get("model", {})
    use_openai_api = bool(model_cfg.get("use_openai_api", True))
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    if use_openai_api:
        model_name = str(model_cfg.get("name", "gpt-4.1-mini"))
        temperature = float(model_cfg.get("temperature", 0.2))
        max_tokens = int(model_cfg.get("max_output_tokens", 220))
        timeout_seconds = int(model_cfg.get("timeout_seconds", 45))

        def factory() -> APIBranchGenerator:
            return APIBranchGenerator(
                api_key=api_key,
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
                base_url=base_url,
            )

        return factory, {
            "generator_mode": "openai_api",
            "provider": "openai",
            "model": model_name,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "api_key_present": bool(api_key),
            "base_url": base_url,
        }

    gen_cfg = config["simulation"]

    def factory() -> SimulatedBranchGenerator:
        return SimulatedBranchGenerator(
            rng=rng,
            max_depth=int(gen_cfg["max_depth"]),
            finish_prob_base=float(gen_cfg["finish_prob_base"]),
            answer_noise=float(gen_cfg["answer_noise"]),
        )

    return factory, {"generator_mode": "simulation", "fallback_reason": "model.use_openai_api=false"}


def build_controllers(config: dict[str, Any], generator_factory: Any) -> dict[str, Any]:
    scoring_cfg = ScoreConfig(
        completion_bonus=float(config["scoring"]["completion_bonus"]),
        depth_penalty=float(config["scoring"]["depth_penalty"]),
    )
    scorer = SimpleBranchScorer(scoring_cfg)
    max_actions = int(config["budget"]["max_actions_per_problem"])

    methods: dict[str, Any] = {
        "greedy_single_path": GreedyController(generator_factory(), scorer, max_actions),
        "best_of_n": BestOfNController(
            generator_factory(),
            scorer,
            max_actions,
            n_candidates=int(config["methods"]["best_of_n"]["n_candidates"]),
        ),
        "fixed_width_beam": BeamController(
            generator_factory(),
            scorer,
            max_actions,
            width=int(config["methods"]["fixed_width_beam"]["width"]),
        ),
        "adaptive_expand_verify_prune": AdaptiveController(
            generator_factory(),
            scorer,
            max_actions,
            high_threshold=float(config["methods"]["adaptive"]["high_threshold"]),
            low_threshold=float(config["methods"]["adaptive"]["low_threshold"]),
            max_branches=int(config["methods"]["adaptive"]["max_branches"]),
            allow_verify=True,
            method_name="adaptive_expand_verify_prune",
        ),
    }

    abl_cfg = config.get("methods", {}).get("adaptive_no_verify")
    if isinstance(abl_cfg, dict) and abl_cfg.get("enabled", False):
        methods["adaptive_no_verify"] = AdaptiveController(
            generator_factory(),
            scorer,
            max_actions,
            high_threshold=float(abl_cfg["high_threshold"]),
            low_threshold=float(abl_cfg["low_threshold"]),
            max_branches=int(abl_cfg["max_branches"]),
            allow_verify=False,
            method_name="adaptive_no_verify",
        )
    return methods


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    rng = random.Random(int(config["seed"]))

    generator_factory, backend_meta = _build_generator_factory(config, rng)
    examples, data_meta = load_pilot_examples(config)

    output_base = Path(args.output_dir or config["output_dir"]).expanduser()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    controllers = build_controllers(config, generator_factory)

    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "num_examples": len(examples),
        "config": config,
        "data": data_meta,
        "backend": backend_meta,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    diag_path = run_dir / "adaptive_diagnostics.jsonl"
    with diag_path.open("w", encoding="utf-8") as diag_file:
        for method_name, controller in controllers.items():
            out_path = run_dir / f"{method_name}.jsonl"
            with out_path.open("w", encoding="utf-8") as f:
                for example in examples:
                    result = controller.run(example.question, example.answer)
                    row = {
                        "example_id": example.example_id,
                        "question": example.question,
                        "gold_answer": example.answer,
                        "method": result.method,
                        "prediction": result.prediction,
                        "is_correct": result.is_correct,
                        "actions_used": result.actions_used,
                        "expansions": result.expansions,
                        "verifications": result.verifications,
                        "avg_surviving_branches": result.avg_surviving_branches,
                        "budget_exhausted": result.budget_exhausted,
                        "metadata": result.metadata,
                    }
                    f.write(json.dumps(row) + "\n")
                    if method_name.startswith("adaptive"):
                        diag_file.write(
                            json.dumps(
                                {
                                    "example_id": example.example_id,
                                    "method": method_name,
                                    "action_trace": result.metadata.get("action_trace", []),
                                    "final_selected_answer": result.prediction,
                                    "is_correct": result.is_correct,
                                    "budget_exhausted": result.budget_exhausted,
                                }
                            )
                            + "\n"
                        )

    print(f"Pilot run complete. Outputs written to: {run_dir}")


if __name__ == "__main__":
    main()
