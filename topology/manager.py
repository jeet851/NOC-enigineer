import sys
import os

# Allow importing root-level modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graph_ocr_packet import Neo4jTopologyConnector

class TopologyManager:
    def __init__(self):
        self.connector = Neo4jTopologyConnector()

    def get_graph(self):
        return self.connector.get_topology_graph()

    def add_node(self, hostname: str, label: str, ip: str, vendor: str):
        self.connector.add_device_node(hostname, label, ip, vendor)

    def add_link(self, source: str, target: str, link_type: str, details: str = ""):
        self.connector.add_link_edge(source, target, link_type, details)
