"""Reproducible NTN experiment matrix and publication-quality plots.

Example:
    python -m lrfhss.ntn_experiments --output results --replications 3
"""

from dataclasses import asdict, dataclass, field
import argparse
import csv
import itertools
import json
import math
import statistics
from pathlib import Path

import matplotlib.pyplot as plt

from lrfhss.run import run_sim
from lrfhss.satellite import SatelliteChannel, SatelliteConfig
from lrfhss.settings import Settings


@dataclass
class ExperimentPlan:
    altitudes_km: tuple = (500.0, 600.0, 800.0)
    device_counts: tuple = (50, 100, 200)
    average_intervals_s: tuple = (300.0, 900.0)
    tx_powers_dbm: tuple = (10.0, 14.0, 18.0)
    codes: tuple = ("1/3", "2/3")
    replications: int = 3
    simulation_time_s: float = 600.0
    seed: int = 20261012
    frequency_hz: float = 868e6
    min_elevation_deg: float = 10.0
    extra: dict = field(default_factory=dict)


def run_plan(plan, output_dir="results"):
    if plan.replications < 1 or plan.simulation_time_s <= 0:
        raise ValueError("replications and simulation time must be positive")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    rows = []
    for altitude, devices, interval, power, code, replication in itertools.product(
        plan.altitudes_km, plan.device_counts, plan.average_intervals_s,
        plan.tx_powers_dbm, plan.codes, range(plan.replications)
    ):
        config = dict(plan.extra)
        # Sweep coordinates must match their CSV labels, even with extra settings.
        config.update(
            altitude_km=altitude, tx_power_dbm=power,
            frequency_hz=plan.frequency_hz, min_elevation_deg=plan.min_elevation_deg,
        )
        channel = SatelliteChannel(SatelliteConfig(**config), seed=plan.seed + replication)
        settings = Settings(
            number_nodes=devices, simulation_time=plan.simulation_time_s,
            code=code, headers=3 if code == "1/3" else 2,
            traffic_param={"average_interval": interval},
            satellite=channel,
        )
        metrics = run_sim(settings, seed=plan.seed + replication, return_metrics=True)
        rows.append({
            "altitude_km": altitude, "devices": devices,
            "average_interval_s": interval, "tx_power_dbm": power,
            "code": code, "replication": replication,
            "seed": plan.seed + replication,
            "simulation_time_s": plan.simulation_time_s,
            "headers": settings.headers,
            "orbit_period_s": channel.orbit_period_s,
            "receiver_sensitivity_dbm": channel.noise_power_dbm() + channel.config.required_snr_db + channel.config.implementation_loss_db,
            **metrics,
        })
    if not rows:
        raise ValueError("experiment matrix must not be empty")
    (output_path / "manifest.json").write_text(json.dumps({
        "model": "circular-overhead-v2", "plan": asdict(plan),
        "satellite_defaults": asdict(SatelliteConfig()),
        "notes": ["Nonrotating Earth; all nodes share one site; Doppler is diagnostic only.",
                  "Receiver sensitivity is illustrative and uncalibrated.",
                  "PDR counts starts and decodes within the finite observation window.",
                  "Summary intervals are sample standard deviations across replications, not confidence intervals."],
    }, indent=2), encoding="utf-8")
    csv_path = output_path / "ntn_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summarize_results(rows, output_path)
    plot_results(rows, output_path)
    return rows


def summarize_results(rows, output_path):
    """Keep configuration effects separate from replication uncertainty."""
    keys = ("altitude_km", "devices", "average_interval_s", "tx_power_dbm", "code")
    groups = {}
    for row in rows:
        groups.setdefault(tuple(row[k] for k in keys), []).append(row)
    summary = []
    for key, group in groups.items():
        record = dict(zip(keys, key))
        for metric in ("pdr", "throughput_bps", "latency_s", "outage_rate"):
            values = [r[metric] for r in group if r[metric] is not None]
            record[metric + "_n"] = len(values)
            record[metric + "_mean"] = statistics.mean(values) if values else None
            record[metric + "_std"] = statistics.stdev(values) if len(values) > 1 else None
        summary.append(record)
    with (output_path / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)


def plot_results(rows, output_dir):
    output_dir = Path(output_dir)
    for metric, ylabel, filename in (
        ("pdr", "Packet delivery ratio", "pdr_vs_altitude.png"),
        ("throughput_bps", "Throughput (bit/s)", "throughput_vs_altitude.png"),
        ("latency_s", "Mean latency (s)", "latency_vs_altitude.png"),
        ("outage_rate", "Fragment outage rate", "outage_vs_altitude.png"),
    ):
        fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=160)
        grouped = {}
        for row in rows:
            key = (row["devices"], row["tx_power_dbm"])
            values = grouped.setdefault(key, {}).setdefault(row["altitude_km"], [])
            if row[metric] is not None:
                values.append(row[metric])
        for (devices, power), values in sorted(grouped.items()):
            x = sorted(values)
            y = [sum(values[a]) / len(values[a]) if values[a] else math.nan for a in x]
            ax.plot(x, y, marker="o", label=f"{devices} devices, {power:g} dBm")
        ax.set_xlabel("LEO altitude (km)")
        ax.set_ylabel(ylabel)
        ax.set_title("Means across traffic intervals, coding profiles and replications", fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()
        fig.savefig(output_dir / filename, bbox_inches="tight")
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Run the LR-FHSS NTN experiment matrix.")
    parser.add_argument("--output", default="results")
    parser.add_argument("--replications", type=int, default=3)
    parser.add_argument("--simulation-time", type=float, default=600.0)
    args = parser.parse_args()
    plan = ExperimentPlan(replications=args.replications, simulation_time_s=args.simulation_time)
    run_plan(plan, args.output)


if __name__ == "__main__":
    main()
