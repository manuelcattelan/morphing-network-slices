from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import dpid
from ryu.lib import stplib
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import udp
from ryu.lib.packet import tcp
from ryu.topology import event
from ryu.topology import switches
from ryu.topology.api import get_switch
from ryu.topology.api import get_link


class Stp_learning_controller(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'stplib': stplib.Stp}

    def __init__(self, *args, **kwargs):
        super(Stp_learning_controller, self).__init__(*args, **kwargs)

        # initialize controller network variables
        self.routing_table = {}
        self.stp = kwargs['stplib']
        self.switches = []
        self.links = []
        
        self.audio_port = 1
        self.video_port = 2

        # define which topology will be used for each packet type
        self.packet_topology = {}
        self.packet_topology['audio']   = 'ring'   # udp for port audio_port
        self.packet_topology['video']   = 'string' # udp for port video_port
        self.packet_topology['udp']     = 'star'   # udp for any other port
        self.packet_topology['tcp']     = 'star'   # all tcp ports
        self.packet_topology['generic'] = 'star'   # anything that doesn't match

        self.slice_exclude = {}
        # hosts h1 and h2 are excluded from sending or receiving audio packets
        self.slice_exclude['audio'] = {'00:00:00:00:00:01','00:00:00:00:00:02'}
        # hosts h3 and h6 are excluded from sending or receiving video packets
        self.slice_exclude['video'] = {'00:00:00:00:00:03','00:00:00:00:00:06'}
        # no excluded hosts for other slices
        self.slice_exclude['udp'] = {}
        self.slice_exclude['tcp'] = {}
        self.slice_exclude['generic'] = {}
        
    @set_ev_cls(stplib.EventPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.routing_table.setdefault(dpid, {})

        # if a node does not know source, learn mac address of source and store in_port to avoid flooding next time
        # only store first time because the packet is sent back along the way
        if src not in self.routing_table[dpid]:
            self.routing_table[dpid][src] = in_port

        # compute the number of external switches in star topology
        external_switches = len(self.switches) - 1
        # initialize packet_type variable
        packet_type = '' 

        # check protocol and destination port in order to change topology
        if (pkt.get_protocol(udp.udp) and pkt.get_protocol(udp.udp).dst_port == self.audio_port):
            packet_type = 'audio'
        elif (pkt.get_protocol(udp.udp) and pkt.get_protocol(udp.udp).dst_port == self.video_port):
            packet_type = 'video'
        elif (pkt.get_protocol(udp.udp)):
            packet_type = 'udp'
        elif (pkt.get_protocol(tcp.tcp)):
            packet_type = 'tcp'
        else:
            packet_type = 'generic'

        # if destination is known and in routing_table, retrieve out_port
        if dst in self.routing_table[dpid]:
            # ignore packets if source/destination is not in the corresponding slice
            if dst in self.slice_exclude[packet_type] or src in self.slice_exclude[packet_type]:
                # self.logger.info("packet excluded")
                return

            # compute toplogy to be used for packet routing 
            topology = self.packet_topology[packet_type]

            if topology == 'star':
                # both outer switches and central switch retrieve the out_port from the routing table
                out_port = self.routing_table[dpid][dst]

            elif topology == 'ring':
                # outer switches 
                if dpid != 1:
                    if in_port == self.routing_table[dpid][dst]:
                        # use OFPP_IN_PORT to send packet to the same port where it was received
                        out_port = ofproto.OFPP_IN_PORT
                    else:
                        out_port = self.routing_table[dpid][dst]

                # central switch
                else:
                    # send packet to port next to in_port (clockwise forwarding) 
                    out_port = (in_port % external_switches) + 1 

            elif topology == 'string':
                # outer switches 
                if dpid != 1:
                    if in_port == self.routing_table[dpid][dst]:
                        out_port = ofproto.OFPP_IN_PORT
                    else:
                        out_port = self.routing_table[dpid][dst]
                # central switch
                else: 
                    out_port = self.routing_table[dpid][dst]
                    # if out_port number if smaller than in_port, packet needs to go left 
                    if out_port < in_port:
                        # send packet only one port to the left
                        out_port = in_port - 1
                    # if out_port number if greater than in_port, packet needs to go right      
                    elif out_port > in_port:
                        # send packet only one port to the right
                        out_port = in_port + 1
                    # otherwise just send to out_port computed first
                    
        # if destination is not known, flood packet to all switch ports
        else:
            out_port = ofproto.OFPP_FLOOD

        # create action object with the computed out_port
        actions = [parser.OFPActionOutput(out_port)]

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)

        # log packet path
        # only print packets for hosts we defined 
        if dst[:2] == '00': 
            if dpid != 1:
                if out_port == ofproto.OFPP_FLOOD:
                    self.logger.info("Switch %s, in_p %s -> FLOOD \t to %s slice: %s", dpid, in_port, dst, packet_type)
                elif out_port == ofproto.OFPP_IN_PORT:
                    self.logger.info("Switch %s, in_p %s <->| \t to %s slice: %s", dpid, in_port, dst, packet_type)
                else:
                    self.logger.info("Switch %s, in_p %s -> %s \t to %s slice: %s", dpid, in_port, out_port, dst, packet_type)
            else:
                self.logger.info("CENTERSW, in_p %s -> %s \t to %s slice: %s", in_port, out_port, dst, packet_type)
                
        datapath.send_msg(out)


    # HELPER METHODS USED BY THE CONTROLLER
    # -------------------------------------
    
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    # function needed to store routing flow in flow_table
    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    # function needed to delete routing flow from flow_table
    def delete_flow(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        for dst in self.routing_table[datapath.id].keys():
            match = parser.OFPMatch(eth_dst=dst)
            mod = parser.OFPFlowMod(
                datapath, command=ofproto.OFPFC_DELETE,
                out_port=ofproto.OFPP_ANY, out_group=ofproto.OFPG_ANY,
                priority=1, match=match)
            datapath.send_msg(mod)

    # function that executes whenever a topology change happens  
    @set_ev_cls(stplib.EventTopologyChange, MAIN_DISPATCHER)
    def _topology_change_handler(self, ev):
        dp = ev.dp
        dpid_str = dpid.dpid_to_str(dp.id)
        msg = 'Receive topology change event. Flush MAC table.'
        self.logger.debug("[dpid=%s] %s", dpid_str, msg)

        if dp.id in self.routing_table:
            self.delete_flow(dp)
            del self.routing_table[dp.id]

    # logger for STP function
    @set_ev_cls(stplib.EventPortStateChange, MAIN_DISPATCHER)
    def _port_state_change_handler(self, ev):
        dpid_str = dpid.dpid_to_str(ev.dp.id)
        of_state = {stplib.PORT_STATE_DISABLE: 'DISABLE',
                    stplib.PORT_STATE_BLOCK: 'BLOCK',
                    stplib.PORT_STATE_LISTEN: 'LISTEN',
                    stplib.PORT_STATE_LEARN: 'LEARN',
                    stplib.PORT_STATE_FORWARD: 'FORWARD'}
        self.logger.debug("[dpid=%s][port=%d] state=%s",
                         dpid_str, ev.port_no, of_state[ev.port_state])
    
    # function that creates a list of all switches inside the network
    @set_ev_cls(event.EventSwitchEnter)
    def get_topology_data(self, ev):
        switch_list = get_switch(self, None)
        self.switches = [switch.dp.id for switch in switch_list]
        links_list = get_link(self, None)
        self.links = [(link.src.dpid,link.dst.dpid,{'port':link.src.port_no}) for link in links_list]