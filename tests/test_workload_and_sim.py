import json
from dataclasses import replace

import pytest

from benchmarks import profile as prof
from benchmarks.readme_table import render_table, update_readme
from benchmarks.run_sdxl import RESULT_FORMAT, validate_result_document
from compiler.sdxl_graph import build_sdxl_workload
from compiler.workload import Op, Workload
from simulator.config import ArchConfig
from simulator.economics import DpuEconomics, GpuBaseline, compare, dpu_cost, load_gpu
from simulator.roofline import simulate


def gemm_wl(m=1024, n=1024, k=1024, steps=1):
    op = Op("g", "linear", macs=m * n * k, weight_elems=n * k, input_elems=m * k, output_elems=m * n)
    return Workload("synthetic", 0, 1, steps, False, "int8", [op])


def test_conv_macs_hand_calc():
    wl = build_sdxl_workload(256, 1, 1, guidance=False)
    conv_in = next(o for o in wl.ops if o.name == "conv_in")
    assert conv_in.macs == 32 * 32 * 320 * 4 * 9
    assert conv_in.flops == 2 * conv_in.macs


def test_sdxl_totals_sane_and_cfg_doubles():
    a = build_sdxl_workload(1024, 1, 20, guidance=False)
    b = build_sdxl_workload(1024, 1, 20, guidance=True)
    assert b.total_macs() == 2 * a.total_macs()
    assert 2.5e12 < a.total_macs() < 4.5e12  # ~3.4 TMACs (unfused attn); regression guard, not a reference
    assert 2.4e9 < a.weight_elems() < 2.8e9  # SDXL UNet ~2.57B params
    assert a.provenance["timing"] == "not_measured"


def test_bad_resolution():
    with pytest.raises(ValueError):
        build_sdxl_workload(1000)


def test_json_roundtrip(tmp_path):
    wl = build_sdxl_workload(512, 1, 2)
    p = tmp_path / "w.json"
    wl.to_json(str(p))
    assert json.loads(p.read_text())["schema"] == "dpu-workload/1"
    assert Workload.load(str(p)).total_macs() == wl.total_macs()
    d = json.loads(p.read_text())
    d["schema"] = "bad"
    with pytest.raises(ValueError):
        Workload.from_dict(d)


def test_roofline_compute_bound_microbench():
    a = ArchConfig(int8_tops=2, compute_utilization=1.0, sram_mb=64, dma_startup_us=1e-9)
    r = simulate(gemm_wl(), a)
    expected = 1024**3 / (1e12)  # 1 TMAC/s
    assert r.per_op[0].bound == "compute"
    assert r.per_op[0].time_s == pytest.approx(expected, rel=1e-3)


def test_roofline_memory_bound_microbench():
    a = ArchConfig(int8_tops=1000, compute_utilization=1.0, dram_bw_gbs=10, sram_mb=64, dma_startup_us=1e-9)
    r = simulate(gemm_wl(), a)
    assert r.per_op[0].bound == "dram"
    assert r.per_op[0].time_s == pytest.approx(1024 * 1024 / 10e9, rel=1e-3)  # weights only, acts on-chip


def test_steps_scale_and_vae_note():
    a = ArchConfig()
    r1, r4 = simulate(gemm_wl(steps=1), a), simulate(gemm_wl(steps=4), a)
    assert r4.total_latency_s == pytest.approx(4 * r1.total_latency_s)
    assert any("VAE" in n for n in r1.notes)


def test_more_bandwidth_never_slower():
    wl = build_sdxl_workload(512, 1, 1)
    a = ArchConfig()
    assert simulate(wl, replace(a, dram_bw_gbs=400)).total_latency_s <= simulate(wl, a).total_latency_s


def test_weights_exceed_dram_flagged():
    r = simulate(build_sdxl_workload(256, 1, 1), ArchConfig(dram_gb=1))
    assert not r.weights_fit_dram


def test_econ_monotonic_and_requirements():
    e = DpuEconomics()
    assert dpu_cost(e, 2.0)["cost_per_1000_images_usd"] < dpu_cost(e, 1.0)["cost_per_1000_images_usd"]
    g = GpuBaseline("g", "assumed", 1.0, 400, 2000)
    c = compare(e, 1.0, g)
    assert c.advantage_x > 0
    if "2x" in c.required_images_per_s:
        got = gpu_ratio = compare(e, c.required_images_per_s["2x"], g).advantage_x
        assert got == pytest.approx(2.0, rel=1e-3)
    assert c.sensitivity["utilization"][0][1] < c.sensitivity["utilization"][-1][1]


def test_gpu_label_required(tmp_path):
    p = tmp_path / "g.json"
    p.write_text(json.dumps({"name": "x", "label": "guess", "images_per_s": 1, "power_w": 1, "purchase_usd": 1}))
    with pytest.raises(ValueError):
        load_gpu(str(p))


