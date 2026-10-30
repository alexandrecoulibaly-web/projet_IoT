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
    # Equivalent receiver noise bandwidth, NOT the hopping-channel bandwidth.
    # This and required_snr_db define an illustrative, uncalibrated sensitivity.
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
    orbit_period_s: float | None = None
    include_doppler: bool = False

    def __post_init__(self):
        for name in ("altitude_km", "frequency_hz", "bandwidth_hz", "earth_radius_km"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not -90 <= self.elevation_deg <= 90:
            raise ValueError("elevation_deg must be between -90 and 90")
        if not 0 <= self.min_elevation_deg <= 90:
            raise ValueError("min_elevation_deg must be between 0 and 90")
        if self.shadowing_std_db < 0:
            raise ValueError("shadowing_std_db must be nonnegative")


class SatelliteChannel:
    """Free-space LEO channel with optional deterministic movement and shadowing."""

    speed_of_light_m_s = 299_792_458.0

    def __init__(self, config=None, seed=0):
        self.config = config or SatelliteConfig()
        self.seed = seed
        self.random = random.Random(seed)

    @property
    def orbit_period_s(self):
        """Kepler period unless explicitly overridden; <=0 requests static geometry."""
        if self.config.orbit_period_s is not None:
            return self.config.orbit_period_s
        radius_m = (self.config.earth_radius_km + self.config.altitude_km) * 1000
        return 2 * math.pi * math.sqrt(radius_m ** 3 / 3.986004418e14)

    def central_angle_rad(self, time_s):
        # Start on the approaching side at elevation_deg, then pass overhead.
        re = self.config.earth_radius_km
        rs = re + self.config.altitude_km
        elevation = math.radians(self.config.elevation_deg)
        initial = math.acos(re / rs * math.cos(elevation)) - elevation
        return -initial + 2 * math.pi * time_s / self.orbit_period_s

    def elevation_deg(self, time_s=0.0):
        """Circular overhead orbit over a fixed site on a nonrotating spherical Earth."""
        if self.orbit_period_s <= 0:
            return self.config.elevation_deg
        angle = self.central_angle_rad(time_s)
        rs = self.config.earth_radius_km + self.config.altitude_km
        return math.degrees(math.atan2(rs * math.cos(angle) - self.config.earth_radius_km,
                                      rs * abs(math.sin(angle))))

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
        if not self.config.include_doppler or self.orbit_period_s <= 0:
            return 0.0
        re = self.config.earth_radius_km
        rs = re + self.config.altitude_km
        radial_speed = (re * rs * math.sin(self.central_angle_rad(time_s))
                        * (2 * math.pi / self.orbit_period_s)
                        / self.slant_range_km(time_s=time_s) * 1000)
        return -radial_speed / self.speed_of_light_m_s * self.config.frequency_hz

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

    def access_fraction(self, samples=720, duration_s=None):
        """Expected usable fraction over one orbit or a specified observation window.

        Integrates Gaussian shadowing analytically without consuming the channel RNG.
        This is temporal availability at one site, not geographic coverage.
        """
        if samples < 1:
            raise ValueError("samples must be positive")
        duration = max(self.orbit_period_s, 0) if duration_s is None else duration_s
        if duration < 0:
            raise ValueError("duration_s must be nonnegative")
        usable = 0.0
        for i in range(samples):
            time = (i + 0.5) * duration / samples
            if self.elevation_deg(time) < self.config.min_elevation_deg:
                continue
            margin = (self.config.tx_power_dbm + self.config.tx_gain_dbi
                      + self.config.rx_gain_dbi - self.free_space_path_loss_db(time_s=time)
                      - self.noise_power_dbm() - self.config.implementation_loss_db
                      - self.config.required_snr_db)
            sigma = self.config.shadowing_std_db
            usable += (0.5 * (1 + math.erf(margin / (sigma * math.sqrt(2))))
                       if sigma else float(margin >= 0))
        return usable / samples
