#!/usr/bin/python3

from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import OVSKernelAP
from mn_wifi.cli import CLI
from mininet.link import TCLink
from mininet.node import RemoteController, OVSKernelSwitch
import argparse
import os
import time


def build_net(num_sta=5, controller_ip='192.168.56.105', use_cli=False):
    """
    Membangun topologi perpustakaan hybrid:
    1 switch -> 3 host kabel + 1 AP + N STA (visitor).
    Semua 1 subnet: 10.0.0.0/24
    """
    net = Mininet_wifi(
        controller=RemoteController,
        link=TCLink,
        accessPoint=OVSKernelAP,
        switch=OVSKernelSwitch
    )

    info('*** Menambahkan controller Ryu (remote)\n')
    c0 = net.addController(
        'c0',
        controller=RemoteController,
        ip=controller_ip,
        port=6653
    )

    info('*** Menambahkan host kabel (staff) – subnet 10.0.0.0/24\n')
    h_buku = net.addHost(
        'h_buku',
        ip='10.0.0.10/24',
        mac='00:00:00:00:00:10'
    )
    h_absen = net.addHost(
        'h_absen',
        ip='10.0.0.20/24',
        mac='00:00:00:00:00:20'
    )
    h_admin = net.addHost(
        'h_admin',
        ip='10.0.0.30/24',
        mac='00:00:00:00:00:30'
    )

    info('*** Menambahkan AP + STA (visitor) – masih 10.0.0.0/24\n')
    ap1 = net.addAccessPoint(
        'ap1',
        ssid='LibWiFi',
        mode='g',
        channel='1',
        position='25,25,1',
        range=30
    )

    sta_list = []
    for i in range(1, num_sta + 1):
        pos_x = 10 + (i * 2)
        pos_y = 10 + (i * 2)
        sta = net.addStation(
            f'sta{i}',
            ip=f'10.0.0.{100 + i}/24',  # 10.0.0.101, 102, dst.
            mac=f'00:00:00:00:30:{i:02x}',
            position=f'{pos_x},{pos_y},0'
        )
        sta_list.append(sta)

    info('*** Konfigurasi WiFi nodes\n')
    net.configureWifiNodes()

    info('*** Menambahkan 1 switch pusat (hybrid)\n')
    s1 = net.addSwitch('s1')

    info('*** Membuat link kabel (bw=100Mbps) host <-> s1 dan ap1 <-> s1\n')
    net.addLink(h_buku, s1, bw=100)
    net.addLink(h_absen, s1, bw=100)
    net.addLink(h_admin, s1, bw=100)
    net.addLink(ap1, s1, bw=100)

    info('*** Membuat link wireless STA <-> AP\n')
    for sta in sta_list:
        net.addLink(sta, ap1)

    info('*** Build dan start jaringan\n')
    net.build()
    c0.start()
    s1.start([c0])
    ap1.start([c0])

    if use_cli:
        info('*** CLI mode diaktifkan\n')
        CLI(net)
        net.stop()
        return None

    host_dict = {
        'net': net,
        'h_buku': h_buku,
        'h_absen': h_absen,
        'h_admin': h_admin,
        'ap1': ap1,
        'sta_list': sta_list
    }
    return host_dict


def log_to_file(filepath, header, content):
    """Helper: tulis teks ke file dengan header pemisah."""
    with open(filepath, 'a') as f:
        f.write("\n" + "=" * 60 + "\n")
        f.write(header + "\n")
        f.write("=" * 60 + "\n\n")
        f.write(content)
        f.write("\n")