def test_cli_profile_static(tmp_path):
    out = tmp_path / "s.json"
    assert prof.main(["--resolution", "512", "--steps", "2", "--output", str(out)]) == 0
    assert json.loads(out.read_text())["measured"]["gpu_timings"] is None


@pytest.mark.parametrize(
    "op",
    [
        Op("unsupported", "linear", macs=10, supported=False),
        Op("unknown-kind", "mystery", vector_elems=10),
    ],
)
def test_simulator_rejects_unsupported_or_unknown_ops(op):
    with pytest.raises(ValueError, match="unsupported|unknown"):
        simulate(Workload("test", 32, 1, 1, False, "int8", [op]), ArchConfig())


def _result_document(weight_bits=16, runtime_int8=False):
    return {
        "format": RESULT_FORMAT,
        "status": "completed",
        "model": {"revision": "a" * 40},
        "configuration": {
            "resolution": 1024, "batch_size": 1, "repetitions": 3,
            "steps": 20, "guidance_scale": 7.5, "seed": 2025,
        },
        "quantization": {
            "weight_bits": weight_bits,
            "actual_int8_runtime_state_verified": runtime_int8,
            "backend_version": "test-version",
            "activation_dtype": "float16",
        },
        "environment": {},
        "raw_latency_samples": {"end_to_end_ms": [1000.0, 1010.0, 990.0]},
        "summary": {
            "end_to_end_median_ms": 1000.0,
            "images_per_second": 1.0,
            "peak_vram_allocated_bytes": 1024**3,
        },
        "artifacts": {},
    }


def test_benchmark_result_schema_requires_pinned_revision_and_quant_metadata():
    validate_result_document(_result_document())
    with pytest.raises(ValueError, match="revision"):
        doc = _result_document()
        doc["model"]["revision"] = "main"
        validate_result_document(doc)
    with pytest.raises(ValueError, match="runtime"):
        validate_result_document(_result_document(weight_bits=8))


def test_benchmark_result_schema_requires_repetition_samples():
    doc = _result_document()
    doc["raw_latency_samples"]["end_to_end_ms"] = [1000.0]
    with pytest.raises(ValueError, match="three"):
        validate_result_document(doc)


def test_quantized_runner_rejects_mismatched_fp16_reference(tmp_path):
    from benchmarks.run_sdxl import main as run_sdxl

    root = tmp_path / "fp16"
    root.mkdir()
    doc = _result_document()
    doc["artifacts"]["image"] = "image.png"
    (root / "image.png").write_bytes(b"placeholder image")
    reference = root / "results.json"
    reference.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        run_sdxl([
            "--revision", "a" * 40,
            "--mode", "bnb-int8",
            "--reference-results", str(reference),
            "--output-dir", str(tmp_path / "int8"),
            "--seed", "1234",
        ])
    assert exc.value.code == 2


def test_readme_benchmark_table_uses_only_completed_artifacts(tmp_path):
    root = tmp_path / "results"
    table = render_table(root)
    assert "| --- | --- | --- | --- |" in table
    assert "| End-to-end latency | Not measured | Not measured | Not simulated |" in table
    assert "| Power | Not measured | Not measured | Not estimated |" in table

    fp16_path = root / "fp16" / "results.json"
    fp16_path.parent.mkdir(parents=True)
    fp16_path.write_text(json.dumps(_result_document()), encoding="utf-8")
    quant = _result_document(weight_bits=8, runtime_int8=True)
    quant["quantization"]["backend_version"] = "1.2.3"
    quant_path = root / "bnb-int8" / "results.json"
    quant_path.parent.mkdir(parents=True)
    quant_path.write_text(json.dumps(quant), encoding="utf-8")
    table = render_table(root)
    assert "| End-to-end latency | 1.000 s | 1.000 s | Not simulated |" in table
    assert "runtime INT8 state verified; bitsandbytes 1.2.3" in table

    readme = tmp_path / "README.md"
    readme.write_text(f"before\n<!-- SDXL_BENCHMARK_TABLE:START -->\nold\n<!-- SDXL_BENCHMARK_TABLE:END -->\nafter\n")
    update_readme(readme, root)
    assert "| Images per second | 1.0000 | 1.0000 | Not simulated |" in readme.read_text()


def test_three_dpu_architecture_inputs_are_explicit_and_distinct():
    configs = [
        ArchConfig.load("configs/dpu_low_cost.json"),
        ArchConfig.load("configs/dpu_balanced.json"),
        ArchConfig.load("configs/dpu_high_performance.json"),
    ]
    assert [config.name for config in configs] == [
        "dpu-low-cost-hypothesis",
        "dpu-balanced-hypothesis",
        "dpu-high-performance-hypothesis",
    ]
    assert configs[0].int8_tops < configs[1].int8_tops < configs[2].int8_tops
