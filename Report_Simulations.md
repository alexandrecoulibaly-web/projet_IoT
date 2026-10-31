# LR-FHSS Simulation Study for a Simplified LEO Satellite IoT Uplink

## I. Context and objectives

Low-Rate Frequency-Hopping Spread Spectrum (LR-FHSS) is a LoRaWAN physical-layer option intended for long-range, low-rate uplinks. A packet is transmitted as repeated physical headers followed by short payload fragments spread across a frequency-hopping grid. This structure can improve robustness to interference: a packet may still be decoded when some fragments are lost, provided that a usable header and enough payload fragments arrive. The regional parameters specify the LR-FHSS profiles and, in particular, three repeated headers for coding rate 1/3 and two for coding rate 2/3 in the profiles used here ([LoRa Alliance Regional Parameters RP002-1.0.3](https://lora-alliance.org/wp-content/uploads/2021/05/RP-2-1.0.3.pdf)).

Satellite IoT adds link availability to the usual random-access problem. A device may transmit while a satellite is below the elevation mask, or the received signal may fall below the assumed receiver threshold. A packet can therefore fail because of link outage, fragment collisions, or both. The objective of these simulations is to explore how altitude, transmit power, device population, offered traffic, and coding profile affect packet delivery and aggregate throughput in a clearly specified, simplified LEO uplink model.

The project is a system-level research study. It is not a complete LoRaWAN implementation, a waveform-accurate LR-FHSS receiver, or a validated prediction for a named satellite constellation. Results should be interpreted as comparisons within the assumptions described below.

## II. Choice of simulator

The study uses [Xexell/LR-FHSS-sim](https://github.com/Xexell/LR-FHSS-sim), an open-source Python discrete-event simulator. The upstream simulator was chosen because it models packets as headers and payload fragments, schedules their transmissions over time, tracks same-channel overlaps, and supports receiver decoding rules. Its event-driven design is suitable for studying asynchronous random access without simulating every waveform sample. The simulator is also modular: traffic generators, receiver logic, and scenario settings can be changed independently. The original simulator is described in the [LR-FHSS-Sim paper](https://oulurepo.oulu.fi/handle/10024/51865).

The repository extends that simulator with an optional satellite channel. The original terrestrial/base-station mode remains available; satellite behavior is activated by attaching a `SatelliteChannel` to the run settings. This makes the selected tool useful both as a baseline for collision experiments and as a platform for controlled satellite-link sensitivity studies.

## III. Simulator methodology

### 3.1 Event and packet model

The core simulation is implemented in Python using SimPy. A node waits for its configured traffic interval, starts a packet, then sends its fragments sequentially. Each fragment has a type, channel, airtime, and start time. The default experiment represents one grid of 35 channels. A fragment is checked against active transmissions on its channel; overlapping airtime marks both fragments as collided. Airtime intervals are treated as half-open, so fragments that meet exactly at an endpoint do not collide.

The basic receiver counts a fragment as successful if it has completed, has no collision, and is available under the satellite link test. It decodes a packet when at least one header fragment and the configured minimum number of payload fragments succeed. This is an abstraction of packet recovery and does not model the LR-FHSS waveform or decoding probabilities at the bit level. An optional ACRDA receiver adds successive interference cancellation; the reported experiment matrix uses the core receiver.

Traffic is generated with exponential inter-transmission waits. The experiment parameter is the mean idle interval after a previous packet finishes, rather than a fixed packet period. Reproducibility is provided by deterministic per-replication seeds. The experiment driver writes individual run metrics to `results_reviewed/ntn_results.csv`, replication summaries to `results_reviewed/summary.csv`, configuration metadata to `results_reviewed/manifest.json`, and figures to the same results directory.

### 3.2 Satellite channel model

The satellite extension assumes a spherical, nonrotating Earth and a circular orbit passing directly over a fixed ground site. All terminals are colocated and share the same time-varying elevation and range. The satellite starts on the approaching side at 45° elevation by default; a 10° minimum elevation defines visibility. The orbital period is calculated from the circular-orbit Kepler relation unless explicitly overridden. For satellite altitude \(h\), Earth radius \(R\), and central angle \(\theta\), the range is computed as

\[
d=\sqrt{(R+h)^2+R^2-2R(R+h)\cos\theta},
\]

and the free-space path loss is

\[
L_{FS}=20\log_{10}\left(\frac{4\pi d f}{c}\right).
\]

Received power is the transmit power plus antenna gains minus free-space path loss and any sampled shadowing. Noise power is calculated from the equivalent receiver noise bandwidth and noise figure; SNR is then compared with a configured threshold. A fragment is link-available only when it is both above the elevation mask and above this threshold. Doppler shift is calculated as a diagnostic output, but it is not used to impair decoding or alter channel selection. Propagation delay is also omitted from event timing.

The default link budget uses 868 MHz, 0 dBi terminal and satellite gains, 125 kHz equivalent noise bandwidth, 5 dB noise figure, and a -15 dB required SNR. This produces an illustrative sensitivity of approximately -133.03 dBm. The bandwidth is a receiver noise assumption; it is not LR-FHSS instantaneous modulation bandwidth. The threshold and sensitivity are uncalibrated and should not be read as measured receiver performance.

### 3.3 Metrics

The simulation records the following metrics:

| Metric | Definition |
|---|---|
| Packet delivery ratio (PDR/PSR) | Packets decoded before the simulation cutoff divided by packets started before the cutoff. It is undefined when no packet starts. |
| Throughput | Successfully decoded payload bits divided by the observation duration. |
| Latency | Time from packet start to successful decode. It is undefined when no packet succeeds. |
| Collision rate | Started fragments that encounter an overlap divided by all started fragments. |
| Outage rate | Started fragments that fail the link-availability test divided by all started fragments. |
| Access fraction | Expected fraction of a full idealized orbit for which the link is usable. |
| Window access fraction | Expected usable-link fraction during the finite observation window. |
| Unfinished packets | Packets still in transmission at the end of the observation window. |

Collision and outage are counted independently, so one fragment may belong to both categories. Their rates should not be added as mutually exclusive packet-loss causes. Packets in progress at the simulation cutoff are not drained to completion; PDR only counts decodes achieved within the finite run.

## IV. Experiments

### 4.1 Parameters and experiment matrix

The corrected experiment matrix varies the following parameters:

| Parameter | Tested values |
|---|---|
| Satellite altitude | 500, 600, and 800 km |
| Number of devices | 50, 100, and 200 |
| Mean idle interval | 300 and 900 s |
| Transmit power | 10, 14, and 18 dBm |
| Coding profile | 1/3 with three headers; 2/3 with two headers |
| Replications | 3 per configuration |
| Observation duration | 600 s per run |
| Frequency | 868 MHz |
| Minimum elevation | 10° |
| Seed base | 20261012 |

This gives \(3\times3\times2\times3\times2\times3=324\) runs. All replications use deterministic seeds derived from the base seed. The traffic rate and device count expose random-access load; altitude and transmit power affect the assumed link budget; and the two coding profiles test packet-fragment recovery under the tested outage and collision conditions.

### 4.2 Satellite environment and scope

The satellite environment approximates one circular LEO pass over one site. It includes changing elevation, slant range, free-space path loss, receiver noise, threshold-based outage, a minimum elevation mask, and optional signed Doppler calculation. This environment allows controlled tests of access and link-budget sensitivity without requiring a particular orbit or location.

The simulation does not represent a constellation, geographic coverage, terminal distribution, handover, a rotating Earth, atmospheric attenuation, antenna patterns, capture/SINR effects, or retransmissions. The default nodes occupy a single modeled 35-channel grid and choose fragment channels independently; the hopping sequence is not a full implementation of the standard. These simplifications define the limits of the interpretation.

## V. Results and conclusion

### 5.1 Main results

The following averages are over the 324 corrected runs in `results_reviewed/ntn_results.csv`:

| Metric | Mean |
|---|---:|
| PDR | 0.1212 |
| Throughput | 2.58 bit/s |
| Fragment outage rate | 0.8780 |
| Fragment collision rate | 0.0160 |
| Full-orbit access fraction | 0.0144 |
| Observation-window access fraction | 0.1225 |
| Successful-packet-weighted latency | 0.9024 s |

Mean PDR and throughput fall as altitude increases: across the other tested parameters, PDR is 0.1505 at 500 km, 0.1241 at 600 km, and 0.0891 at 800 km. Transmit power has a strong effect under the selected threshold: mean PDR is 0.0000 at 10 dBm, 0.0716 at 14 dBm, and 0.2921 at 18 dBm. The two coding-profile means are close in this matrix (0.1219 for 1/3 and 0.1206 for 2/3); three replications and an uncalibrated common receiver threshold do not establish that the profiles perform equivalently.

The reported mean PDR is close to the mean access fraction over the observation windows, while the full-orbit access fraction is much lower because the full orbit includes long intervals below the elevation mask. Collision rate is much lower than fragment outage rate under the current assumptions. This indicates that the selected link threshold and visibility assumptions dominate these particular runs; it does not show that collisions are unimportant in other traffic loads or receiver configurations. Collision and outage can overlap on a fragment, so the comparison is descriptive rather than an additive loss decomposition.

Historical results in `results_small` and the earlier `Report_legacy.md` used a moving-satellite geometry that incorrectly kept the satellite visible throughout the pass. They reported an overall mean PDR of 0.3822 and should not be mixed with or substituted for the corrected `results_reviewed` results. The earlier report [`Report.md`](Report.md) documents the code review, corrections, and fuller interpretation of the corrected matrix.

### 5.2 Conclusion

The experiments show how an event-driven LR-FHSS simulator can be extended to explore the interaction between fragment collisions and a simplified satellite link budget. Within the evaluated matrix, altitude and transmit power have the clearest effects, while the two coding profiles have similar aggregate PDR. The results provide a reproducible baseline for parameter comparisons, not a prediction of satellite service performance.

Before using the outputs for a deployment conclusion, the link sensitivity should be calibrated to a specific receiver or measurement campaign. Further work should model distributed ground terminals and complete orbital passes, add realistic orbit and antenna/environment models, incorporate Doppler and propagation delay into reception, and validate the decoding model against a waveform-level implementation or measurements. The present implementation is best suited to transparent system-level sensitivity analysis under explicitly stated assumptions.

### Sources and reproducibility

- Simulator source: [Xexell/LR-FHSS-sim](https://github.com/Xexell/LR-FHSS-sim)
- Simulator paper: [LR-FHSS-Sim: A Discrete-Event Simulator for LR-FHSS Networks](https://oulurepo.oulu.fi/handle/10024/51865)
- LR-FHSS regional profile reference: [LoRa Alliance RP002-1.0.3](https://lora-alliance.org/wp-content/uploads/2021/05/RP-2-1.0.3.pdf)
- Corrected code review and results: [`Report.md`](Report.md)
- Raw corrected experiment output: [`results_reviewed/ntn_results.csv`](results_reviewed/ntn_results.csv)

The matrix can be regenerated from the repository root with:

```powershell
python -m lrfhss.ntn_experiments --output results_reviewed --replications 3 --simulation-time 600
```
