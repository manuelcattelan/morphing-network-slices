# Morphing Network Slicing #

## Introduction ##
The project shows how to implement network slicing in an SDN in order to obtain different virtualized topologies starting from a shared, predefined configuration. The goal here is to show that data packets can be routed differently with regard to their type (audio, video, udp packet, tcp packet, etc...) and that different subnets containing different (but not necessarily all) hosts can be derived for each datagram type.

**Phisical topology** (star):
```text             
[h1] --\          /-- [h3]  
       (S2)    (S3)     
[h2] --/  \    /  \-- [h4]
           \  /    
           (S1)
           /  \
[h8] --\  /    \  /-- [h5]
       (S5)    (S4)     
[h7] --/          \-- [h6]
```

The folder contains the following files:

1. `network.py`: Script created to build a generic network with any topology (star, ring, string) and connect an arbitrary number of host nodes to each outer switch;

2. `topology_morphing_controller.py`: A Ryu SDN controller script that allows for different virtual topologies to be used for different network slices based on the protocol used and the type of packet to be transmitted.

## Topology morphing
The topology of the network can be virtualized by changing the behaivour of the central switch:

#### Virtualized circle topology:
```text
    h1 h2  h3 h4   
     \/     \/    
     S2     S3   
      |     |    
 /-->S1---->S1-->\
 |               |
 \<--S1<----S1<--/
      |     |
     S5     S4
     /\     /\
   h8 h7   h6 h5
```
For a ring network the packets are simply forwarded to the *out_port* next to the *in_port* in the same direction (clockwise), as if the 
outer switches were just connected to their neighbors.  

#### Virtualized string topology:
```text
 h1 h2 h3 h4  h5 h6 h7 h8
  \/    \/     \/    \/
  S2    S3     S4    S5
  |      |     |      |
  \-S1---S1---S1---S1-/
```
A string works very similarly to a circle but the packets have to be routed to the switch immediately to the left or right based on whether the *out_port* is smaller or larger than the *in_port*, so the routing table is checked before sending a datagram to the next switch.

## How to Run
You can simple run the emulation applications with following commands:

1. Making sure Mininet is clear and all Ryu controllers instances are terminated:
    ```bash
    $ sudo mn -c
    ```

1. Enabling Ryu controller to load the application and to run in the background:
    ```bash
    $ ryu-manager topology_morphing_controller.py &
    ```
    It's best to run this on another terminal window or by using `tmux`
1. Starting the network with Mininet:
    ```bash
    $ sudo mn --custom network.py --controller remote --topo star,5,2 --mac
    ```
    This command generates a custom network using the `network.py` script with 5 switches in a star topolgy: a central switch S1, 4 other switches (S2, S3, S4, S5) connected to it directly and 2 hosts for each of the outer switches, with progressive mac addresses (from `00:00:00:00:00:01`, in the order they are created).

*Please note: before testing the network you need to wait for STP to configure all ports. Wait until you see STP messages reading "FORWARD" (this can take up to a minute).*

## How to test the network
Here are a set of tests to verfy that our network is working as expected:

1. ping mode: verifying connectivity, e.g.
    ```bash
    mininet> pingall
	*** Ping: testing ping reachability
	h1 -> h2 h3 h4 h5 h6 h7 h8
	h2 -> h1 h3 h4 h5 h6 h7 h8
	h3 -> h1 h2 h4 h5 h6 h7 h8
	h4 -> h1 h2 h3 h5 h6 h7 h8
	h5 -> h1 h2 h3 h4 h6 h7 h8
	h6 -> h1 h2 h3 h4 h5 h7 h8
	h7 -> h1 h2 h3 h4 h5 h6 h8
	h8 -> h1 h2 h3 h4 h5 h6 h7
	*** Results: 0% dropped (56/56 received)
    ```
    Since *ping* uses the Internet Control Message Protocol (ICMP) it will use the 'generic' network slice, with a star topology and all hosts included.

1. iperf mode: verifying bandwidth, e.g.
    ```bash
    mininet> iperf h1 h3
    *** Iperf: testing TCP bandwidth between h1 and h3 
    *** Results: ['958 Kbits/sec', '1.76 Mbits/sec']
    mininet> iperf h2 h4
    *** Iperf: testing TCP bandwidth between h2 and h4 
    *** Results: ['958 Kbits/sec', '1.76 Mbits/sec']
    ```
    This test uses TCP to test bandwidth between hosts following a star topology which excludes no hosts.

1. Testing ***RING*** mode: 

    The audio slice, which is identified by a UDP connection on port 1, uses a ring topology and excludes hosts h1 and h2.

    Log on to h3 and h6 in new terminals:
    ```bash
    mininet> xterm h3 h6
    ```
    *Note: this isn't supported on Windows installations of comnetsemu because the terminal cannot open new windows.*

    Configure h6 as server (`-s`) listening for UDP packets (`-u`) on port 1 (`-p 1`):
    ```bash
    $ iperf -s -u -p 1
    ```

    Generate traffic from h3 configured as client (`-c`) to h6 identified by it's IP address with a bandwith of .1M (`-b .1M`):
    ```bash
    $ iperf -c 10.0.0.6 -u -p 1 -b .1M -t 10 -i 1
    ```

    This command will send packets on the "audio" slice with a ring topolgy. The path taken is visible on the controller terminal from the logs printed.
    
    If instead of h3 we used h1, none of the packets would reach the destination since host h1 is blocked from sending or receiving packets on this slice.

1. Testing ***STRING*** mode: 

    The video slice, which is identified by a UDP connection on port 2, uses a string topology and excludes hosts h3 and h6.

    Log on to h2 and h7 in new terminals:
    ```bash
    mininet> xterm h2 h7
    ```

    Configure h2 as server listening for UDP packets on port 2:
    ```bash
    $ iperf -s -u -p 2
    ```

    Generate traffic from h7 configured as client to h2 identified by it's IP address with a bandwith of .1M:
    ```bash
    $ iperf -c 10.0.0.2 -u -p 1 -b .1M -t .1 -i 1
    ```

    This command will send packets on the "video" slice with a string topolgy. The path taken is again visible on the controller terminal from the logs printed.
    
    If instead of h7 we used h6, none of the packets would reach the destination since host h6 is blocked from sending or receiving packets on this slice.
