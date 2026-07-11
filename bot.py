import os
import re
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import ai_engine

# Load environment variables
load_dotenv()

# Initialize the Slack App (disable startup auth_test so it initializes cleanly even with dummy tokens)
app = App(token=os.environ.get("SLACK_BOT_TOKEN"), token_verification_enabled=False)

# Help Block Kit layout updated for all 8 agents (Phases 5-10)
def get_help_blocks():
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🤖 Enterprise AIOps Copilot",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Welcome to the **AIOps Multi-Agent Platform**. You can chat with me in channels by mentioning me "
                    "or by messaging me directly in DMs.\n\n"
                    "I will **automatically route** your incident alerts to the correct agent domain, or you can switch agents manually."
                )
            }
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Active Operational Agents:*\n"
                        "• 🌐 *Network Engineer*: BGP/OSPF, VLAN configuration, VPN troubleshooting.\n"
                        "• 🖥️ *Windows Administrator*: Active Directory management, IIS, Hyper-V, and DNS.\n"
                        "• 🐧 *Linux Administrator*: Apache/Nginx routing, Docker, Kubernetes system loads.\n"
                        "• 🚨 *NOC Engineer*: Alert analysis, SLA monitoring, telemetry sweeps.\n"
                        "• 🛡️ *Security Analyst*: Firewall syslog audits, threat detection, blocking access IPs.\n"
                        "• ☁️ *Cloud Engineer*: Public Cloud (AWS/Azure/GCP) networking and access rules.\n"
                        "• 📝 *Documentation Specialist*: SOP/MOP writing, post-outage RCA generation.\n"
                        "• ⚙️ *Automation Engineer*: Self-healing execution, playbooks, and scripting."
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Switch Persona ⚙️",
                        "emoji": True
                    },
                    "action_id": "open_persona_selector"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Clear Conversation 🧹",
                        "emoji": True
                    },
                    "action_id": "clear_conversation"
                }
            ]
        }
    ]

# Persona selector layout updated for all 8 agents
def get_persona_blocks(current_persona):
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Select Bot Persona:*\nChoose one of the specialized profiles below to lock the bot to that specific domain agent."
            }
        }
    ]
    
    # We split the buttons into 2 blocks because Slack allows max 5 elements per actions block
    actions1 = {
        "type": "actions",
        "elements": []
    }
    actions2 = {
        "type": "actions",
        "elements": []
    }
    
    keys = list(ai_engine.PERSONAS.keys())
    for idx, key in enumerate(keys):
        val = ai_engine.PERSONAS[key]
        is_current = (key == current_persona)
        label = f"{val['emoji']} {val['name']}"
        if is_current:
            label += " (Active)"
            
        button = {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": label,
                "emoji": True
            },
            "value": key,
            "action_id": f"select_persona_{key}",
            "style": "primary" if is_current else None
        }
        
        if idx < 5:
            actions1["elements"].append(button)
        else:
            actions2["elements"].append(button)
        
    blocks.append(actions1)
    if actions2["elements"]:
        blocks.append(actions2)
        
    return blocks

# Registering Persona Button Actions
for key in ai_engine.PERSONAS.keys():
    @app.action(f"select_persona_{key}")
    def handle_persona_select(ack, body, client):
        ack()
        persona_key = body["actions"][0]["value"]
        channel_id = body["container"]["channel_id"]
        thread_ts = body["container"].get("thread_ts")
        session_key = thread_ts if thread_ts else channel_id
        
        ai_engine.set_persona(session_key, persona_key)
        persona = ai_engine.PERSONAS[persona_key]
        
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"Switched persona to {persona['emoji']} *{persona['name']}*! {persona['description']}"
        )

@app.action("open_persona_selector")
def handle_open_selector(ack, body, client):
    ack()
    channel_id = body["container"]["channel_id"]
    thread_ts = body["container"].get("thread_ts")
    session_key = thread_ts if thread_ts else channel_id
    current_persona = ai_engine.get_persona(session_key)
    
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        blocks=get_persona_blocks(current_persona),
        text="Choose bot persona:"
    )

