import asyncio
import io
import time
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from api.deps import get_current_user
from scapy.all import IP, TCP, UDP, DNS, DNSQR, DNSRR, wrpcap, Ether

router = APIRouter(prefix="/api/packets", tags=["packets"])

class PacketCaptureConfigRequest(BaseModel):
    interface: str
    filter: Optional[str] = None

# In-memory generator for simulated packets (JSON format)
def get_simulated_packets_json() -> List[Dict[str, Any]]:
    return [
        {
            "id": 1,
            "time": 0.000000,
            "source": "10.0.10.5",
            "destination": "10.0.1.1",
            "protocol": "DNS",
            "length": 74,
            "info": "Standard query 0x1a32 A portal.internal",
            "decode": {
                "Frame": "Frame 1: 74 bytes on wire, 74 bytes captured",
                "Ethernet": "Ethernet II, Src: 00:1b:44:11:3a:01, Dst: 00:50:56:88:99:aa",
                "IP": "Internet Protocol Version 4, Src: 10.0.10.5, Dst: 10.0.1.1",
                "UDP": "User Datagram Protocol, Src Port: 58912, Dst Port: 53",
                "DNS": "Domain Name System (query)\n Transaction ID: 0x1a32\n Flags: 0x0100 Standard query\n Queries:\n   portal.internal: type A, class IN"
            },
            "hex": "00 50 56 88 99 aa 00 1b 44 11 3a 01 08 00 45 00\n00 3c 1a 32 40 00 40 11 b3 c2 0a 00 0a 05 0a 00\n0a 01 e6 20 00 35 00 28 d4 12 1a 32 01 00 00 01\n00 00 00 00 00 00 06 70 6f 72 74 61 6c 08 69 6e\n74 65 72 6e 61 6c 00 00 01 00 01",
            "ascii": ".PV.....D.:...E..<.2@.@.................2......portal.internal...",
            "anomalies": []
        },
        {
            "id": 2,
            "time": 0.002410,
            "source": "10.0.1.1",
            "destination": "10.0.10.5",
            "protocol": "DNS",
            "length": 90,
            "info": "Standard query response 0x1a32 A portal.internal A 10.0.10.5",
            "decode": {
                "Frame": "Frame 2: 90 bytes on wire, 90 bytes captured",
                "Ethernet": "Ethernet II, Src: 00:50:56:88:99:aa, Dst: 00:1b:44:11:3a:01",
                "IP": "Internet Protocol Version 4, Src: 10.0.1.1, Dst: 10.0.10.5",
                "UDP": "User Datagram Protocol, Src Port: 53, Dst Port: 58912",
                "DNS": "Domain Name System (response)\n Transaction ID: 0x1a32\n Flags: 0x8180 Standard query response, No error\n Queries:\n   portal.internal: type A, class IN\n Answers:\n   portal.internal: type A, class IN, addr 10.0.10.5"
            },
            "hex": "00 1b 44 11 3a 01 00 50 56 88 99 aa 08 00 45 00\n00 4c 1b 12 40 00 40 11 b2 d1 0a 00 0a 01 0a 00\n0a 05 00 35 e6 20 00 38 a4 19 1a 32 81 80 00 01\n00 01 00 00 00 00 06 70 6f 72 74 61 6c 08 69 6e\n74 65 72 6e 61 6c 00 00 01 00 01 c0 0c 00 01 00\n01 00 00 00 3c 00 04 0a 00 0a 05",
            "ascii": "..D.:..PV.....E..L..@.@............5. .8...2.......portal.internal.........<.....",
            "anomalies": []
        },
        {
            "id": 3,
            "time": 0.010212,
            "source": "10.0.20.10",
            "destination": "10.0.10.5",
            "protocol": "TCP",
            "length": 66,
            "info": "49210 -> 80 [SYN] Seq=1000 Win=64240 Len=0 MSS=1460",
            "decode": {
                "Frame": "Frame 3: 66 bytes on wire, 66 bytes captured",
                "Ethernet": "Ethernet II, Src: 00:1b:44:11:3a:02, Dst: 00:1b:44:11:3a:01",
                "IP": "Internet Protocol Version 4, Src: 10.0.20.10, Dst: 10.0.10.5",
                "TCP": "Transmission Control Protocol, Src Port: 49210, Dst Port: 80, Seq: 1000, Len: 0\n Flags: 0x002 (SYN)\n Options: (Maximum segment size: 1460)"
            },
            "hex": "00 1b 44 11 3a 01 00 1b 44 11 3a 02 08 00 45 00\n00 34 2c 10 40 00 40 06 b3 f0 0a 00 14 0a 0a 00\n0a 05 c0 3a 00 50 00 00 03 e8 00 00 00 00 80 02\nfa f0 d4 b2 00 00 02 04 05 b4",
            "ascii": "..D.:..D.:....E..4.,.@.@...............:.P....................",
            "anomalies": []
        },
        {
            "id": 4,
            "time": 0.012540,
            "source": "10.0.10.5",
            "destination": "10.0.20.10",
            "protocol": "TCP",
            "length": 66,
            "info": "80 -> 49210 [SYN, ACK] Seq=5000 Ack=1001 Win=65160 Len=0",
            "decode": {
                "Frame": "Frame 4: 66 bytes on wire, 66 bytes captured",
                "Ethernet": "Ethernet II, Src: 00:1b:44:11:3a:01, Dst: 00:1b:44:11:3a:02",
                "IP": "Internet Protocol Version 4, Src: 10.0.10.5, Dst: 10.0.20.10",
                "TCP": "Transmission Control Protocol, Src Port: 80, Dst Port: 49210, Seq: 5000, Ack: 1001, Len: 0\n Flags: 0x012 (SYN, ACK)"
            },
            "hex": "00 1b 44 11 3a 02 00 1b 44 11 3a 01 08 00 45 00\n00 34 2c 11 40 00 40 06 b3 ef 0a 00 0a 05 0a 00\n14 0a 00 50 c0 3a 00 00 13 88 00 00 03 e9 80 12\nfe 88 d4 b2 00 00 02 04 05 b4",
            "ascii": "..D.:..D.:....E..4.,.@.@...........P.:........................",
            "anomalies": []
        },
        {
            "id": 5,
            "time": 0.014210,
            "source": "10.0.20.10",
            "destination": "10.0.10.5",
            "protocol": "TCP",
            "length": 60,
            "info": "49210 -> 80 [ACK] Seq=1001 Ack=5001 Win=64240 Len=0",
            "decode": {
                "Frame": "Frame 5: 60 bytes on wire, 60 bytes captured",
                "Ethernet": "Ethernet II, Src: 00:1b:44:11:3a:02, Dst: 00:1b:44:11:3a:01",
                "IP": "Internet Protocol Version 4, Src: 10.0.20.10, Dst: 10.0.10.5",
                "TCP": "Transmission Control Protocol, Src Port: 49210, Dst Port: 80, Seq: 1001, Ack: 5001, Len: 0\n Flags: 0x010 (ACK)"
            },
            "hex": "00 1b 44 11 3a 01 00 1b 44 11 3a 02 08 00 45 00\n00 28 2c 12 40 00 40 06 b3 fb 0a 00 14 0a 0a 00\n0a 05 c0 3a 00 50 00 00 03 e9 00 00 13 89 50 10\nfa f0 d4 b2 00 00",
            "ascii": "..D.:..D.:....E..(.,.@.@...............:.P............P.......",
            "anomalies": []
        },
        {
            "id": 6,
            "time": 0.018112,
            "source": "10.0.20.10",
            "destination": "10.0.10.5",
            "protocol": "HTTP",
            "length": 154,
            "info": "GET /index.html HTTP/1.1",
            "decode": {
                "Frame": "Frame 6: 154 bytes on wire, 154 bytes captured",
                "Ethernet": "Ethernet II, Src: 00:1b:44:11:3a:02, Dst: 00:1b:44:11:3a:01",
                "IP": "Internet Protocol Version 4, Src: 10.0.20.10, Dst: 10.0.10.5",
                "TCP": "Transmission Control Protocol, Src Port: 49210, Dst Port: 80, Seq: 1001, Ack: 5001, Len: 88\n Flags: 0x018 (PSH, ACK)",
                "HTTP": "Hypertext Transfer Protocol\n GET /index.html HTTP/1.1\\r\\n\n Host: portal.internal\\r\\n\n User-Agent: Mozilla/5.0\\r\\n\n Accept: */*\\r\\n"
            },
            "hex": "00 1b 44 11 3a 01 00 1b 44 11 3a 02 08 00 45 00\n00 80 2c 13 40 00 40 06 b3 a2 0a 00 14 0a 0a 00\n0a 05 c0 3a 00 50 00 00 03 e9 00 00 13 89 50 18\nfa f0 a1 e2 00 00 47 45 54 20 2f 69 6e 64 65 78\n2e 68 74 6d 6c 20 48 54 54 50 2f 31 2e 31 0d 0a\n48 6f 73 74 3a 20 70 6f 72 74 61 6c 2e 69 6e 74\n65 72 6e 61 6c 0d 0a 0d 0a",
            "ascii": "..D.:..D.:....E...,.@.@...............:.P............P.....GET /index.html HTTP/1.1..Host: portal.internal....",
            "anomalies": []
        },
        {
            "id": 7,
            "time": 0.052102,
            "source": "10.0.20.10",
            "destination": "10.0.10.5",
            "protocol": "TCP",
            "length": 154,
            "info": "[TCP Retransmission] GET /index.html HTTP/1.1",
            "decode": {
                "Frame": "Frame 7: 154 bytes on wire, 154 bytes captured (Retransmission)",
                "Ethernet": "Ethernet II, Src: 00:1b:44:11:3a:02, Dst: 00:1b:44:11:3a:01",
                "IP": "Internet Protocol Version 4, Src: 10.0.20.10, Dst: 10.0.10.5",
                "TCP": "Transmission Control Protocol, Src Port: 49210, Dst Port: 80, Seq: 1001, Ack: 5001, Len: 88 (RETRANSMISSION)\n Flags: 0x018 (PSH, ACK)"
            },
            "hex": "00 1b 44 11 3a 01 00 1b 44 11 3a 02 08 00 45 00\n00 80 2c 13 40 00 40 06 b3 a2 0a 00 14 0a 0a 00\n0a 05 c0 3a 00 50 00 00 03 e9 00 00 13 89 50 18\nfa f0 a1 e2 00 00 47 45 54 20 2f 69 6e 64 65 78\n2e 68 74 6d 6c 20 48 54 54 50 2f 31 2e 31 0d 0a\n48 6f 73 74 3a 20 70 6f 72 74 61 6c 2e 69 6e 74\n65 72 6e 61 6c 0d 0a 0d 0a",
            "ascii": "..D.:..D.:....E...,.@.@...............:.P............P.....GET /index.html HTTP/1.1..Host: portal.internal....",
            "anomalies": ["TCP Retransmission", "Duplicate ACK Detected"]
        },
        {
            "id": 8,
            "time": 0.082450,
            "source": "10.0.10.5",
            "destination": "10.0.20.10",
            "protocol": "HTTP",
            "length": 182,
            "info": "HTTP/1.1 200 OK (text/html)",
            "decode": {
                "Frame": "Frame 8: 182 bytes on wire, 182 bytes captured",
                "Ethernet": "Ethernet II, Src: 00:1b:44:11:3a:01, Dst: 00:1b:44:11:3a:02",
                "IP": "Internet Protocol Version 4, Src: 10.0.10.5, Dst: 10.0.20.10",
                "TCP": "Transmission Control Protocol, Src Port: 80, Dst Port: 49210, Seq: 5001, Ack: 1089, Len: 116\n Flags: 0x018 (PSH, ACK)",
                "HTTP": "Hypertext Transfer Protocol\n HTTP/1.1 200 OK\\r\\n\n Content-Type: text/html\\r\\n\n Content-Length: 26\\r\\n\n\\r\\n\n HTML Body: <html>Success</html>"
            },
            "hex": "00 1b 44 11 3a 02 00 1b 44 11 3a 01 08 00 45 00\n00 9c 2c 14 40 00 40 06 b3 85 0a 00 0a 05 0a 00\n14 0a 00 50 c0 3a 00 00 13 89 00 00 04 41 50 18\nfe 88 a2 e1 00 00 48 54 54 50 2f 31 2e 31 20 32\n30 30 20 4f 4b 0d 0a 43 6f 6e 74 65 6e 74 2d 54\n79 70 65 3a 20 74 65 78 74 2f 68 74 6d 6c 0d 0a\n0d 0a 3c 68 74 6d 6c 3e 53 75 63 63 65 73 73 3c\n2f 68 74 6d 6c 3e",
            "ascii": "..D.:..D.:....E...,.@.@...........P.:.......AP....HTTP/1.1 200 OK..Content-Type: text/html....<html>Success</html>",
            "anomalies": []
        },
        {
            "id": 9,
            "time": 0.120412,
            "source": "10.0.20.10",
            "destination": "10.0.10.6",
            "protocol": "TLS",
            "length": 185,
            "info": "Client Hello (TLSv1.2)",
            "decode": {
                "Frame": "Frame 9: 185 bytes on wire, 185 bytes captured",
                "Ethernet": "Ethernet II, Src: 00:1b:44:11:3a:02, Dst: 00:1b:44:11:3a:03",
                "IP": "Internet Protocol Version 4, Src: 10.0.20.10, Dst: 10.0.10.6",
                "TCP": "Transmission Control Protocol, Src Port: 49212, Dst Port: 443, Seq: 2001, Ack: 6001, Len: 119\n Flags: 0x018 (PSH, ACK)",
                "TLS": "Transport Layer Security\n TLSv1.2 Record Layer: Handshake Protocol: Client Hello\n   Version: TLS 1.2 (0x0303)\n   Cipher Suites: TLS_AES_256_GCM_SHA384 (0x1302), TLS_CHACHA20_POLY1305_SHA256 (0x1303)"
            },
            "hex": "00 1b 44 11 3a 03 00 1b 44 11 3a 02 08 00 45 00\n00 9f 2c 15 40 00 40 06 b3 81 0a 00 14 0a 0a 00\n0a 06 c0 3c 01 bb 00 00 07 d1 00 00 17 71 50 18\nfa f0 d4 b2 00 00 16 03 01 00 64 01 00 00 60 03\n03 00 11 22 33 44 55 66 77 88 99 aa bb cc dd ee\nff 00 11 22 33 44 55 66 77 88 99 aa bb cc dd ee",
            "ascii": "..D.:..D.:....E...,.@.@...........<..........qP...........d...`...3DUfww...................",
            "anomalies": []
        },
        {
            "id": 10,
            "time": 0.124512,
            "source": "10.0.10.6",
            "destination": "10.0.20.10",
            "protocol": "TLS",
            "length": 150,
            "info": "Server Hello (TLSv1.2)",
            "decode": {
                "Frame": "Frame 10: 150 bytes on wire, 150 bytes captured",
                "Ethernet": "Ethernet II, Src: 00:1b:44:11:3a:03, Dst: 00:1b:44:11:3a:02",
                "IP": "Internet Protocol Version 4, Src: 10.0.10.6, Dst: 10.0.20.10",
                "TCP": "Transmission Control Protocol, Src Port: 443, Dst Port: 49212, Seq: 6001, Ack: 2120, Len: 84\n Flags: 0x018 (PSH, ACK)",
                "TLS": "Transport Layer Security\n TLSv1.2 Record Layer: Handshake Protocol: Server Hello\n   Version: TLS 1.2 (0x0303)\n   Cipher Suite: TLS_AES_256_GCM_SHA384 (0x1302)"
            },
            "hex": "00 1b 44 11 3a 02 00 1b 44 11 3a 03 08 00 45 00\n00 7c 2c 16 40 00 40 06 b3 a3 0a 00 0a 06 0a 00\n14 0a 01 bb c0 3c 00 00 17 71 00 00 08 48 50 18\nfe 88 d4 b2 00 00 16 03 03 00 46 02 00 00 42 03\n03 44 55 66 77 88 99 aa bb cc dd ee ff 00 11 22",
            "ascii": "..D.:..D.:....E..|,.@.@...........<.....q...HP...........F...B..DUfww..............\"",
            "anomalies": []
        },
        {
            "id": 11,
            "time": 0.131012,
            "source": "10.0.10.6",
            "destination": "10.0.20.10",
            "protocol": "TLS",
            "length": 60,
            "info": "Alert (Level: Fatal, Description: Handshake Failure)",
            "decode": {
                "Frame": "Frame 11: 60 bytes on wire, 60 bytes captured",
                "Ethernet": "Ethernet II, Src: 00:1b:44:11:3a:03, Dst: 00:1b:44:11:3a:02",
                "IP": "Internet Protocol Version 4, Src: 10.0.10.6, Dst: 10.0.20.10",
                "TCP": "Transmission Control Protocol, Src Port: 443, Dst Port: 49212, Seq: 6085, Ack: 2120, Len: 7\n Flags: 0x018 (PSH, ACK)",
                "TLS": "Transport Layer Security\n TLSv1.2 Record Layer: Alert (Level: Fatal, Description: Handshake Failure)\n   Alert Message: Fatal Alert (0x02), Handshake Failure (0x28)"
            },
            "hex": "00 1b 44 11 3a 02 00 1b 44 11 3a 03 08 00 45 00\n00 2f 2c 17 40 00 40 06 b3 ef 0a 00 0a 06 0a 00\n14 0a 01 bb c0 3c 00 00 17 c5 00 00 08 48 50 18\nfe 88 a0 b2 00 00 15 03 03 00 02 02 28",
            "ascii": "..D.:..D.:....E../,.@.@...........<..........HP................(",
            "anomalies": ["TLS Handshake Failure Alert"]
        }
    ]

