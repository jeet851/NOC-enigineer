import os
import re
import random
import sys
from datetime import datetime
import ai_engine
import json

USERS = {
    "admin": {"password": "admin123", "role": "Admin", "name": "System Administrator"},
    "manager": {"password": "manager123", "role": "Manager", "name": "Operations Manager"},
    "senior_eng": {"password": "senior123", "role": "Senior Engineer", "name": "Senior Infrastructure Engineer"},
    "net_eng": {"password": "engineer123", "role": "Network Engineer", "name": "Network Automation Analyst"},
    "guest": {"password": "guest123", "role": "Guest", "name": "Auditor / Guest"}
}

AUDIT_LOG_FILE = "audit_log.json"

def log_audit_event(username, role, action, ip, details, status="Success", changes="N/A", approvals="N/A", rollback="N/A"):
    event = {
        "timestamp": datetime.now().isoformat(),
        "user": username,
        "role": role,
        "ip": ip,
        "action": action,
        "details": details,
        "status": status,
        "changes": changes,
        "approvals": approvals,
        "rollback": rollback
    }
    
    events = []
    if os.path.exists(AUDIT_LOG_FILE):
        try:
            with open(AUDIT_LOG_FILE, "r") as f:
                events = json.load(f)
        except:
            events = []
            
    events.insert(0, event)
    with open(AUDIT_LOG_FILE, "w") as f:
        json.dump(events, f, indent=4)

def print_separator():
    print("-" * 75)

