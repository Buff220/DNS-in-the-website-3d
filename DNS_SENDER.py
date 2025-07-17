from scapy.all import *
import socket
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

def process_packet(packet):
    if packet.haslayer(DNS) and packet.getlayer(DNS).qr == 0:  # Query only
        domain = packet.getlayer(DNS).qd.qname.decode()
        print(f"[DNS Query] {domain}")
        s.sendto(domain.encode(),("127.0.0.1",8989))
# Start sniffing (use iface="your_adapter" on Linux)
sniff(filter="udp port 53", prn=process_packet, store=False)

#run sudo ~/Desktop/projs/projs/.venv/bin/python DNS_SENDER.py 
