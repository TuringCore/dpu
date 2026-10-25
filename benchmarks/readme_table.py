"""Render the README SDXL table from benchmark artifacts, never from estimates."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmarks.run_sdxl import validate_result_document

START = "<!-- SDXL_BENCHMARK_TABLE:START -->"
END = "<!-- SDXL_BENCHMARK_TABLE:END -->"


def _load_gpu_result(path: Path, expected_bits: int) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    result = json.loads(path.read_text(encoding="utf-8"))
    validate_result_document(result)
    if result["quantization"].get("weight_bits") != expected_bits:
        raise ValueError(f"{path} is not the expected {expected_bits}-bit benchmark artifact")
    return result


def _ms(result: dict[str, Any] | None) -> str:
    if result is None:
        return "Not measured"
    return f"{result['summary']['end_to_end_median_ms'] / 1000:.3f} s"


def _ips(result: dict[str, Any] | None) -> str:
    return "Not measured" if result is None else f"{result['summary']['images_per_second']:.4f}"


def _memory(result: dict[str, Any] | None) -> str:
    if result is None:
        return "Not measured"
    gib = result["summary"]["peak_vram_allocated_bytes"] / (1024 ** 3)
    return f"{gib:.2f} GiB peak allocated"


def render_table(results_dir: str | Path) -> str:
    """Return a table populated only by valid, completed and compatible artifacts."""
    root = Path(results_dir)
    fp16 = _load_gpu_result(root / "fp16" / "results.json", 16)
    quant = _load_gpu_result(root / "bnb-int8" / "results.json", 8)
    environment_blocked = (root / "execution_blocker.json").is_file()
    available = [result for result in (fp16, quant) if result is not None]
    if len(available) == 2 and (
        available[0]["model"]["revision"] != available[1]["model"]["revision"]
        or available[0]["configuration"] != available[1]["configuration"]
    ):
        raise ValueError("FP16 and quantized artifacts must use the same model revision and settings")

    revision = available[0]["model"]["revision"] if available else "not resolved"
    quantized_precision = "Not measured"
    if quant is not None:
        quantized_precision = (
            f"bitsandbytes INT8 UNet Linear weights / FP16 remainder "
            f"(runtime INT8 state verified; bitsandbytes "
            f"{quant['quantization']['backend_version']})"
        )
    rows = [
        ("Metric", "GPU FP16", "GPU Quantized", "Turing DPU Simulated"),
        ("---", "---", "---", "---"),
        ("Model", f"SDXL base 1.0 @ `{revision}`" if available else "SDXL base 1.0; revision not resolved",
         f"SDXL base 1.0 @ `{revision}`" if available else "SDXL base 1.0; revision not resolved",
         "Exact quantized workload unavailable"),
        ("Precision", "FP16" if fp16 else "Not measured", quantized_precision, "Not simulated"),
        ("End-to-end latency", _ms(fp16), _ms(quant), "Not simulated"),
        ("Images per second", _ips(fp16), _ips(quant), "Not simulated"),
        ("Memory requirement", _memory(fp16), _memory(quant), "Not simulated"),
        ("Power", "Not measured" if fp16 is None else "Not measured by runner",
         "Not measured" if quant is None else "Not measured by runner", "Not estimated"),
        ("Cost per 1,000 images", "Not calculated", "Not calculated", "Not calculated"),
        ("Measurement status",
         ("Not run: environment blocker" if environment_blocked else "Not run: no artifact")
         if fp16 is None else "Measured GPU inference",
         ("Not run: environment blocker" if environment_blocked else "Not run: no artifact")
         if quant is None else "Measured GPU inference; paired pixel error only",
         "Not simulated from an executed graph"),
    ]
    return "\n".join("| " + " | ".join(row) + " |" for row in rows)


def update_readme(readme: str | Path, results_dir: str | Path) -> None:
    path = Path(readme)
    content = path.read_text(encoding="utf-8")
    start = content.find(START)
    end = content.find(END)
    if start < 0 or end < start:
        raise ValueError("README benchmark table markers are missing or out of order")
    table = render_table(results_dir)
    path.write_text(
        content[:start + len(START)] + "\n" + table + "\n" + content[end:],
        encoding="utf-8",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="benchmarks/results")
    parser.add_argument("--readme", default="README.md")
    args = parser.parse_args()
    update_readme(args.readme, args.results_dir)
