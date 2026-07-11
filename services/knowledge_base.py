import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import re

KB_DB_PATH = "knowledge_base.json"

DEFAULT_DOCUMENTS = [
    {
        "id": "DOC-CISCO-01",
        "title": "Cisco IOS-XE OSPF Interface Configuration Guide",
        "source": "Cisco Docs",
        "version": "2.1",
        "timestamp": "2026-03-12T08:00:00",
        "content": "To enable OSPFv2 on an interface, use the 'ip ospf <process-id> area <area-id>' command in interface configuration mode. MTU mismatch between neighbors will cause OSPF adjacency to stick in EXSTART/EXCHANGE state. Bypass this using 'ip ospf mtu-ignore' under extreme troubleshooting scenarios.",
        "citations": "[Cisco-OSPF-Config-v2.1]"
    },
    {
        "id": "DOC-JUNIPER-01",
        "title": "Juniper Junos OS BGP Peer Group Policies",
        "source": "Juniper Docs",
        "version": "1.8",
        "timestamp": "2025-11-20T14:30:00",
        "content": "Under Junos, BGP configurations are configured within the 'protocols bgp group <group-name>' hierarchy. Neighbor statements define peer IPs and AS details. MD5 authentication is applied via the 'authentication-key <secret>' statement. Session flaps indicate holdtime mismatches.",
        "citations": "[Junos-BGP-Peer-v1.8]"
    },
    {
        "id": "DOC-RFC-2328",
        "title": "RFC 2328 - OSPF Version 2 Specification",
        "source": "RFCs",
        "version": "1.0",
        "timestamp": "1998-04-01T00:00:00",
        "content": "OSPF is a link-state routing protocol. Adjacency state transitions follow: Down -> Attempt -> Init -> 2-Way -> ExStart -> Exchange -> Loading -> Full. Hello intervals default to 10 seconds on broadcast networks with a dead interval of 4 times the hello interval.",
        "citations": "[IETF-RFC-2328]"
    },
    {
        "id": "DOC-TAC-01",
        "title": "TAC Alert: IPSec Lifetime Mismatch Negotiation Failures",
        "source": "Vendor TAC",
        "version": "3.0",
        "timestamp": "2026-05-15T09:12:00",
        "content": "Security Association (SA) negotiations fail during IKE Phase 1 handshake when the configured lifetime values (default 86400 seconds) differ between endpoints. Cisco devices raise LIFETIME_MISMATCH syslog notifications. Align lifetimes on both tunnels to restore QM_IDLE state.",
        "citations": "[Cisco-TAC-IKE-Phase1]"
    },
    {
        "id": "DOC-INC-402",
        "title": "Incident Log: Mumbai Branch Office VPN Tunnel Down",
        "source": "Previous Incidents",
        "version": "1.0",
        "timestamp": "2026-07-05T08:15:00",
        "content": "Incident INC-402 details: Physical link to Mumbai gateway was active, but IPsec tunnel failed to bring up security associations. Isolated root cause as lifetime mismatch (peer had 28800s, local switch had 86400s). Patch applied: 'crypto isakmp policy 10\\n lifetime 28800'. Status: Resolved.",
        "citations": "[INC-402-Mumbai-VPN]"
    },
    {
        "id": "DOC-CFG-GOLD",
        "title": "Gold Standard Router OSPF Security Template",
        "source": "Configuration Library",
        "version": "1.2",
        "timestamp": "2026-06-01T10:00:00",
        "content": "Standardized configuration lines for core network: router ospf 1\\n log-adjacency-changes\\n passive-interface default\\n no passive-interface GigabitEthernet2\\n area 0 authentication message-digest. Ensure all active interface ports configure MD5 message-digest-key.",
        "citations": "[Gold-OSPF-Security-v1.2]"
    }
]

