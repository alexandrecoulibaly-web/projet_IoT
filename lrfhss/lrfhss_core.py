import random
import numpy as np
from abc import ABC, abstractmethod

        
class Fragment():
    def __init__(self, type, duration, channel, packet):
        self.packet = packet
        self.duration = duration
        self.success = 0
        self.transmitted = 0
        self.type = type
        self.channel = channel
        self.timestamp = 0
        self.id = id(self)
        self.collided = []
        self.ever_collided = False
        self.link_success = True

class Packet():
    def __init__(self, node_id, obw, headers, payloads, header_duration, payload_duration):
        self.id = id(self)
        self.node_id = node_id
        self.index_transmission = 0
        self.success = 0
        self.channels = random.choices(range(obw), k=headers+payloads)
        self.fragments = []
        self.transmission_start = None
        self.decode_time = None
        for h in range(headers):
            self.fragments.append(Fragment('header',header_duration, self.channels[h], self.id))
        for p in range(payloads):
            self.fragments.append(Fragment('payload',payload_duration, self.channels[p+headers], self.id))

    def next(self):
        self.index_transmission+=1
        try:
            return self.fragments[self.index_transmission-1]
        except:
            return False
        
# Instead of grid selection, we consider one grid of obw (usually 35 for EU) channels, as it is faster to simulate and extrapolate the number.
# Later we can implement the grid selection in case of interest of studying it.
#    def new_channels(self, obw, fragments):
#        self.channels = random.sample(range(obw), fragments)


class Traffic(ABC):
    @abstractmethod
    def __init__(self, traffic_param):
        self.traffic_param = traffic_param

    @abstractmethod
    def traffic_function(self):
        pass

class Node():
    def __init__(self, obw, headers, payloads, header_duration, payload_duration, transceiver_wait, traffic_generator):
        self.id = id(self)
        self.transmitted = 0
        self.traffic_generator = traffic_generator
        self.transceiver_wait = transceiver_wait
        # Packet info that Node has to store
        self.obw = obw
        self.headers = headers
        self.payloads = payloads
        self.header_duration = header_duration
        self.payload_duration = payload_duration
        self.packet = Packet(self.id, self.obw, self.headers, self.payloads, self.header_duration, self.payload_duration)

    def next_transmission(self):
        return self.traffic_generator.traffic_function()

    def end_of_transmission(self):
        self.packet = Packet(self.id, self.obw, self.headers, self.payloads, self.header_duration, self.payload_duration)

    def transmit(self, env, bs):
        while 1:
            #time between transmissions
            yield env.timeout(self.next_transmission())
            self.transmitted += 1
            self.packet.transmission_start = env.now
            bs.add_packet(self.packet)
            next_fragment = self.packet.next()
            first_payload = 0
            while next_fragment:
                if first_payload == 0 and next_fragment.type=='payload': #account for the transceiver wait time between the last header and first payload fragment
                    first_payload=1
                    yield env.timeout(self.transceiver_wait)
                next_fragment.timestamp = env.now
                #checks if the fragment is colliding with the fragments in transmission now
                bs.check_collision(next_fragment)
                #add the fragment to the list of fragments being transmitted.
                bs.receive_packet(next_fragment)
                #wait the duration (time on air) of the fragment
                yield env.timeout(next_fragment.duration)
                #removes the fragment from the list.
                bs.finish_fragment(next_fragment)
                #check if base can decode the packet now.
                #tries to decode if not decoded yet.
                if self.packet.success == 0:
                    bs.try_decode(self.packet,env.now)
                #select the next fragment
                next_fragment = self.packet.next()
            
            #end of transmission procedure
            self.end_of_transmission()

class Base():
    def __init__(self, obw, threshold, channel=None):
        self.id = id(self)
        self.transmitting = {}
        for channel_id in range(obw):
            self.transmitting[channel_id] = []
        self.packets_received = {}
        self.threshold = threshold
        self.channel = channel
        self.fragments_total = 0
        self.fragments_collided = 0
        self.fragments_outage = 0
        self.latencies = []

    def add_packet(self, packet):
        pass

    def add_node(self, id):
        self.packets_received[id] = 0

    def receive_packet(self, fragment):
        self.fragments_total += 1
        if self.channel is not None:
            fragment.link_success = self.channel.fragment_available(fragment.timestamp)
            if not fragment.link_success:
                self.fragments_outage += 1
        self.transmitting[fragment.channel].append(fragment)

    def finish_fragment(self, fragment):
        self.transmitting[fragment.channel].remove(fragment)
        if len(fragment.collided) == 0 and fragment.link_success:
            fragment.success = 1
        fragment.transmitted = 1

    def check_collision(self,fragment):
        for f in self.transmitting[fragment.channel]:
            # Half-open airtime intervals: touching endpoints do not collide.
            if f.timestamp + f.duration <= fragment.timestamp:
                continue
            for collided in (f, fragment):
                if not collided.ever_collided:
                    self.fragments_collided += 1
                    collided.ever_collided = True
            f.collided.append(fragment)
            fragment.collided.append(f)

    def try_decode(self,packet,now):
        if packet.success:
            return False
        h_success = sum( ((len(f.collided)==0) and f.transmitted==1 and f.link_success) if (f.type=='header') else 0 for f in packet.fragments)
        p_success = sum( ((len(f.collided)==0) and f.transmitted==1 and f.link_success) if (f.type=='payload') else 0 for f in packet.fragments)
        success = 1 if ((h_success>0) and (p_success >= self.threshold)) else 0
        if success == 1:
            self.packets_received[packet.node_id] += 1
            packet.success = 1
            packet.decode_time = now
            if packet.transmission_start is not None:
                self.latencies.append(now - packet.transmission_start)
            return True
        else:
            return False
