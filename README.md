# Interactive Assistant Slack Bot

An interactive, multi-persona assistant Slack Bot built with Python, using the official Slack Bolt framework and Socket Mode. 

This bot responds to channel mentions (`@Assistant`) and direct messages (DMs), handles threaded conversation history for multi-turn chats, and uses Slack's Block Kit for interactive UI components (like dropdowns and buttons).

---

## Features

1. **Direct Mentions & DMs**: Responds to user queries when mentioned or messaged directly.
2. **Conversation Threading**: Keeps track of message threads to provide coherent multi-turn replies.
3. **Interactive Personas**: Run `/bot-persona` (or click "Change Persona") to select a personality for the bot:
   - 💻 **Code Master**: Specialized in refactoring, debugging, and explaining code.
   - 🌐 **Network Genius**: Helps diagnose networking protocols (OSPF, BGP, VLANs, etc.) and generate configuration patches.
   - 🛡️ **Security Specialist**: Provides security advice, firewall configuration tips, and log analysis.
   - 🤖 **Friendly Assistant**: General-purpose helpful chatbot with an approachable tone.
4. **Command Palette**:
   - `/bot-help`: Displays the help menu with interactive guidelines.
   - `/bot-persona`: Opens the personality selection UI.
   - `/bot-clear`: Resets active context or thread configurations.

---

## Slack App Configuration Setup

To run this bot, you must register a Slack App in the Slack Developer Console:

### 1. Create the App
1. Go to [Slack API: Your Apps](https://api.slack.com/apps) and click **Create New App**.
2. Select **From an app manifest**.
3. Choose your workspace and paste the following manifest YAML (or configure manually using the steps below):

```yaml
display_information:
  name: AssistantBot
  description: Multi-persona AI chatbot assistant
  background_color: "#1e1e2e"
features:
  app_home:
    home_tab_enabled: true
    messages_tab_enabled: true
    messages_tab_read_only_disabled: false
  bot_user:
    display_name: AssistantBot
    always_online: true
  slash_commands:
    - command: /bot-help
      description: Show bot help and usage commands
      should_share_channel: true
    - command: /bot-persona
      description: Change the bot's current active personality
      should_share_channel: true
    - command: /bot-clear
      description: Clear context/thread history
      should_share_channel: true
oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - chat:write
      - im:history
      - im:read
      - commands
      - channels:history
      - groups:history
settings:
  event_subscriptions:
    bot_events:
      - app_mention
      - message.im
  interactivity:
    is_enabled: true
  org_deploy_enabled: false
  socket_mode_enabled: true
```

### 2. Manual Configuration (Alternative)
If not using the manifest:
1. **Enable Socket Mode**: Go to **Settings > Socket Mode** and enable it. Generate an **App-Level Token** with the `connections:write` scope. (This is your `SLACK_APP_TOKEN` starting with `xapp-`).
2. **Enable Interactivity**: Go to **Features > Interactivity & Shortcuts** and turn it ON.
3. **Enable Events**: Go to **Features > Event Subscriptions**, turn it ON, and add these bot user events under "Subscribe to bot events":
   - `app_mention`
   - `message.im` (for DMs)
4. **Slash Commands**: Add `/bot-help`, `/bot-persona`, and `/bot-clear` in **Features > Slash Commands**.
5. **OAuth Scopes**: In **Features > OAuth & Permissions**, scroll down to Scopes and ensure these scopes are added:
   - `app_mentions:read`
   - `chat:write`
   - `im:history`
   - `im:read`
   - `commands`
   - `channels:history`
6. **Install App**: Click **Install to Workspace** at the top of the OAuth & Permissions page. Copy the **Bot User OAuth Token** (starts with `xoxb-`).

---

## Local Setup

1. **Clone/Move to the project directory** and install the Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables**:
   Create a `.env` file in the root folder (copying `.env.example`) and fill in your keys:
   ```env
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_APP_TOKEN=xapp-your-app-token
   GEMINI_API_KEY=your-gemini-api-key (optional)
   ```

3. **Run the Slack Bot**:
   ```bash
   python bot.py
   ```
   You will see a console message `⚡️ Bolt app is running!` when the bot successfully connects to Slack.

---

## Local Interactive CLI Simulator (No Tokens Required)

If you want to test the full enterprise multi-agent system, intent auto-routing, diagnostic sweeps, self-healing logs, and RCA generation directly in your terminal without configuring Slack tokens, run the console simulator:

```bash
python cli_harness.py
```

Try typing command prompts like `"VPN is down"` or `"Server CPU is 100%"`, and interact using keyboard options `1` to `4` to execute diagnostics and playbooks!

---

## Usage in Slack

- **Talk in channels**: Mention the bot using `@AssistantBot hello!`
- **Talk in DMs**: Go to App Home or search for `@AssistantBot` in your DMs and chat directly.
- **Change persona**: Type `/bot-persona` or click the button in help menus to choose another assistant type.
- **Show help**: Type `/bot-help` to inspect capabilities.

---

## Enterprise Production-Ready Backend Hardening (Phase 1)

This project has been hardened for enterprise-grade production environments with the following enhancements:

- **Centralized Configuration**: Managed using Pydantic Settings with full validations. See [docs/CONFIGURATION.md](file:///c:/Users/GANESH/Downloads/NOC-enigineer/docs/CONFIGURATION.md).
- **Structured JSON Logging**: Named logging namespaces with file rotation policies. See [docs/LOGGING.md](file:///c:/Users/GANESH/Downloads/NOC-enigineer/docs/LOGGING.md).
- **Centralized Error Handling**: 17 new custom domain exception classes mapping to unified standard responses. See [api/exceptions.py](file:///c:/Users/GANESH/Downloads/NOC-enigineer/api/exceptions.py).
- **Zero-Trust Hardening**: Capturing real client IP in audit logs, rate-limiting via SlowAPI, and secure HTTP response headers. See [docs/SECURITY.md](file:///c:/Users/GANESH/Downloads/NOC-enigineer/docs/SECURITY.md).
- **Database Schema & Migrations**: Integrated database migration versions via Alembic. See [docs/MIGRATIONS.md](file:///c:/Users/GANESH/Downloads/NOC-enigineer/docs/MIGRATIONS.md) and [docs/DATABASE_SCHEMA.md](file:///c:/Users/GANESH/Downloads/NOC-enigineer/docs/DATABASE_SCHEMA.md).
- **Core Architecture Layout**: Detailed component interaction diagram. See [docs/ARCHITECTURE.md](file:///c:/Users/GANESH/Downloads/NOC-enigineer/docs/ARCHITECTURE.md).
- **API Reference**: Comprehensive endpoint documentation. See [docs/API_OVERVIEW.md](file:///c:/Users/GANESH/Downloads/NOC-enigineer/docs/API_OVERVIEW.md).

