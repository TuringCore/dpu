"""Run revision-pinned SDXL FP16 or bitsandbytes INT8 inference on CUDA.

Example:
  python -m benchmarks.run_sdxl --revision <40-char-hub-commit> --mode fp16 \
      --output-dir benchmarks/results/fp16
  python -m benchmarks.run_sdxl --revision <same-commit> --mode bnb-int8 \
      --reference-image benchmarks/results/fp16/image.png \
      --output-dir benchmarks/results/bnb-int8
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
RESULT_FORMAT = "turing-sdxl-benchmark/1"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def validate_result_document(result: dict[str, Any]) -> None:
    """Check the minimum machine-readable artifact contract without ML dependencies."""
    required = {
        "format", "status", "model", "configuration", "quantization",
        "environment", "raw_latency_samples", "summary", "artifacts",
    }
    missing = required - result.keys()
    if missing:
        raise ValueError(f"benchmark result is missing fields: {sorted(missing)}")
    if result["format"] != RESULT_FORMAT or result["status"] != "completed":
        raise ValueError("invalid benchmark result format or status")
    revision = result["model"].get("revision")
    if not isinstance(revision, str) or not COMMIT_RE.fullmatch(revision):
        raise ValueError("model revision must be a full 40-character commit SHA")
    if result["configuration"].get("resolution") != 1024:
        raise ValueError("the reproducible SDXL benchmark requires 1024x1024")
    if result["configuration"].get("batch_size") != 1:
        raise ValueError("the reproducible SDXL benchmark requires batch size 1")
    samples = result["raw_latency_samples"].get("end_to_end_ms")
    if not isinstance(samples, list) or len(samples) < 3 or not all(
        isinstance(x, (int, float)) and math.isfinite(x) and x > 0 for x in samples
    ):
        raise ValueError("at least three finite positive end-to-end latency samples are required")


def _tensor_shapes(value: Any) -> tuple[list[list[int]], list[str]]:
    shapes: list[list[int]] = []
    dtypes: list[str] = []
    if isinstance(value, (tuple, list)):
        for item in value:
            child_shapes, child_dtypes = _tensor_shapes(item)
            shapes.extend(child_shapes)
            dtypes.extend(child_dtypes)
    elif hasattr(value, "shape") and hasattr(value, "dtype"):
        shapes.append(list(value.shape))
        dtypes.append(str(value.dtype))
    return shapes, dtypes


def _replace_linears(module: Any, torch: Any, bnb: Any, device: str, prefix: str = "") -> list[str]:
    replaced: list[str] = []
    for name, child in list(module.named_children()):
        path = f"{prefix}.{name}" if prefix else name
        if isinstance(child, torch.nn.Linear):
            quantized = bnb.nn.Linear8bitLt(
                child.in_features,
                child.out_features,
                bias=child.bias is not None,
                has_fp16_weights=False,
                threshold=6.0,
            ).to(device)
            quantized.weight = bnb.nn.Int8Params(
                child.weight.detach().to(device),
                requires_grad=False,
                has_fp16_weights=False,
            )
            if child.bias is not None:
                quantized.bias = torch.nn.Parameter(
                    child.bias.detach().to(device), requires_grad=False
                )
            quantized.train(child.training)
            setattr(module, name, quantized)
            replaced.append(path)
        else:
            replaced.extend(_replace_linears(child, torch, bnb, device, path))
    return replaced


def _resident_tensor_bytes(tensors: list[Any]) -> int:
    seen: set[tuple[str, int]] = set()
    total = 0
    for tensor in tensors:
        try:
            storage = tensor.untyped_storage()
            key = (str(tensor.device), storage.data_ptr())
            if key not in seen:
                seen.add(key)
                total += storage.nbytes()
        except (AttributeError, RuntimeError):
            continue
    return total


def _image_error(reference: Path, generated: Any) -> dict[str, Any]:
    import numpy as np
    from PIL import Image

    ref = Image.open(reference).convert("RGB")
    actual = generated.convert("RGB")
    if ref.size != actual.size:
        raise ValueError(f"reference image size {ref.size} does not match generated {actual.size}")
    delta = np.asarray(actual, dtype=np.float32) - np.asarray(ref, dtype=np.float32)
    mse = float(np.mean(np.square(delta)))
    return {
        "metric": "paired RGB pixel error (not a semantic-quality metric)",
        "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "mse": mse,
        "psnr_db": None if mse == 0 else 10.0 * math.log10((255.0 ** 2) / mse),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True, help="full 40-character Hugging Face commit SHA")
    parser.add_argument("--mode", choices=("fp16", "bnb-int8"), required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--reference-image", help="same-prompt FP16 PNG; required for bnb-int8")
    parser.add_argument("--prompt", default="a photograph of an astronaut riding a horse")
    parser.add_argument("--negative-prompt", default="")
    parser.add_argument("--seed", type=int, default=2025)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args(argv)
    if not COMMIT_RE.fullmatch(args.revision):
        parser.error("--revision must be the full 40-character model commit SHA")
    if args.warmups < 1 or args.repetitions < 3:
        parser.error("use at least one warm-up and three measured repetitions")
    if args.mode == "bnb-int8" and not args.reference_image:
        parser.error("--reference-image is required for bnb-int8 quality comparison")

    try:
        import torch
        import diffusers
        from diffusers import DPMSolverMultistepScheduler, StableDiffusionXLPipeline
    except ImportError as exc:
        raise SystemExit(
            "Missing GPU benchmark dependency. Install the GPU extra and bitsandbytes; "
            "this command never substitutes a synthetic model."
        ) from exc
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is unavailable; no model was loaded and no benchmark was run.")
    if args.mode == "bnb-int8":
        try:
            import bitsandbytes as bnb
        except ImportError as exc:
            raise SystemExit("bnb-int8 requires bitsandbytes with CUDA support.") from exc
    else:
        bnb = None

    from PIL import Image

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    pipe = StableDiffusionXLPipeline.from_pretrained(
        MODEL_ID,
        revision=args.revision,
        torch_dtype=torch.float16,
        use_safetensors=True,
    ).to("cuda")
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(
        pipe.scheduler.config,
        algorithm_type="dpmsolver++",
        use_karras_sigmas=False,
    )

    replaced: list[str] = []
    if bnb is not None:
        replaced = _replace_linears(pipe.unet, torch, bnb, "cuda")
        if not replaced:
            raise RuntimeError("INT8 conversion replaced no UNet Linear modules")
        quantized_modules = {
            name: mod for name, mod in pipe.unet.named_modules()
            if isinstance(mod, bnb.nn.Linear8bitLt)
        }
    else:
        quantized_modules = {}

    denoiser_events: list[tuple[Any, Any]] = []
    denoiser_calls = 0

    def denoiser_pre(_module: Any, _inputs: Any) -> None:
        nonlocal denoiser_calls
        start = torch.cuda.Event(enable_timing=True)
        start.record()
        denoiser_events.append((start, None))
        denoiser_calls += 1

    def denoiser_post(_module: Any, _inputs: Any, _output: Any) -> None:
        end = torch.cuda.Event(enable_timing=True)
        end.record()
        start, _ = denoiser_events[-1]
        denoiser_events[-1] = (start, end)

    pre_handle = pipe.unet.register_forward_pre_hook(denoiser_pre)
    post_handle = pipe.unet.register_forward_hook(denoiser_post)

    def infer() -> Any:
        generator = torch.Generator(device="cuda").manual_seed(args.seed)
        return pipe(
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            height=1024,
            width=1024,
            num_inference_steps=20,
            guidance_scale=7.5,
            generator=generator,
            output_type="pil",
        ).images[0]

    try:
        for _ in range(args.warmups):
            infer()
        torch.cuda.synchronize()
        if bnb is not None:
            initialized = sum(
                isinstance(getattr(mod.state, "CB", None), torch.Tensor)
                and mod.state.CB.dtype == torch.int8
                for mod in quantized_modules.values()
            )
            if initialized == 0:
                raise RuntimeError("bitsandbytes did not initialize any INT8 quantized weight state")

        model_tensors = [
            tensor
            for component in (pipe.unet, pipe.vae, pipe.text_encoder, pipe.text_encoder_2)
            for tensor in [*(p for p in component.parameters()), *(b for b in component.buffers())]
        ]
        model_bytes = _resident_tensor_bytes(model_tensors)
        if bnb is not None:
            model_bytes += _resident_tensor_bytes([
                tensor for mod in quantized_modules.values()
                for tensor in (getattr(mod.state, "CB", None), getattr(mod.state, "SCB", None))
                if isinstance(tensor, torch.Tensor)
            ])
        baseline_allocated = int(torch.cuda.memory_allocated())
        torch.cuda.reset_peak_memory_stats()

        end_to_end_ms: list[float] = []
        denoiser_ms: list[float] = []
        last_image = None
        for _ in range(args.repetitions):
            torch.cuda.synchronize()
            start = time.perf_counter()
            last_image = infer()
            torch.cuda.synchronize()
            end_to_end_ms.append((time.perf_counter() - start) * 1000.0)
            start_idx = len(denoiser_events) - denoiser_calls
            events = denoiser_events[start_idx:]
            denoiser_ms.append(sum(a.elapsed_time(b) for a, b in events if b is not None))
            denoiser_calls = 0
        pre_handle.remove()
        post_handle.remove()
        assert last_image is not None
        image_path = output_dir / "image.png"
        last_image.save(image_path)
        torch.cuda.synchronize()

        leaf_graph: list[dict[str, Any]] = []
        graph_handles = []
        for name, module in pipe.unet.named_modules():
            if any(module.children()):
                continue

            def hook(mod: Any, inputs: Any, output: Any, module_name: str = name) -> None:
                in_shapes, in_dtypes = _tensor_shapes(inputs)
                out_shapes, out_dtypes = _tensor_shapes(output)
                leaf_graph.append({
                    "name": module_name,
                    "module_type": type(mod).__name__,
                    "input_shapes": in_shapes,
                    "output_shapes": out_shapes,
                    "input_dtypes": sorted(set(in_dtypes)),
                    "output_dtypes": sorted(set(out_dtypes)),
                })

            graph_handles.append(module.register_forward_hook(hook))
        with torch.profiler.profile(
            activities=[torch.profiler.ProfilerActivity.CPU, torch.profiler.ProfilerActivity.CUDA],
            record_shapes=True,
            with_flops=True,
        ) as prof:
            infer()
        torch.cuda.synchronize()
        for handle in graph_handles:
            handle.remove()
        trace_path = output_dir / "operator_trace.json"
        prof.export_chrome_trace(str(trace_path))

        operator_events = []
        for event in prof.key_averages(group_by_input_shape=True):
            operator_events.append({
                "operator": event.key,
                "calls": event.count,
                "input_shapes": getattr(event, "input_shapes", []),
                "estimated_flops": int(getattr(event, "flops", 0) or 0),
                "self_cuda_time_us": float(getattr(event, "self_cuda_time_total", 0.0) or 0.0),
            })
        runtime_int8 = sum(
            isinstance(getattr(mod.state, "CB", None), torch.Tensor)
            and mod.state.CB.dtype == torch.int8
            for mod in quantized_modules.values()
        )
        for name, module in quantized_modules.items():
            if name not in replaced:
                replaced.append(name)

        result: dict[str, Any] = {
            "format": RESULT_FORMAT,
            "status": "completed",
            "model": {
                "id": MODEL_ID,
                "revision": args.revision,
                "weights_loaded_from": "Hugging Face Diffusers from_pretrained",
            },
            "configuration": {
                "resolution": 1024,
                "batch_size": 1,
                "steps": 20,
                "guidance_scale": 7.5,
                "scheduler": "DPMSolverMultistepScheduler (dpmsolver++, Karras disabled)",
                "prompt": args.prompt,
                "negative_prompt": args.negative_prompt,
                "seed": args.seed,
                "warmups": args.warmups,
                "repetitions": args.repetitions,
                "synchronization": "CUDA synchronize before and after each timed generation; host perf_counter",
            },
            "quantization": {
                "scheme": "none" if bnb is None else "bitsandbytes Linear8bitLt, UNet Linear weights INT8",
                "weight_bits": 16 if bnb is None else 8,
                "activation_dtype": "float16; bitsandbytes dynamically quantizes matrix operands internally",
                "quantized_module_paths": replaced,
                "quantized_modules_with_runtime_int8_state": runtime_int8,
                "actual_int8_runtime_state_verified": bnb is not None and runtime_int8 > 0,
                "backend_version": None if bnb is None else bnb.__version__,
                "non-Linear UNet layers and VAE/text encoders remain FP16",
            },
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "torch": torch.__version__,
                "cuda_runtime": torch.version.cuda,
                "diffusers": diffusers.__version__,
                "gpu": torch.cuda.get_device_name(0),
                "gpu_total_memory_bytes": int(torch.cuda.get_device_properties(0).total_memory),
            },
            "raw_latency_samples": {
                "end_to_end_ms": end_to_end_ms,
                "denoiser_only_ms": denoiser_ms,
            },
            "summary": {
                "end_to_end_median_ms": statistics.median(end_to_end_ms),
                "images_per_second": 1000.0 / statistics.median(end_to_end_ms),
                "denoiser_only_median_ms": statistics.median(denoiser_ms),
                "peak_vram_allocated_bytes": int(torch.cuda.max_memory_allocated()),
                "baseline_vram_allocated_bytes": baseline_allocated,
                "model_resident_bytes": model_bytes,
                "gpu_power_w": None,
                "power_status": "Not measured; no power telemetry sampler is enabled",
                "image_quality_vs_fp16": None,
            },
            "artifacts": {
                "image": image_path.name,
                "operator_trace": trace_path.name,
                "module_graph": "module_graph.json",
                "profiler_operators": "profiler_operators.json",
            },
        }
        if args.mode == "bnb-int8":
            result["summary"]["image_quality_vs_fp16"] = _image_error(
                Path(args.reference_image), last_image
            )
        validate_result_document(result)
        (output_dir / "module_graph.json").write_text(
            json.dumps(leaf_graph, indent=2) + "\n", encoding="utf-8"
        )
        (output_dir / "profiler_operators.json").write_text(
            json.dumps(operator_events, indent=2) + "\n", encoding="utf-8"
        )
        (output_dir / "results.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {output_dir / 'results.json'}")
    finally:
        pre_handle.remove()
        post_handle.remove()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
