from lrfhss.lrfhss_core import Base

class BaseACRDA(Base):
    def __init__(self, obw, window_size, window_step, time_on_air, threshold, channel=None):

        super().__init__(obw, threshold, channel)
        self.memory = {}
        self.window_size = window_size*time_on_air
        self.window_step = window_step*time_on_air

    def add_packet(self, packet):
        self.memory[packet.id] = packet

    def try_decode(self,packet,now):
        if packet.success:
            return False
        # Never mutate the transmitter's fragment list: Packet.next indexes it.
        fragments = [f for f in packet.fragments if self.in_window(f, now)]
        h_success = sum(f.type == 'header' and not f.collided and f.transmitted and f.link_success for f in fragments)
        p_success = sum(f.type == 'payload' and not f.collided and f.transmitted and f.link_success for f in fragments)
        success = 1 if ((h_success>0) and (p_success >= self.threshold)) else 0
        if success == 1:
            self.packets_received[packet.node_id] += 1
            packet.success = 1
            packet.decode_time = now
            if packet.transmission_start is not None:
                self.latencies.append(now - packet.transmission_start)
            for f in fragments:
                f.success = 1
                for c in list(f.collided):
                    f.collided.remove(c)
                    c.collided.remove(f)
            return True
        else:
            return False

    def sic_window(self, env):
        yield env.timeout(self.window_size)
        while(1):
            #FIRST: Remove fragments from memory that are outside the window.
            for p in list(self.memory):
                if all(f.transmitted and not self.in_window(f, env.now)
                       for f in self.memory[p].fragments):
                    del(self.memory[p])
            
            #SECOND: Apply interference cancellation
            new_recover = True #variable to check if at least one packet was recovered the interference cancellation
                       #if it did, we need to do the same procedure again until no new packet is recovered
            while(new_recover):
                failed_packets = (p for p in self.memory.values() if p.success == 0)
                new_recover = False
                for p in failed_packets:
                    if self.try_decode(p,env.now):
                        new_recover = True

            yield env.timeout(self.window_step)


    def in_window(self, fragment, now):
        return True if (now - fragment.timestamp)<=self.window_size else False