def skenario1(outfile):
    """
    SKENARIO 1:
    - 5 STA
    - Kondisi idle (tidak ada iperf)
    - Ping (latency) antara:
        h_buku <-> h_admin
        sta1   <-> h_admin
    """
    info('\n=== Menjalankan SKENARIO 1 (5 STA, idle, ping) ===\n')
    hosts = build_net(num_sta=5)
    net = hosts['net']
    h_buku = hosts['h_buku']
    h_admin = hosts['h_admin']
    sta1 = hosts['sta_list'][0]

    # Tunggu sedikit supaya koneksi stabil
    time.sleep(2)

    # Warm-up ARP & flow agar spike tidak terlalu besar
    h_buku.cmd('ping -c 2 10.0.0.30 > /dev/null 2>&1')
    h_admin.cmd('ping -c 2 10.0.0.10 > /dev/null 2>&1')
    sta1.cmd('ping -c 2 10.0.0.30 > /dev/null 2>&1')

    # Ping h_buku -> h_admin
    info('*** Ping h_buku -> h_admin\n')
    out1 = h_buku.cmd('ping -c 10 10.0.0.30')
    log_to_file(outfile, 'Ping h_buku -> h_admin (10 paket)', out1)

    # Ping h_admin -> h_buku
    info('*** Ping h_admin -> h_buku\n')
    out2 = h_admin.cmd('ping -c 10 10.0.0.10')
    log_to_file(outfile, 'Ping h_admin -> h_buku (10 paket)', out2)

    # Ping sta1 -> h_admin
    info('*** Ping sta1 -> h_admin\n')
    out3 = sta1.cmd('ping -c 10 10.0.0.30')
    log_to_file(outfile, 'Ping sta1 -> h_admin (10 paket)', out3)

    net.stop()
    info('=== Skenario 1 selesai, hasil disimpan di %s ===\n' % outfile)


def skenario2(outfile):
    """
    SKENARIO 2:
    - 10 STA
    - Trafik sibuk visitor ke h_admin (UDP iperf)
    - Log iperf per STA untuk analisis throughput & packet loss
    (client dijalankan satu per satu)
    """
    info('\n=== Menjalankan SKENARIO 2 (10 STA, visitor UDP ke admin) ===\n')
    hosts = build_net(num_sta=10)
    net = hosts['net']
    h_admin = hosts['h_admin']
    sta_list = hosts['sta_list']

    time.sleep(2)

    # h_admin sebagai server UDP
    info('*** Menjalankan iperf server UDP di h_admin (port 5002)\n')
    h_admin.cmd('pkill iperf')
    h_admin.cmd('iperf -s -u -p 5002 > /tmp/iperf_server_sken2.log 2>&1 &')

    # Jalankan beberapa STA sebagai client UDP (sta1..sta5)
    durasi = 20
    bitrate = '10M'  # 10 Mbps per STA
    for i in range(5):
        sta = sta_list[i]
        info(f'*** STA {sta.name} kirim UDP {bitrate} ke h_admin\n')
        cmd = f'iperf -c 10.0.0.30 -u -p 5002 -b {bitrate} -t {durasi}'
        out = sta.cmd(cmd)
        log_to_file(outfile,
                    f'iperf UDP {sta.name} -> h_admin ({bitrate}, {durasi}s)',
                    out)

    # hentikan server (paksa kill iperf)
    h_admin.cmd('pkill iperf')
    net.stop()
    info('=== Skenario 2 selesai, hasil disimpan di %s ===\n' % outfile)


def skenario3(outfile):
    """
    SKENARIO 3:
    - 15 STA
    - Trafik prioritas dari h_buku -> h_admin (TCP iperf)
    - Trafik background UDP dari STA ke h_admin (mengganggu)
    - Tujuan: lihat stabilitas throughput buku vs background
    """
    info('\n=== Menjalankan SKENARIO 3 (15 STA, prioritas buku + background visitor) ===\n')
    hosts = build_net(num_sta=15)
    net = hosts['net']
    h_buku = hosts['h_buku']
    h_admin = hosts['h_admin']
    sta_list = hosts['sta_list']

    time.sleep(2)

    # 1) Trafik background UDP dari beberapa STA
    info('*** Menjalankan iperf server UDP (background) di h_admin (port 5002)\n')
    h_admin.cmd('pkill iperf')
    h_admin.cmd('iperf -s -u -p 5002 > /tmp/iperf_server_bg_sken3.log 2>&1 &')

    durasi_bg = 30
    bitrate_bg = '5M'
    bg_clients = sta_list[:5]

    for sta in bg_clients:
        info(f'*** Background: {sta.name} kirim UDP {bitrate_bg} ke h_admin\n')
        cmd_bg = (
            f'iperf -c 10.0.0.30 -u -p 5002 -b {bitrate_bg} -t {durasi_bg} '
            f'> /tmp/{sta.name}_bg_sken3.log 2>&1 &'
        )
        sta.cmd(cmd_bg)

    # 2) Trafik prioritas dari h_buku (TCP, diasumsikan Ryu kasih queue prioritas)
    info('*** Menjalankan iperf server TCP di h_admin (port 5001)\n')
    h_admin.cmd('iperf -s -p 5001 > /tmp/iperf_server_tcp_sken3.log 2>&1 &')

    time.sleep(2)

    info('*** Trafik prioritas: h_buku -> h_admin (TCP, 20s)\n')
    out_tcp = h_buku.cmd('iperf -c 10.0.0.30 -p 5001 -t 20')
    log_to_file(outfile,
                'iperf TCP h_buku -> h_admin (prioritas, 20s)',
                out_tcp)

    # hentikan semua iperf
    h_admin.cmd('pkill iperf')
    net.stop()
    info('=== Skenario 3 selesai, hasil disimpan di %s ===\n' % outfile)