@app.action("clear_conversation")
def handle_clear_conv(ack, body, client):
    ack()
    channel_id = body["container"]["channel_id"]
    thread_ts = body["container"].get("thread_ts")
    session_key = thread_ts if thread_ts else channel_id
    ai_engine.set_persona(session_key, "assistant")
    
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text="🧹 Persona reset to *Friendly Assistant* and local cache context cleared!"
    )

# Scenario Interactive Actions (Diagnostics, Self-Healing, RCA)
@app.action(re.compile("run_diagnostics_(.+)"))
def handle_diagnostics_click(ack, body, client):
    ack()
    action_id = body["actions"][0]["action_id"]
    scenario_safe_key = re.match("run_diagnostics_(.+)", action_id).group(1)
    scenario_key = scenario_safe_key.replace("_", " ")
    
    channel_id = body["container"]["channel_id"]
    thread_ts = body["container"].get("thread_ts")
    response_thread_ts = thread_ts if thread_ts else body["container"].get("message_ts")
    
    scenario = ai_engine.SCENARIOS.get(scenario_key)
    if scenario:
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=response_thread_ts,
            text=scenario["diagnostics"]
        )

@app.action(re.compile("approve_healing_(.+)"))
def handle_healing_click(ack, body, client):
    ack()
    action_id = body["actions"][0]["action_id"]
    scenario_safe_key = re.match("approve_healing_(.+)", action_id).group(1)
    scenario_key = scenario_safe_key.replace("_", " ")
    
    channel_id = body["container"]["channel_id"]
    thread_ts = body["container"].get("thread_ts")
    response_thread_ts = thread_ts if thread_ts else body["container"].get("message_ts")
    
    scenario = ai_engine.SCENARIOS.get(scenario_key)
    if scenario:
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=response_thread_ts,
            text=scenario["healing"]
        )

@app.action(re.compile("generate_rca_(.+)"))
def handle_rca_click(ack, body, client):
    ack()
    action_id = body["actions"][0]["action_id"]
    scenario_safe_key = re.match("generate_rca_(.+)", action_id).group(1)
    scenario_key = scenario_safe_key.replace("_", " ")
    
    channel_id = body["container"]["channel_id"]
    thread_ts = body["container"].get("thread_ts")
    response_thread_ts = thread_ts if thread_ts else body["container"].get("message_ts")
    
    scenario = ai_engine.SCENARIOS.get(scenario_key)
    if scenario:
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=response_thread_ts,
            text=scenario["rca"]
        )

# Slash Commands
@app.command("/bot-help")
def command_help(ack, respond, command):
    ack()
    respond(blocks=get_help_blocks())

@app.command("/bot-persona")
def command_persona(ack, respond, command):
    ack()
    channel_id = command["channel_id"]
    current_persona = ai_engine.get_persona(channel_id)
    respond(blocks=get_persona_blocks(current_persona))

@app.command("/bot-clear")
def command_clear(ack, respond, command):
    ack()
    channel_id = command["channel_id"]
    ai_engine.set_persona(channel_id, "assistant")
    respond(text="🧹 Persona reset to *Friendly Assistant* and context cleared!")

