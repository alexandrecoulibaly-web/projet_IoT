import unittest

from lrfhss.run import run_sim
from lrfhss.satellite import SatelliteChannel, SatelliteConfig
from lrfhss.settings import Settings


class SatelliteModelTests(unittest.TestCase):
    def test_slant_range_increases_with_altitude(self):
        low = SatelliteChannel(SatelliteConfig(altitude_km=500)).slant_range_km(elevation_deg=90)
        high = SatelliteChannel(SatelliteConfig(altitude_km=800)).slant_range_km(elevation_deg=90)
        self.assertAlmostEqual(low, 500.0, places=6)
        self.assertGreater(high, low)

    def test_path_loss_increases_with_altitude(self):
        low = SatelliteChannel(SatelliteConfig(altitude_km=500)).free_space_path_loss_db(
            distance_km=500
        )
        high = SatelliteChannel(SatelliteConfig(altitude_km=800)).free_space_path_loss_db(
            distance_km=800
        )
        self.assertGreater(high, low)

    def test_reproducible_metrics(self):
        channel = SatelliteChannel(SatelliteConfig(elevation_deg=90, shadowing_std_db=0))
        settings = Settings(number_nodes=4, simulation_time=30, satellite=channel)
        first = run_sim(settings, seed=7, return_metrics=True)
        second = run_sim(settings, seed=7, return_metrics=True)
        self.assertEqual(first, second)
        self.assertIn("pdr", first)

    def test_link_outage_when_snr_requirement_is_unreachable(self):
        channel = SatelliteChannel(SatelliteConfig(required_snr_db=100, elevation_deg=90))
        settings = Settings(
            number_nodes=2, simulation_time=10,
            traffic_param={"average_interval": 0.1}, satellite=channel,
        )
        result = run_sim(settings, seed=1, return_metrics=True)
        self.assertEqual(result["pdr"], 0.0)
        self.assertGreater(result["outage_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
