#!/usr/bin/env python3
"""Print a standard DPU performance scorecard (and write it to $GITHUB_STEP_SUMMARY).

Inputs: simulation log (PERF key=value lines) and yosys log (stat + ltp output).
Everything is derived from the RTL; there is no PDK dependency, so area/timing
numbers are technology-neutral proxies (generic gates, logic depth) and
frequency/power/cost figures are explicit, adjustable model assumptions.
"""
import argparse, os, re, sys

p = argparse.ArgumentParser()
p.add_argument("--sim", required=True)
p.add_argument("--synth", required=True)
p.add_argument("--data-w", type=int, default=8)
p.add_argument("--acc-w", type=int, default=16)
p.add_argument("--len-w", type=int, default=6)
# Model assumptions (override on CLI)
p.add_argument("--freq-mhz", type=float, default=50.0, help="assumed clock (sky130 hd conservative)")
p.add_argument("--ns-per-level", type=float, default=0.25, help="assumed sky130 ns per logic level")
p.add_argument("--um2-per-gate", type=float, default=12.0, help="assumed um^2 per generic gate (NAND2-ish ~3.75; avg w/ routing/util)")
p.add_argument("--uw-per-mhz-per-gate", type=float, default=0.01, help="assumed dynamic uW/MHz per gate at ~0.2 activity")
p.add_argument("--tiles", type=int, default=64, help="tiles assumed for workload projection")
p.add_argument("--workload-gmacs", type=float, default=0.5,
               help="MACs per diffusion UNet step (default: small 0.5 GMAC model; SD-1.5 UNet is ~400 GMAC)")
p.add_argument("--steps", type=int, default=20, help="denoising steps")
p.add_argument("--max-yield-cost-per-mm2", type=float, default=0.0,
               help="optional $/mm^2 for silicon cost estimate (0 = skip)")
a = p.parse_args()

perf = {}
for line in open(a.sim):
    m = re.match(r"PERF (\w+)=(\d+)", line)
    if m:
        perf[m.group(1)] = int(m.group(2))
need = ["sustained_cycles", "sustained_macs"]
if any(k not in perf for k in need):
    sys.exit("perf_report: simulation log missing PERF lines")

synth = open(a.synth).read()
# synth and the explicit stat both print a stat block; parse only the first
first = synth.find("Number of cells")
second = synth.find("Number of cells", first + 1) if first >= 0 else -1
stat_txt = synth[:second] if second > 0 else synth
# last 'Number of cells' block (top-level stat)
cells = int(re.findall(r"Number of cells:?\s+(\d+)", synth)[-1]) if re.search(r"Number of cells", synth) else 0
cell_counts = {}
for m in re.finditer(r"^\s+(\$_\w+_|\$\w+)\s+(\d+)\s*$", stat_txt, re.M):
    cell_counts[m.group(1)] = cell_counts.get(m.group(1), 0) + int(m.group(2))
ffs = sum(n for c, n in cell_counts.items() if "DFF" in c or "dff" in c)
if cells == 0:
    cells = sum(cell_counts.values())
depth_m = re.findall(r"Longest topological path.*?\(length=(\d+)\)", synth)
depth = int(depth_m[-1]) if depth_m else 0

# ---- Compute ----
cyc, macs = perf["sustained_cycles"], perf["sustained_macs"]
util = macs / cyc
f = a.freq_mhz * 1e6
gmacs_tile = util * f / 1e9
ops_tile = 2 * gmacs_tile  # GOPS (mul+add)
# ---- Memory / state ----
state_bits = ffs
op_bytes_per_mac = 2 * a.data_w / 8
bw_gbs = util * f * op_bytes_per_mac / 1e9  # operand bandwidth a tile must be fed
# ---- Area / power / timing (proxies) ----
area_mm2 = cells * a.um2_per_gate / 1e6
fmax_mhz = 1000.0 / (depth * a.ns_per_level) if depth else float("nan")
power_mw = cells * a.uw_per_mhz_per_gate * a.freq_mhz / 1000.0
eff_tops_w = (ops_tile / 1000.0) / (power_mw / 1000.0) if power_mw else float("nan")
# ---- Workload projection ----
step_s = a.workload_gmacs * 1e9 / (gmacs_tile * 1e9 * a.tiles)
img_s = step_s * a.steps
energy_img_j = power_mw / 1000.0 * a.tiles * img_s