def skenario4(outfile):
    """
    SKENARIO 4:
    - 15 STA
    - Bandingkan latency idle vs latency saat jaringan sibuk.
    - Langkah:
        1) Warm-up ping (agar ARP & flow siap)
        2) Ping (idle) h_buku -> h_admin dan sta1 -> h_admin
        3) Jalankan traffic UDP dari beberapa STA
        4) Ping lagi (busy) h_buku -> h_admin dan sta1 -> h_admin
    """
    info('\n=== Menjalankan SKENARIO 4 (15 STA, idle vs busy latency) ===\n')
    hosts = build_net(num_sta=15)
    net = hosts['net']
    h_buku = hosts['h_buku']
    h_admin = hosts['h_admin']
    sta1 = hosts['sta_list'][0]
    sta_list = hosts['sta_list']

    time.sleep(2)

    # Warm-up supaya idle measurement tidak kena ARP pertama
    h_buku.cmd('ping -c 2 10.0.0.30 > /dev/null 2>&1')
    sta1.cmd('ping -c 2 10.0.0.30 > /dev/null 2>&1')
    h_admin.cmd('ping -c 2 10.0.0.10 > /dev/null 2>&1')

    # 1) PING dalam kondisi idle
    info('*** Ping idle: h_buku -> h_admin\n')
    out_idle1 = h_buku.cmd('ping -c 10 10.0.0.30')
    log_to_file(outfile, 'PING IDLE: h_buku -> h_admin (10 paket)', out_idle1)

    info('*** Ping idle: sta1 -> h_admin\n')
    out_idle2 = sta1.cmd('ping -c 10 10.0.0.30')
    log_to_file(outfile, 'PING IDLE: sta1 -> h_admin (10 paket)', out_idle2)

    # 2) Traffic sibuk UDP dari beberapa STA
    info('*** Menjalankan iperf server UDP di h_admin (port 5003)\n')
    h_admin.cmd('iperf -s -u -p 5003 > /tmp/iperf_server_sken4.log 2>&1 &')

    durasi_bg = 25
    bitrate_bg = '8M'
    bg_clients = sta_list[:5]

    for sta in bg_clients:
        info(f'*** Background busy: {sta.name} kirim UDP {bitrate_bg} ke h_admin\n')
        cmd_bg = (
            f'iperf -c 10.0.0.30 -u -p 5003 -b {bitrate_bg} -t {durasi_bg} '
            f'> /tmp/{sta.name}_bg_sken4.log 2>&1 &'
        )
        sta.cmd(cmd_bg)

    time.sleep(3)  # tunggu traffic jalan

    # 3) PING dalam kondisi busy
    info('*** Ping busy: h_buku -> h_admin\n')
    out_busy1 = h_buku.cmd('ping -c 10 10.0.0.30')
    log_to_file(outfile, 'PING BUSY: h_buku -> h_admin (10 paket)', out_busy1)

    info('*** Ping busy: sta1 -> h_admin\n')
    out_busy2 = sta1.cmd('ping -c 10 10.0.0.30')
    log_to_file(outfile, 'PING BUSY: sta1 -> h_admin (10 paket)', out_busy2)

    # hentikan iperf
    h_admin.cmd('pkill iperf')
    net.stop()
    info('=== Skenario 4 selesai, hasil disimpan di %s ===\n' % outfile)


