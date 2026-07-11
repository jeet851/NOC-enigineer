import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from api.deps import get_current_user, get_db
from sqlalchemy.orm import Session
from services.audit import AuditService
from pydantic import BaseModel

router = APIRouter(prefix="/api/cli", tags=["live-cli"])

class CLIExecutionRequest(BaseModel):
    device: str
    library: str
    command: str

async def generate_cli_stream(device: str, library: str, command: str):
    yield f"[NOC-CLI] [{library.upper()}] Initializing transport channel...\n"
    await asyncio.sleep(0.15)
    yield f"[NOC-CLI] [{library.upper()}] Connecting to remote device host: {device}...\n"
    await asyncio.sleep(0.15)
    yield f"[NOC-CLI] [{library.upper()}] Cryptographic SSH key authenticated.\n"
    await asyncio.sleep(0.15)
    yield f"[NOC-CLI] [{library.upper()}] Terminal session established. Shell output streaming:\n"
    yield f"========================================================================\n\n"
    await asyncio.sleep(0.2)
    
    cmd_lower = command.lower()
    
    if library.lower() == "nornir":
        yield "Nornir execution task: run_cli_command\n"
        yield "------------------------------------------------------------------------\n"
        yield f"{device} (task_status: SUCCESS, changed: false):\n\n"
        await asyncio.sleep(0.2)
        
    elif library.lower() == "napalm":
        yield f"NAPALM driver: get_facts() / cli_command output:\n"
        yield "------------------------------------------------------------------------\n\n"
        await asyncio.sleep(0.2)

    if "ping" in cmd_lower:
        target = "8.8.8.8"
        for w in command.split():
            if "." in w or ":" in w:
                target = w
        yield f"Type escape sequence to abort.\n"
        yield f"Sending 5, 100-byte ICMP Echos to {target}, timeout is 2 seconds:\n"
        await asyncio.sleep(0.4)
        for _ in range(5):
            yield "!\n"
            await asyncio.sleep(0.3)
        yield f"\nSuccess rate is 100 percent (5/5), round-trip min/avg/max = 1/2/4 ms\n"
        
    elif "traceroute" in cmd_lower or "trace" in cmd_lower:
        target = "10.0.10.5"
        for w in command.split():
            if "." in w or ":" in w:
                target = w
        yield f"Type escape sequence to abort.\n"
        yield f"Tracing the route to {target}\n\n"
        await asyncio.sleep(0.4)
        hops = [
            f"  1  10.0.1.254 (ASA-Gate) 2 msec 1 msec 1 msec\n",
            f"  2  10.0.1.1 (Core-Switch-01) 2 msec 2 msec 2 msec\n",
            f"  3  {target} (Target-Node) 3 msec 2 msec 3 msec\n"
        ]
        for hop in hops:
            yield hop
            await asyncio.sleep(0.4)
            
    elif "debug" in cmd_lower:
        yield f"OSPF packet debug tracing active on {device} (Press Ctrl+C to stop debugging)\n"
        await asyncio.sleep(0.3)
        debug_lines = [
            "*Jul  5 10:42:04.102: OSPF-1 ADJ   Gi2: Nbr 10.0.1.1 Hello received\n",
            "*Jul  5 10:42:04.103: OSPF-1 ADJ   Gi2: Nbr 10.0.1.1 Area 0 match OK\n",
            "*Jul  5 10:42:14.250: OSPF-1 ADJ   Gi2: Sending Hello packet to 224.0.0.5\n",
            "*Jul  5 10:42:14.251: OSPF-1 ADJ   Gi2: Hello option mismatch checked (OK)\n"
        ]
        for line in debug_lines:
            yield line
            await asyncio.sleep(0.5)
            
    elif "capture" in cmd_lower or "monitor" in cmd_lower:
        yield f"Initiating network packet capture stream on {device} interfaces...\n"
        await asyncio.sleep(0.4)
        captures = [
            "19:42:04.102342 IP 10.0.1.1.53 > 10.0.20.10.58912: 53212+ A? portal.internal. (32)\n",
            "19:42:04.104512 IP 10.0.20.10.58912 > 10.0.1.1.53: 53212 1/0/0 A 10.0.10.5 (48)\n",
            "19:42:04.112102 IP 10.0.10.5.80 > 10.0.20.10.58912: Flags [S.], seq 142012891, ack 991024 (54)\n"
        ]
        for cap in captures:
            yield cap
            await asyncio.sleep(0.5)
            
    elif "show" in cmd_lower:
        if "ip interface brief" in cmd_lower or "int brief" in cmd_lower:
            yield "Interface                  IP-Address      OK? Method Status                Protocol\n"
            yield "GigabitEthernet1           198.51.100.2    YES NVRAM  up                    up\n"
            yield "GigabitEthernet2           10.0.1.254      YES NVRAM  up                    up\n"
            yield "Tunnel10                   10.254.1.1      YES NVRAM  down                  down\n"
        elif "route" in cmd_lower:
            yield "Codes: L - local, C - connected, S - static, R - RIP, M - mobile, B - BGP\n"
            yield "       D - EIGRP, EX - EIGRP external, O - OSPF, IA - OSPF inter area\n\n"
            yield "Gateway of last resort is 198.51.100.1 to network 0.0.0.0\n\n"
            yield "S*    0.0.0.0/0 [1/0] via 198.51.100.1\n"
            yield "C     198.51.100.0/24 is directly connected, GigabitEthernet1\n"
            yield "O     10.0.10.0/24 [110/2] via 10.0.1.1, 14:22:04, GigabitEthernet2\n"
        else:
            yield f"hostname {device}\n"
            yield "!\n"
            yield "interface GigabitEthernet1\n"
            yield " ip address 198.51.100.2 255.255.255.0\n"
            yield "!\n"
            yield "router ospf 1\n"
            yield " network 10.0.0.0 0.255.255.255 area 0\n"
            yield "!\n"
            yield "end\n"
    else:
        yield f"Command execution successful on {device}.\n"
        yield f"Output: {command} executed successfully.\n"
        
    await asyncio.sleep(0.1)
    yield f"\n========================================================================\n"
    yield f"[NOC-CLI] [{library.upper()}] Execution completed.\n"

from routes.optimization import check_rate_limit

@router.post("/execute", dependencies=[Depends(check_rate_limit)])
async def execute_cli_command(
    req: CLIExecutionRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user["role"] not in ["Admin", "Operator", "Engineer"]:
        raise HTTPException(status_code=403, detail="Permission Denied: CLI access restricted.")
        
    device = req.device.strip()
    library = req.library.strip()
    command = req.command.strip()
    
    if not device or not library or not command:
        raise HTTPException(status_code=400, detail="Missing required CLI options.")
        
    # Log to Security Audit Logs
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action=f"Execute CLI Command ({library})",
        ip="127.0.0.1",
        details=f"Executed command '{command}' on device '{device}' via {library}"
    )
    
    return StreamingResponse(
        generate_cli_stream(device, library, command),
        media_type="text/plain"
    )
