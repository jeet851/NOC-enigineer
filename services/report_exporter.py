import json
import csv
import io
from typing import Dict, Any, List

class ReportExporterService:
    @staticmethod
    def get_report_data() -> Dict[str, Any]:
        return {
            "title": "AIOps Enterprise Operations & Incident Report",
            "timestamp": "2026-07-05T11:56:48+05:30",
            "root_cause": "IPsec VPN Phase 1 Tunnel negotiation failed due to lifetime mismatch on primary gateway peer router-hq.",
            "metrics": {
                "CPU Utilization": "48%",
                "Memory Allocation": "68%",
                "Uptime": "14 weeks, 3 days",
                "Interface Status": "GigabitEthernet2 (Up/Up)",
                "Packet Loss": "0.0%",
                "Ping Latency": "2.4 ms"
            },
            "timeline": [
                "11:49:04 - User requested playbook automation center launch",
                "11:51:12 - Ansible playbook 'Configure OSPF Adjacencies' validated successfully",
                "11:51:30 - Backup baseline configuration created: CFG_BCK_ROUTER-HQ_17623912",
                "11:51:45 - Playbook task applied on targets: router-hq",
                "11:52:02 - Post-deployment validation sweep passed: OSPF Full state restored"
            ],
            "commands": [
                "interface GigabitEthernet2",
                " ip ospf 1 area 0",
                "crypto isakmp policy 10",
                " lifetime 28800"
            ],
            "logs": [
                "[INFO] Connection established to router-hq via SSHv2",
                "[ANSIBLE] running task: Ensure OSPF is active",
                "[ANSIBLE] changed: [router-hq]",
                "[INFO] Verification: ping 10.0.1.1 -> Success",
                "[INFO] Closed-loop monitoring: active incident resolved"
            ],
            "topology": {
                "nodes": ["router-hq (Active)", "sw-core-01 (Active)", "asa-edge-01 (Active)", "app-srv-02 (Active)"],
                "links": [
                    "router-hq -- sw-core-01 (Utilization: 35%, Latency: 1.2ms)",
                    "sw-core-01 -- app-srv-02 (Utilization: 12%, Latency: 0.8ms)",
                    "router-hq -- asa-edge-01 (Utilization: 5%, Latency: 2.1ms)"
                ]
            },
            "recommendations": [
                "1. Verify OSPF Dynamic routing timers regularly to prevent neighbor dropouts.",
                "2. Enforce strict change control verification with automated configuration drift detectors.",
                "3. Limit public SSH interface sweeps via localized access-list blocks on perimeter firewall.",
                "4. Schedule automatic config back-up cron timers at low-traffic operational windows."
            ],
            "automation_history": [
                {"Job ID": "JOB-1001", "Name": "Ansible: Configure OSPF Multi-Area Adjacency", "Framework": "Ansible", "Status": "Success"},
                {"Job ID": "JOB-1002", "Name": "Nornir: Multi-Node Telemetry Collector", "Framework": "Nornir", "Status": "Success"},
                {"Job ID": "JOB-1003", "Name": "Netmiko: Dual-Gateway Router BGP Route Map", "Framework": "Netmiko", "Status": "Rolled Back"}
            ]
        }

    @staticmethod
    def export_json() -> bytes:
        data = ReportExporterService.get_report_data()
        return json.dumps(data, indent=2).encode("utf-8")

    @staticmethod
    def export_csv() -> bytes:
        data = ReportExporterService.get_report_data()
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(["Section", "Property/Log Line", "Detail/Value"])
        writer.writerow([])
        
        # Meta info
        writer.writerow(["Metadata", "Title", data["title"]])
        writer.writerow(["Metadata", "Timestamp", data["timestamp"]])
        writer.writerow(["Metadata", "Root Cause", data["root_cause"]])
        writer.writerow([])
        
        # Metrics
        for k, v in data["metrics"].items():
            writer.writerow(["Metrics", k, v])
        writer.writerow([])
        
        # Timeline
        for idx, line in enumerate(data["timeline"], 1):
            writer.writerow(["Timeline", f"Event {idx}", line])
        writer.writerow([])
        
        # Commands
        for idx, cmd in enumerate(data["commands"], 1):
            writer.writerow(["Commands", f"Command {idx}", cmd])
        writer.writerow([])
        
        # Logs
        for line in data["logs"]:
            writer.writerow(["Logs", "Log Line", line])
        writer.writerow([])
        
        # Topology
        for n in data["topology"]["nodes"]:
            writer.writerow(["Topology", "Node", n])
        for l in data["topology"]["links"]:
            writer.writerow(["Topology", "Link", l])
        writer.writerow([])
        
        # Recommendations
        for rec in data["recommendations"]:
            writer.writerow(["Recommendations", "Item", rec])
        writer.writerow([])
        
        # Automation History
        writer.writerow(["Automation History", "Job ID / Name", "Framework - Status"])
        for job in data["automation_history"]:
            writer.writerow(["Automation History", f"{job['Job ID']} - {job['Name']}", f"{job['Framework']} - {job['Status']}"])
            
        return output.getvalue().encode("utf-8")

    @staticmethod
    def export_pdf() -> bytes:
        """
        Generates a valid, lightweight PDF/1.4 byte structure.
        """
        data = ReportExporterService.get_report_data()
        
        # Build text segments
        body_lines = []
        body_lines.append(f"TITLE: {data['title']}")
        body_lines.append(f"DATE: {data['timestamp']}")
        body_lines.append("=" * 60)
        body_lines.append("")
        body_lines.append("1. ROOT CAUSE")
        body_lines.append("-" * 30)
        body_lines.append(data["root_cause"])
        body_lines.append("")
        body_lines.append("2. METRICS")
        body_lines.append("-" * 30)
        for k, v in data["metrics"].items():
            body_lines.append(f"  {k}: {v}")
        body_lines.append("")
        body_lines.append("3. EVENT TIMELINE")
        body_lines.append("-" * 30)
        for line in data["timeline"]:
            body_lines.append(f"  * {line}")
        body_lines.append("")
        body_lines.append("4. Remediations Applied")
        body_lines.append("-" * 30)
        for cmd in data["commands"]:
            body_lines.append(f"  cisco-config# {cmd}")
        body_lines.append("")
        body_lines.append("5. Execution Console Logs")
        body_lines.append("-" * 30)
        for log in data["logs"]:
            body_lines.append(f"  {log}")
        body_lines.append("")
        body_lines.append("6. Network Topology Summary")
        body_lines.append("-" * 30)
        body_lines.append("  Nodes:")
        for n in data["topology"]["nodes"]:
            body_lines.append(f"    - {n}")
        body_lines.append("  Links:")
        for l in data["topology"]["links"]:
            body_lines.append(f"    - {l}")
        body_lines.append("")
        body_lines.append("7. Preventative Recommendations")
        body_lines.append("-" * 30)
        for rec in data["recommendations"]:
            body_lines.append(f"  {rec}")
        body_lines.append("")
        body_lines.append("8. Playbook Automation History")
        body_lines.append("-" * 30)
        for job in data["automation_history"]:
            body_lines.append(f"  [{job['Job ID']}] {job['Name']} ({job['Framework']}) -> {job['Status']}")
            
        # PDF objects assembler helper
        pdf_objs = []
        def write_obj(content: str) -> str:
            pdf_objs.append(content.encode('latin1'))
            return f"{len(pdf_objs)} 0 obj"
            
        # 1. Header
        # Catalog -> Pages -> Page -> Content -> Font
        # We will write:
        # Object 1: Catalog
        # Object 2: Pages list
        # Object 3: Page 1
        # Object 4: Font Courier
        # Object 5: Content Stream
        
        # Prepare text streams
        stream_lines = []
        stream_lines.append("BT")
        stream_lines.append("/F1 10 Tf")
        stream_lines.append("1.2 TL")
        stream_lines.append("50 750 Td")
        
        # Convert text to PDF command strings (escaping parentheses)
        for line in body_lines:
            escaped = line.replace("(", "\\(").replace(")", "\\)")
            # PDF text line breaks
            stream_lines.append(f"({escaped}) Tj T*")
            
        stream_lines.append("ET")
        stream_data = "\n".join(stream_lines)
        
        # Build PDF structure
        # Obj 1: Catalog
        o1 = "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj"
        pdf_objs.append(o1.encode('latin1'))
        
        # Obj 2: Pages list
        o2 = "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj"
        pdf_objs.append(o2.encode('latin1'))
        
        # Obj 3: Page 1
        o3 = "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj"
        pdf_objs.append(o3.encode('latin1'))
        
        # Obj 4: Font Courier
        o4 = "4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj"
        pdf_objs.append(o4.encode('latin1'))
        
        # Obj 5: Content stream
        stream_bytes = stream_data.encode('latin1')
        o5 = f"5 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode('latin1') + stream_bytes + "\nendstream\nendobj".encode('latin1')
        pdf_objs.append(o5)
        
        # Compile PDF bytes with XRef tables
        pdf_buf = io.BytesIO()
        pdf_buf.write(b"%PDF-1.4\n")
        
        xref_offsets = []
        for idx, obj in enumerate(pdf_objs, 1):
            xref_offsets.append(pdf_buf.tell())
            pdf_buf.write(obj)
            pdf_buf.write(b"\n")
            
        startxref = pdf_buf.tell()
        pdf_buf.write(b"xref\n")
        pdf_buf.write(f"0 {len(pdf_objs) + 1}\n".encode('latin1'))
        pdf_buf.write(b"0000000000 65535 f \n")
        for offset in xref_offsets:
            pdf_buf.write(f"{offset:010d} 00000 n \n".encode('latin1'))
            
        pdf_buf.write(b"trailer\n")
        pdf_buf.write(f"<< /Size {len(pdf_objs) + 1} /Root 1 0 R >>\n".encode('latin1'))
        pdf_buf.write(b"startxref\n")
        pdf_buf.write(f"{startxref}\n".encode('latin1'))
        pdf_buf.write(b"%%EOF\n")
        
        return pdf_buf.getvalue()
