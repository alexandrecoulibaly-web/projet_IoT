import math
import tempfile
import unittest
from pathlib import Path

from lrfhss.acrda import BaseACRDA
from lrfhss.lrfhss_core import Base, Fragment, Packet
from lrfhss.ntn_experiments import ExperimentPlan, run_plan
from lrfhss.run import run_sim
from lrfhss.satellite import SatelliteChannel, SatelliteConfig
from lrfhss.settings import Settings
from lrfhss.traffic import Constant_Traffic


class GeometryTests(unittest.TestCase):
    def test_orbit_visibility_matches_analytic_fraction(self):
        channel = SatelliteChannel(SatelliteConfig(elevation_deg=90, required_snr_db=-200))
        self.assertAlmostEqual(channel.elevation_deg(0), 90)
        self.assertAlmostEqual(channel.elevation_deg(channel.orbit_period_s / 2), -90)
        self.assertFalse(channel.fragment_available(channel.orbit_period_s / 2))
        mask = math.radians(channel.config.min_elevation_deg)
        expected = (math.acos(6371 / 6971 * math.cos(mask)) - mask) / math.pi
        self.assertAlmostEqual(channel.access_fraction(samples=10000), expected, delta=0.0002)

    def test_initial_elevation_and_altitude_dependent_period(self):
        channel = SatelliteChannel()
        self.assertAlmostEqual(channel.elevation_deg(0), 45)
        self.assertGreater(SatelliteChannel(SatelliteConfig(altitude_km=800)).orbit_period_s,
                           channel.orbit_period_s)

    def test_signed_doppler_agrees_with_range_derivative(self):
        channel = SatelliteChannel(SatelliteConfig(elevation_deg=90, include_doppler=True))
        self.assertGreater(channel.doppler_hz(-60), 0)
        self.assertLess(channel.doppler_hz(60), 0)
        self.assertAlmostEqual(channel.doppler_hz(0), 0)
        dt = 0.001
        velocity = (channel.slant_range_km(time_s=60 + dt) -
                    channel.slant_range_km(time_s=60 - dt)) * 1000 / (2 * dt)
        self.assertAlmostEqual(channel.doppler_hz(60),
                               -velocity * 868e6 / channel.speed_of_light_m_s, places=3)

    def test_static_and_diagnostic_rng(self):
        channel = SatelliteChannel(SatelliteConfig(orbit_period_s=0, shadowing_std_db=3))
        state = channel.random.getstate()
        channel.access_fraction()
        self.assertEqual(state, channel.random.getstate())
        self.assertEqual(channel.elevation_deg(5000), 45)

    def test_link_budget_reference(self):
        channel = SatelliteChannel(SatelliteConfig(elevation_deg=90, orbit_period_s=0))
        self.assertAlmostEqual(channel.free_space_path_loss_db(), 146.781, delta=0.01)
        self.assertAlmostEqual(channel.noise_power_dbm(), -118.0309, places=3)


class ReceiverTests(unittest.TestCase):
    def test_touching_fragments_do_not_collide(self):
        base = Base(1, 1)
        a, b = (Fragment('payload', 1, 0, i) for i in range(2))
        b.timestamp = 1
        base.receive_packet(a)
        base.check_collision(b)
        self.assertEqual(base.fragments_collided, 0)

    def test_collision_count_is_unique_and_survives_cancellation(self):
        base = Base(1, 1)
        fragments = [Fragment('payload', 1, 0, i) for i in range(3)]
        for f in fragments:
            base.check_collision(f)
            base.receive_packet(f)
        self.assertEqual(base.fragments_collided, 3)
        for f in fragments:
            f.collided.clear()
            base.finish_fragment(f)
        self.assertEqual(base.fragments_collided, 3)

    def test_acrda_does_not_mutate_transmit_sequence(self):
        base = BaseACRDA(1, 0.1, 0.05, 1, 1)
        packet = Packet(1, 1, 1, 3, 0.2, 0.1)
        original = list(packet.fragments)
        packet.fragments[0].transmitted = 1
        base.try_decode(packet, 1)
        self.assertEqual(packet.fragments, original)

    def test_acrda_records_latency_once_and_respects_outage(self):
        base = BaseACRDA(1, 2, 0.5, 1, 1)
        packet = Packet(1, 1, 1, 1, 0.2, 0.1)
        base.add_node(1)
        packet.transmission_start = 0
        for f in packet.fragments:
            f.transmitted = 1
        packet.fragments[1].link_success = False
        self.assertFalse(base.try_decode(packet, 1))
        packet.fragments[1].link_success = True
        self.assertTrue(base.try_decode(packet, 1))
        self.assertFalse(base.try_decode(packet, 1.1))
        self.assertEqual(base.latencies, [1])

    def test_packet_without_headers_can_be_constructed(self):
        self.assertEqual(len(Packet(1, 1, 0, 2, 0.2, 0.1).fragments), 2)


class SimulationTests(unittest.TestCase):
    def test_no_traffic_is_missing_pdr_and_latency(self):
        result = run_sim(Settings(number_nodes=0, simulation_time=1), return_metrics=True)
        self.assertIsNone(result['pdr'])
        self.assertIsNone(result['latency_s'])
        self.assertEqual(result['access_fraction'], 1)

    def test_no_success_has_no_latency(self):
        result = run_sim(Settings(number_nodes=2, simulation_time=10,
            traffic_param={'average_interval': 0.1},
            satellite=SatelliteChannel(SatelliteConfig(required_snr_db=200))), return_metrics=True)
        self.assertGreater(result['transmitted_packets'], 0)
        self.assertIsNone(result['latency_s'])

    def test_shadowing_reproducibility_with_actual_traffic(self):
        settings = Settings(number_nodes=3, simulation_time=20,
            traffic_param={'average_interval': 1},
            satellite=SatelliteChannel(SatelliteConfig(shadowing_std_db=5)))
        first = run_sim(settings, seed=1, return_metrics=True)
        self.assertGreater(first['transmitted_packets'], 0)
        self.assertEqual(first, run_sim(settings, seed=1, return_metrics=True))

    def test_constant_traffic_initializes_its_state(self):
        traffic = Constant_Traffic({'constant_interval': 2, 'standard_deviation': 0})
        self.assertGreaterEqual(traffic.traffic_function(), 0)
        self.assertEqual(traffic.traffic_function(), 2)

    def test_transmit_power_override(self):
        settings = Settings(satellite=SatelliteChannel(), tx_power_dbm=18)
        self.assertEqual(settings.satellite.config.tx_power_dbm, 18)

    def test_experiment_exports_missing_metrics_and_manifest(self):
        plan = ExperimentPlan(altitudes_km=(600,), device_counts=(0,),
            average_intervals_s=(300,), tx_powers_dbm=(14,), codes=('1/3',),
            replications=1, simulation_time_s=1)
        with tempfile.TemporaryDirectory() as directory:
            rows = run_plan(plan, directory)
            self.assertIsNone(rows[0]['latency_s'])
            self.assertTrue((Path(directory) / 'manifest.json').exists())
            self.assertTrue((Path(directory) / 'summary.csv').exists())


if __name__ == '__main__':
    unittest.main()