def main():
    print("\n" + "=" * 75)
    print(" [SECURE CLI]  AI NETWORK ENGINEER - ZERO-TRUST CONSOLE ")
    print("=" * 75)
    print("Authentication Required. This system complies with NIST SP 800-207.")
    print_separator()

    # 1. Zero-Trust Username & Password verification
    authenticated_user = None
    role = None
    
    while not authenticated_user:
        try:
            username = input("Username: ").strip().lower()
            password = input("Password: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting CLI...")
            sys.exit(0)
            
        if username in USERS and USERS[username]["password"] == password:
            # 2. MFA Challenge
            otp = str(random.randint(100000, 999999))
            print(f"\n[MFA CHALLENGE] Simulated Hardware Token OTP: {otp}")
            try:
                entered_otp = input("Enter 6-digit OTP: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting CLI...")
                sys.exit(0)
                
            if entered_otp == otp:
                authenticated_user = USERS[username]
                authenticated_user["username"] = username
                role = authenticated_user["role"]
                print(f"\n[SUCCESS] Welcome, {authenticated_user['name']}! Role: [{role}] authorized.")
                log_audit_event(username, role, "CLI Login Successful", "127.0.0.1", "CLI Zero-Trust login with Password + OTP.")
            else:
                print("[ERROR] Invalid OTP. Access Denied.\n")
                log_audit_event(username, "N/A", "CLI MFA Verification Failed", "127.0.0.1", "Invalid OTP entered.", "Failed")
        else:
            print("[ERROR] Invalid username or password credentials.\n")
            log_audit_event(username or "unknown", "N/A", "CLI Login Failed", "127.0.0.1", "Invalid credentials.", "Failed")

    print_separator()
    print("Suggestions: Try typing these operations scenarios:")
    print("  * 'VPN is down'")
    print("  * 'Server CPU is 100%'")
    print("  * 'Configure VLAN 20'")
    print("  * 'Check daily server health'")
    print("  * 'Analyze this firewall log'")
    print("  * Type 'help' to see active agents list or 'exit' to quit.")
    print_separator()
    
    active_persona = "assistant"
    
    while True:
        try:
            user_input = input(f"\n[{role}] Copilot> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
            
        if not user_input:
            continue
            
        cmd = user_input.lower()
        if cmd in ["exit", "quit", "q"]:
            print("Exiting simulator...")
            log_audit_event(authenticated_user["username"], role, "CLI Logout", "127.0.0.1", "CLI Session terminated.")
            break
            
        if cmd == "help":
            print("\n[AI] *Active Operational Agents Pool*")
            for key, val in ai_engine.PERSONAS.items():
                print(f"  [{val['name']}] - {val['description']}")
            continue
            
        # 3. Prompt Injection Check
        if ai_engine.check_prompt_injection(user_input):
            print("\n[ALERT] Zero-Trust Block: Prompt Injection Attempt Intercepted.")
            log_audit_event(authenticated_user["username"], role, "CLI Prompt Injection Blocked", "127.0.0.1", f"Injection prompt: '{user_input[:40]}'", "Blocked")
            continue

        # Normalization and routing
        normalized = user_input.lower().rstrip("?.- ")
        routed_persona = ai_engine.auto_route_intent(normalized)
        scenario_key = ai_engine.find_matching_scenario(user_input)
        
        if routed_persona:
            active_persona = routed_persona
            persona = ai_engine.PERSONAS[active_persona]
            print(f"\n[AIOps Dispatcher] -> Auto-routing message to [{persona['name']}]\n")
        else:
            persona = ai_engine.PERSONAS[active_persona]
            
        # Get Response (which complies with 13-point layout)
        response = ai_engine.generate_ai_response(user_input, persona_key=active_persona, active_scenario=scenario_key)
        print(response)
        
        # Interactive loop for known scenarios
        if scenario_key:
            scenario = ai_engine.SCENARIOS[scenario_key]
            while True:
                print("\n[Zero-Trust Operational Controls]:")
                print("  [1] Run Diagnostics Sweep [NIST]")
                print("  [2] Deploy Automated Configuration Patch [Rollback Enable]")
                print("  [3] Generate Incident Root Cause Analysis (RCA)")
                print("  [4] Ask another question / Back")
                
                choice = input("Select command [1-4]: ").strip()
                if choice == "1":
                    print("\n--- Running Remote Diagnostics System ---")
                    print(scenario["diagnostics"])
                    print_separator()
                elif choice == "2":
                    print("\n--- Initializing Zero-Trust Configuration Stepper ---")
                    
                    # Determine target commands
                    commands = ""
                    if scenario_key == "vpn is down":
                        commands = "crypto isakmp policy 10\n lifetime 28800"
                    elif scenario_key == "server cpu is 100%":
                        commands = "kill -9 40912\nsystemctl reload nginx"
                    elif scenario_key == "configure vlan 20":
                        commands = "vlan 20\n name DB_Subnet\ninterface range GigabitEthernet1/0/1 - 12\n switchport access vlan 20"
                    elif scenario_key == "check daily server health":
                        commands = "find /var/log -name '*.gz' -mtime +30 -delete"
                    elif scenario_key == "analyze this firewall log":
                        commands = "access-list outside_access_in line 1 extended deny tcp host 198.51.100.45 any eq 22"
                        
                    # Stage 1: Validation
                    print("\n[Step 1/5] Running Command Validation Engine...")
                    v_logs, v_err = ai_engine.validate_commands(commands)
                    for log in v_logs:
                        print(f"  * [{log['status']}] {log['check']}: {log['details']}")
                    
                    if v_err:
                        print("[HALT] Command validation tests failed. Configuration rejected.")
                        print_separator()
                        continue
                        
                    # Stage 2: Simulation
                    print("\n[Step 2/5] Initializing Topology Impact Simulator...")
                    s_logs, s_warn = ai_engine.run_simulation(commands)
                    for log in s_logs:
                        print(f"  * [{log['status']}] {log['step']}: {log['details']}")
                        
                    # Stage 3: Role Approvals
                    print("\n[Step 3/5] Verifying Security Approvals for current Operator Role...")
                    if role == "Guest":
                        print("[BLOCK] Guests have read-only access. Deployment aborted.")
                        log_audit_event(authenticated_user["username"], role, "CLI Deploy Blocked", "127.0.0.1", "Read-only Guest blocked.", "Blocked")
                        print_separator()
                        break
                    if role == "Network Engineer":
                        print("[BLOCK] Network Engineers cannot deploy. Escalated for Senior/Manager approvals.")
                        log_audit_event(authenticated_user["username"], role, "CLI Deploy Blocked", "127.0.0.1", "Engineer access blocked.", "Blocked")
                        print_separator()
                        break
                        
                    destructive_alerts = ai_engine.check_ai_safety(commands)
                    requires_dual = len(destructive_alerts) > 0
                    
                    manager_approved = False
                    admin_approved = False
                    
                    if requires_dual:
                        print("[WARNING] Destructive commands detected. Dual Approvals (Manager + Admin) required.")
                        mgr_code = input("Enter Manager Authorization Code: ").strip()
                        adm_code = input("Enter Admin Override Code: ").strip()
                        if mgr_code == "123456" and adm_code == "admin123":
                            manager_approved = True
                            admin_approved = True
                            print("[SUCCESS] Dual approvals validated successfully.")
                        else:
                            print("[BLOCK] Dual approvals verification failed. Deployment aborted.")
                            print_separator()
                            continue
                    elif role == "Senior Engineer":
                        print("[WARNING] Senior Engineers require Manager authorization.")
                        mgr_code = input("Enter Manager Authorization Code (Hint: 123456): ").strip()
                        if mgr_code == "123456":
                            manager_approved = True
                            print("[SUCCESS] Manager approval accepted.")
                        else:
                            print("[BLOCK] Manager approval verification failed. Deployment aborted.")
                            print_separator()
                            continue
                            
                    # Stage 4: Execution
                    print("\n[Step 4/5] Capturing device state backup and running deploy playbook...")
                    backup_id = f"CLI_BCK_{int(datetime.now().timestamp())}"
                    print(f"  * Saved running-config backup to ID: {backup_id}")
                    print("  * Connecting to node via secure SSHv2...")
                    print("  * Applying configuration patch commands...")
                    print("  * Startup configuration written successfully.")
                    
                    # Stage 5: Verification
                    print("\n[Step 5/5] Running automated verification sweeps...")
                    simulate_fail = input("Simulate verification check failure? (y/N): ").strip().lower() == "y"
                    
                    if simulate_fail:
                        print("  * Running verification tests... Failed.")
                        print("\n[CRITICAL ALERT] Verification sweep FAILED. Initiating automatic rollback...")
                        print(f"  * Retrieving state backup {backup_id}...")
                        print("  * Restoring configuration... Rollback completed successfully.")
                        log_audit_event(
                            username=authenticated_user["username"],
                            role=role,
                            action="CLI Deploy Config",
                            ip="127.0.0.1",
                            details="Deployed config patch. Verification failed, auto-rolled back.",
                            status="Failed (Rolled Back)",
                            changes=commands,
                            approvals="Manager" if role == "Senior Engineer" else "Admin",
                            rollback=f"Restored {backup_id}"
                        )
                    else:
                        print("  * Running verification tests... Passed.")
                        print("[SUCCESS] Deployment successfully completed and validated.")
                        log_audit_event(
                            username=authenticated_user["username"],
                            role=role,
                            action="CLI Deploy Config",
                            ip="127.0.0.1",
                            details="Deployed config patch. Verification passed.",
                            status="Success",
                            changes=commands,
                            approvals="Manager" if role == "Senior Engineer" else "Admin"
                        )
                        
                        # Update status of incident
                        # Enable step 3 (RCA) in choice menu
                        
                    print_separator()
                elif choice == "3":
                    print("\n--- Generating Operational RCA Documentation ---")
                    print(scenario["rca"])
                    print_separator()
                elif choice == "4" or choice == "":
                    break
                else:
                    print("Invalid selection. Choose between 1 and 4.")

if __name__ == "__main__":
    main()
