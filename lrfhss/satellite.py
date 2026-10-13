"""Simple, reproducible satellite-link models for LR-FHSS experiments.

The model is intentionally analytical.  It is suitable for system-level
comparisons, not for replacing a mission-specific orbit or propagation tool.
"""

from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class SatelliteConfig:
    altitude_km: float = 600.0
    elevation_deg: float = 45.0
    frequency_hz: float = 868e6
    bandwidth_hz: float = 125e3
    tx_power_dbm: float = 14.0
    tx_gain_dbi: float = 0.0
    rx_gain_dbi: float = 0.0
    noise_figure_db: float = 5.0
    required_snr_db: float = -15.0
    implementation_loss_db: float = 0.0
    shadowing_std_db: float = 0.0
    min_elevation_deg: float = 10.0
    earth_radius_km: float = 6371.0
    orbit_period_s: float = 5760.0
    include_doppler: bool = False


class SatelliteChannel:
    """Free-space LEO channel with optional deterministic movement and shadowing."""

    speed_of_light_m_s = 299_792_458.0

    def __init__(self, config=None, seed=0):
        self.config = config or SatelliteConfig()
        self.random = random.Random(seed)

    def elevation_deg(self, time_s=0.0):
        """Return a smooth pass elevation, centered on the configured elevation."""
        if self.config.orbit_period_s <= 0:
            return self.config.elevation_deg
        amplitude = max(0.0, 90.0 - self.config.min_elevation_deg)
        center = (self.config.elevation_deg - self.config.min_elevation_deg) / max(amplitude, 1e-12)
        center = min(1.0, max(0.0, center))
        phase = math.asin(2.0 * center - 1.0)
        return self.config.min_elevation_deg + amplitude * (
            (math.sin(2.0 * math.pi * time_s / self.config.orbit_period_s + phase) + 1.0) / 2.0
        )

    def slant_range_km(self, elevation_deg=None, time_s=0.0):
        elevation = self.elevation_deg(time_s) if elevation_deg is None else elevation_deg
        re = self.config.earth_radius_km
        rs = re + self.config.altitude_km
        elevation_rad = math.radians(elevation)
        return math.sqrt(rs * rs - (re * math.cos(elevation_rad)) ** 2) - re * math.sin(elevation_rad)

    def free_space_path_loss_db(self, distance_km=None, time_s=0.0):
        distance_m = (self.slant_range_km(time_s=time_s) if distance_km is None else distance_km) * 1000.0
        wavelength_m = self.speed_of_light_m_s / self.config.frequency_hz
        return 20.0 * math.log10(4.0 * math.pi * distance_m / wavelength_m)

    def received_power_dbm(self, time_s=0.0):
        loss = self.free_space_path_loss_db(time_s=time_s)
        shadowing = self.random.gauss(0.0, self.config.shadowing_std_db)
        return self.config.tx_power_dbm + self.config.tx_gain_dbi + self.config.rx_gain_dbi - loss - shadowing

    def noise_power_dbm(self):
        return -174.0 + 10.0 * math.log10(self.config.bandwidth_hz) + self.config.noise_figure_db

    def snr_db(self, time_s=0.0):
        return self.received_power_dbm(time_s) - self.noise_power_dbm() - self.config.implementation_loss_db

    def doppler_hz(self, time_s=0.0):
        if not self.config.include_doppler:
            return 0.0
        orbital_speed = math.sqrt(3.986004418e14 / ((self.config.earth_radius_km + self.config.altitude_km) * 1000.0))
        radial_speed = orbital_speed * math.cos(math.radians(self.elevation_deg(time_s)))
        return radial_speed / self.speed_of_light_m_s * self.config.frequency_hz

    def link_budget(self, time_s=0.0):
        elevation = self.elevation_deg(time_s)
        distance = self.slant_range_km(time_s=time_s)
        received_power = self.received_power_dbm(time_s)
        noise_power = self.noise_power_dbm()
        snr = received_power - noise_power - self.config.implementation_loss_db
        return {
            "elevation_deg": elevation,
            "distance_km": distance,
            "path_loss_db": self.free_space_path_loss_db(distance),
            "received_power_dbm": received_power,
            "noise_power_dbm": noise_power,
            "snr_db": snr,
            "doppler_hz": self.doppler_hz(time_s),
            "visible": elevation >= self.config.min_elevation_deg,
            "outage": elevation < self.config.min_elevation_deg or snr < self.config.required_snr_db,
        }

    def fragment_available(self, time_s=0.0):
        budget = self.link_budget(time_s)
        return budget["visible"] and not budget["outage"]

    def access_fraction(self, samples=720):
        """Estimate the fraction of an orbit with a usable link."""
        if samples < 1:
            raise ValueError("samples must be positive")
        usable = sum(self.fragment_available(i * self.config.orbit_period_s / samples) for i in range(samples))
        return usable / samples