class KnowledgeBaseService:
    @staticmethod
    def _load_db() -> Dict[str, Any]:
        if not os.path.exists(KB_DB_PATH):
            db_init = {"documents": DEFAULT_DOCUMENTS}
            with open(KB_DB_PATH, "w") as f:
                json.dump(db_init, f, indent=2)
            return db_init
            
        try:
            with open(KB_DB_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {"documents": []}

    @staticmethod
    def _save_db(data: Dict[str, Any]):
        with open(KB_DB_PATH, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def get_documents(sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        db = KnowledgeBaseService._load_db()
        docs = db.get("documents", [])
        if sources:
            docs = [d for d in docs if d["source"] in sources]
        return docs

    @staticmethod
    def add_document(title: str, source: str, content: str, citation: str) -> Dict[str, Any]:
        db = KnowledgeBaseService._load_db()
        new_doc = {
            "id": f"DOC-{source.replace(' ', '-').upper()}-{int(time.time()) % 100000}",
            "title": title,
            "source": source,
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "content": content,
            "citations": f"[{citation}]" if not citation.startswith("[") else citation
        }
        db.setdefault("documents", []).append(new_doc)
        KnowledgeBaseService._save_db(db)
        return new_doc

    @staticmethod
    def update_document_version(doc_id: str, new_content: str, version: str) -> Dict[str, Any]:
        db = KnowledgeBaseService._load_db()
        docs = db.get("documents", [])
        doc = next((d for d in docs if d["id"] == doc_id), None)
        
        if not doc:
            raise ValueError(f"Document ID '{doc_id}' not found.")
            
        doc["version"] = version
        doc["content"] = new_content
        doc["timestamp"] = datetime.now().isoformat()
        KnowledgeBaseService._save_db(db)
        return doc

    @staticmethod
    def search_kb(query: str, sources: List[str], search_mode: str = "semantic") -> Dict[str, Any]:
        docs = KnowledgeBaseService.get_documents(sources)
        results = []
        
        query_terms = [term.lower().strip() for term in re.split(r'\W+', query) if term.strip()]
        
        for doc in docs:
            content_lower = doc["content"].lower()
            title_lower = doc["title"].lower()
            
            # Compute match relevance score
            matches = 0
            for term in query_terms:
                if term in content_lower:
                    matches += 1.5
                if term in title_lower:
                    matches += 2.0
                    
            # Basic vector-distance simulation
            relevance = 0.0
            if len(query_terms) > 0:
                relevance = min(99.0, 50.0 + (matches / len(query_terms)) * 25.0)
            else:
                relevance = 60.0
                
            # If keyword matching, drop zero match results
            if search_mode == "keyword" and matches == 0:
                continue
                
            results.append({
                "document": doc,
                "relevance": f"{relevance:.1f}%",
                "matches_count": matches
            })
            
        # Sort by relevance score
        results = sorted(results, key=lambda x: float(x["relevance"].replace("%", "")), reverse=True)
        
        # Build RAG Synthesized Answer with citations
        rag_answer = ""
        citations_found = []
        
        if results and float(results[0]["relevance"].replace("%", "")) > 65.0:
            top_doc = results[0]["document"]
            citations_found.append(top_doc["citations"])
            
            # Synthesize answer based on query keywords
            query_clean = query.lower()
            if "ospf" in query_clean:
                rag_answer = (
                    f"According to {top_doc['citations']}, OSPF adjacency transitions follow the state path: "
                    f"Init -> 2-Way -> ExStart -> Exchange -> Loading -> Full. A common issue preventing OSPF "
                    f"convergence is an MTU mismatch, which causes neighbors to get stuck in ExStart/Exchange states. "
                    f"To bypass, verify interface MTU configurations or configure 'mtu-ignore' as detailed in Cisco OSPF standards."
                )
            elif "vpn" in query_clean or "lifetime" in query_clean:
                rag_answer = (
                    f"Based on {top_doc['citations']} and Cisco TAC investigations, IPSec Phase 1 SA negotiation failures "
                    f"often stem from LIFETIME_MISMATCH parameters. Ensure lifetimes match on both tunnel endpoints "
                    f"(commonly 28800s or 86400s) to transition to QM_IDLE state."
                )
            elif "bgp" in query_clean:
                rag_answer = (
                    f"Per {top_doc['citations']}, BGP sessions operate under protocols bgp hierarchies. Session timeouts "
                    f"or reset logs indicate holdtime mismatches or TCP port 179 transport connection drops."
                )
            else:
                rag_answer = (
                    f"Search findings from {top_doc['citations']} state that: '{top_doc['content'][:150]}...'. "
                    f"Please review the matching vendor document for detailed troubleshooting playbooks."
                )
        else:
            rag_answer = "No highly relevant documents found in the selected indexes. Refine your query parameters or select alternative document repositories."
            
        return {
            "query": query,
            "search_mode": search_mode,
            "rag_answer": rag_answer,
            "citations": citations_found,
            "results": results[:5]  # Limit to top 5 hits
        }