rows = [
    ("Latency", None, None),
    ("Job latency, len=1 (cycles)", perf.get("latency_len_1_cycles"), "cfg->out_valid"),
    ("Job latency, len=16 (cycles)", perf.get("latency_len_16_cycles"), ""),
    ("Job latency, len=%d (cycles)" % perf.get("max_len", 0), perf.get("latency_len_%d_cycles" % perf.get("max_len", 0)), ""),
    ("Job latency, max len, 8-cycle consumer stall", perf.get("latency_len_%d_stall8_cycles" % perf.get("max_len", 0)), "backpressure"),
    ("Throughput", None, None),
    ("Sustained MAC/cycle (back-to-back max jobs)", "%.3f" % util, "ideal 1.0; loss = cfg+drain overhead"),
    ("Overhead cycles per job", "%.2f" % ((cyc - macs) / perf["jobs"]), ""),
    ("Per-tile GMAC/s @ %.0f MHz" % a.freq_mhz, "%.3f" % gmacs_tile, "assumed clock"),
    ("Per-tile GOPS (2 ops/MAC)", "%.3f" % ops_tile, ""),
    ("Memory / state", None, None),
    ("State elements (flip-flops)", state_bits, "on-chip storage; no SRAM in tile"),
    ("Operand bandwidth per tile (GB/s)", "%.3f" % bw_gbs, "must be fed by external buffer"),
    ("Area / timing (generic-gate proxies)", None, None),
    ("Cells (generic, flattened)", cells, "yosys synth"),
    ("Logic depth (levels)", depth, "yosys ltp"),
    ("Est. Fmax (MHz)", "%.0f" % fmax_mhz, "%.2f ns/level assumed" % a.ns_per_level),
    ("Est. area (mm^2)", "%.5f" % area_mm2, "%.0f um^2/cell assumed" % a.um2_per_gate),
    ("Est. dynamic power (mW) @ %.0f MHz" % a.freq_mhz, "%.3f" % power_mw, "model"),
    ("Efficiency (TOPS/W)", "%.2f" % eff_tops_w, "model"),
    ("Throughput density (GMAC/s/mm^2)", "%.1f" % (gmacs_tile / area_mm2 if area_mm2 else 0), ""),
    ("Diffusion workload projection", None, None),
    ("Workload", "%.2f GMAC/step x %d steps, %d tiles" % (a.workload_gmacs, a.steps, a.tiles), "assumption"),
    ("Time per step (ms)", "%.2f" % (step_s * 1e3), ""),
    ("Time per image (s)", "%.2f" % img_s, ""),
    ("Energy per image (J)", "%.3f" % energy_img_j, ""),
    ("Total array area (mm^2)", "%.3f" % (area_mm2 * a.tiles), "tiles only, no I/O or buffers"),
]
if a.max_yield_cost_per_mm2:
    rows.append(("Silicon cost per image-engine ($)", "%.2f" % (area_mm2 * a.tiles * a.max_yield_cost_per_mm2), "tiles only"))

out = ["### DPU performance scorecard", "", "| Metric | Value | Note |", "|---|---|---|"]
for name, val, note in rows:
    out.append("| **%s** | | |" % name if val is None else "| %s | %s | %s |" % (name, val, note))
out += ["", "_Measured: latency, MAC/cycle, flip-flops, cells, logic depth. Modeled (see flags in "
        "scripts/perf_report.py): frequency, area, power, workload, cost._"]
text = "\n".join(out)
print(text)
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
        fh.write(text + "\n")
