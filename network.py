#!/usr/bin/python3

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel

# definition for star topology class
class star_topology(Topo):
    def build(self, total_switches, hosts_per_switch):

        # compute the total number of hosts
        total_hosts = (total_switches - 1) * hosts_per_switch
        
        # create #total_switches switch nodes 
        for i in range(total_switches):
            self.addSwitch("s%s" % (i + 1))

        # create #total_hosts host nodes
        for i in range(total_hosts):
            self.addHost("h%s" % (i + 1))

        # central switch with dpid of last switch node created
        central_switch_dpid = ("s%s" % 1)

        # create inner links between outer switches and central switch
        for i in range(1, total_switches):
            outer_switch_dpid = ("s%s" % (i + 1))
            self.addLink(outer_switch_dpid, central_switch_dpid)
    
        # create outer links between outer switches and hosts
        index = 1
        for i in range(1, total_switches):
            outer_switch_dpid = ("s%s" % (i + 1))
            for j in range(hosts_per_switch):
                host_dpid = ("h%s" % index)
                self.addLink(outer_switch_dpid, host_dpid)
                index = index + 1

# definition for string topology class
class string_topology(Topo):
    def build(self, total_switches, hosts_per_switch):

        # compute the total number of hosts
        total_hosts = (total_switches) * hosts_per_switch
        
        # create #switches switch nodes 
        for i in range(total_switches):
            self.addSwitch("s%s" % (i + 1))

        # create #total_hosts host nodes
        for i in range(total_hosts):
            self.addHost("h%s" % (i + 1))

        # create links between switches
        for i in range(1, total_switches):
            previous_switch_dpid = ("s%s" % i)
            present_switch_dpid = ("s%s" % (i+1))
            self.addLink(previous_switch_dpid, present_switch_dpid)
    
        # create outer links between switches and hosts
        index = 1
        for i in range(total_switches):
            switch_dpid = ("s%s" % (i + 1))
            for j in range(hosts_per_switch):
                host_dpid = ("h%s" % index)
                self.addLink(switch_dpid, host_dpid)
                index = index + 1

# definition for ring topology class
class ring_topology(Topo):
    def build(self, total_switches, hosts_per_switch):

        # compute the total number of hosts
        total_hosts = (total_switches) * hosts_per_switch
        
        # create #switches switch nodes 
        for i in range(total_switches):
            self.addSwitch("s%s" % (i + 1))

        # create #total_hosts host nodes
        for i in range(total_hosts):
            self.addHost("h%s" % (i + 1))

        # create links between switches
        for i in range(1, total_switches):
            previous_switch_dpid = ("s%s" % i)
            present_switch_dpid = ("s%s" % (i+1))
            self.addLink(previous_switch_dpid, present_switch_dpid)
        
        #create link between first and last switches
        first_switch_dpid = ("s%s" % 1)
        last_switch_dpid = ("s%s" % total_switches)
        self.addLink(first_switch_dpid, last_switch_dpid)
    
        # create outer links between switches and hosts
        index = 1
        for i in range(total_switches):
            switch_dpid = ("s%s" % (i + 1))
            for j in range(hosts_per_switch):
                host_dpid = ("h%s" % index)
                self.addLink(switch_dpid, host_dpid)
                index = index + 1

topos = { 'star' : star_topology,
          'string' : string_topology,
          'ring' : ring_topology 
        }

def startNetwork():
    # build topology
    topo = topology()
    # build network
    net = Mininet(
            topo = topo,
            controller = RemoteController ('c0', ip = '127.0.0.1', port = 6633)
        )
    # start network
    net.start()
    # prompt CLI
    CLI(net)
    # stop network
    net.stop()

# main function
if __name__ == '__main__':
    # print useful information
    setLogLevel('info')
    startNetwork()