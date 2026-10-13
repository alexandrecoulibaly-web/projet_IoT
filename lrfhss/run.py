from lrfhss.lrfhss_core import *
from lrfhss.acrda import BaseACRDA
from lrfhss.settings import Settings
import simpy

def run_sim(settings: Settings, seed=0, return_metrics=False):
    random.seed(seed)
    np.random.seed(seed)
    env = simpy.Environment()
    if settings.base=='acrda':
        bs = BaseACRDA(settings.obw, settings.window_size, settings.window_step, settings.time_on_air, settings.threshold, settings.satellite)
        env.process(bs.sic_window(env))
    else:
        bs = Base(settings.obw, settings.threshold, settings.satellite)
    
    nodes = []
    for i in range(settings.number_nodes):
        traffic_generator = settings.traffic_class(dict(settings.traffic_param))
        node = Node(settings.obw, settings.headers, settings.payloads, settings.header_duration, settings.payload_duration, settings.transceiver_wait, traffic_generator)
        bs.add_node(node.id)
        nodes.append(node)
        env.process(node.transmit(env, bs))
    # start simulation
    env.run(until=settings.simulation_time)

    # after simulation
    success = sum(bs.packets_received.values())
    transmitted = sum(n.transmitted for n in nodes)

    if transmitted == 0:
        return 1 if not return_metrics else {
            "pdr": 1.0, "psr": 1.0, "collision_rate": 0.0, "throughput_bps": 0.0,
            "latency_s": 0.0, "outage_rate": 0.0, "access_fraction": 0.0,
            "successful_packets": 0, "transmitted_packets": 0,
        }
    metrics = {
        "pdr": success / transmitted,
        "psr": success / transmitted,
        "collision_rate": bs.fragments_collided / max(bs.fragments_total, 1),
        "throughput_bps": success * settings.payload_size * 8 / settings.simulation_time,
        "latency_s": float(np.mean(bs.latencies)) if bs.latencies else 0.0,
        "outage_rate": bs.fragments_outage / max(bs.fragments_total, 1),
        "access_fraction": settings.satellite.access_fraction() if settings.satellite else 1.0,
        "successful_packets": success,
        "transmitted_packets": transmitted,
    }
    return metrics if return_metrics else [[metrics["pdr"]], [success * settings.payload_size], [transmitted]]

    #Get the average success per device, used to plot the CDF 
    #success_per_device = [1 if n.transmitted == 0 else bs.packets_received[n.id]/n.transmitted for n in nodes]
    #return success_per_device
if __name__ == "__main__":
   s = Settings()
   print(run_sim(s))