"""Print independently aggregated legacy/corrected results and physical checks.

Run from the repository root: python examples/audit_results.py
"""
import csv
from pathlib import Path
from statistics import mean


def summarize(path):
    with path.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    print(path, 'rows:', len(rows))
    for key in ('pdr', 'throughput_bps', 'outage_rate', 'collision_rate',
                'access_fraction', 'window_access_fraction', 'unfinished_packets'):
        values = [float(r[key]) for r in rows if r.get(key, '') != '']
        if values:
            print(key, mean(values))
    delivered = sum(int(r['successful_packets']) for r in rows)
    latency_sum = sum(float(r['latency_s']) * int(r['successful_packets'])
                      for r in rows if r['latency_s'] != '')
    print('packet-weighted successful latency:', latency_sum / delivered if delivered else None)
    for key in ('altitude_km', 'tx_power_dbm', 'code'):
        for value in sorted(set(r[key] for r in rows)):
            group = [r for r in rows if r[key] == value]
            print(key, value, 'PDR:', mean(float(r['pdr']) for r in group),
                  'throughput:', mean(float(r['throughput_bps']) for r in group))
    group = [r for r in rows if float(r['altitude_km']) == 500 and float(r['tx_power_dbm']) == 18]
    print('500 km AND 18 dBm PDR:', mean(float(r['pdr']) for r in group))


if __name__ == '__main__':
    for directory in ('results_small', 'results_reviewed'):
        path = Path(directory) / 'ntn_results.csv'
        if path.exists():
            summarize(path)