# Binary PCAP builder helper
def build_scapy_packets(protocol_filter: Optional[str] = None):
    packets = []
    
    # 1. DNS Query
    dns_q = Ether()/IP(src="10.0.10.5", dst="10.0.1.1")/UDP(sport=58912, dport=53)/DNS(rd=1, qd=DNSQR(qname="portal.internal"))
    packets.append(dns_q)
    
    # DNS Response
    dns_r = Ether()/IP(src="10.0.1.1", dst="10.0.10.5")/UDP(sport=53, dport=58912)/DNS(qr=1, aa=1, rcode=0, qd=DNSQR(qname="portal.internal"), an=DNSRR(rrname="portal.internal", rdata="10.0.10.5"))
    packets.append(dns_r)
    
    # 2. TCP Handshake (HTTP)
    syn = Ether()/IP(src="10.0.20.10", dst="10.0.10.5")/TCP(sport=49210, dport=80, flags="S", seq=1000)
    packets.append(syn)
    
    syn_ack = Ether()/IP(src="10.0.10.5", dst="10.0.20.10")/TCP(sport=80, dport=49210, flags="SA", seq=5000, ack=1001)
    packets.append(syn_ack)
    
    ack = Ether()/IP(src="10.0.20.10", dst="10.0.10.5")/TCP(sport=49210, dport=80, flags="A", seq=1001, ack=5001)
    packets.append(ack)
    
    # HTTP GET
    http_req = Ether()/IP(src="10.0.20.10", dst="10.0.10.5")/TCP(sport=49210, dport=80, flags="PA", seq=1001, ack=5001)/"GET /index.html HTTP/1.1\r\nHost: portal.internal\r\n\r\n"
    packets.append(http_req)
    
    # TCP Retransmission
    http_req_dup = Ether()/IP(src="10.0.20.10", dst="10.0.10.5")/TCP(sport=49210, dport=80, flags="PA", seq=1001, ack=5001)/"GET /index.html HTTP/1.1\r\nHost: portal.internal\r\n\r\n"
    packets.append(http_req_dup)
    
    # HTTP Response
    http_res = Ether()/IP(src="10.0.10.5", dst="10.0.20.10")/TCP(sport=80, dport=49210, flags="PA", seq=5001, ack=1050)/"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html>Success</html>"
    packets.append(http_res)
    
    # 3. TLS session
    syn_tls = Ether()/IP(src="10.0.20.10", dst="10.0.10.6")/TCP(sport=49212, dport=443, flags="S", seq=2000)
    packets.append(syn_tls)
    syn_ack_tls = Ether()/IP(src="10.0.10.6", dst="10.0.20.10")/TCP(sport=443, dport=49212, flags="SA", seq=6000, ack=2001)
    packets.append(syn_ack_tls)
    ack_tls = Ether()/IP(src="10.0.20.10", dst="10.0.10.6")/TCP(sport=49212, dport=443, flags="A", seq=2001, ack=6001)
    packets.append(ack_tls)
    
    # Client Hello (TLS)
    client_hello = Ether()/IP(src="10.0.20.10", dst="10.0.10.6")/TCP(sport=49212, dport=443, flags="PA", seq=2001, ack=6001)/b"\x16\x03\x01\x00\x64\x01\x00\x00\x60\x03\x03\x00\x11\x22\x33"
    packets.append(client_hello)
    
    # Server Hello (TLS)
    server_hello = Ether()/IP(src="10.0.10.6", dst="10.0.20.10")/TCP(sport=443, dport=49212, flags="PA", seq=6001, ack=2101)/b"\x16\x03\x03\x00\x46\x02\x00\x00\x42\x03\x03\x44\x55\x66"
    packets.append(server_hello)
    
    # TLS Alert (Error)
    tls_alert = Ether()/IP(src="10.0.10.6", dst="10.0.20.10")/TCP(sport=443, dport=49212, flags="PA", seq=6071, ack=2101)/b"\x15\x03\x03\x00\x02\x02\x30"
    packets.append(tls_alert)
    
    if protocol_filter and protocol_filter.lower() != "all":
        proto = protocol_filter.lower().strip()
        filtered = []
        for p in packets:
            if proto == "tcp" and p.haslayer(TCP):
                filtered.append(p)
            elif proto == "udp" and p.haslayer(UDP):
                filtered.append(p)
            elif proto == "dns" and p.haslayer(DNS):
                filtered.append(p)
            elif proto == "http" and p.haslayer(TCP) and (b"GET " in bytes(p[TCP].payload) or b"HTTP/" in bytes(p[TCP].payload)):
                filtered.append(p)
            elif proto == "tls" and p.haslayer(TCP) and (bytes(p[TCP].payload).startswith(b"\x16\x03") or bytes(p[TCP].payload).startswith(b"\x15\x03")):
                filtered.append(p)
        return filtered

    return packets