# Message & Mention Handlers
def process_incoming_chat(client, event):
    channel_id = event["channel"]
    thread_ts = event.get("thread_ts")
    message_ts = event["ts"]
    user_text = event["text"]
    
    # Strip user mention if present
    cleaned_text = re.sub(r"<@[A-Z0-9]+>", "", user_text).strip()
    normalized_prompt = cleaned_text.lower().rstrip("?.- ")
    
    response_thread_ts = thread_ts if thread_ts else message_ts
    session_key = thread_ts if thread_ts else channel_id
    
    # AIOps Auto-Routing Intent Classifier
    routed_persona = ai_engine.auto_route_intent(normalized_prompt)
    if routed_persona:
        ai_engine.set_persona(session_key, routed_persona)
        
    persona_key = ai_engine.get_persona(session_key)
    persona = ai_engine.PERSONAS[persona_key]
    
    # Fetch thread history
    conversation_history = []
    if thread_ts:
        try:
            replies = client.conversations_replies(channel=channel_id, ts=thread_ts)
            for msg in replies.get("messages", []):
                if msg["ts"] == message_ts:
                    continue
                is_bot = "bot_id" in msg or msg.get("subtype") == "bot_message"
                role = "model" if is_bot else "user"
                text_clean = re.sub(r"<@[A-Z0-9]+>", "", msg["text"]).strip()
                conversation_history.append({"role": role, "text": text_clean})
        except Exception as e:
            print(f"Error fetching thread replies: {e}")
            
    # Send response
    try:
        scenario_key = ai_engine.find_matching_scenario(cleaned_text)
        
        reply_text = ai_engine.generate_ai_response(
            prompt_text=cleaned_text,
            conversation_history=conversation_history,
            persona_key=persona_key,
            active_scenario=scenario_key
        )
        
        # Build block layout response
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": reply_text
                }
            }
        ]
        
        # If it matches an interactive scenario, append diagnostic and action buttons
        if scenario_key:
            safe_key = scenario_key.replace(" ", "_")
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Run Diagnostics 📋",
                            "emoji": True
                        },
                        "action_id": f"run_diagnostics_{safe_key}"
                    },
                    {
                        "type": "button",
                        "style": "primary",
                        "text": {
                            "type": "plain_text",
                            "text": "Approve Self-Healing ⚙️",
                            "emoji": True
                        },
                        "action_id": f"approve_healing_{safe_key}"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Generate RCA 📝",
                            "emoji": True
                        },
                        "action_id": f"generate_rca_{safe_key}"
                    }
                ]
            })
        
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Active Persona: {persona['emoji']} *{persona['name']}* | AIOps Dispatcher Mode"
                }
            ]
        })
        
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=response_thread_ts,
            blocks=blocks,
            text=reply_text
        )
    except Exception as e:
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=response_thread_ts,
            text=f"⚠️ Failed to generate response: {e}"
        )

@app.event("app_mention")
def handle_app_mention(event, client):
    process_incoming_chat(client, event)

@app.event("message")
def handle_message(event, client):
    channel_type = event.get("channel_type")
    channel_id = event.get("channel", "")
    
    # DM check
    is_dm = channel_type == "im" or channel_id.startswith("D")
    is_bot = "bot_id" in event or event.get("subtype") == "bot_message"
    
    if is_dm and not is_bot:
        process_incoming_chat(client, event)

if __name__ == "__main__":
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    app_token = os.environ.get("SLACK_APP_TOKEN")
    
    if not bot_token or not app_token or "your-slack" in bot_token or "your-slack" in app_token or bot_token == "xoxb-your-slack-bot-token" or app_token == "xapp-your-slack-app-token":
        print("WARNING: SLACK_BOT_TOKEN or SLACK_APP_TOKEN environment variables are missing or default.")
        print("Please configure valid Slack app credentials in your .env file.")
        print("Slack Bot service deactivated. Exiting cleanly.")
        import sys
        sys.exit(0)
        
    try:
        handler = SocketModeHandler(app, app_token)
        print("⚡️ Bolt app is starting...")
        handler.start()
    except Exception as e:
        print("\n[SLACK BOLT APP ERROR] Failed to connect to Slack API via Socket Mode.")
        print(f"Error details: {e}")
        print("Please verify that your SLACK_BOT_TOKEN and SLACK_APP_TOKEN are correct and that Socket Mode is enabled in your Slack App settings.")
        print("Slack Bot service deactivated. Exiting cleanly.\n")
        import sys
        sys.exit(0)
