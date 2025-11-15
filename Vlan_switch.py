from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet, ipv4, arp

# IP host buku di topologi mininet (sudah 1 subnet 10.0.0.0/24)
BUKU_IP = '10.0.0.10'


class QosBukuSwitch(app_manager.RyuApp):
    OFP_VERSION = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(QosBukuSwitch, self).__init__(*args, **kwargs)
        # Learning table: per dpid simpan mac -> port
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """Dipanggil saat switch/AP pertama kali connect ke Ryu."""
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Table-miss: semua paket yang tidak match dikirim ke controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions,
                 buffer_id=None, idle_timeout=0, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        if buffer_id is not None and buffer_id != ofproto.OFP_NO_BUFFER:
            mod = parser.OFPFlowMod(datapath=datapath,
                                    buffer_id=buffer_id,
                                    priority=priority,
                                    idle_timeout=idle_timeout,
                                    hard_timeout=hard_timeout,
                                    match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath,
                                    priority=priority,
                                    idle_timeout=idle_timeout,
                                    hard_timeout=hard_timeout,
                                    match=match,
                                    instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        in_port = msg.match['in_port']

        pkt = packet.Packet(data=msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        dst = eth.dst
        src = eth.src

        # Learning MAC address
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        # 1) Tangani ARP: selalu flood agar semua host bisa ARP
        if eth.ethertype == 0x0806:  # ARP
            out_port = ofproto.OFPP_FLOOD
            actions = [parser.OFPActionOutput(out_port)]

            data = None
            if msg.buffer_id == ofproto.OFP_NO_BUFFER:
                data = msg.data

            out = parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=msg.buffer_id,
                in_port=in_port,
                actions=actions,
                data=data
            )
            datapath.send_msg(out)
            return

        # 2) Tentukan out_port (learning switch)
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        # 3) Cek apakah paket IPv4 — untuk logika QoS prioritas buku
        ip_pkt = pkt.get_protocol(ipv4.ipv4)

        # Default: traffic biasa, priority rendah
        actions = [parser.OFPActionOutput(out_port)]
        priority = 10

        if ip_pkt:
            src_ip = ip_pkt.src
            dst_ip = ip_pkt.dst

            # Kalau traffic melibatkan h_buku → set queue 1, priority lebih tinggi
            if src_ip == BUKU_IP or dst_ip == BUKU_IP:
                self.logger.info("Traffic prioritas (buku): %s -> %s", src_ip, dst_ip)
                actions = [
                    parser.OFPActionSetQueue(1),  # arahkan ke queue 1 (high priority)
                    parser.OFPActionOutput(out_port)
                ]
                priority = 20

        # Flow match berdasarkan port & MAC (standard learning switch)
        match = parser.OFPMatch(in_port=in_port, eth_src=src, eth_dst=dst)

        # 4) Install flow supaya paket berikutnya tidak perlu ke controller
        if out_port != ofproto.OFPP_FLOOD:
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, priority, match, actions,
                              buffer_id=msg.buffer_id,
                              idle_timeout=30, hard_timeout=0)
                return
            else:
                self.add_flow(datapath, priority, match, actions,
                              idle_timeout=30, hard_timeout=0)

        # 5) Kirim packet_out untuk paket sekarang
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )
        datapath.send_msg(out)