@router.post("/sniff")
async def start_sniffing_session(
    req: PacketCaptureConfigRequest,
    user: dict = Depends(get_current_user)
):
    if user["role"] not in ["Admin", "Operator", "Engineer"]:
        raise HTTPException(status_code=403, detail="Permission Denied: Sniffing sweep restricted.")
        
    proto_filter = req.filter.strip() if req.filter else "All"
    
    # Filter the dynamic json payload to simulate live sniff output matching request filters
    all_pkts = get_simulated_packets_json()
    if proto_filter.lower() != "all":
        p_filter = proto_filter.upper()
        if p_filter == "HTTP":
            all_pkts = [p for p in all_pkts if p["protocol"] in ["HTTP", "TCP"] and ("GET" in p["info"] or "200 OK" in p["info"])]
        elif p_filter == "TLS":
            all_pkts = [p for p in all_pkts if p["protocol"] in ["TLS", "TCP"] and ("Hello" in p["info"] or "Alert" in p["info"])]
        else:
            all_pkts = [p for p in all_pkts if p["protocol"] == p_filter]

    return {
        "status": "Success",
        "interface": req.interface,
        "filter": proto_filter,
        "packets": all_pkts
    }

@router.get("/export")
async def export_captured_pcap(
    proto: Optional[str] = "all",
    user: dict = Depends(get_current_user)
):
    pkts = build_scapy_packets(proto)
    
    buf = io.BytesIO()
    wrpcap(buf, pkts)
    buf.seek(0)
    
    return StreamingResponse(
        buf,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=live_capture.pcap"}
    )
