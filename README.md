# LR-FHSS-sim
LR-FHSS event-driven simulator built in python.

## Instalation Guide
* pip:
  
Download the source code and extract it to a folder.

Open a terminal in the folder and execute the following to install the prerequisites libraries.
  ```sh
  pip install -r requirements.txt
  ```

Run the following to install the library.
  ```sh
  pip install .
  ```

If you wish to make changes to the library, you can install it with the editable flag, so any changes to the source code will apply to the version installed.
  ```sh
  pip install -e .
  ```

## Usage

The project contains three main files. lrfhss_core.py contains the the main classes and features needed to run the simulation. This classes don't have any main procedures. In order to run the simulation, you have to built the simulation setup with the classes present in that file. The second file, settings.py, contains several adjustable simulation parameters and is used to configure the simulator behavior. The file run.py is an example of a simulation scenario setup. It simply builds a network with a certain amount of devices with certain input parameters, run it for a certain amount of time and returns the amount of successfully received packets divided by the amount of packets transmitted. For an example of how to use the run.py file, refer to the file examples/examples.ipynb.

Two other files provide simulator extensions. The file traffic.py implements different types of traffic generators to be used by Node objects. Finally, acrda.py implements a new version of the Base (base station) class to implement the ACRDA receiver/decoder.

Plots were made with the [SciencePlots](https://github.com/garrettj403/SciencePlots) library.

## Simplified satellite IoT uplink extension

The original terrestrial/base-station simulator remains the default.  The
opt-in `lrfhss.satellite.SatelliteChannel` adds an analytical LEO link budget:
altitude/elevation-dependent slant range, free-space path loss, received power,
thermal noise, SNR thresholding, access fraction, circular overhead satellite
movement, and signed Doppler estimation. A fragment is only decodable when it is
both collision-free and within the link budget.

Run the reproducible experiment matrix (the default is laptop-sized but can be
reduced with `--replications` and `--simulation-time`):

```powershell
python -m lrfhss.ntn_experiments --output results_reviewed --replications 3 --simulation-time 600
```

This writes `ntn_results.csv`, `summary.csv`, `manifest.json` and four PNG figures.
The default profiles are 1/3 with three headers and 2/3 with two headers.
Every replication uses a
deterministic seed derived from `20261012`.  For a single run, construct
`Settings(..., satellite=SatelliteChannel(SatelliteConfig(...)))` and call
`run_sim(settings, seed=..., return_metrics=True)`.  The returned dictionary
contains PDR/PSR, collision and outage rates, throughput, mean latency,
successful/transmitted packet counts, unfinished transmissions, and both orbit
and observation-window access fractions. PDR is `None` when no packet starts;
latency is `None` when none succeeds. CSV exports these as empty cells.

Validate the extension with:

```powershell
python -m unittest discover -s tests -v
```

The model assumes free-space propagation, colocated ground terminals, a
nonrotating spherical Earth and a circular overhead orbit. The initial elevation
is on the approaching side; the default orbital period follows Kepler's law.
Set `orbit_period_s=0` for static geometry. Doppler is diagnostic only, and
propagation delay is absent from event timing. Antenna patterns, handover,
link adaptation and waveform decoding are not modeled.

The default 125 kHz equivalent noise bandwidth and -15 dB SNR threshold imply
an **illustrative, uncalibrated -133.03 dBm sensitivity** with 5 dB noise figure.
Do not interpret that bandwidth as LR-FHSS's instantaneous modulation bandwidth
or use the output as a validated satellite link prediction.

Read [Report.md](Report.md) for the code audit, corrected results and remaining
model limitations. [Report_legacy.md](Report_legacy.md), `results_small` and
`results_quick` preserve the historical analysis, which used an incorrect
always-visible moving-satellite model. Do not overwrite those folders when
running corrected experiments. `python examples/audit_results.py` independently
prints the historical and corrected aggregate statistics.