def skenario5_bandwidth_vs_sta(outfile):
    """
    SKENARIO 5:
    Bandingkan kemampuan server ketika:
    - 5 STA aktif
    - 10 STA aktif
    - 15 STA aktif
    Semua STA kirim trafik UDP dengan bitrate yang sama secara bersamaan.
    """
    for n_sta in [5, 10, 15]:
        info(f'\n=== SKENARIO 5: {n_sta} STA aktif (UDP bareng) ===\n')
        hosts = build_net(num_sta=n_sta)
        net = hosts['net']
        h_admin = hosts['h_admin']
        sta_list = hosts['sta_list']

        time.sleep(2)

        # Server UDP (log di /tmp/iperf_server_nsta_<N>.log)
        h_admin.cmd('pkill iperf')
        server_log_path = f'/tmp/iperf_server_nsta_{n_sta}.log'
        info(f'*** Menjalankan iperf server UDP di h_admin (port 5004) untuk {n_sta} STA\n')
        h_admin.cmd(f'iperf -s -u -p 5004 > {server_log_path} 2>&1 &')

        durasi = 20
        bitrate = '5M'  # 5 Mbps per STA
        client_logs = []

        # Jalankan semua STA sebagai client UDP secara bersamaan
        for sta in sta_list:
            log_path = f'/tmp/{sta.name}_nsta_{n_sta}.log'
            info(f'*** {sta.name} kirim UDP {bitrate} ke h_admin (N_STA={n_sta})\n')
            cmd = (
                f'iperf -c 10.0.0.30 -u -p 5004 -b {bitrate} -t {durasi} '
                f'> {log_path} 2>&1 &'
            )
            sta.cmd(cmd)
            client_logs.append((sta, log_path))

        # Tunggu semua traffic selesai
        time.sleep(durasi + 5)

        # Matikan iperf server
        h_admin.cmd('pkill iperf')

        # Ambil log server
        server_log = h_admin.cmd(f'cat {server_log_path}')
        log_to_file(
            outfile,
            f'SERVER REPORT (h_admin, UDP, port 5004) N_STA={n_sta}',
            server_log
        )

        # Ambil log tiap client STA
        for sta, log_path in client_logs:
            client_log = sta.cmd(f'cat {log_path}')
            log_to_file(
                outfile,
                f'CLIENT REPORT {sta.name} -> h_admin (UDP {bitrate}, {durasi}s), N_STA={n_sta}',
                client_log
            )

        net.stop()
        info(f'=== Skenario 5, N_STA={n_sta} selesai ===\n')


def main():
    parser = argparse.ArgumentParser(
        description='Simulasi Perpustakaan WiFi + QoS, auto log txt'
    )
    parser.add_argument(
        '--mode',
        choices=['auto', 'cli'],
        default='auto',
        help='auto: jalankan semua skenario dan simpan txt; '
             'cli: hanya bangun topo (5 STA) dan masuk CLI'
    )
    parser.add_argument(
        '--controller-ip',
        default='127.0.0.1',
        help='IP controller Ryu (default 127.0.0.1)'
    )
    args = parser.parse_args()

    setLogLevel('info')

    if args.mode == 'cli':
        # Mode CLI manual (buat cek topologi tanpa skenario otomatis)
        build_net(num_sta=5, controller_ip=args.controller_ip, use_cli=True)
        return

    # Mode auto: jalankan semua skenario
    outdir = 'hasil_qos'
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    skenario1(os.path.join(outdir, 'skenario1.txt'))
    skenario2(os.path.join(outdir, 'skenario2.txt'))
    skenario3(os.path.join(outdir, 'skenario3.txt'))
    skenario4(os.path.join(outdir, 'skenario4.txt'))
    skenario5_bandwidth_vs_sta(os.path.join(outdir, 'skenario5_bandwidth_vs_sta.txt'))

    info('\n=== Semua skenario selesai. File log ada di folder: %s ===\n' % outdir)


if __name__ == '__main__':
    main()
