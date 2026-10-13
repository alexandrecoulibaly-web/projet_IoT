"""Reproducible NTN experiment matrix and publication-quality plots.

Example:
    python -m lrfhss.ntn_experiments --output results --replications 3
"""

from dataclasses import dataclass, field
import argparse
import csv
import itertools
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
    codes: tuple = ("1/3", "1/2")
    replications: int = 3
    simulation_time_s: float = 600.0
    seed: int = 20261012
    frequency_hz: float = 868e6
    min_elevation_deg: float = 10.0
    extra: dict = field(default_factory=dict)


def run_plan(plan, output_dir="results"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    rows = []
    for altitude, devices, interval, power, code, replication in itertools.product(
        plan.altitudes_km, plan.device_counts, plan.average_intervals_s,
        plan.tx_powers_dbm, plan.codes, range(plan.replications)
    ):
        channel = SatelliteChannel(SatelliteConfig(
            altitude_km=altitude, tx_power_dbm=power,
            frequency_hz=plan.frequency_hz, min_elevation_deg=plan.min_elevation_deg,
        ), seed=plan.seed + replication)
        settings = Settings(
            number_nodes=devices, simulation_time=plan.simulation_time_s,
            code=code, traffic_param={"average_interval": interval},
            satellite=channel,
        )
        metrics = run_sim(settings, seed=plan.seed + replication, return_metrics=True)
        rows.append({
            "altitude_km": altitude, "devices": devices,
            "average_interval_s": interval, "tx_power_dbm": power,
            "code": code, "replication": replication,
            **metrics,
        })
    csv_path = output_path / "ntn_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    plot_results(rows, output_path)
    return rows


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
            grouped.setdefault(key, {}).setdefault(row["altitude_km"], []).append(row[metric])
        for (devices, power), values in sorted(grouped.items()):
            x = sorted(values)
            y = [sum(values[a]) / len(values[a]) for a in x]
            ax.plot(x, y, marker="o", label=f"{devices} devices, {power:g} dBm")
        ax.set_xlabel("LEO altitude (km)")
        ax.set_ylabel(ylabel)
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
