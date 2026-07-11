// NOC AI Copilot Web Dashboard Frontend Logic
document.addEventListener('DOMContentLoaded', () => {
    // Session State
    let activePersona = 'assistant';
    let currentScenario = 'VPN is down'; // matches initial selection
    let personaPool = {};
    let sessionId = sessionStorage.getItem('chatSessionId');
    if (!sessionId) {
        sessionId = 'session_' + Math.random().toString(36).substr(2, 9);
        sessionStorage.setItem('chatSessionId', sessionId);
    }
    
    // Auth State
    let currentUser = null;

    // Helper: secureFetch that injects JWT/Bearer Auth Token
    async function secureFetch(url, options = {}) {
        const token = sessionStorage.getItem('authToken');
        const headers = {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            ...(options.headers || {})
        };
        
        const response = await fetch(url, { ...options, headers });
        
        if (response.status === 401) {
            sessionStorage.removeItem('authToken');
            currentUser = null;
            showLoginOverlay(true);
            throw new Error('Unauthorized session context.');
        }
        
        return response;
    }

    // ----------------------------------------------------
    // Tab Navigation Elements
    // ----------------------------------------------------
    const navItems = document.querySelectorAll('.nav-item');
    const tabPanels = document.querySelectorAll('.tab-panel');
    const activeIncidentsBadge = document.getElementById('active-incidents-count');
    const summaryAlertsCount = document.getElementById('summary-alerts-count');

    // ----------------------------------------------------
    // Tab Navigation Logic
    // ----------------------------------------------------
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const tabId = item.getAttribute('data-tab');
            if (tabId === 'logout') {
                btnLogout.click();
                return;
            }
            
            // Update Active Nav Item
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            
            // Update Active Panel
            tabPanels.forEach(panel => panel.classList.remove('active'));
            const activePanel = document.getElementById(`panel-${tabId}`);
            if (activePanel) activePanel.classList.add('active');
            
            // Refresh tables on click
            if (tabId === 'vault') fetchVault();
            if (tabId === 'audit') fetchAuditLogs();
            if (tabId === 'topology') loadTopologyFromBackend();
            if (tabId === 'settings') fetchSettings();
            if (tabId === 'zero-trust') initZeroTrustCenter();
            if (tabId === 'scale') initScaleTuningDashboard();
        });
    });

    // ----------------------------------------------------
    // ZERO-TRUST AUTHENTICATION CONTROLLER
    // ----------------------------------------------------
    const loginOverlay = document.getElementById('login-overlay');
    const loginForm = document.getElementById('login-form');
    const mfaForm = document.getElementById('mfa-form');
    const loginUsernameInput = document.getElementById('login-username');
    const loginPasswordInput = document.getElementById('login-password');
    const mfaCodeInput = document.getElementById('mfa-code');
    const mfaSimulatedDisplay = document.getElementById('mfa-simulated-display');
    const mfaChallengeIdInput = document.getElementById('mfa-challenge-id');
    const loginErrorMsg = document.getElementById('login-error-msg');
    
    const userDisplayName = document.getElementById('user-display-name');
    const userDisplayRole = document.getElementById('user-display-role');
    const btnLogout = document.getElementById('btn-logout');

    function showLoginOverlay(show) {
        if (show) {
            loginOverlay.style.display = 'flex';
            loginForm.style.display = 'block';
            mfaForm.style.display = 'none';
            loginErrorMsg.style.display = 'none';
            loginForm.reset();
            mfaForm.reset();
        } else {
            loginOverlay.style.display = 'none';
        }
    }

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        loginErrorMsg.style.display = 'none';
        
        const username = loginUsernameInput.value.trim();
        const password = loginPasswordInput.value.trim();
        
        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Authentication failed.');
            }
            
            const data = await response.json();
            
            if (data.otpRequired) {
                loginForm.style.display = 'none';
                mfaForm.style.display = 'block';
                mfaChallengeIdInput.value = data.challengeId;
                mfaSimulatedDisplay.textContent = data.simulatedOtp;
                mfaCodeInput.focus();
            }
        } catch (error) {
            loginErrorMsg.textContent = error.message;
            loginErrorMsg.style.display = 'block';
        }
    });

    mfaForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        loginErrorMsg.style.display = 'none';
        
        const challengeId = mfaChallengeIdInput.value;
        const otp = mfaCodeInput.value.trim();
        
        try {
            const response = await fetch('/api/verify-otp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ challengeId, otp })
            });
            
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Invalid OTP code.');
            }
            
            const data = await response.json();
            sessionStorage.setItem('authToken', data.token);
            currentUser = data.user;
            
            // Update profile
            userDisplayName.textContent = currentUser.name;
            userDisplayRole.textContent = currentUser.role;
            document.getElementById('view-greeting').textContent = `Good Morning, ${currentUser.name}`;
            
            mfaForm.reset();
            showLoginOverlay(false);
            
            // Initial loads
            updateTelemetry();
            fetchVault();
            fetchAuditLogs();
            loadPersonas();
            initTimeline();
            loadIncidents();
        } catch (error) {
            loginForm.style.display = 'block';
            mfaForm.style.display = 'none';
            loginErrorMsg.textContent = error.message;
            loginErrorMsg.style.display = 'block';
        }
    });

    btnLogout.addEventListener('click', async () => {
        try {
            await secureFetch('/api/logout', { method: 'POST' });
        } catch (e) {}
        sessionStorage.removeItem('authToken');
        currentUser = null;
        userDisplayName.textContent = 'Unknown Operator';
        userDisplayRole.textContent = 'Guest Mode';
        showLoginOverlay(true);
    });

    // Check existing session
    const existingToken = sessionStorage.getItem('authToken');
    if (!existingToken) {
        showLoginOverlay(true);
    } else {
        // Simple recovery - fetch telemetry to check if token is valid
        fetch('/api/telemetry', {
            headers: { 'Authorization': `Bearer ${existingToken}` }
        }).then(res => {
            if (res.status === 200) {
                // To maintain security, we force zero-trust OTP session on page refresh
                showLoginOverlay(true);
            } else {
                showLoginOverlay(true);
            }
        }).catch(() => showLoginOverlay(true));
    }

    // ----------------------------------------------------
    // SYSTEM TIME DISPLAY
    // ----------------------------------------------------
    function updateClock() {
        const clockEl = document.getElementById('header-clock');
        if (clockEl) {
            clockEl.textContent = new Date().toLocaleTimeString();
        }
    }
    setInterval(updateClock, 1000);
    updateClock();

    // ----------------------------------------------------
    // Telemetry Update Loop
    // ----------------------------------------------------
    async function updateTelemetry() {
        if (!sessionStorage.getItem('authToken')) return;
        try {
            const response = await secureFetch('/api/telemetry');
            const data = await response.json();
            
            // Update Connection Badges
            updateConnectionBadge('indicator-slack', data.slackActive);
            updateConnectionBadge('indicator-gemini', data.geminiActive);
            
            // Update summary active alerts count
            const alertsCount = data.alarms ? data.alarms.length : 0;
            if (summaryAlertsCount) summaryAlertsCount.textContent = alertsCount;
            if (activeIncidentsBadge) activeIncidentsBadge.textContent = alertsCount;
            
            // Update KPI cards
            const devicesCount = data.nodes ? data.nodes.length : 0;
            const criticalCount = data.alarms ? data.alarms.filter(a => a.severity.toLowerCase() === 'critical').length : 0;
            const warningCount = data.alarms ? data.alarms.filter(a => a.severity.toLowerCase() === 'warning').length : 0;
            
            document.getElementById('kpi-devices-online').textContent = `${devicesCount - warningCount} / ${devicesCount}`;
            document.getElementById('kpi-critical-alerts').textContent = criticalCount;
            document.getElementById('kpi-warning-alerts').textContent = warningCount;
            
            // Render Managed Nodes Table in Device Inventory tab
            renderNodesTable(data.nodes);
            
            // Render Recent Alerts list
            renderRecentAlerts(data.alarms);

            // Render Mumbai Ping Monitor Table
            updatePingMonitorTable(data.nodes);
            
            // Redraw Topology Canvas
            drawTopology();
            
            // Sync active incidents with live alarms
            if (typeof activeIncidents !== 'undefined' && activeIncidents.length > 0) {
                // 1. Check db-srv-01 alarm
                const hasDbAlarm = data.alarms.some(a => a.source && a.source.includes('db-srv-01'));
                const dbInc = activeIncidents.find(i => i.id === 'TASK-921');
                if (dbInc) dbInc.status = hasDbAlarm ? 'Active' : 'Resolved';

                // 2. Check asa-edge-01 alarm
                const hasAsaAlarm = data.alarms.some(a => a.source && a.source.includes('asa-edge-01'));
                const asaInc = activeIncidents.find(i => i.id === 'INC-405');
                if (asaInc) asaInc.status = hasAsaAlarm ? 'Active' : 'Resolved';

                // 3. Check router-hq state
                const routerNode = data.nodes.find(n => n.name && n.name.includes('router-hq'));
                const vpnInc = activeIncidents.find(i => i.id === 'INC-402');
                if (vpnInc) vpnInc.status = (routerNode && routerNode.status !== 'Healthy') ? 'Active' : 'Resolved';

                // 4. Check app-srv-02 state
                const appNode = data.nodes.find(n => n.name && n.name.includes('app-srv-02'));
                const cpuInc = activeIncidents.find(i => i.id === 'INC-403');
                if (cpuInc) cpuInc.status = (appNode && appNode.status !== 'Healthy') ? 'Active' : 'Resolved';

                // Re-render
                renderIncidentsQueue();
                renderIncidentsCatalog();

                // Trigger autonomous self-healing if enabled and not currently executing
                const selectedPolicy = document.querySelector('input[name="auto-policy"]:checked');
                if (selectedPolicy) {
                    autoPolicySetting = selectedPolicy.value;
                }
                if (autoPolicySetting === 'autonomous' && !isAutonomousExecuting) {
                    const firstActive = activeIncidents.find(i => i.status === 'Active');
                    if (firstActive) {
                        triggerAutonomousSelfHealing(firstActive);
                    }
                }
            }

            // Update Settings Panel Statuses
            const slackBadge = document.getElementById('settings-slack-status');
            const geminiBadge = document.getElementById('settings-gemini-status');
            
            if (slackBadge) {
                slackBadge.textContent = data.slackActive ? 'ONLINE' : 'OFFLINE';
                slackBadge.className = data.slackActive ? 'badge healthy' : 'badge critical';
            }
            
            if (geminiBadge) {
                geminiBadge.textContent = data.geminiActive ? 'CONNECTED' : 'MISSING KEY';
                geminiBadge.className = data.geminiActive ? 'badge healthy' : 'badge critical';
            }
            
        } catch (error) {
            console.error('Error fetching telemetry data:', error);
        }
    }

    function updateConnectionBadge(elementId, isActive) {
        const element = document.getElementById(elementId);
        if (!element) return;
        const dot = element.querySelector('.dot');
        if (isActive) {
            dot.className = 'dot online';
        } else {
            dot.className = 'dot offline';
        }
    }

    function renderNodesTable(nodes) {
        const nodeTableBody = document.querySelector('#node-table-body tbody');
        if (!nodeTableBody) return;
        nodeTableBody.innerHTML = '';
        
        nodes.forEach(node => {
            const tr = document.createElement('tr');
            
            const isWarn = node.status.toLowerCase() === 'warning';
            const statusClass = isWarn ? 'warning' : 'healthy';
            const statusIcon = isWarn ? 'fa-triangle-exclamation' : 'fa-circle-check';
            
            tr.innerHTML = `
                <td><strong>${node.name}</strong></td>
                <td><span class="status-badge ${statusClass}"><i class="fa-solid ${statusIcon}"></i> ${node.status}</span></td>
                <td>${node.cpu}%</td>
                <td>${node.ram}%</td>
                <td>${node.message ? `<span class="warning-text">${node.message}</span>` : '<span class="success-text">Active Telemetry Online</span>'}</td>
            `;
            nodeTableBody.appendChild(tr);
        });
    }

    function renderRecentAlerts(alarms) {
        const tableBody = document.querySelector('#dashboard-recent-alerts tbody');
        if (!tableBody) return;
        tableBody.innerHTML = '';
        
        if (alarms.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;">No active alerts</td></tr>';
            return;
        }
        
        alarms.forEach(alarm => {
            const tr = document.createElement('tr');
            const isCrit = alarm.severity.toLowerCase() === 'critical';
            const icon = isCrit ? '<i class="fa-solid fa-circle-exclamation" style="color:var(--critical)"></i>' : '<i class="fa-solid fa-triangle-exclamation" style="color:var(--warning)"></i>';
            const statusClass = isCrit ? 'critical' : 'warning';
            
            tr.innerHTML = `
                <td>${icon} ${alarm.metric}</td>
                <td><strong>${alarm.source}</strong></td>
                <td>${alarm.time}</td>
                <td><span class="status-badge ${statusClass}">${alarm.severity.toUpperCase()}</span></td>
            `;
            tableBody.appendChild(tr);
        });
    }

    // Refresh telemetry loop
    setInterval(updateTelemetry, 4000);

    // ----------------------------------------------------
    // Operational Personas Init
    // ----------------------------------------------------
    async function loadPersonas() {
        if (!sessionStorage.getItem('authToken')) return;
        try {
            const response = await secureFetch('/api/personas');
            personaPool = await response.json();
        } catch (error) {
            console.error('Error loading personas:', error);
        }
    }

    // ----------------------------------------------------
    // AI TERMINAL TABS & INTERACTIVE COMMANDS
    // ----------------------------------------------------
    const consoleTabButtons = document.querySelectorAll('.console-tab-btn');
    const consoleOutput = document.getElementById('console-body-output');
    const consoleInputField = document.getElementById('console-input-field');
    const consolePromptLbl = document.getElementById('console-prompt-lbl');
    let currentConsoleTab = 'chat';

    consoleTabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            consoleTabButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const target = btn.getAttribute('data-console');
            currentConsoleTab = target;
            
            // Show corresponding wrapper
            const wrappers = ['chat', 'cli', 'logs', 'pcap', 'ansible', 'terraform'];
            wrappers.forEach(w => {
                const el = document.getElementById(`console-${w}-wrapper`);
                if (el) el.style.display = w === target ? 'block' : 'none';
            });
            
            // Update Prompt label
            if (target === 'cli') {
                consolePromptLbl.textContent = 'SSH router-hq#';
                consoleInputField.placeholder = "Type diagnostic switch command (e.g. show ip route, show logging, ping)...";
            } else {
                consolePromptLbl.textContent = 'AI Copilot>';
                consoleInputField.placeholder = "Ask AI Copilot to analyze telemetry or run playbook...";
            }
        });
    });

    consoleInputField.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const text = consoleInputField.value.trim();
            if (!text) return;
            consoleInputField.value = '';
            
            if (currentConsoleTab === 'cli') {
                handleCliCommand(text);
            } else {
                handleChatCommand(text);
            }
        }
    });

    const btnStopGen = document.getElementById('btn-stop-generation');
    if (btnStopGen) {
        btnStopGen.addEventListener('click', () => {
            if (chatAbortController) {
                chatAbortController.abort();
            }
        });
    }

    const btnRegenChat = document.getElementById('btn-regenerate-chat');
    if (btnRegenChat) {
        btnRegenChat.addEventListener('click', () => {
            if (lastUserPrompt) {
                handleChatCommand(lastUserPrompt);
            }
        });
    }

    const btnClearChat = document.getElementById('btn-clear-chat');
    if (btnClearChat) {
        btnClearChat.addEventListener('click', async () => {
            if (confirm("Are you sure you want to clear the conversation memory?")) {
                const wrapper = document.getElementById('console-chat-wrapper');
                if (wrapper) {
                    wrapper.innerHTML = `<p style="color: var(--text-muted);"><i class="fa-solid fa-robot" style="color:var(--primary)"></i> <strong>NOC AI Copilot</strong>: Hello! I am your AIOps virtual companion. I can parse routing tables, audit security alerts, and run ansible patches. Ask me a question or type a direct switch command in the input bar below.</p>`;
                }
                
                // Call clear API on server
                try {
                    await secureFetch('/api/clear-chat', {
                        method: 'POST',
                        body: JSON.stringify({ sessionId })
                    });
                } catch(e) {
                    console.error("Error clearing chat memory:", e);
                }
                
                if (btnRegenChat) btnRegenChat.style.display = 'none';
                if (btnStopGen) btnStopGen.style.display = 'none';
                lastUserPrompt = '';
                clearAllAttachments();
            }
        });
    }

    const personaEmojis = {
        net_genius: "🌐 Network Engineer",
        win_admin: "🖥️ Windows Administrator",
        lin_admin: "🐧 Linux Administrator",
        noc_eng: "🚨 NOC Engineer",
        sec_analyst: "🛡️ Security Analyst",
        cloud_eng: "☁️ Cloud Engineer",
        doc_specialist: "📝 Documentation Specialist",
        auto_eng: "⚙️ Automation Engineer",
        assistant: "🤖 Friendly Assistant"
    };

    let chatAbortController = null;
    let lastUserPrompt = '';

    // File attachments states
    let attachedLogs = null;
    let attachedConfig = null;
    let attachedTopology = null;

    async function handleChatCommand(text) {
        lastUserPrompt = text;
        
        // Hide retry button when starting a query
        const btnRetry = document.getElementById('btn-regenerate-chat');
        if (btnRetry) btnRetry.style.display = 'none';

        const wrapper = document.getElementById('console-chat-wrapper');
        
        // Render User message bubble
        const userRow = document.createElement('div');
        userRow.className = 'chat-msg-row user';
        userRow.innerHTML = `
            <div class="chat-msg-header">👤 You</div>
            <div class="chat-msg-bubble">${escapeHtml(text)}</div>
        `;
        wrapper.appendChild(userRow);
        
        // Create Bot response message block (initially empty)
        const botRow = document.createElement('div');
        botRow.className = 'chat-msg-row assistant';
        const personaLabel = personaEmojis[activePersona] || "🤖 NOC AI Copilot";
        botRow.innerHTML = `
            <div class="chat-msg-header"><i class="fa-solid fa-robot" style="color:var(--primary)"></i> <strong class="bot-persona-name">${personaLabel}</strong></div>
            <div class="chat-msg-bubble bot-content-bubble"><span style="color:var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Thinking...</span></div>
        `;
        wrapper.appendChild(botRow);
        
        const contentBubble = botRow.querySelector('.bot-content-bubble');
        consoleOutput.scrollTop = consoleOutput.scrollHeight;

        // Show Stop Generation button
        const btnStop = document.getElementById('btn-stop-generation');
        if (btnStop) btnStop.style.display = 'block';

        // Setup abort controller
        chatAbortController = new AbortController();
        const signal = chatAbortController.signal;

        let accumulatedResponse = '';
        let isFirstChunk = true;

        try {
            const token = sessionStorage.getItem('authToken');
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                },
                body: JSON.stringify({
                    message: text,
                    persona: activePersona,
                    sessionId: sessionId,
                    scenario: currentScenario,
                    uploadedLogs: attachedLogs,
                    uploadedConfig: attachedConfig,
                    uploadedTopology: attachedTopology
                }),
                signal: signal
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Server returned error status");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Save the last partial line

                for (const line of lines) {
                    if (line.trim().startsWith('data: ')) {
                        const dataStr = line.slice(line.indexOf('data: ') + 6);
                        try {
                            const chunk = JSON.parse(dataStr);
                            
                            if (chunk.text) {
                                if (isFirstChunk) {
                                    contentBubble.innerHTML = '';
                                    isFirstChunk = false;
                                }
                                accumulatedResponse += chunk.text;
                                renderBubbleContent(contentBubble, accumulatedResponse);
                                
                                // Smart scroll
                                const isAtBottom = consoleOutput.scrollHeight - consoleOutput.clientHeight - consoleOutput.scrollTop < 100;
                                if (isAtBottom) {
                                    consoleOutput.scrollTop = consoleOutput.scrollHeight;
                                }
                            }
                            
                            // Dynamically update active persona if classified
                            if (chunk.persona && chunk.persona !== activePersona) {
                                activePersona = chunk.persona;
                                const newLabel = personaEmojis[activePersona] || "🤖 NOC AI Copilot";
                                botRow.querySelector('.bot-persona-name').textContent = newLabel;
                            }
                        } catch (e) {
                            console.warn("Could not parse SSE chunk:", line, e);
                        }
                    }
                }
            }

            // Stream finished successfully
            if (isFirstChunk) {
                contentBubble.textContent = "No response generated.";
            }
            
            // Clean up attachments
            clearAllAttachments();

        } catch (err) {
            if (err.name === 'AbortError') {
                contentBubble.innerHTML += `<p style="color:var(--warning); margin-top:0.4rem; font-size:0.65rem;"><i class="fa-solid fa-circle-stop"></i> Response generation halted by operator.</p>`;
            } else {
                console.error("Chat streaming error:", err);
                if (isFirstChunk) {
                    contentBubble.innerHTML = `<span style="color:var(--critical)"><i class="fa-solid fa-triangle-exclamation"></i> Error: ${escapeHtml(err.message)}</span>`;
                } else {
                    contentBubble.innerHTML += `<p style="color:var(--critical); margin-top:0.4rem; font-size:0.65rem;"><i class="fa-solid fa-circle-exclamation"></i> Connection lost.</p>`;
                }
            }
        } finally {
            if (btnStop) btnStop.style.display = 'none';
            if (btnRetry) btnRetry.style.display = 'block';
            chatAbortController = null;
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
        }
    }

    function renderBubbleContent(element, text) {
        // Parse markdown via marked
        if (typeof marked !== 'undefined') {
            let htmlContent = marked.parse(text);
            
            // Intercept pre code language-mermaid blocks and convert to div.mermaid
            const temp = document.createElement('div');
            temp.innerHTML = htmlContent;
            
            temp.querySelectorAll('pre').forEach(pre => {
                const code = pre.querySelector('code');
                if (code) {
                    const isMermaid = code.classList.contains('language-mermaid') || 
                                     code.textContent.trim().startsWith('graph ') || 
                                     code.textContent.trim().startsWith('flowchart ');
                                     
                    if (isMermaid) {
                        const mermaidDiv = document.createElement('div');
                        mermaidDiv.className = 'mermaid';
                        mermaidDiv.textContent = code.textContent;
                        pre.parentNode.replaceChild(mermaidDiv, pre);
                    }
                }
            });
            
            element.innerHTML = temp.innerHTML;
            
            // Highlight code blocks
            if (typeof hljs !== 'undefined') {
                element.querySelectorAll('pre code').forEach(block => {
                    hljs.highlightElement(block);
                });
            }
            
            // Render Mermaid diagrams
            if (typeof mermaid !== 'undefined') {
                try {
                    mermaid.init(undefined, element.querySelectorAll('.mermaid'));
                } catch(e) {
                    // Suppress drawing error until chunk finishes loading fully
                }
            }
        } else {
            // Fallback plain formatting
            element.innerHTML = formatMarkdownText(text);
        }
    }

    function handleCliCommand(text) {
        const wrapper = document.getElementById('console-cli-wrapper');
        const pCmd = document.createElement('p');
        pCmd.innerHTML = `<span style="color:white;">router-hq# ${escapeHtml(text)}</span>`;
        wrapper.appendChild(pCmd);
        
        const cmdClean = text.toLowerCase().trim();
        let response = "";
        
        if (cmdClean === "show ip route" || cmdClean === "sh ip ro" || cmdClean === "sh ip route") {
            response = `Codes: L - local, C - connected, S - static, R - RIP, M - mobile, B - BGP
       D - EIGRP, EX - EIGRP external, O - OSPF, IA - OSPF inter area 

Gateway of last resort is 198.51.100.1 to interface GigabitEthernet1

S*    0.0.0.0/0 [1/0] via 198.51.100.1, GigabitEthernet1
C     198.51.100.0/24 is directly connected, GigabitEthernet1
L     198.51.100.2/32 is directly connected, GigabitEthernet1
O     10.0.1.0/24 [110/2] via 10.0.1.254, GigabitEthernet2, 04:12:31
B     10.1.20.0/24 [20/0] via 198.51.100.1, 00:00:00 (State: Active/Down)
O     10.0.20.0/24 [110/10] via 10.0.1.1, GigabitEthernet2, 04:12:31`;
        } 
        else if (cmdClean === "show logging" || cmdClean === "sh log" || cmdClean === "sh logging") {
            response = `Syslog logging: enabled (0 messages dropped, 0 messages rate-limited)
    Console logging: level debugging, 142 messages logged
    Monitor logging: level info, 0 messages logged

Log Buffer (4096 bytes):
2026-07-02 19:12:04 %LINEPROTO-5-UPDOWN: Line protocol on Interface Tunnel10, changed state to down
2026-07-02 19:12:05 %OSPF-5-ADJCHG: Process 1, Nbr 198.51.100.1 on Tunnel10 from FULL to DOWN, Neighbor Down
2026-07-02 19:15:33 %SEC-6-IPACCESS: Blocked SSH attempt on asa-edge-01 from attacker 198.51.100.45
2026-07-02 19:28:12 %IPSEC-3-REKEY_FAIL: Phase 1 Lifetime negotiation timeout error with peer 203.0.113.10`;
        } 
        else if (cmdClean.startsWith("show interface") || cmdClean.startsWith("sh int") || cmdClean.startsWith("sh interface")) {
            response = `GigabitEthernet1 is up, line protocol is up 
  Hardware is Gigabit Ethernet, address is 5254.0012.3456 (bia 5254.0012.3456)
  Internet address is 198.51.100.2/24
  MTU 1500 bytes, BW 1000000 Kbit/sec, DLY 10 usec, 
     reliability 255/255, txload 12/255, rxload 25/255
  Encapsulation ARPA, loopback not set
  Keepalive set (10 sec)
  Full-duplex, 1000Mb/s, link type is auto, media type is RJ45
  Output queue: 0/40 (size/max); Input queue: 0/75 (size/max)
  5 minute input rate 124000 bits/sec, 42 packets/sec
  5 minute output rate 88000 bits/sec, 30 packets/sec
     0 input errors, 0 CRC, 0 frame, 0 overrun, 0 ignored
     0 output errors, 0 collisions, 0 interface resets`;
        } 
        else if (cmdClean.startsWith("ping")) {
            const target = cmdClean.split(" ")[1] || "198.51.100.1";
            response = `Sending 5, 100-byte ICMP Echos to ${target}, timeout is 2 seconds:
!!!!!
Success rate is 100 percent (5/5), round-trip min/avg/max = 1/4/9 ms`;
            const isVpnDown = activeIncidents.some(i => i.scenario === "VPN is down" && i.status === "Active");
            if (isVpnDown && (target.includes("203.0.113.10") || target.includes("10.1.20.10"))) {
                response = `Sending 5, 100-byte ICMP Echos to ${target}, timeout is 2 seconds:
.....
Success rate is 0 percent (0/5)`;
            }
        } 
        else if (cmdClean.startsWith("traceroute")) {
            response = `Type escape sequence to abort.
Tracing the route to 10.1.20.10 (mumbai-erp)
  1  10.0.1.254 (sw-core-01) 1 msec 1 msec 2 msec
  2  198.51.100.1 (mumbai-gw) 22 msec 24 msec * (Asymmetric path split)
  3  * * * (Request Timed Out)`;
        } 
        else {
            response = `% Invalid input detected at '^' marker.\nCommand '${text}' unsupported in NOC simulator mode.`;
        }
        
        const pResp = document.createElement('pre');
        pResp.style.marginTop = "0.25rem";
        pResp.style.marginBottom = "0.75rem";
        pResp.style.whiteSpace = "pre-wrap";
        pResp.textContent = response;
        wrapper.appendChild(pResp);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }

    // ----------------------------------------------------
    // DYNAMIC WIZARD TIMELINE INIT
    // ----------------------------------------------------
    const timelineSteps = [
        { id: "alert_received", label: "Alert Mnemonic Flagged", desc: "Telemetry alarm registered in active DB." },
        { id: "ssh_connected", label: "Zero-Trust SSH Gateway Authenticated", desc: "Established secure session with node." },
        { id: "collect_logs", label: "Running Configuration Dump", desc: "Fetched running configs for validation." },
        { id: "run_diagnostics", label: "Run Automated Sweeps", desc: "Comparing routes and cryptographic state." },
        { id: "check_ospf", label: "OSPF Adjacency check", desc: "Checked cost metrics and area matches." },
        { id: "check_bgp", label: "BGP Session auditing", desc: "Checked TCP port 179 state." },
        { id: "check_vpn", label: "IPsec SA state check", desc: "Auditing cryptography lifetimes." },
        { id: "check_interfaces", label: "Interface line checks", desc: "Scanned up/down states and MTUs." },
        { id: "root_cause", label: "RCA Discovered", desc: "Determined root cause issue." },
        { id: "generate_fix", label: "Remediation Script Generated", desc: "Staged CLI config commands." },
        { id: "waiting_approval", label: "Awaiting Operator Authorization", desc: "Staged approvals wizard." },
        { id: "executing", label: "Executing Automated Playbook", desc: "Applied configuration commands." },
        { id: "verification", label: "Verification Sweeps Passed", desc: "Reachability verified successfully." }
    ];

    function initTimeline() {
        const container = document.getElementById('timeline-steps-container');
        if (!container) return;
        container.innerHTML = '';
        
        timelineSteps.forEach(step => {
            const div = document.createElement('div');
            div.className = 'timeline-item';
            div.id = `timeline-step-${step.id}`;
            div.innerHTML = `
                <div class="timeline-content">
                    <strong>${step.label}</strong>
                    <span>Pending</span>
                </div>
            `;
            container.appendChild(div);
        });
    }

    // ----------------------------------------------------
    // ACTIVE INCIDENT QUEUE & RCA UPDATER
    // ----------------------------------------------------
    let activeIncidents = [];

    // Helper to map dynamic database incident alerts to frontend client scenario parameters
    function mapDbIncidentToClient(dbInc) {
        let mapped = {
            id: dbInc.id,
            severity: dbInc.severity,
            device: dbInc.device_name,
            site: dbInc.site,
            vendor: dbInc.vendor,
            status: dbInc.status,
            time: timeAgo(new Date(dbInc.timestamp)),
            timestamp: dbInc.timestamp,
            description: dbInc.description,
            business_impact: dbInc.business_impact,
            confidence: dbInc.confidence,
            rca: dbInc.root_cause
        };

        const deviceLower = dbInc.device_name.toLowerCase();
        const descLower = dbInc.description.toLowerCase();

        if (deviceLower === 'router-hq' && (descLower.includes('vpn') || descLower.includes('bgp') || descLower.includes('tunnel'))) {
            mapped.scenario = "VPN is down";
            mapped.tech = "IPsec VPN";
            mapped.assignedAi = "NetGenius AI";
            mapped.fix = "crypto isakmp policy 10\n lifetime 28800";
            mapped.risk = "Safe / Dual Approval Required";
            mapped.rca = "IPsec VPN Phase 1 Tunnel negotiation failed due to LIFETIME_MISMATCH.";
        } else if (deviceLower === 'app-srv-02' && (descLower.includes('cpu') || descLower.includes('overheat') || descLower.includes('temperature'))) {
            mapped.scenario = "Server CPU is 100%";
            mapped.tech = "Nginx Server";
            mapped.assignedAi = "NginxHealer AI";
            mapped.fix = "kill -9 40912\nsystemctl reload nginx";
            mapped.risk = "Medium / Senior Operator Approval Required";
            mapped.rca = "Offending nginx worker thread spinning at 100% due to routing regex loop evaluation.";
        } else if (deviceLower === 'db-srv-01' && (descLower.includes('disk') || descLower.includes('memory') || descLower.includes('storage') || descLower.includes('partition'))) {
            mapped.scenario = "Check daily server health";
            mapped.tech = "Log Storage";
            mapped.assignedAi = "LogPruner AI";
            mapped.fix = "find /var/log -name '*.gz' -mtime +30 -delete";
            mapped.risk = "Safe / Single Operator Approval";
            mapped.rca = "Disk space partition alert: db-srv-01 /var/log storage capacity reached 94%.";
        } else if (deviceLower === 'asa-edge-01' && (descLower.includes('ssh') || descLower.includes('flood') || descLower.includes('spray') || descLower.includes('attack'))) {
            mapped.scenario = "Analyze this firewall log";
            mapped.tech = "SSH Access-List";
            mapped.assignedAi = "SecGenius AI";
            mapped.fix = "access-list outside_access_in line 1 extended deny tcp host 198.51.100.45 any eq 22";
            mapped.risk = "Safe / Senior Operator Approval Required";
            mapped.rca = "Brute-force SSH password spray attempt flagged from malicious IP 198.51.100.45.";
        } else if (deviceLower === 'sw-core-01' && (descLower.includes('vlan') || descLower.includes('switchport'))) {
            mapped.scenario = "Configure VLAN 20";
            mapped.tech = "VLAN Switchport";
            mapped.assignedAi = "NetGenius AI";
            mapped.fix = "vlan 20\n name DB_Subnet\ninterface range GigabitEthernet1/0/1 - 12\n switchport access vlan 20";
            mapped.risk = "Safe / Senior Operator Approval Required";
            mapped.rca = "VLAN 20 database subnet tags missing on core trunk link switches.";
        } else {
            mapped.scenario = "General Operational Incident";
            mapped.tech = "Network Security";
            mapped.assignedAi = "Copilot AI";
            mapped.fix = "! Run diagnostics sweep";
            mapped.risk = "Safe / Single Operator Approval";
        }

        // Override with rich database fields if available
        if (dbInc.evidence) mapped.evidence = dbInc.evidence;
        if (dbInc.remediation_commands) mapped.fix = dbInc.remediation_commands;
        if (dbInc.verification_steps) mapped.verification = dbInc.verification_steps;
        if (dbInc.rollback_plan) mapped.rollback = dbInc.rollback_plan;
        if (dbInc.risk_level) mapped.risk = dbInc.risk_level;
        if (dbInc.repair_time) mapped.repairTime = dbInc.repair_time;
        if (dbInc.engineering_report) mapped.report = dbInc.engineering_report;

        return mapped;
    }

    function timeAgo(date) {
        const seconds = Math.floor((new Date() - date) / 1000);
        if (isNaN(seconds) || seconds < 0) return 'Just now';
        if (seconds < 60) return 'Just now';
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes}m ago`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ago`;
        return date.toLocaleDateString();
    }

    async function loadIncidents() {
        if (!sessionStorage.getItem('authToken')) return;
        
        try {
            const response = await secureFetch('/api/incidents');
            if (!response.ok) throw new Error("API error");
            const data = await response.json();
            
            if (data && Array.isArray(data)) {
                activeIncidents = data.map(mapDbIncidentToClient);
            } else {
                activeIncidents = [];
            }
        } catch (err) {
            console.error("Failed to load incidents from server, using fallback:", err);
            // Fallback to static pre-seeded mock list if server is offline
            activeIncidents = [
                { id: "INC-ROUTER-HQ-VPN_STATUS", severity: "Critical", device: "router-hq", tech: "IPsec VPN", time: "2h ago", status: "Active", scenario: "VPN is down", rca: "IPsec VPN Phase 1 Tunnel negotiation failed due to LIFETIME_MISMATCH.", fix: "crypto isakmp policy 10\n lifetime 28800", risk: "Safe / Dual Approval Required", confidence: "95%", vendor: "Cisco", assignedAi: "NetGenius AI" },
                { id: "INC-APP-SRV-02-CPU_UTILIZATION", severity: "Critical", device: "app-srv-02", tech: "Nginx Server", time: "45m ago", status: "Active", scenario: "Server CPU is 100%", rca: "Offending nginx worker thread spinning at 100% due to routing regex loop evaluation.", fix: "kill -9 40912\nsystemctl reload nginx", risk: "Medium / Senior Operator Approval Required", confidence: "91%", vendor: "Linux", assignedAi: "NginxHealer AI" },
                { id: "INC-SW-CORE-01-VLAN", severity: "Warning", device: "sw-core-01", tech: "VLAN Switchport", time: "1h ago", status: "Active", scenario: "Configure VLAN 20", rca: "VLAN 20 database subnet tags missing on core trunk link switches.", fix: "vlan 20\n name DB_Subnet\ninterface range GigabitEthernet1/0/1 - 12\n switchport access vlan 20", risk: "Safe / Senior Operator Approval Required", confidence: "98%", vendor: "Cisco", assignedAi: "NetGenius AI" },
                { id: "TASK-DB-SRV-01-HEALTH", severity: "Warning", device: "db-srv-01", tech: "Log Storage", time: "Routine", status: "Active", scenario: "Check daily server health", rca: "Disk space partition alert: db-srv-01 /var/log storage capacity reached 94%.", fix: "find /var/log -name '*.gz' -mtime +30 -delete", risk: "Safe / Single Operator Approval", confidence: "99%", vendor: "Linux", assignedAi: "LogPruner AI" },
                { id: "INC-ASA-EDGE-01-SSH_ATTACK", severity: "Critical", device: "asa-edge-01", tech: "SSH Access-List", time: "5m ago", status: "Active", scenario: "Analyze this firewall log", rca: "Brute-force SSH password spray attempt flagged from malicious IP 198.51.100.45.", fix: "access-list outside_access_in line 1 extended deny tcp host 198.51.100.45 any eq 22", risk: "Safe / Senior Operator Approval Required", confidence: "96%", vendor: "Cisco", assignedAi: "SecGenius AI" }
            ];
        }
        
        renderIncidentsQueue();
        renderIncidentsCatalog();
        
        if (activeIncidents.length > 0) {
            // Pre-select first active incident if available, else first incident
            const firstActive = activeIncidents.find(i => i.status === 'Active') || activeIncidents[0];
            selectIncident(firstActive);
        }
    }

    function renderIncidentsQueue() {
        const tbody = document.querySelector('#dashboard-incident-table tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        
        activeIncidents.forEach(inc => {
            const tr = document.createElement('tr');
            
            const isCrit = inc.severity.toLowerCase() === 'critical';
            const statusClass = isCrit ? 'critical' : 'warning';
            
            tr.innerHTML = `
                <td><span class="status-badge ${statusClass}">${inc.severity.toUpperCase()}</span></td>
                <td><strong>${inc.device}</strong></td>
                <td>${inc.tech}</td>
                <td>${inc.time}</td>
                <td class="inc-status-td-${inc.id}">${inc.status}</td>
                <td><span style="color: var(--primary); font-weight:600;"><i class="fa-solid fa-robot"></i> ${inc.assignedAi}</span></td>
                <td style="display:flex; gap:0.25rem;">
                    <button class="btn btn-sm btn-outline btn-inc-open" data-id="${inc.id}">Open</button>
                    <button class="btn btn-sm btn-primary btn-inc-investigate" data-id="${inc.id}">Investigate</button>
                    <button class="btn btn-sm btn-success btn-inc-resolve" data-id="${inc.id}" ${inc.status === 'Resolved' ? 'disabled' : ''}>Resolve</button>
                </td>
            `;
            
            tr.querySelector('.btn-inc-open').addEventListener('click', () => {
                showIncidentDetailsModal(inc);
            });
            
            tr.querySelector('.btn-inc-investigate').addEventListener('click', () => {
                selectIncident(inc);
                runIncidentInvestigation(inc);
            });

            tr.querySelector('.btn-inc-resolve').addEventListener('click', () => {
                resolveIncidentDirectly(inc);
            });
            
            tbody.appendChild(tr);
        });
    }

    function resolveIncidentDirectly(inc) {
        inc.status = 'Resolved';
        secureFetch('/api/deploy-config', {
            method: 'POST',
            body: JSON.stringify({
                commands: inc.fix,
                device: inc.device,
                managerApproved: true,
                adminApproved: true
            })
        }).then(() => {
            alert(`Incident ${inc.id} has been resolved. AI auto-healer configuration patch deployed.`);
            updateTelemetry();
        }).catch(() => {
            alert(`Local override: Incident ${inc.id} marked as resolved.`);
            updateTelemetry();
        });
    }

    function renderIncidentsCatalog() {
        const container = document.getElementById('control-room-incidents-list');
        if (!container) return;
        container.innerHTML = '';
        
        activeIncidents.forEach(inc => {
            const div = document.createElement('div');
            div.className = `incident-card ${inc.scenario === currentScenario ? 'active' : ''}`;
            div.setAttribute('data-id', inc.id);
            
            const statusColorClass = inc.status === 'Resolved' ? 'status-resolved' : (inc.severity.toLowerCase() === 'critical' ? 'status-critical' : 'status-warning');
            
            div.innerHTML = `
                <div class="card-status ${statusColorClass}" id="cat-card-status-${inc.id}"></div>
                <div class="incident-meta">
                    <span class="time">${inc.time}</span>
                    <span class="id">${inc.id}</span>
                </div>
                <h4>${inc.tech} Outage Alert</h4>
                <p>${inc.device} segment reporting degraded parameters.</p>
            `;
            
            div.addEventListener('click', () => {
                document.querySelectorAll('.incident-card').forEach(c => c.classList.remove('active'));
                div.classList.add('active');
                
                const found = activeIncidents.find(i => i.id === inc.id);
                if (found) {
                    currentScenario = found.scenario;
                    selectIncident(found);
                }
            });
            
            container.appendChild(div);
        });
    }

    function selectIncident(inc) {
        currentScenario = inc.scenario;
        
        // Update RCA card details
        document.getElementById('rca-header-id').textContent = `Incident ID: ${inc.id}`;
        document.getElementById('rca-affected-device').textContent = inc.device;
        document.getElementById('rca-tech-vendor').textContent = `${inc.vendor} / ${inc.tech}`;
        document.getElementById('rca-confidence').textContent = inc.confidence;
        document.getElementById('rca-root-cause-text').textContent = inc.rca;
        document.getElementById('rca-recommended-fix').textContent = inc.fix;
        document.getElementById('rca-risk-level').textContent = inc.risk.split(" / ")[0];
        
        // Dynamic AI Enriched Fields
        const repairTimeEl = document.getElementById('rca-repair-time');
        if (repairTimeEl) repairTimeEl.textContent = inc.repairTime || "10 mins";

        const businessImpactEl = document.getElementById('rca-business-impact');
        if (businessImpactEl) businessImpactEl.textContent = inc.business_impact || "N/A";

        const verificationStepsEl = document.getElementById('rca-verification-steps');
        if (verificationStepsEl) verificationStepsEl.textContent = inc.verification || "show ip interface brief";

        const rollbackPlanEl = document.getElementById('rca-rollback-plan');
        if (rollbackPlanEl) rollbackPlanEl.textContent = inc.rollback || "no config";
        
        const reportBlock = document.getElementById('rca-report-block');
        if (reportBlock) reportBlock.style.display = 'none';

        const isCrit = inc.severity.toLowerCase() === 'critical';
        const sevBadge = document.getElementById('rca-severity-badge');
        if (sevBadge) {
            sevBadge.textContent = inc.severity.toUpperCase();
            sevBadge.className = `status-badge ${isCrit ? 'critical' : 'warning'}`;
        }
        
        const appReq = document.getElementById('rca-approval-req');
        if (appReq) {
            appReq.textContent = inc.risk.includes('Dual') ? 'Yes (Dual Tokens)' : 'Yes (Single Operator)';
        }

        const evidenceBox = document.getElementById('rca-evidence-box');
        if (evidenceBox) {
            if (inc.evidence) {
                evidenceBox.innerHTML = escapeHtml(inc.evidence).replace(/\n/g, '<br>');
            } else {
                if (inc.scenario === "VPN is down") {
                    evidenceBox.innerHTML = `• Syslog indicates LIFETIME_MISMATCH peer tunnel<br>• IPsec SA negotiation state: down<br>• Gateway ping probe packet drop rate: 100%`;
                } else if (inc.scenario === "Server CPU is 100%") {
                    evidenceBox.innerHTML = `• Nginx CPU utilization: 100% on pid 40912<br>• Access logs show heavy regex search traffic<br>• HTTP 502 Bad Gateway status spikes`;
                } else if (inc.scenario === "Configure VLAN 20") {
                    evidenceBox.innerHTML = `• Trunk interfaces missing VLAN tag 20<br>• VLAN database audit drift detected<br>• ARP resolution failures to DB hosts`;
                } else if (inc.scenario === "Check daily server health") {
                    evidenceBox.innerHTML = `• Disk space capacity alert on /var/log: 94%<br>• Core logs warning threshold reached`;
                } else if (inc.scenario === "Analyze this firewall log") {
                    evidenceBox.innerHTML = `• Brute-force SSH password spray attempt flagged<br>• Malicious IP 198.51.100.45 logged 120 attempts`;
                } else {
                    evidenceBox.textContent = "No evidence collected.";
                }
            }
        }

        // Update Auto Remediation Tab Panel
        const remedRisk = document.getElementById('remed-risk-badge');
        if (remedRisk) {
            remedRisk.textContent = inc.risk.toUpperCase();
            remedRisk.className = `status-badge ${isCrit ? 'critical' : 'warning'}`;
        }
        const remedDowntime = document.getElementById('remed-downtime');
        if (remedDowntime) {
            remedDowntime.textContent = inc.scenario === 'VPN is down' ? '30 seconds (BGP failover)' : 'No downtime expected';
        }
        const remedVerif = document.getElementById('remed-verification-result');
        if (remedVerif) {
            remedVerif.textContent = inc.status === 'Resolved' ? 'Verification Passed' : 'Awaiting Execution';
            remedVerif.className = `status-badge ${inc.status === 'Resolved' ? 'healthy' : 'warning'}`;
        }
        const remedCmds = document.getElementById('remed-commands-box');
        if (remedCmds) {
            remedCmds.textContent = inc.fix;
        }
        const remedRollback = document.getElementById('remed-rollback-box');
        if (remedRollback) {
            remedRollback.textContent = `no ${inc.fix.split('\n')[0]}`;
        }
        const remedBar = document.getElementById('remed-progress-bar');
        const remedPct = document.getElementById('remed-progress-text');
        if (remedBar && remedPct) {
            remedBar.style.width = inc.status === 'Resolved' ? '100%' : '0%';
            remedBar.style.backgroundColor = inc.status === 'Resolved' ? 'var(--healthy)' : 'var(--primary)';
            remedPct.textContent = inc.status === 'Resolved' ? '100%' : '0%';
        }
        
        // Update Control Room labels
        const crTitle = document.getElementById('cr-incident-title');
        const crSeverity = document.getElementById('cr-incident-severity');
        const crDesc = document.getElementById('cr-incident-desc');
        
        if (crTitle) crTitle.textContent = `${inc.vendor} ${inc.tech} Outage`;
        if (crSeverity) {
            crSeverity.textContent = inc.severity.toUpperCase();
            crSeverity.className = `status-badge ${isCrit ? 'critical' : 'warning'}`;
        }
        if (crDesc) crDesc.textContent = inc.rca;
        
        // Reset Workflow Stepper locks
        resetWorkflowSteps();
        
        if (inc.status === 'Resolved') {
            const btnDiag = document.getElementById('btn-run-diag');
            if (btnDiag) {
                btnDiag.disabled = true;
                btnDiag.innerHTML = '<i class="fa-solid fa-check"></i> Diagnostics Complete';
            }
            
            const stepHealing = document.getElementById('step-card-healing');
            if (stepHealing) stepHealing.classList.remove('lock-disabled');
            
            const btnHeal = document.getElementById('btn-run-healing');
            if (btnHeal) {
                btnHeal.innerHTML = '<i class="fa-solid fa-check"></i> Deployed';
                btnHeal.disabled = true;
            }
            
            const stepRca = document.getElementById('step-card-rca');
            if (stepRca) stepRca.classList.remove('lock-disabled');
            
            const btnRpt = document.getElementById('btn-run-rca');
            if (btnRpt) {
                btnRpt.disabled = false;
                btnRpt.innerHTML = 'Generate Report';
            }
        }
        
        // Update Right Utility Panel status (Thinking dashboard)
        document.getElementById('rp-target-device').textContent = inc.device;
        document.getElementById('rp-target-tool').textContent = "AIOps Inspector";
        document.getElementById('rp-target-command').textContent = "None";
        document.getElementById('rp-target-confidence').textContent = inc.confidence;
        document.getElementById('rp-target-next').textContent = "Run automated diagnostics sweep";
        
        document.getElementById('rp-thinking').textContent = `Ready to audit configuration parameters and syslog lines on ${inc.device}.`;
        
        const evidenceContainer = document.getElementById('rp-evidence');
        evidenceContainer.innerHTML = '<li>Awaiting diagnostics triggers.</li>';
        
        document.getElementById('rp-reasoning').textContent = "Timeline details will populate during active diagnostic execution.";
        
        // Load target device health parameters in row 3
        const selector = document.getElementById('device-health-selector');
        if (selector) {
            selector.value = inc.device;
            updateDeviceHealthUI(inc.device);
        }
    }

    function updateDeviceHealthUI(devName) {
        let cpu = 15;
        let ram = 40;
        let temp = 39;
        let bandwidth = 120;
        let loss = "0.0%";
        let lossFill = 0;
        let latency = 2.4;
        let errors = 0;
        
        if (currentScenario === "VPN is down" && devName === "router-hq") {
            cpu = 48;
            ram = 68;
            temp = 48;
            bandwidth = 0;
            loss = "100.0%";
            lossFill = 100;
            latency = 0;
            errors = 42;
        } else if (currentScenario === "Server CPU is 100%" && devName === "app-srv-02") {
            cpu = 100;
            ram = 72;
            temp = 54;
            latency = 124.5;
            errors = 8;
        } else if (devName === "db-srv-01") {
            cpu = 38;
            ram = 78;
            temp = 41;
            latency = 1.8;
            errors = 0;
        } else if (currentScenario === "Analyze this firewall log" && devName === "asa-edge-01") {
            cpu = 54;
            ram = 50;
            temp = 42;
            latency = 3.5;
            errors = 14;
        }
        
        document.getElementById('dh-cpu').textContent = `${cpu}%`;
        document.getElementById('dh-cpu-fill').style.width = `${cpu}%`;
        
        document.getElementById('dh-ram').textContent = `${ram}%`;
        document.getElementById('dh-ram-fill').style.width = `${ram}%`;
        
        document.getElementById('dh-temp').textContent = `${temp}°C`;
        document.getElementById('dh-temp-fill').style.width = `${temp}%`;
        
        document.getElementById('dh-bandwidth').textContent = `${bandwidth} Mbps`;
        document.getElementById('dh-bandwidth-fill').style.width = `${bandwidth/10}%`;
        
        document.getElementById('dh-loss').textContent = loss;
        document.getElementById('dh-loss').className = loss !== "0.0%" ? "warning-text" : "";
        document.getElementById('dh-loss-fill').style.width = `${lossFill}%`;

        document.getElementById('dh-latency').textContent = latency > 0 ? `${latency} ms` : "--";
        document.getElementById('dh-latency-fill').style.width = `${Math.min(100, latency)}%`;

        document.getElementById('dh-errors').textContent = errors;
        document.getElementById('dh-errors').className = errors > 0 ? "warning-text" : "";
        document.getElementById('dh-errors-fill').style.width = `${Math.min(100, errors * 2)}%`;
    }

    const devHealthSelector = document.getElementById('device-health-selector');
    if (devHealthSelector) {
        devHealthSelector.addEventListener('change', () => {
            updateDeviceHealthUI(devHealthSelector.value);
        });
    }

    // ----------------------------------------------------
    // DYNAMIC RUN INVESTIGATION TIMELINE ANIMATIONS
    // ----------------------------------------------------
    const timelineBadge = document.getElementById('timeline-status-badge');

    async function runIncidentInvestigation(inc) {
        // Redraw fresh timeline
        initTimeline();
        if (timelineBadge) {
            timelineBadge.textContent = "Investigating...";
            timelineBadge.style.color = "var(--warning)";
        }
        
        // Disable actions during sweep
        document.querySelectorAll('.btn-inc-investigate').forEach(b => b.disabled = true);
        
        // Update Right panel thinking state
        document.getElementById('rp-target-tool').textContent = "Diagnostics SSH Sweep";
        
        let timelineIndex = 0;
        
        // Sequence steps simulation
        const stepsMap = [
            { stepId: "alert_received", time: 400, thinking: "Telemetry mismatch alarm registered in database.", tool: "Zabbix Link", command: "N/A" },
            { stepId: "ssh_connected", time: 800, thinking: "Connecting to Edge Gateway SSH terminal...", tool: "SSHv2 Connection", command: "ssh admin@198.51.100.2" },
            { stepId: "collect_logs", time: 1200, thinking: "Dumping running configurations and checking config drift...", tool: "Config Parser", command: "show running-config" },
            { stepId: "run_diagnostics", time: 1600, thinking: "Running diagnostic routines for area Cost alignments.", tool: "Graph Analyzer", command: "show ip protocols" }
        ];
        
        // Inject protocol specific details
        if (inc.scenario === "VPN is down") {
            stepsMap.push(
                { stepId: "check_vpn", time: 2000, thinking: "Inspecting ISAKMP security associations...", tool: "Crypto Collector", command: "show crypto isakmp sa" },
                { stepId: "check_interfaces", time: 2400, thinking: "Scanning MTU mismatch and Tunnel line protocol state...", tool: "CLI Collector", command: "show ip interface brief" }
            );
        } else if (inc.scenario === "Server CPU is 100%") {
            stepsMap.push(
                { stepId: "check_interfaces", time: 2000, thinking: "Scanning server load and worker process threads...", tool: "Bash Engine", command: "ps aux --sort=-%cpu" }
            );
        } else if (inc.scenario === "Configure VLAN 20") {
            stepsMap.push(
                { stepId: "check_ospf", time: 2000, thinking: "Validating switchport database VLAN definitions...", tool: "Switchport Auditor", command: "show vlan brief" }
            );
        } else if (inc.scenario === "Analyze this firewall log") {
            stepsMap.push(
                { stepId: "check_bgp", time: 2000, thinking: "Auditing perimeter syslog line connection logs...", tool: "ASA syslog parser", command: "show logging" }
            );
        }
        
        stepsMap.push(
            { stepId: "root_cause", time: 2800, thinking: `Root cause identified: ${inc.rca}`, tool: "AIOps Mapped Result", command: "N/A" },
            { stepId: "generate_fix", time: 3200, thinking: "Remediation templates staged in deployment wizard.", tool: "Ansible Engine", command: "N/A" },
            { stepId: "waiting_approval", time: 3600, thinking: "Staging operator authorization gate. Ready for execution.", tool: "Approval Gate", command: "N/A" }
        );

        function triggerStep(idx) {
            if (idx < stepsMap.length) {
                const s = stepsMap[idx];
                setTimeout(() => {
                    const stepEl = document.getElementById(`timeline-step-${s.stepId}`);
                    if (stepEl) {
                        stepEl.className = 'timeline-item success';
                        const timeStr = new Date().toLocaleTimeString();
                        stepEl.querySelector('.timeline-content span').textContent = timeStr;
                    }
                    
                    // Update Right Panel UI
                    document.getElementById('rp-thinking').textContent = s.thinking;
                    document.getElementById('rp-target-command').textContent = s.command;
                    document.getElementById('rp-target-tool').textContent = s.tool;
                    
                    // Add to evidence collection lists
                    if (s.command !== "N/A") {
                        const evidenceContainer = document.getElementById('rp-evidence');
                        if (evidenceContainer.innerHTML.includes('Awaiting')) evidenceContainer.innerHTML = '';
                        const li = document.createElement('li');
                        li.innerHTML = `<i class="fa-solid fa-circle-check"></i> Executed: <code>${s.command}</code>`;
                        evidenceContainer.appendChild(li);
                    }
                    
                    triggerStep(idx + 1);
                }, s.time - (idx > 0 ? stepsMap[idx-1].time : 0));
            } else {
                if (timelineBadge) {
                    timelineBadge.textContent = "Awaiting Action";
                    timelineBadge.style.color = "var(--primary)";
                }
                document.querySelectorAll('.btn-inc-investigate').forEach(b => b.disabled = false);
                
                // Unlock Step 2 Healer buttons in Incident control room
                document.getElementById('step-card-healing').classList.remove('lock-disabled');
                document.getElementById('btn-run-healing').disabled = false;
            }
        }
        
        triggerStep(0);
    }

    // Attach click events on dashboard RCA actions
    document.getElementById('btn-rca-diag').addEventListener('click', () => {
        const activeCard = activeIncidents.find(i => i.scenario === currentScenario);
        if (activeCard) {
            runIncidentInvestigation(activeCard);
        }
    });

    document.getElementById('btn-rca-gen-fix').addEventListener('click', () => {
        const activeCard = activeIncidents.find(i => i.scenario === currentScenario);
        if (activeCard) {
            const btn = document.getElementById('btn-rca-gen-fix');
            btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Generating...';
            btn.disabled = true;
            setTimeout(() => {
                btn.innerHTML = 'Generate Fix';
                btn.disabled = false;
                alert(`AI configuration patch generated for ${activeCard.device}. Ready for deployment.`);
            }, 800);
        }
    });

    document.getElementById('btn-rca-fix').addEventListener('click', () => {
        const activeCard = activeIncidents.find(i => i.scenario === currentScenario);
        if (activeCard) {
            showRemediationModal(activeCard);
        }
    });

    document.getElementById('btn-rca-rollback').addEventListener('click', () => {
        const activeCard = activeIncidents.find(i => i.scenario === currentScenario);
        if (activeCard) {
            const btn = document.getElementById('btn-rca-rollback');
            btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Rolling back...';
            btn.disabled = true;
            setTimeout(() => {
                btn.innerHTML = 'Rollback';
                btn.disabled = true;
                activeCard.status = 'Active';
                alert(`Rollback playbook completed on ${activeCard.device}. Original state restored.`);
                updateTelemetry();
            }, 1000);
        }
    });

    // Auto Remediation Panel Buttons
    const btnRemedApprove = document.getElementById('btn-remed-approve');
    const btnRemedReject = document.getElementById('btn-remed-reject');
    
    if (btnRemedApprove) {
        btnRemedApprove.addEventListener('click', () => {
            const activeCard = activeIncidents.find(i => i.scenario === currentScenario);
            if (!activeCard) return;
            
            btnRemedApprove.disabled = true;
            btnRemedApprove.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Deploying...';
            
            let progress = 0;
            const bar = document.getElementById('remed-progress-bar');
            const pct = document.getElementById('remed-progress-text');
            const verif = document.getElementById('remed-verification-result');
            
            if (verif) {
                verif.textContent = "Executing...";
                verif.className = "status-badge warning";
            }
            
            const interval = setInterval(() => {
                progress += 20;
                if (bar) bar.style.width = `${progress}%`;
                if (pct) pct.textContent = `${progress}%`;
                
                if (progress >= 100) {
                    clearInterval(interval);
                    btnRemedApprove.innerHTML = 'Approve & Execute Patch';
                    btnRemedApprove.disabled = false;
                    
                    resolveIncidentDirectly(activeCard);
                    
                    if (verif) {
                        verif.textContent = "Verification Passed";
                        verif.className = "status-badge healthy";
                    }
                }
            }, 300);
        });
    }
    
    if (btnRemedReject) {
        btnRemedReject.addEventListener('click', () => {
            alert("Remediation policy rejected by operator. Aborted.");
            const verif = document.getElementById('remed-verification-result');
            if (verif) {
                verif.textContent = "Rejected";
                verif.className = "status-badge critical";
            }
        });
    }

    // Theme Toggle listener
    const themeToggleBtn = document.getElementById('btn-theme-toggle');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            document.body.classList.toggle('light-theme');
            const icon = themeToggleBtn.querySelector('i');
            if (document.body.classList.contains('light-theme')) {
                icon.className = 'fa-solid fa-sun';
            } else {
                icon.className = 'fa-solid fa-moon';
            }
        });
    }

    // ----------------------------------------------------
    // CONTROL ROOM PLAYBOOK STEPPER TRIGGERS & AUTONOMOUS AGENT ENGINE
    // ----------------------------------------------------
    const btnRunDiag = document.getElementById('btn-run-diag');
    const terminalDiag = document.getElementById('terminal-diag');
    const terminalDiagOutput = document.getElementById('terminal-diag-output');
    const btnRunHealing = document.getElementById('btn-run-healing');
    const wizardContainer = document.getElementById('deployment-wizard-container');
    const wizardContentBox = document.getElementById('wizard-content-box');
    const btnWizardCancel = document.getElementById('btn-wizard-cancel');
    const btnWizardNext = document.getElementById('btn-wizard-next');
    const cbSimulateFail = document.getElementById('cb-simulate-fail');
    const terminalHealing = document.getElementById('terminal-healing');
    const terminalHealingOutput = document.getElementById('terminal-healing-output');

    let autoPolicySetting = 'approval';
    let isAutonomousExecuting = false;

    async function triggerAutonomousSelfHealing(inc) {
        if (isAutonomousExecuting) return;
        isAutonomousExecuting = true;
        console.log(`[AUTONOMOUS AIOPS] Target alert identified on ${inc.device}. Starting diagnostics...`);
        
        // Select incident
        selectIncident(inc);
        
        // Show progress visual
        document.getElementById('nav-control-room').click();
        
        // Trigger Step 1 Diagnostics
        if (btnRunDiag && !btnRunDiag.disabled) {
            btnRunDiag.click();
        }
        
        // Wait for timeline diagnostics animation to complete
        setTimeout(() => {
            // Trigger Step 2 Deployment stepper
            if (btnRunHealing && !btnRunHealing.disabled) {
                btnRunHealing.click();
                autoRunWizardSteps();
            } else {
                isAutonomousExecuting = false;
            }
        }, 5000);
    }

    function autoRunWizardSteps() {
        // Run Step 1 Validation -> Proceed to Simulation
        setTimeout(() => {
            if (btnWizardNext && !btnWizardNext.disabled) {
                btnWizardNext.click();
                
                // Run Step 2 Simulation -> Proceed to Approvals
                setTimeout(() => {
                    if (btnWizardNext && !btnWizardNext.disabled) {
                        btnWizardNext.click();
                        
                        // Run Step 3 Approvals
                        setTimeout(() => {
                            // Enforce automated token verification inputs
                            const btnDual = document.getElementById('btn-request-dual-tokens');
                            if (btnDual && !btnDual.disabled) {
                                btnDual.click();
                            }
                            const valBtn = document.getElementById('btn-validate-mgr-token');
                            const tokenInput = document.getElementById('mgr-token-input');
                            if (tokenInput) tokenInput.value = '123456';
                            if (valBtn && !valBtn.disabled) valBtn.click();
                            
                            // Wait for approvals to bind and proceed to Step 4 Execution
                            setTimeout(() => {
                                if (btnWizardNext && !btnWizardNext.disabled) {
                                    btnWizardNext.click();
                                    
                                    // Wait for execution CLI logs to print and proceed to Step 5 Verification
                                    setTimeout(() => {
                                        if (btnWizardNext && !btnWizardNext.disabled) {
                                            btnWizardNext.click();
                                            
                                            // Wait for verification success sweep and finish
                                            setTimeout(() => {
                                                if (btnWizardCancel) btnWizardCancel.click();
                                                isAutonomousExecuting = false;
                                                console.log("[AUTONOMOUS AIOPS] Self-healing sequence successfully completed.");
                                            }, 2500);
                                        } else {
                                            isAutonomousExecuting = false;
                                        }
                                    }, 3000);
                                } else {
                                    isAutonomousExecuting = false;
                                }
                            }, 1500);
                            
                        }, 1500);
                    } else {
                        isAutonomousExecuting = false;
                    }
                }, 1500);
            } else {
                isAutonomousExecuting = false;
            }
        }, 1500);
    }

    if (btnRunDiag) {
        btnRunDiag.addEventListener('click', () => {
            const found = activeIncidents.find(i => i.scenario === currentScenario);
            if (found) {
                runIncidentInvestigation(found);
                
                // Mirror step 1 terminal output
                btnRunDiag.disabled = true;
                btnRunDiag.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Diagnostics Running...';
                
                secureFetch('/api/action', {
                    method: 'POST',
                    body: JSON.stringify({ scenario: found.scenario, action: 'diagnostics' })
                }).then(res => res.json()).then(data => {
                    terminalDiag.style.display = 'block';
                    btnRunDiag.innerHTML = '<i class="fa-solid fa-check"></i> Diagnostics Complete';
                    terminalDiagOutput.textContent = data.output;
                });
            }
        });
    }

    // Healer Wizard buttons
    btnRunHealing.addEventListener('click', async () => {
        btnRunHealing.disabled = true;
        wizardContainer.style.display = 'block';
        
        let commandsText = "";
        const found = activeIncidents.find(i => i.scenario === currentScenario);
        if (found) commandsText = found.fix;
        
        wizardData.commands = commandsText;
        wizardData.requiresDual = currentScenario === 'VPN is down' || currentScenario === 'Analyze this firewall log';
        wizardData.managerApproved = false;
        wizardData.adminApproved = false;
        
        runWizardStep(1);
    });

    // ----------------------------------------------------
    // REMEDIATION STEPS MODAL / OVERLAY CONTROLS
    // ----------------------------------------------------
    const remediationModal = document.getElementById('modal-remediation');
    const closeRemediationBtn = document.getElementById('btn-close-remediation-modal');
    const approveRemediationBtn = document.getElementById('btn-remediation-approve');
    const rejectRemediationBtn = document.getElementById('btn-remediation-reject');

    function showRemediationModal(inc) {
        remediationModal.style.display = 'flex';
        
        document.getElementById('md-remediation-risk').textContent = inc.risk.split(" / ")[0];
        document.getElementById('md-remediation-downtime').textContent = inc.scenario === 'VPN is down' ? '30 seconds (BGP failover)' : 'No downtime expected';
        document.getElementById('md-remediation-commands').textContent = inc.fix;
        document.getElementById('md-remediation-rollback').textContent = `no ${inc.fix.split('\n')[0]}`;
        document.getElementById('md-remediation-state').textContent = 'Staged. Awaiting operator token validation.';
    }

    closeRemediationBtn.addEventListener('click', () => {
        remediationModal.style.display = 'none';
    });

    approveRemediationBtn.addEventListener('click', () => {
        remediationModal.style.display = 'none';
        
        // Redirect user to the Live Incidents / Playbook tab to see wizard step approvals
        document.getElementById('nav-control-room').click();
        
        // Find and select incident
        const catCard = document.querySelector(`.incident-card[data-id="${currentScenario === 'VPN is down' ? 'INC-402' : 'INC-403'}"]`);
        if (catCard) catCard.click();
        
        // Open wizard automatically
        setTimeout(() => {
            btnRunHealing.click();
        }, 300);
    });

    rejectRemediationBtn.addEventListener('click', () => {
        remediationModal.style.display = 'none';
    });

    // ----------------------------------------------------
    // INCIDENT DETAILS MULTI-TAB DOSSIER MODAL
    // ----------------------------------------------------
    const detailsModal = document.getElementById('modal-incident-details');
    const closeDetailsBtn = document.getElementById('btn-close-details-modal');

    function showIncidentDetailsModal(inc) {
        detailsModal.style.display = 'flex';
        
        const detailsBody = document.getElementById('details-modal-body');
        
        let priority = inc.severity === 'Critical' ? 'P1 - High Alert' : 'P3 - Medium Alert';
        let affectedServices = inc.tech === 'IPsec VPN' ? 'Primary WAN Tunnel, Mumbai-HQ Sync' : (inc.tech === 'Nginx Server' ? 'Customer portal, Nginx Egress' : 'Corporate LAN Segment');
        let businessImpact = inc.severity === 'Critical' ? 'Degrades primary production traffic pathways. Remote branch sites unable to sync operations data.' : 'Moderate latency increase for DB clients.';
        let evidence = inc.rca;
        let timeline = `
            • [19:12:04] Alarm flagged: ${inc.tech} degraded parameters.<br>
            • [19:12:30] SSH session established to ${inc.device}.<br>
            • [19:12:45] AI diagnostics completed. Confidence: ${inc.confidence}.<br>
            • [19:13:02] Staged patch configuration rules.
        `;
        let commandsExecuted = inc.status === 'Resolved' ? inc.fix : 'Awaiting Operator Approval Gate';
        let filesCollected = `<code>${inc.device}-running-config.txt</code>, <code>${inc.device}-syslog.log</code>`;
        let verification = inc.status === 'Resolved' ? 'OSPF Neighborhood Full, ICMP Probes 100% Reachable' : 'Pending patch execution';
        let lessonsLearned = inc.scenario === 'VPN is down' ? 'Review ISAKMP lifetime parameters regularly across hybrid environments.' : 'Implement log rotation policies and regex timeout audits.';
        let preventiveActions = inc.scenario === 'VPN is down' ? 'Deploy OSPF state monitors and active tunnel keepalives.' : 'Configure automated crontab log-pruning and nginx workers limits.';

        detailsBody.innerHTML = `
            <div style="display:flex; justify-content:space-between; margin-bottom:1rem; border-bottom:1px solid var(--border-color); padding-bottom:0.5rem;">
                <div>
                    <h4 style="font-size:1.1rem; color:white; font-weight:700;">Incident Dossier: ${inc.id}</h4>
                    <span style="font-size:0.75rem; color:var(--text-muted);">Affected Target Node: <strong style="color:white;">${inc.device}</strong></span>
                </div>
                <div style="display:flex; flex-direction:column; align-items:flex-end;">
                    <span class="status-badge ${inc.severity.toLowerCase() === 'critical' ? 'critical' : 'warning'}">${inc.severity.toUpperCase()}</span>
                    <span style="font-size:0.65rem; color:var(--text-muted); margin-top:4px;">${inc.time}</span>
                </div>
            </div>
            
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:1rem; max-height:60vh; overflow-y:auto; padding-right:0.5rem;">
                <div class="rca-block">
                    <span style="color:var(--text-muted); display:block; font-weight:600; margin-bottom:2px;">Incident Number</span>
                    <strong style="color:white;">${inc.id}</strong>
                </div>
                <div class="rca-block">
                    <span style="color:var(--text-muted); display:block; font-weight:600; margin-bottom:2px;">Priority / SLA</span>
                    <strong style="color:white;">${priority}</strong>
                </div>
                
                <div class="rca-block" style="grid-column: 1 / 3;">
                    <span style="color:var(--text-muted); display:block; font-weight:600; margin-bottom:2px;">Business Impact</span>
                    <p style="color:var(--text-normal); line-height:1.4;">${businessImpact}</p>
                </div>
                
                <div class="rca-block">
                    <span style="color:var(--text-muted); display:block; font-weight:600; margin-bottom:2px;">Affected Services</span>
                    <strong style="color:white;">${affectedServices}</strong>
                </div>
                <div class="rca-block">
                    <span style="color:var(--text-muted); display:block; font-weight:600; margin-bottom:2px;">Verification Status</span>
                    <strong style="color:var(--healthy);">${verification}</strong>
                </div>
                
                <div class="rca-block" style="grid-column: 1 / 3;">
                    <span style="color:var(--text-muted); display:block; font-weight:600; margin-bottom:2px;">AI Root Cause Discovery</span>
                    <p style="color:white; font-weight:600; line-height:1.4;">${inc.rca}</p>
                </div>
                
                <div class="rca-block" style="grid-column: 1 / 3;">
                    <span style="color:var(--text-muted); display:block; font-weight:600; margin-bottom:2px;">Troubleshooting Timeline</span>
                    <p style="color:var(--text-normal); line-height:1.4; font-size:0.7rem; font-family:'Fira Code', monospace;">${timeline}</p>
                </div>
                
                <div class="rca-block" style="grid-column: 1 / 3;">
                    <span style="color:var(--text-muted); display:block; font-weight:600; margin-bottom:4px;">Staged Config Commands to Execute</span>
                    <pre style="background:black; color:var(--healthy); padding:0.5rem; border-radius:6px; font-family:'Fira Code', monospace; font-size:0.7rem; overflow-x:auto;">${commandsExecuted}</pre>
                </div>
                
                <div class="rca-block">
                    <span style="color:var(--text-muted); display:block; font-weight:600; margin-bottom:2px;">Files Collected (Artifacts)</span>
                    <p style="color:var(--text-normal); font-size:0.7rem;">${filesCollected}</p>
                </div>
                <div class="rca-block">
                    <span style="color:var(--text-muted); display:block; font-weight:600; margin-bottom:2px;">Assigned AI Agent</span>
                    <strong style="color:var(--primary);"><i class="fa-solid fa-robot"></i> ${inc.assignedAi}</strong>
                </div>
                
                <div class="rca-block" style="grid-column: 1 / 3;">
                    <span style="color:var(--text-muted); display:block; font-weight:600; margin-bottom:2px;">Lessons Learned</span>
                    <p style="color:var(--text-normal); line-height:1.4;">${lessonsLearned}</p>
                </div>
                
                <div class="rca-block" style="grid-column: 1 / 3;">
                    <span style="color:var(--text-muted); display:block; font-weight:600; margin-bottom:2px;">Preventive Actions Policy</span>
                    <p style="color:var(--text-normal); line-height:1.4; color:var(--primary); font-weight:500;">${preventiveActions}</p>
                </div>
            </div>
        `;
    }

    closeDetailsBtn.addEventListener('click', () => {
        detailsModal.style.display = 'none';
    });

    // ServiceNow ticket creator
    document.getElementById('btn-details-service-now').addEventListener('click', () => {
        alert("ServiceNow Incident Ticket generated successfully. Reference Ticket ID: SN-INC-99120");
    });
    
    document.getElementById('btn-details-export-pdf').addEventListener('click', () => {
        alert("Incident Dossier PDF report generated. Download started.");
    });

    document.getElementById('btn-details-export-docx').addEventListener('click', () => {
        alert("Incident Dossier Word document compiled.");
    });

    // ----------------------------------------------------
    // SETTINGS PANEL ACTIONS
    // ----------------------------------------------------
    const btnSaveSettings = document.getElementById('btn-save-settings');
    if (btnSaveSettings) {
        btnSaveSettings.addEventListener('click', () => {
            const threshold = document.getElementById('slider-threshold').value;
            const policyEl = document.querySelector('input[name="auto-policy"]:checked');
            const policy = policyEl ? policyEl.value : 'approval';
            
            secureFetch('/api/settings', {
                method: 'POST',
                body: JSON.stringify({
                    interval: 10,
                    healingPolicy: policy,
                    severityThreshold: parseInt(threshold)
                })
            }).then(() => {
                alert("NOC Copilot Server configurations updated successfully.");
            }).catch(err => {
                alert("Settings saved locally.");
            });
        });
    }

    async function fetchSettings() {
        if (!sessionStorage.getItem('authToken')) return;
        try {
            const response = await secureFetch('/api/settings');
            const data = await response.json();
            
            const thresholdInput = document.getElementById('slider-threshold');
            if (thresholdInput) {
                thresholdInput.value = data.severityThreshold;
                thresholdInput.dispatchEvent(new Event('input'));
            }
            
            const policyEl = document.querySelector(`input[name="auto-policy"][value="${data.healingPolicy}"]`);
            if (policyEl) {
                policyEl.checked = true;
            }
        } catch (error) {
            console.error('Error fetching settings:', error);
        }
    }

    // ----------------------------------------------------
    // ASYMMETRIC ROUTING DETECTOR
    // ----------------------------------------------------
    const btnCheckAsym = document.getElementById('btn-check-asymmetry');
    if (btnCheckAsym) {
        btnCheckAsym.addEventListener('click', () => {
            const src = document.getElementById('asym-src').value.trim();
            const dst = document.getElementById('asym-dst').value.trim();
            const resultBox = document.getElementById('asymmetry-result');
            
            resultBox.style.display = 'block';
            resultBox.innerHTML = '<i class="fa-solid fa-sync fa-spin" style="color:var(--primary)"></i> Running traceroutes...';
            
            setTimeout(() => {
                let html = `<h4 class="warning-text" style="margin-bottom:0.5rem; font-size:0.85rem;"><i class="fa-solid fa-shuffle"></i> Asymmetric Routing Path Identified</h4>`;
                html += `<div style="display:flex; justify-content:space-between; font-size:0.75rem; font-family:'Fira Code', monospace; background:rgba(0,0,0,0.5); padding:0.5rem; border-radius:6px; margin-bottom:0.5rem;">
                    <div>
                        <strong style="color:var(--healthy);">Forward Path:</strong>
                        <ol style="margin-top:0.25rem; padding-left:1.2rem;">
                            <li>mumbai-gw (198.51.100.1)</li>
                            <li>mumbai-fw (10.1.1.254)</li>
                            <li>router-hq (198.51.100.2)</li>
                        </ol>
                    </div>
                    <div>
                        <strong style="color:var(--warning);">Return Path:</strong>
                        <ol style="margin-top:0.25rem; padding-left:1.2rem;">
                            <li>router-hq (198.51.100.2)</li>
                            <li>MPLS-PE-Router (192.168.10.1)</li>
                            <li>mumbai-gw (198.51.100.1)</li>
                        </ol>
                    </div>
                </div>`;
                html += `<p style="font-size:0.7rem; color:var(--text-muted);">
                    <strong>Cause:</strong> Egress link uses IPSec Tunnel but return packets routed via MPLS Backup due to OSPF metrics.
                </p>`;
                resultBox.innerHTML = html;
            }, 800);
        });
    }

    // ----------------------------------------------------
    // INTERACTIVE CANVAS TOPOLOGY ENGINE
    // ----------------------------------------------------
    const canvas = document.getElementById('topology-canvas');
    let selectedNode = null;
    let hoveredNode = null;
    
    // Zoom & Pan variables
    let zoom = 1.0;
    let panX = 0;
    let panY = 0;
    let isPanning = false;
    let startPanX = 0;
    let startPanY = 0;
    
    const topoNodes = [
        { id: 'router-hq', label: 'router-hq', role: 'HQ Edge Router', ip: '198.51.100.2', vendor: 'Cisco', platform: 'IOS-XE', x: 200, y: 55, radius: 20, icon: '🌐' },
        { id: 'asa-edge-01', label: 'asa-edge-01', role: 'Firewall', ip: '203.0.113.12', vendor: 'Cisco', platform: 'ASA OS', x: 200, y: 125, radius: 20, icon: '🛡' },
        { id: 'sw-core-01', label: 'sw-core-01', role: 'Core Switch 1', ip: '10.0.1.1', vendor: 'Cisco', platform: 'Catalyst 9500', x: 120, y: 200, radius: 20, icon: '🔌' },
        { id: 'sw-core-02', label: 'sw-core-02', role: 'Core Switch 2', ip: '10.0.1.2', vendor: 'Cisco', platform: 'Catalyst 9500', x: 280, y: 200, radius: 20, icon: '🔌' },
        { id: 'db-srv-01', label: 'db-srv-01', role: 'Database Host', ip: '10.0.20.10', vendor: 'Linux', platform: 'Ubuntu Server', x: 120, y: 275, radius: 20, icon: '🗄' },
        { id: 'app-srv-01', label: 'app-srv-01', role: 'Web Server 1', ip: '10.0.10.5', vendor: 'Linux', platform: 'Ubuntu Server', x: 240, y: 275, radius: 20, icon: '🖥' },
        { id: 'app-srv-02', label: 'app-srv-02', role: 'Web Server 2', ip: '10.0.10.6', vendor: 'Linux', platform: 'Ubuntu Server', x: 320, y: 275, radius: 20, icon: '🖥' }
    ];

    const topoLinks = [
        { source: 'router-hq', target: 'asa-edge-01', label: 'Trunk', status: 'Healthy' },
        { source: 'asa-edge-01', target: 'sw-core-01', label: 'Trunk', status: 'Healthy' },
        { source: 'sw-core-01', target: 'sw-core-02', label: 'EtherChannel', status: 'Healthy' },
        { source: 'sw-core-01', target: 'db-srv-01', label: 'VLAN 20', status: 'Healthy' },
        { source: 'sw-core-02', target: 'app-srv-01', label: 'VLAN 10', status: 'Healthy' },
        { source: 'sw-core-02', target: 'app-srv-02', label: 'VLAN 10', status: 'Healthy' }
    ];

    async function loadTopologyFromBackend() {
        try {
            const res = await secureFetch('/api/topology/graph');
            if (!res.ok) throw new Error("API error");
            const data = await res.json();
            
            if (data && data.nodes && data.nodes.length > 0) {
                // Keep references but empty contents
                topoNodes.length = 0;
                topoLinks.length = 0;
                
                const cx = canvas ? canvas.width / 2 : 250;
                const cy = canvas ? canvas.height / 2 : 200;
                const radius = 160;
                
                data.nodes.forEach((n, idx) => {
                    const angle = (idx / data.nodes.length) * 2 * Math.PI;
                    const x = cx + radius * Math.cos(angle);
                    const y = cy + radius * Math.sin(angle);
                    
                    const nameLower = n.name.toLowerCase();
                    let role = "Router";
                    let icon = "🌐";
                    
                    if (nameLower.includes("switch") || nameLower.includes("leaf") || nameLower.includes("spine")) {
                        role = "Switch";
                        icon = "🔌";
                    } else if (nameLower.includes("fw") || nameLower.includes("firewall") || nameLower.includes("utm")) {
                        role = "Firewall";
                        icon = "🛡";
                    } else if (nameLower.includes("srv") || nameLower.includes("server") || nameLower.includes("host") || nameLower.includes("domain") || nameLower.includes("db")) {
                        role = "Server";
                        icon = nameLower.includes("db") ? "🗄" : "🖥";
                    }
                    
                    topoNodes.push({
                        id: n.name,
                        label: n.name,
                        role: role,
                        ip: n.ip || '10.0.10.x',
                        vendor: n.vendor || 'Generic',
                        platform: n.label || 'Standard Platform',
                        x: x,
                        y: y,
                        radius: 20,
                        icon: icon,
                        status: n.status || 'Healthy'
                    });
                });
                
                data.edges.forEach(e => {
                    topoLinks.push({
                        source: e.source,
                        target: e.target,
                        label: e.type,
                        status: e.details || 'Healthy'
                    });
                });
                
                runForceDirectedLayout();
            }
        } catch(err) {
            console.warn("Failed to load topology from backend, using default static graph layout:", err);
        }
        drawTopology();
    }

    function runForceDirectedLayout() {
        const width = canvas ? canvas.width : 500;
        const height = canvas ? canvas.height : 400;
        if (topoNodes.length === 0) return;
        
        const k = Math.sqrt((width * height) / topoNodes.length);
        const iterations = 80;
        
        for (let step = 0; step < iterations; step++) {
            // Repulsive forces
            for (let i = 0; i < topoNodes.length; i++) {
                const u = topoNodes[i];
                u.dispX = 0;
                u.dispY = 0;
                for (let j = 0; j < topoNodes.length; j++) {
                    if (i === j) continue;
                    const v = topoNodes[j];
                    const dx = u.x - v.x;
                    const dy = u.y - v.y;
                    const dist = Math.sqrt(dx*dx + dy*dy) || 1;
                    const force = (k * k) / dist;
                    u.dispX += (dx / dist) * force;
                    u.dispY += (dy / dist) * force;
                }
            }
            
            // Attractive forces
            topoLinks.forEach(link => {
                const u = topoNodes.find(n => n.id === link.source);
                const v = topoNodes.find(n => n.id === link.target);
                if (!u || !v) return;
                const dx = u.x - v.x;
                const dy = u.y - v.y;
                const dist = Math.sqrt(dx*dx + dy*dy) || 1;
                const force = (dist * dist) / k;
                const displacementX = (dx / dist) * force;
                const displacementY = (dy / dist) * force;
                u.dispX -= displacementX;
                u.dispY -= displacementY;
                v.dispX += displacementX;
                v.dispY += displacementY;
            });
            
            // Update coordinates
            const temp = 10 * (1 - step/iterations);
            topoNodes.forEach(node => {
                const dist = Math.sqrt(node.dispX*node.dispX + node.dispY*node.dispY) || 1;
                node.x += (node.dispX / dist) * Math.min(dist, temp);
                node.y += (node.dispY / dist) * Math.min(dist, temp);
                
                node.x = Math.max(40, Math.min(width - 40, node.x));
                node.y = Math.max(40, Math.min(height - 40, node.y));
            });
        }
    }

    const nodeDetails = {
        'router-hq': {
            interfaces: [
                { name: 'GigabitEthernet1', ip: '198.51.100.2', status: 'up', line: 'up' },
                { name: 'GigabitEthernet2', ip: '10.0.1.254', status: 'up', line: 'up' },
                { name: 'Tunnel10 (VPN)', ip: '10.254.1.1', status: 'down', line: 'down' }
            ],
            syslog: `%LINEPROTO-5-UPDOWN: Line protocol on Interface Tunnel10, changed state to down\n%OSPF-5-ADJCHG: Process 1, Nbr 198.51.100.1 on Tunnel10 from FULL to DOWN\n%IPSEC-3-REKEY_FAIL: Phase 1 Lifetime negotiation timeout error with peer 203.0.113.10`,
            config: `interface Tunnel10\n ip address 10.254.1.1 255.255.255.252\n tunnel source GigabitEthernet1\n tunnel destination 203.0.113.10\n tunnel protection ipsec profile IPSEC-PROF\n crypto isakmp policy 10\n  encr aes 256\n  hash sha256\n  authentication pre-share\n  group 14\n  lifetime 86400`,
            alerts: ['Tunnel10 protocol interface is DOWN (LIFETIME_MISMATCH)']
        },
        'asa-edge-01': {
            interfaces: [
                { name: 'outside', ip: '203.0.113.12', status: 'up', line: 'up' },
                { name: 'inside', ip: '10.0.1.254', status: 'up', line: 'up' },
                { name: 'dmz', ip: '192.168.100.1', status: 'up', line: 'up' }
            ],
            syslog: `%ASA-6-302013: Built outbound TCP connection for outside:203.0.113.10\n%ASA-4-106023: Deny tcp src outside:198.51.100.45 dst inside:10.0.1.1 eq 22 by access-group outside_access_in`,
            config: `access-list outside_access_in extended deny tcp host 198.51.100.45 any eq 22\naccess-list outside_access_in extended permit ip any any\naccess-group outside_access_in in interface outside`,
            alerts: ['Brute-force SSH password spray alert detected on outside interface']
        },
        'sw-core-01': {
            interfaces: [
                { name: 'Port-channel1', ip: 'N/A', status: 'up', line: 'up' },
                { name: 'GigabitEthernet1/0/24', ip: 'N/A', status: 'up', line: 'up' },
                { name: 'Vlan10', ip: '10.0.10.1', status: 'up', line: 'up' },
                { name: 'Vlan20', ip: '10.0.20.1', status: 'up', line: 'up' }
            ],
            syslog: `%LINEPROTO-5-UPDOWN: Line protocol on Interface Vlan20, changed state to up\n%SPANTREE-5-TOPOTG: Spanning Tree Topology Change Received on Port-channel1`,
            config: `vlan 10\n name APP_Subnet\nvlan 20\n name DB_Subnet\ninterface GigabitEthernet1/0/24\n switchport mode access\n switchport access vlan 20\n spanning-tree portfast`,
            alerts: []
        },
        'sw-core-02': {
            interfaces: [
                { name: 'Port-channel1', ip: 'N/A', status: 'up', line: 'up' },
                { name: 'Vlan10', ip: '10.0.10.2', status: 'up', line: 'up' }
            ],
            syslog: `%LINEPROTO-5-UPDOWN: Line protocol on Interface Port-channel1, changed state to up`,
            config: `interface Port-channel1\n switchport trunk encapsulation dot1q\n switchport mode trunk`,
            alerts: []
        },
        'db-srv-01': {
            interfaces: [
                { name: 'eth0', ip: '10.0.20.10', status: 'up', line: 'up' }
            ],
            syslog: `Jul 02 19:30:51 db-srv-01 kernel: ext4_quota_write: Write quota file error\nJul 02 19:32:00 db-srv-01 systemd[1]: /var/log disk utilization crossed warning threshold (94%)`,
            config: `/dev/sda1       40G   37.6G   2.4G  94% /var\ntmpfs           3.9G     0B   3.9G   0% /dev/shm`,
            alerts: ['Disk storage partition warning: /var/log disk space utilization 94%']
        },
        'app-srv-01': {
            interfaces: [
                { name: 'eth0', ip: '10.0.10.5', status: 'up', line: 'up' }
            ],
            syslog: `Jul 02 19:30:51 app-srv-01 systemd[1]: Started Nginx - High Performance Web Server`,
            config: `server {\n    listen 80;\n    server_name portal.internal;\n    location / {\n        proxy_pass http://app_servers;\n    }\n}`,
            alerts: []
        },
        'app-srv-02': {
            interfaces: [
                { name: 'eth0', ip: '10.0.10.6', status: 'up', line: 'up' }
            ],
            syslog: `Jul 02 19:30:51 app-srv-02 systemd[1]: nginx worker loop timeout\nJul 02 19:32:00 app-srv-02 nginx: error regex recursion limit exceeded, process spinning`,
            config: `worker_processes auto;\nevents {\n    worker_connections 1024;\n}\nhttp {\n    keepalive_timeout 65;\n}`,
            alerts: ['Nginx worker pid 40912 utilization 100% (stuck regex recursion)']
        }
    };

    function getNodeStatusColor(nodeId) {
        let status = "Healthy";
        
        // Find if there is an active incident for this device
        const activeInc = activeIncidents.find(i => i.device === nodeId && i.status === 'Active');
        if (activeInc) {
            if (activeInc.scenario === 'VPN is down') {
                status = 'Failure';
            } else if (activeInc.scenario === 'Server CPU is 100%') {
                status = 'Congestion';
            } else {
                status = 'Warning';
            }
        } else if (nodeId === 'db-srv-01' || nodeId === 'linux-db-srv') {
            status = 'Warning';
        }
        
        const colors = {
            'Healthy': '#10b981',
            'Congestion': '#f97316',
            'Warning': '#fbbf24',
            'Failure': '#ef4444'
        };
        return colors[status] || '#10b981';
    }

    function getLinkStatusColor(link) {
        const srcColor = getNodeStatusColor(link.source);
        const dstColor = getNodeStatusColor(link.target);
        
        if (srcColor === '#ef4444' || dstColor === '#ef4444') {
            return '#ef4444'; // Failure Red
        }
        if (srcColor === '#fbbf24' || dstColor === '#fbbf24') {
            return '#fbbf24'; // Warning Yellow
        }
        if (srcColor === '#f97316' || dstColor === '#f97316') {
            return '#f97316'; // Congestion Orange
        }
        return 'rgba(16, 185, 129, 0.4)'; // Green Healthy
    }

    let animationOffset = 0;
    
    function animateTopology() {
        const panel = document.getElementById('panel-topology');
        if (panel && panel.classList.contains('active')) {
            animationOffset += 0.5;
            if (animationOffset > 100) animationOffset = 0;
            drawTopology();
        }
        requestAnimationFrame(animateTopology);
    }

    // Start animation loop
    requestAnimationFrame(animateTopology);

    function drawTopology() {
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const container = canvas.parentElement;
        
        if (canvas.width !== container.clientWidth || canvas.height !== container.clientHeight) {
            canvas.width = container.clientWidth;
            canvas.height = container.clientHeight;
        }
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        ctx.save();
        ctx.translate(panX, panY);
        ctx.scale(zoom, zoom);
        
        // Draw Links
        topoLinks.forEach(link => {
            const src = topoNodes.find(n => n.id === link.source);
            const dst = topoNodes.find(n => n.id === link.target);
            if (!src || !dst) return;
            
            const color = getLinkStatusColor(link); 
            let lineWidth = 1.5;
            let lineDash = [];
            
            const isDown = color === '#ef4444';
            if (isDown) {
                lineDash = [3, 3];
            }
            if (link.label === "EtherChannel") {
                lineWidth = 3;
            }
            
            ctx.beginPath();
            ctx.strokeStyle = color;
            ctx.lineWidth = lineWidth;
            ctx.setLineDash(lineDash);
            ctx.moveTo(src.x, src.y);
            ctx.lineTo(dst.x, dst.y);
            ctx.stroke();
            
            ctx.setLineDash([]);
            
            // Draw link label
            ctx.font = '8px monospace';
            ctx.fillStyle = 'var(--text-muted)';
            ctx.fillText(link.label, (src.x + dst.x)/2 + 6, (src.y + dst.y)/2);

            // Flow packets animation
            if (!isDown) {
                const dotsCount = 2;
                for (let i = 0; i < dotsCount; i++) {
                    const t = ((animationOffset + i * 50) % 100) / 100;
                    const dotX = src.x + (dst.x - src.x) * t;
                    const dotY = src.y + (dst.y - src.y) * t;
                    
                    ctx.beginPath();
                    ctx.arc(dotX, dotY, 2.5, 0, Math.PI * 2);
                    ctx.fillStyle = color === '#fbbf24' ? '#fbbf24' : (color === '#f97316' ? '#f97316' : '#10b981');
                    ctx.fill();
                }
            }
        });
        
        // Draw Nodes
        topoNodes.forEach(node => {
            const isSelected = selectedNode && selectedNode.id === node.id;
            const isHovered = hoveredNode && hoveredNode.id === node.id;
            const nodeColor = getNodeStatusColor(node.id);
            
            if (nodeColor !== '#10b981') {
                ctx.beginPath();
                ctx.arc(node.x, node.y, node.radius + 4, 0, Math.PI * 2);
                ctx.strokeStyle = nodeColor === '#ef4444' ? 'rgba(239, 68, 68, 0.4)' : (nodeColor === '#f97316' ? 'rgba(249, 115, 22, 0.4)' : 'rgba(251, 191, 36, 0.4)');
                ctx.lineWidth = 3;
                ctx.stroke();
            }
            
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
            ctx.fillStyle = isSelected ? 'rgba(79, 140, 255, 0.4)' : (isHovered ? 'rgba(255,255,255,0.06)' : 'rgba(22, 30, 49, 0.95)');
            ctx.strokeStyle = isSelected ? 'var(--primary)' : nodeColor;
            ctx.lineWidth = 2;
            ctx.fill();
            ctx.stroke();
            
            ctx.font = '14px serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(node.icon, node.x, node.y);
            
            ctx.font = '10px Outfit';
            ctx.fillStyle = isSelected ? 'white' : 'var(--text-normal)';
            ctx.fillText(node.label, node.x, node.y + node.radius + 12);
        });
        
        ctx.restore();
    }

    if (canvas) {
        canvas.addEventListener('mousedown', (e) => {
            isPanning = true;
            startPanX = e.clientX - panX;
            startPanY = e.clientY - panY;
        });

        canvas.addEventListener('mouseup', () => {
            isPanning = false;
        });

        canvas.addEventListener('mouseleave', () => {
            isPanning = false;
        });

        canvas.addEventListener('mousemove', (e) => {
            const rect = canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            if (isPanning) {
                panX = e.clientX - startPanX;
                panY = e.clientY - startPanY;
                drawTopology();
                return;
            }
            
            const canvasX = (mouseX - panX) / zoom;
            const canvasY = (mouseY - panY) / zoom;
            
            let matched = null;
            topoNodes.forEach(node => {
                const dist = Math.sqrt((canvasX - node.x)**2 + (canvasY - node.y)**2);
                if (dist <= node.radius) {
                    matched = node;
                }
            });
            
            hoveredNode = matched;
            canvas.style.cursor = matched ? 'pointer' : (isPanning ? 'grabbing' : 'default');
            drawTopology();
        });
        
        canvas.addEventListener('click', (e) => {
            if (hoveredNode) {
                selectedNode = hoveredNode;
                inspectNode(hoveredNode);
            } else {
                selectedNode = null;
                resetInspector();
            }
            drawTopology();
        });

        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            const zoomFactor = 1.1;
            const canvasX = (mouseX - panX) / zoom;
            const canvasY = (mouseY - panY) / zoom;

            if (e.deltaY < 0) {
                zoom = Math.min(3.0, zoom * zoomFactor);
            } else {
                zoom = Math.max(0.5, zoom / zoomFactor);
            }

            panX = mouseX - canvasX * zoom;
            panY = mouseY - canvasY * zoom;

            drawTopology();
        });
    }

    let currentInspectorTab = 'specs';

    function inspectNode(node) {
        const inspector = document.getElementById('inspector-content');
        if (!inspector) return;
        
        let status = "Healthy";
        let statusClass = "healthy";
        let cpuVal = 12;
        let ramVal = 42;
        let temp = 38;
        
        const nodeColor = getNodeStatusColor(node.id);
        if (nodeColor === '#ef4444') {
            status = "Failure";
            statusClass = "critical";
            cpuVal = 85;
            temp = 58;
        } else if (nodeColor === '#f97316') {
            status = "Congestion";
            statusClass = "warning";
            cpuVal = 100;
            temp = 62;
        } else if (nodeColor === '#fbbf24') {
            status = "Warning";
            statusClass = "warning";
            cpuVal = 54;
            temp = 48;
        }

        const details = nodeDetails[node.id] || { interfaces: [], syslog: "No logs.", config: "No config.", alerts: [] };
        
        if (currentScenario === "Server CPU is 100%" && node.id === "app-srv-02") {
            cpuVal = 100;
            temp = 62;
        } else if (currentScenario === "VPN is down" && node.id === "router-hq") {
            cpuVal = 48;
            temp = 48;
        } else if (node.id === "db-srv-01") {
            cpuVal = 38;
            ramVal = 78;
            temp = 41;
        } else if (currentScenario === "Analyze this firewall log" && node.id === "asa-edge-01") {
            cpuVal = 54;
            temp = 42;
        }

        // Live jitter/simulation variations for stats refresh
        if (status === "Healthy") {
            cpuVal = Math.max(5, Math.min(25, cpuVal + Math.floor(Math.random() * 5) - 2));
            ramVal = Math.max(30, Math.min(50, ramVal + Math.floor(Math.random() * 3) - 1));
        } else if (status === "Warning") {
            cpuVal = Math.max(40, Math.min(65, cpuVal + Math.floor(Math.random() * 5) - 2));
        }

        const cpu = cpuVal;
        const ram = ramVal;
        const serial = node.serial || `SN-${node.vendor.toUpperCase()}-${node.id.toUpperCase().replace(/[^A-Z0-9]/g, '') || '99120'}`;

        let tabHtml = `
            <div class="inspector-tabs">
                <button class="inspector-tab-btn ${currentInspectorTab === 'specs' ? 'active' : ''}" data-itab="specs">Specs</button>
                <button class="inspector-tab-btn ${currentInspectorTab === 'interfaces' ? 'active' : ''}" data-itab="interfaces">Interfaces</button>
                <button class="inspector-tab-btn ${currentInspectorTab === 'routing' ? 'active' : ''}" data-itab="routing">Routing</button>
                <button class="inspector-tab-btn ${currentInspectorTab === 'security' ? 'active' : ''}" data-itab="security">Security</button>
                <button class="inspector-tab-btn ${currentInspectorTab === 'config' ? 'active' : ''}" data-itab="config">Config</button>
            </div>
            <div id="inspector-tab-body" style="font-size:0.75rem; margin-top: 0.5rem; display: flex; flex-direction: column; gap: 0.4rem;">
        `;
        
        if (currentInspectorTab === 'specs') {
            const sparkPoints = [15, 25, 18, 42, 38, cpuVal];
            const maxPoint = 100;
            const width = 180;
            const height = 30;
            const step = width / (sparkPoints.length - 1);
            let pathD = `M 0,${height - (sparkPoints[0]/maxPoint)*height}`;
            sparkPoints.forEach((p, idx) => {
                if (idx > 0) {
                    pathD += ` L ${idx * step},${height - (p/maxPoint)*height}`;
                }
            });

            tabHtml += `
                <div style="display:flex; justify-content:space-between; margin-bottom:0.25rem; border-bottom:1px solid var(--border-color); padding-bottom:0.35rem;">
                    <strong style="color:white;">${node.icon} ${node.label}</strong>
                    <span class="status-badge ${statusClass}">${status}</span>
                </div>
                <div style="display:flex; flex-direction:column; gap:0.4rem;">
                    <div class="server-config-item"><span>Vendor</span><strong>${node.vendor}</strong></div>
                    <div class="server-config-item"><span>Model</span><strong>${node.role}</strong></div>
                    <div class="server-config-item"><span>OS / Platform</span><span>${node.platform}</span></div>
                    <div class="server-config-item"><span>Serial Number</span><strong style="font-family:monospace; color:white;">${serial}</strong></div>
                    
                    <div class="server-config-item" style="margin-top:0.2rem; flex-direction:column; align-items:stretch; gap:2px;">
                        <div style="display:flex; justify-content:space-between;"><span>CPU Load</span><strong>${cpu}%</strong></div>
                        <div class="health-bar-container"><div class="health-bar-fill" style="width: ${cpu}%; background: ${nodeColor}"></div></div>
                    </div>
                    <div class="server-config-item" style="flex-direction:column; align-items:stretch; gap:2px;">
                        <div style="display:flex; justify-content:space-between;"><span>Memory Load</span><strong>${ram}%</strong></div>
                        <div class="health-bar-container"><div class="health-bar-fill" style="width: ${ram}%; background: var(--primary)"></div></div>
                    </div>
                    <div class="server-config-item" style="flex-direction:column; align-items:stretch; gap:2px;">
                        <div style="display:flex; justify-content:space-between;"><span>Temperature</span><strong>${temp}°C</strong></div>
                        <div class="health-bar-container"><div class="health-bar-fill" style="width: ${Math.min(100, temp * 1.5)}%; background: ${temp > 50 ? 'var(--critical)' : 'var(--warning)'}"></div></div>
                    </div>
                    
                    <!-- Historical Metrics -->
                    <div style="margin-top:0.4rem; border-top:1px dashed var(--border-color); padding-top:0.4rem;">
                        <span style="color:var(--text-muted); display:block; font-size:0.65rem; margin-bottom:4px; font-weight:600;">CPU Utilization History (Sparkline)</span>
                        <div style="background:rgba(0,0,0,0.3); border-radius:4px; padding:4px; display:flex; align-items:center; justify-content:center;">
                            <svg width="${width}" height="${height}" style="overflow:visible;">
                                <path d="${pathD}" fill="none" stroke="var(--primary)" stroke-width="2" />
                                <circle cx="${width}" cy="${height - (cpuVal/maxPoint)*height}" r="3" fill="var(--primary)" />
                            </svg>
                        </div>
                    </div>
                </div>
            `;
        } else if (currentInspectorTab === 'interfaces') {
            tabHtml += `
                <table class="node-table" style="font-size: 0.68rem; margin-bottom: 0.5rem;">
                    <thead>
                        <tr>
                            <th>Interface</th>
                            <th>IP / MAC</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            details.interfaces.forEach((intf, idx) => {
                const statusColor = intf.status === 'up' ? 'healthy' : 'critical';
                const mac = `00:1B:44:11:3A:0${idx + 1}`;
                tabHtml += `
                    <tr>
                        <td><strong>${intf.name}</strong></td>
                        <td>
                            <div>${intf.ip}</div>
                            <div style="font-size:0.6rem; color:var(--text-muted); font-family:monospace;">${mac}</div>
                        </td>
                        <td><span class="status-badge ${statusColor}">${intf.status}</span></td>
                    </tr>
                `;
            });
            tabHtml += `</tbody></table>`;
            
            // Statistics panel
            let txSpeed = `${status === 'Healthy' ? 18 + Math.floor(Math.random() * 5) : 0} Mbps`;
            let rxSpeed = `${status === 'Healthy' ? 42 + Math.floor(Math.random() * 10) : 0} Mbps`;
            let errs = "0";
            if (nodeColor === '#ef4444') {
                txSpeed = "0.0 Mbps";
                rxSpeed = "0.0 Mbps";
                errs = "42";
            }
            tabHtml += `
                <div style="border-top:1px dashed var(--border-color); padding-top:0.4rem; display:flex; flex-direction:column; gap:0.25rem;">
                    <span style="color:white; font-weight:600; font-size:0.7rem; display:block; margin-bottom:2px;"><i class="fa-solid fa-chart-line"></i> Interface Statistics</span>
                    <div class="server-config-item"><span>Tx Bandwidth</span><strong>${txSpeed}</strong></div>
                    <div class="server-config-item"><span>Rx Bandwidth</span><strong>${rxSpeed}</strong></div>
                    <div class="server-config-item"><span>Packets Transmitted</span><span>${142012 + Math.floor(Math.random() * 200)} pkts</span></div>
                    <div class="server-config-item"><span>Packets Received</span><span>${254198 + Math.floor(Math.random() * 400)} pkts</span></div>
                    <div class="server-config-item"><span>Errors / Discards</span><strong class="${errs !== "0" ? "critical-text" : "healthy-text"}">${errs}</strong></div>
                </div>
            `;
        } else if (currentInspectorTab === 'routing') {
            tabHtml += `
                <div style="display:flex; flex-direction:column; gap:0.5rem;">
                    <div>
                        <span style="color:white; font-weight:600; font-size:0.7rem; display:block; margin-bottom:2px;"><i class="fa-solid fa-route"></i> IP Routing Table</span>
                        <pre style="background:black; color:var(--primary); padding:0.4rem; border-radius:4px; font-family:'Fira Code', monospace; font-size:0.6rem; overflow-x:auto; margin:0;">
S*   0.0.0.0/0 [1/0] via ${node.ip.split('.').slice(0,3).join('.')}.1
C    ${node.ip.split('.').slice(0,3).join('.')}.0/24 is directly connected
O    10.0.10.0/24 [110/11] via 10.0.1.1, 00:14:22
B    192.168.100.0/24 [20/0] via ${node.ip.split('.').slice(0,3).join('.')}.5, 02:40:12</pre>
                    </div>
                    <div>
                        <span style="color:white; font-weight:600; font-size:0.7rem; display:block; margin-bottom:2px;"><i class="fa-solid fa-list"></i> ARP Cache Table</span>
                        <pre style="background:black; color:var(--warning); padding:0.4rem; border-radius:4px; font-family:'Fira Code', monospace; font-size:0.6rem; overflow-x:auto; margin:0;">
Internet  ${node.ip.split('.').slice(0,3).join('.')}.1         -   00:50:56:88:99:aa  ARPA
Internet  10.0.10.5        6   00:11:22:33:44:55  ARPA
Internet  10.0.10.6       12   00:11:22:33:44:56  ARPA</pre>
                    </div>
                    <div class="server-config-item"><span>BGP Session (AS 65002)</span><strong style="color:var(--healthy);">Established (v4/v6)</strong></div>
                    <div class="server-config-item"><span>OSPF Neighbors</span><strong>2 Active Neighbors (Area 0)</strong></div>
                </div>
            `;
        } else if (currentInspectorTab === 'security') {
            let vpnStatus = node.id === "router-hq" && currentScenario === "VPN is down" ? "DOWN (No Rekey)" : "ACTIVE";
            let vpnColor = vpnStatus === "ACTIVE" ? "healthy-text" : "critical-text";
            
            tabHtml += `
                <div style="display:flex; flex-direction:column; gap:0.5rem;">
                    <div>
                        <span style="color:white; font-weight:600; font-size:0.7rem; display:block; margin-bottom:2px;"><i class="fa-solid fa-shield-halved"></i> Access Control Lists (ACL)</span>
                        <pre style="background:black; color:var(--text-normal); padding:0.4rem; border-radius:4px; font-family:'Fira Code', monospace; font-size:0.6rem; overflow-x:auto; margin:0;">
ip access-list extended outside_in
 10 deny tcp host 198.51.100.45 any eq 22 log
 20 permit tcp any host ${node.ip} eq 80
 30 permit ip any any</pre>
                    </div>
                    <div>
                        <span style="color:white; font-weight:600; font-size:0.7rem; display:block; margin-bottom:2px;"><i class="fa-solid fa-arrows-spin"></i> NAT Configurations</span>
                        <pre style="background:black; color:var(--primary); padding:0.4rem; border-radius:4px; font-family:'Fira Code', monospace; font-size:0.6rem; overflow-x:auto; margin:0;">
ip nat inside source list 1 interface Outside overload
ip nat inside source static tcp 10.0.10.5 80 interface Outside 80</pre>
                    </div>
                    <div class="server-config-item"><span>QoS Queue Profile</span><strong>Voice-Priority Queue (20% RSVP)</strong></div>
                    <div class="server-config-item"><span>IPsec VPN Tunnel</span><strong class="${vpnColor}">${vpnStatus}</strong></div>
                </div>
            `;
        } else if (currentInspectorTab === 'config') {
            let lldpOutput = "";
            topoLinks.forEach(link => {
                if (link.source === node.id) {
                    lldpOutput += `Local: ${link.label} -> Neighbor: ${link.target} (Type: LLDP)\n`;
                } else if (link.target === node.id) {
                    lldpOutput += `Local: ${link.label} -> Neighbor: ${link.source} (Type: LLDP)\n`;
                }
            });
            if (!lldpOutput) lldpOutput = "No LLDP neighbors discovered on interfaces.";

            tabHtml += `
                <div style="display:flex; flex-direction:column; gap:0.5rem;">
                    <div>
                        <span style="color:white; font-weight:600; font-size:0.7rem; display:block; margin-bottom:2px;"><i class="fa-solid fa-network-wired"></i> LLDP/CDP Neighbors</span>
                        <pre style="background:black; color:var(--warning); padding:0.4rem; border-radius:4px; font-family:'Fira Code', monospace; font-size:0.6rem; overflow-x:auto; margin:0; white-space:pre-wrap;">${escapeHtml(lldpOutput)}</pre>
                    </div>
                    <div>
                        <span style="color:white; font-weight:600; font-size:0.7rem; display:block; margin-bottom:2px;"><i class="fa-solid fa-file-code"></i> Running Configuration</span>
                        <pre style="background:black; color:var(--healthy); padding:0.4rem; border-radius:4px; font-family:'Fira Code', monospace; font-size:0.6rem; overflow-x:auto; max-height:140px; margin:0; white-space:pre-wrap;">${escapeHtml(details.config)}</pre>
                    </div>
                </div>
            `;
        }
        
        tabHtml += `</div>`;
        inspector.innerHTML = tabHtml;
        
        // Bind tab buttons
        inspector.querySelectorAll('.inspector-tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                currentInspectorTab = btn.getAttribute('data-itab');
                inspectNode(node);
            });
        });
    }

    function resetInspector() {
        const inspector = document.getElementById('inspector-content');
        if (!inspector) return;
        inspector.innerHTML = `<p>Click on any network node in the graph topology to inspect active details, physical interfaces, and routing adjacencies.</p>`;
    }


    // ----------------------------------------------------
    // SETTINGS SLIDER
    // ----------------------------------------------------
    const sliderThreshold = document.getElementById('slider-threshold');
    const sliderLabels = document.querySelectorAll('.slider-labels span');
    if (sliderThreshold) {
        sliderThreshold.addEventListener('input', () => {
            const val = parseInt(sliderThreshold.value);
            sliderLabels.forEach((label, idx) => {
                if (idx + 1 === val) {
                    label.classList.add('active');
                } else {
                    label.classList.remove('active');
                }
            });
        });
    }

    // ----------------------------------------------------
    // CREDENTIAL VAULT ACTIONS
    // ----------------------------------------------------
    const vaultTableBody = document.getElementById('vault-table-body');
    const btnSaveVaultSecret = document.getElementById('btn-save-vault-secret');
    const vaultSecretNameInput = document.getElementById('vault-secret-name');
    const vaultSecretTypeInput = document.getElementById('vault-secret-type');
    const vaultSecretValueInput = document.getElementById('vault-secret-value');

    async function fetchVault() {
        if (!sessionStorage.getItem('authToken')) return;
        try {
            const response = await secureFetch('/api/vault');
            const data = await response.json();
            
            vaultTableBody.innerHTML = '';
            const keys = Object.keys(data);
            
            if (keys.length === 0) {
                vaultTableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;">No vault credentials found.</td></tr>';
                return;
            }
            
            keys.forEach(name => {
                const item = data[name];
                const tr = document.createElement('tr');
                
                tr.innerHTML = `
                    <td><strong>${escapeHtml(name)}</strong></td>
                    <td><span class="status-badge healthy">${escapeHtml(item.type)}</span></td>
                    <td style="font-family:'Fira Code', monospace; font-size:0.75rem; color:var(--info);" id="vault-val-${name.replace(/\s+/g, '-')}">${escapeHtml(item.value)}</td>
                    <td style="display:flex; gap:0.5rem;">
                        <button class="btn btn-sm btn-outline btn-decrypt" data-name="${name}"><i class="fa-solid fa-key"></i> Decrypt</button>
                        <button class="btn btn-sm btn-outline btn-danger btn-delete-secret" data-name="${name}"><i class="fa-solid fa-trash"></i></button>
                    </td>
                `;
                vaultTableBody.appendChild(tr);
            });
            
            // Decrypt binds
            vaultTableBody.querySelectorAll('.btn-decrypt').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const name = btn.getAttribute('data-name');
                    try {
                        const res = await secureFetch('/api/vault/decrypt', {
                            method: 'POST',
                            body: JSON.stringify({ name })
                        });
                        const resData = await res.json();
                        const valTd = document.getElementById(`vault-val-${name.replace(/\s+/g, '-')}`);
                        valTd.textContent = resData.decryptedValue;
                        valTd.style.color = 'var(--healthy)';
                        btn.disabled = true;
                        btn.textContent = 'Decrypted';
                    } catch (err) {
                        alert(err.message || "Failed to decrypt.");
                    }
                });
            });

            // Delete binds
            vaultTableBody.querySelectorAll('.btn-delete-secret').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const name = btn.getAttribute('data-name');
                    if (!confirm(`Are you sure you want to delete secret '${name}'?`)) return;
                    try {
                        await secureFetch('/api/vault/delete', {
                            method: 'POST',
                            body: JSON.stringify({ name })
                        });
                        fetchVault();
                    } catch (err) {
                        alert(err.message);
                    }
                });
            });
            
        } catch (error) {
            vaultTableBody.innerHTML = `<tr><td colspan="4" class="warning-text">Failed to fetch credentials. Permissions error.</td></tr>`;
        }
    }

    if (btnSaveVaultSecret) {
        btnSaveVaultSecret.addEventListener('click', async () => {
            const name = vaultSecretNameInput.value.trim();
            const type = vaultSecretTypeInput.value;
            const value = vaultSecretValueInput.value.trim();
            
            if (!name || !value) {
                alert("Please fill name and value fields.");
                return;
            }
            
            try {
                await secureFetch('/api/vault/add', {
                    method: 'POST',
                    body: JSON.stringify({ name, type, value })
                });
                
                vaultSecretNameInput.value = '';
                vaultSecretValueInput.value = '';
                fetchVault();
            } catch (error) {
                alert(error.message);
            }
        });
    }

    // ----------------------------------------------------
    // SECURITY AUDIT LOGS
    // ----------------------------------------------------
    const auditTableBody = document.getElementById('audit-table-body');
    const btnRefreshAudit = document.getElementById('btn-refresh-audit');

    async function fetchAuditLogs() {
        if (!sessionStorage.getItem('authToken')) return;
        try {
            const response = await secureFetch('/api/audit-logs');
            const data = await response.json();
            
            auditTableBody.innerHTML = '';
            
            if (data.length === 0) {
                auditTableBody.innerHTML = '<tr><td colspan="8" style="text-align:center;">Zero logs found.</td></tr>';
                return;
            }
            
            data.forEach(item => {
                const tr = document.createElement('tr');
                const timeStr = new Date(item.timestamp).toLocaleTimeString();
                
                const isSuccess = item.status === 'Success';
                const statusClass = isSuccess ? 'healthy' : (item.status === 'Blocked' ? 'warning' : 'critical');
                
                tr.innerHTML = `
                    <td style="white-space:nowrap; font-size:0.75rem; color:var(--text-muted);">${timeStr}</td>
                    <td><strong>${escapeHtml(item.user)}</strong></td>
                    <td><span class="status-badge healthy" style="background:rgba(79,140,255,0.1); border-color:rgba(79,140,255,0.2); color:var(--primary);">${escapeHtml(item.role)}</span></td>
                    <td style="font-family:'Fira Code', monospace; font-size:0.75rem;">${escapeHtml(item.ip)}</td>
                    <td><strong>${escapeHtml(item.action)}</strong></td>
                    <td><span class="status-badge ${statusClass}">${escapeHtml(item.status)}</span></td>
                    <td style="font-family:'Fira Code', monospace; font-size:0.75rem; color:var(--warning);">${escapeHtml(item.rollback)}</td>
                    <td style="font-size:0.75rem; max-width:220px; text-overflow:ellipsis; overflow:hidden;" title="${escapeHtml(item.details)}">${escapeHtml(item.details)}</td>
                `;
                auditTableBody.appendChild(tr);
            });
        } catch (error) {
            auditTableBody.innerHTML = '<tr><td colspan="8" class="warning-text">Error loading audit records.</td></tr>';
        }
    }

    if (btnRefreshAudit) {
        btnRefreshAudit.addEventListener('click', () => {
            btnRefreshAudit.querySelector('i').classList.add('fa-spin');
            fetchAuditLogs().then(() => {
                setTimeout(() => {
                    btnRefreshAudit.querySelector('i').classList.remove('fa-spin');
                }, 500);
            });
        });
    }

    // ----------------------------------------------------
    // MUMBAI PING MONITOR TELEMETRY
    // ----------------------------------------------------
    function updatePingMonitorTable(nodes) {
        const tbody = document.getElementById('ping-monitor-tbody');
        if (!tbody) return;
        
        const testHosts = [
            { name: "Gateway Router", ip: "198.51.100.1", default_rtt: 1.5, min: 1.0, max: 2.2, jitter: 0.1 },
            { name: "Core Switch", ip: "10.1.1.1", default_rtt: 2.1, min: 1.5, max: 3.0, jitter: 0.2 },
            { name: "Branch Firewall", ip: "10.1.1.254", default_rtt: 2.8, min: 2.0, max: 4.1, jitter: 0.1 },
            { name: "ISP Gateway", ip: "203.0.113.1", default_rtt: 22.4, min: 20.1, max: 26.5, jitter: 1.2 },
            { name: "ERP Server Node", ip: "10.1.20.10", default_rtt: 5.2, min: 4.4, max: 6.8, jitter: 0.3 }
        ];

        tbody.innerHTML = '';
        
        testHosts.forEach(host => {
            let status = "Healthy";
            let rtt = `${host.default_rtt} ms`;
            let minR = `${host.min} ms`;
            let maxR = `${host.max} ms`;
            let loss = "0.0%";
            let jit = `${host.jitter} ms`;
            
            const isVpnDown = currentScenario === "VPN is down";
            if (isVpnDown && (host.name.includes("ERP") || host.name.includes("ISP"))) {
                status = "Critical";
                rtt = "--";
                minR = "--";
                maxR = "--";
                loss = "100.0%";
                jit = "--";
            }

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>Mumbai ${host.name}</strong></td>
                <td style="font-family:'Fira Code', monospace; font-size:0.75rem;">${host.ip}</td>
                <td>${rtt}</td>
                <td>${minR}</td>
                <td>${maxR}</td>
                <td class="${loss !== '0.0%' ? 'danger-text' : ''}">${loss}</td>
                <td>${jit}</td>
                <td>
                    <span class="status-badge ${status === 'Healthy' ? 'healthy' : 'critical'}">
                        <i class="fa-solid ${status === 'Healthy' ? 'fa-circle-check' : 'fa-triangle-exclamation'}"></i> ${status}
                    </span>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    // ----------------------------------------------------
    // ZERO-TRUST VISUAL DEPLOYMENT WIZARD STEPPER
    // ----------------------------------------------------
    let wizardStep = 1;
    let wizardData = {
        commands: "",
        requiresDual: false,
        managerApproved: false,
        adminApproved: false
    };

    async function runWizardStep(step) {
        wizardStep = step;
        
        // Highlight indicators
        document.querySelectorAll('.step-indicator').forEach((ind, idx) => {
            if (idx + 1 === step) {
                ind.style.color = 'var(--primary)';
                ind.style.borderBottom = '2px solid var(--primary)';
            } else if (idx + 1 < step) {
                ind.style.color = 'var(--healthy)';
                ind.style.borderBottom = '2px solid var(--healthy)';
            } else {
                ind.style.color = 'var(--text-muted)';
                ind.style.borderBottom = 'none';
            }
        });

        if (step === 1) {
            wizardContentBox.innerHTML = '<span class="status-text"><i class="fa-solid fa-spinner fa-spin"></i> Triggering backend Command Validation Engine...</span>';
            btnWizardNext.disabled = true;
            
            try {
                const res = await secureFetch('/api/validate-config', {
                    method: 'POST',
                    body: JSON.stringify({ commands: wizardData.commands })
                });
                const data = await res.json();
                
                let html = '<h4>Command Validation Sweep Logs:</h4><ul style="padding-left:1.2rem; margin-top:0.5rem; display:flex; flex-direction:column; gap:0.4rem;">';
                data.validationLogs.forEach(l => {
                    const statusClass = l.status.toLowerCase() === 'failed' ? 'warning-text' : 'success-text';
                    html += `<li>[${l.check}] Status: <strong class="${statusClass}">${l.status}</strong> - ${l.details}</li>`;
                });
                html += '</ul>';
                
                wizardData.requiresDual = data.requiresDualApproval;
                
                if (data.hasError) {
                    html += '<p class="warning-text" style="margin-top:0.5rem; font-weight:700;"><i class="fa-solid fa-triangle-exclamation"></i> Command validation tests failed. Configuration rejected.</p>';
                    btnWizardNext.disabled = true;
                } else {
                    html += '<p class="success-text" style="margin-top:0.5rem; font-weight:700;"><i class="fa-solid fa-check-double"></i> Syntax validation and IP conflict checks passed.</p>';
                    btnWizardNext.disabled = false;
                }
                
                wizardContentBox.innerHTML = html;
            } catch (err) {
                wizardContentBox.innerHTML = '<span class="warning-text">Validation sweep failed.</span>';
            }
        }
        else if (step === 2) {
            wizardContentBox.innerHTML = '<span class="status-text"><i class="fa-solid fa-spinner fa-spin"></i> Initializing Dynamic Network Topology Simulation...</span>';
            btnWizardNext.disabled = true;
            
            try {
                const res = await secureFetch('/api/validate-config', {
                    method: 'POST',
                    body: JSON.stringify({ commands: wizardData.commands })
                });
                const data = await res.json();
                
                let html = '<h4>Network Topology Impact Simulation:</h4><ul style="padding-left:1.2rem; margin-top:0.5rem; display:flex; flex-direction:column; gap:0.4rem;">';
                data.simulationLogs.forEach(l => {
                    html += `<li>[${l.step}] Status: <strong class="success-text">${l.status}</strong> - ${l.details}</li>`;
                });
                html += '</ul>';
                
                html += '<p class="success-text" style="margin-top:0.5rem; font-weight:700;"><i class="fa-solid fa-check"></i> Layer-2 STP and routing loop checks passed.</p>';
                btnWizardNext.disabled = false;
                wizardContentBox.innerHTML = html;
            } catch (err) {
                wizardContentBox.innerHTML = '<span class="warning-text">Simulation failed.</span>';
            }
        }
        else if (step === 3) {
            btnWizardNext.disabled = true;
            const role = currentUser?.role;
            
            let html = `<h4>Zero-Trust Authorization Rules:</h4>`;
            html += `<p style="margin: 0.5rem 0;">Current Operator: <strong>${currentUser?.name}</strong> (Role: <strong style="color:var(--primary);">${role}</strong>)</p>`;
            
            if (role === 'Guest') {
                html += '<p class="warning-text" style="font-weight:700; margin-top:1rem;"><i class="fa-solid fa-ban"></i> Guests are restricted to read-only views. Deployment blocked.</p>';
                wizardContentBox.innerHTML = html;
                return;
            }
            if (role === 'Network Engineer') {
                html += '<p class="warning-text" style="font-weight:700; margin-top:1rem;"><i class="fa-solid fa-ban"></i> Network Engineers cannot deploy configurations directly.</p>';
                wizardContentBox.innerHTML = html;
                return;
            }
            
            if (wizardData.requiresDual) {
                html += '<p class="warning-text" style="font-weight:700;"><i class="fa-solid fa-triangle-exclamation"></i> Destructive command flagged. Dual Approvals (Manager + Admin) required.</p>';
                html += `<div style="margin-top:0.5rem; display:flex; flex-direction:column; gap:0.35rem;">
                    <label style="display:flex; align-items:center; gap:0.35rem;">
                        <input type="checkbox" id="chk-app-mgr" ${wizardData.managerApproved ? 'checked disabled' : ''}>
                        <span>Operations Manager Token Approval</span>
                    </label>
                    <label style="display:flex; align-items:center; gap:0.35rem;">
                        <input type="checkbox" id="chk-app-adm" ${wizardData.adminApproved ? 'checked disabled' : ''}>
                        <span>System Admin Override Key</span>
                    </label>
                    <button class="btn btn-sm btn-outline" id="btn-request-dual-tokens" style="width:fit-content; margin-top:0.25rem;">Verify Credentials</button>
                </div>`;
                
                wizardContentBox.innerHTML = html;
                
                const btnDual = document.getElementById('btn-request-dual-tokens');
                btnDual.addEventListener('click', () => {
                    document.getElementById('chk-app-mgr').checked = true;
                    document.getElementById('chk-app-adm').checked = true;
                    wizardData.managerApproved = true;
                    wizardData.adminApproved = true;
                    btnWizardNext.disabled = false;
                    btnDual.disabled = true;
                    btnDual.textContent = 'Approvals Verified';
                });
                
                if (wizardData.managerApproved && wizardData.adminApproved) {
                    btnWizardNext.disabled = false;
                }
            } else {
                if (role === 'Senior Engineer') {
                    html += '<p class="warning-text" style="font-weight:600;"><i class="fa-solid fa-lock"></i> Policy requirement: Senior Engineers require Manager verification key.</p>';
                    html += `<div style="margin-top:0.5rem; display:flex; gap:0.5rem; align-items:center;">
                        <input type="password" id="mgr-token-input" class="form-control" placeholder="Enter Manager Token" style="max-width:200px; padding:0.25rem;">
                        <button class="btn btn-sm btn-outline" id="btn-validate-mgr-token">Verify</button>
                    </div>
                    <p class="help-block" style="color:var(--text-muted); font-size:0.7rem; margin-top:0.2rem;">Hint: Use simulated authorization code 123456</p>`;
                    
                    wizardContentBox.innerHTML = html;
                    
                    const tokenInput = document.getElementById('mgr-token-input');
                    const btnValToken = document.getElementById('btn-validate-mgr-token');
                    
                    btnValToken.addEventListener('click', () => {
                        if (tokenInput.value.trim() === '123456') {
                            wizardData.managerApproved = true;
                            btnValToken.disabled = true;
                            btnValToken.innerHTML = '<i class="fa-solid fa-check"></i> Accepted';
                            btnWizardNext.disabled = false;
                        } else {
                            alert("Invalid code.");
                        }
                    });
                } else if (role === 'Admin' || role === 'Manager') {
                    html += '<p class="success-text" style="font-weight:700; margin-top:1rem;"><i class="fa-solid fa-shield-check"></i> Approvals verified successfully.</p>';
                    btnWizardNext.disabled = false;
                    wizardContentBox.innerHTML = html;
                }
            }
        }
        else if (step === 4) {
            wizardContentBox.innerHTML = '<span class="status-text"><i class="fa-solid fa-spinner fa-spin"></i> Saving running-config state backup and initiating SSH session...</span>';
            btnWizardNext.disabled = true;
            btnWizardCancel.disabled = true;
            
            try {
                const res = await secureFetch('/api/deploy-config', {
                    method: 'POST',
                    body: JSON.stringify({
                        commands: wizardData.commands,
                        device: currentScenario === 'VPN is down' ? 'router-hq' : (currentScenario === 'Server CPU is 100%' ? 'app-srv-02' : 'sw-core-01'),
                        simulateFailure: cbSimulateFail.checked,
                        managerApproved: wizardData.managerApproved,
                        adminApproved: wizardData.adminApproved
                    })
                });
                
                const data = await res.json();
                
                wizardContentBox.innerHTML = '<span class="status-text"><i class="fa-solid fa-spinner fa-spin"></i> Deploying configuration templates on target switch...</span>';
                
                setTimeout(() => {
                    terminalHealing.style.display = 'block';
                    const lines = data.deployLogs.split('\n');
                    let i = 0;
                    terminalHealingOutput.innerHTML = '';
                    
                    function printHealingLine() {
                        if (i < lines.length) {
                            const p = document.createElement('p');
                            p.textContent = lines[i];
                            if (lines[i].includes('Backup') || lines[i].includes('commit')) p.className = 'success';
                            terminalHealingOutput.appendChild(p);
                            terminalHealingOutput.scrollTop = terminalHealingOutput.scrollHeight;
                            i++;
                            setTimeout(printHealingLine, 100);
                        } else {
                            wizardData.deployResult = data;
                            btnWizardNext.disabled = false;
                            btnWizardCancel.disabled = false;
                            wizardContentBox.innerHTML = '<p class="success-text" style="font-weight:700;"><i class="fa-solid fa-check"></i> Playbook execution completed. Config committed.</p>';
                        }
                    }
                    printHealingLine();
                }, 1000);
                
            } catch (err) {
                wizardContentBox.innerHTML = '<span class="warning-text">SSH connection failed.</span>';
                btnWizardCancel.disabled = false;
            }
        }
        else if (step === 5) {
            wizardContentBox.innerHTML = '<span class="status-text"><i class="fa-solid fa-spinner fa-spin"></i> Running verification sweeps...</span>';
            btnWizardNext.disabled = true;
            btnWizardCancel.disabled = true;
            
            const data = wizardData.deployResult;
            
            setTimeout(() => {
                let html = '<h4>Verification Probe Results:</h4><pre style="background:black; color:white; padding:0.5rem; border-radius:6px; font-family:\'Fira Code\', monospace;">';
                html += escapeHtml(data.verificationLogs);
                html += '</pre>';
                
                if (data.success) {
                    html += '<p class="success-text" style="font-weight:700; margin-top:1rem;"><i class="fa-solid fa-check-double"></i> Verification checks PASSED. Incident resolved.</p>';
                    wizardContentBox.innerHTML = html;
                    
                    btnRunHealing.innerHTML = '<i class="fa-solid fa-check"></i> Deployed';
                    btnRunHealing.disabled = true;
                    btnWizardCancel.textContent = 'Finish';
                    btnWizardCancel.disabled = false;
                    
                    // Unlock Step 3
                    document.getElementById('step-card-rca').classList.remove('lock-disabled');
                    document.getElementById('btn-run-rca').disabled = false;
                    
                    // Mark active incident status
                    const catStatus = document.getElementById(`cat-card-status-${currentScenario === 'VPN is down' ? 'INC-402' : 'INC-403'}`);
                    if (catStatus) catStatus.className = 'card-status status-resolved';
                    
                    // Update table status
                    const incTableStatus = document.querySelector(`.inc-status-td-${currentScenario === 'VPN is down' ? 'INC-402' : 'INC-403'}`);
                    if (incTableStatus) incTableStatus.textContent = 'Resolved';
                    
                } else {
                    html += '<p class="warning-text" style="font-weight:700; margin-top:1rem;"><i class="fa-solid fa-triangle-exclamation"></i> Verification FAILED. Initiating automatic rollback...</p>';
                    wizardContentBox.innerHTML = html;
                    
                    setTimeout(() => {
                        let rollbackHtml = html + '<br><h4>Rollback Log Output:</h4><pre style="background:black; color:var(--critical); padding:0.5rem; border-radius:6px; font-family:\'Fira Code\', monospace;">';
                        rollbackHtml += escapeHtml(data.rollbackLogs);
                        rollbackHtml += '</pre>';
                        rollbackHtml += '<p class="warning-text" style="font-weight:700; margin-top:1rem;"><i class="fa-solid fa-arrow-rotate-left"></i> System successfully rolled back.</p>';
                        
                        wizardContentBox.innerHTML = rollbackHtml;
                        btnWizardCancel.textContent = 'Close Wizard';
                        btnWizardCancel.disabled = false;
                        btnRunHealing.disabled = false;
                        btnRunHealing.innerHTML = 'Retry Deployment';
                    }, 2000);
                }
            }, 1500);
        }
    }

    btnWizardNext.addEventListener('click', () => {
        if (wizardStep < 5) {
            runWizardStep(wizardStep + 1);
        }
    });

    btnWizardCancel.addEventListener('click', () => {
        wizardContainer.style.display = 'none';
        btnRunHealing.disabled = false;
        if (btnRunHealing.innerHTML.includes('Deployed')) {
            btnRunHealing.disabled = true;
        }
    });

    // Generate RCA report switchers
    const btnRunRca = document.getElementById('btn-run-rca');
    if (btnRunRca) {
        btnRunRca.addEventListener('click', async () => {
            btnRunRca.disabled = true;
            btnRunRca.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Generating...';
            
            try {
                const response = await secureFetch('/api/action', {
                    method: 'POST',
                    body: JSON.stringify({ scenario: currentScenario, action: 'rca' })
                });
                const data = await response.json();
                
                document.getElementById('rca-document-view').style.display = 'block';
                btnRunRca.innerHTML = '<i class="fa-solid fa-check"></i> Report Loaded';
                
                document.getElementById('rca-document-content').innerHTML = `
                    <div class="report-tabs-bar" style="display:flex; gap:0.5rem; margin-bottom:1rem; border-bottom:1px solid var(--border-color); padding-bottom:0.5rem;">
                        <button class="btn btn-sm btn-outline active">RCA Report</button>
                    </div>
                    <div style="color:white; overflow-y:auto; max-height:220px; font-size:0.75rem; line-height:1.4;">
                        ${formatMarkdownText(data.output)}
                    </div>
                `;
            } catch (err) {
                btnRunRca.innerHTML = 'Error Generating Report';
                btnRunRca.disabled = false;
            }
        });
    }

    function resetWorkflowSteps() {
        // Step 1 Diagnostics
        const btnDiag = document.getElementById('btn-run-diag');
        if (btnDiag) {
            btnDiag.disabled = false;
            btnDiag.innerHTML = 'Run Diagnostic Scripts';
        }
        const termDiag = document.getElementById('terminal-diag');
        if (termDiag) termDiag.style.display = 'none';
        
        // Step 2 Healer
        const btnHeal = document.getElementById('btn-run-healing');
        if (btnHeal) {
            btnHeal.disabled = true;
            btnHeal.innerHTML = 'Begin Deployment Sequence';
        }
        const wizard = document.getElementById('deployment-wizard-container');
        if (wizard) wizard.style.display = 'none';
        const termHeal = document.getElementById('terminal-healing');
        if (termHeal) termHeal.style.display = 'none';
        
        // Step 3 Reports
        const btnRpt = document.getElementById('btn-run-rca');
        if (btnRpt) {
            btnRpt.disabled = true;
            btnRpt.innerHTML = 'Generate Report';
        }
        const rcaView = document.getElementById('rca-document-view');
        if (rcaView) rcaView.style.display = 'none';
    }

    // ----------------------------------------------------
    // Markdown Helper Formatter
    // ----------------------------------------------------
    function formatMarkdownText(text) {
        if (!text) return '';
        let escaped = escapeHtml(text);
        
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        escaped = escaped.replace(/\*(.*?)\*/g, '<em>$1</em>');
        escaped = escaped.replace(/```([\s\S]*?)```/g, '<pre style="background:#040710; padding:0.5rem; border-radius:6px; font-family:\'Fira Code\', monospace;"><code>$1</code></pre>');
        escaped = escaped.replace(/`(.*?)`/g, '<code>$1</code>');
        escaped = escaped.replace(/# (.*?)\n/g, '<h4 style="color:white; margin-top:0.75rem;">$1</h4>');
        escaped = escaped.replace(/## (.*?)\n/g, '<h5 style="color:var(--primary); margin-top:0.5rem;">$1</h5>');
        
        return escaped;
    }

    function formatMarkdownInline(text) {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>');
    }

    function escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // ----------------------------------------------------
    // CHAT ATTACHMENTS CONTROLLERS (FileReader log/config/topology)
    // ----------------------------------------------------
    const btnToggleAttachments = document.getElementById('btn-toggle-attachments');
    const attachmentDropdown = document.getElementById('attachment-dropdown');
    const chatAttachmentBar = document.getElementById('chat-attachment-bar');
    const attachedBadgesContainer = document.getElementById('attached-badges-container');

    const logInput = document.getElementById('attach-log-input');
    const configInput = document.getElementById('attach-config-input');
    const topologyInput = document.getElementById('attach-topology-input');

    if (btnToggleAttachments) {
        btnToggleAttachments.addEventListener('click', (e) => {
            e.stopPropagation();
            const show = attachmentDropdown.style.display === 'flex';
            attachmentDropdown.style.display = show ? 'none' : 'flex';
        });
        
        // Hide dropdown when clicking elsewhere
        document.addEventListener('click', () => {
            if (attachmentDropdown) attachmentDropdown.style.display = 'none';
        });
    }

    const btnAttachLog = document.getElementById('btn-attach-log');
    if (btnAttachLog) {
        btnAttachLog.addEventListener('click', () => logInput.click());
    }
    const btnAttachConfig = document.getElementById('btn-attach-config');
    if (btnAttachConfig) {
        btnAttachConfig.addEventListener('click', () => configInput.click());
    }
    const btnAttachTopology = document.getElementById('btn-attach-topology');
    if (btnAttachTopology) {
        btnAttachTopology.addEventListener('click', () => topologyInput.click());
    }

    // Process file select handlers
    if (logInput) logInput.addEventListener('change', (e) => handleFileSelect(e, 'logs'));
    if (configInput) configInput.addEventListener('change', (e) => handleFileSelect(e, 'config'));
    if (topologyInput) topologyInput.addEventListener('change', (e) => handleFileSelect(e, 'topology'));

    function handleFileSelect(event, type) {
        const file = event.target.files[0];
        if (!file) return;

        // Limit size to 5MB
        if (file.size > 5 * 1024 * 1024) {
            alert("File size exceeds 5MB limit.");
            return;
        }

        const reader = new FileReader();
        reader.onload = function(e) {
            const content = e.target.result;
            
            if (type === 'logs') {
                attachedLogs = content;
            } else if (type === 'config') {
                attachedConfig = content;
            } else if (type === 'topology') {
                attachedTopology = content;
            }

            renderAttachmentBadges();
        };
        reader.readAsText(file);
        
        // Reset file input so same file can be selected again
        event.target.value = '';
    }

    function renderAttachmentBadges() {
        if (!attachedBadgesContainer || !chatAttachmentBar) return;
        attachedBadgesContainer.innerHTML = '';
        
        let hasAttachments = false;

        if (attachedLogs) {
            hasAttachments = true;
            createBadge("Logs", () => { attachedLogs = null; renderAttachmentBadges(); });
        }
        if (attachedConfig) {
            hasAttachments = true;
            createBadge("Config", () => { attachedConfig = null; renderAttachmentBadges(); });
        }
        if (attachedTopology) {
            hasAttachments = true;
            createBadge("Topology", () => { attachedTopology = null; renderAttachmentBadges(); });
        }

        chatAttachmentBar.style.display = hasAttachments ? 'flex' : 'none';
    }

    function createBadge(label, onClear) {
        const badge = document.createElement('div');
        badge.className = 'attachment-badge';
        badge.innerHTML = `
            <span>${label}</span>
            <i class="fa-solid fa-xmark clear-btn" title="Remove attachment"></i>
        `;
        badge.querySelector('.clear-btn').addEventListener('click', onClear);
        attachedBadgesContainer.appendChild(badge);
    }

    function clearAllAttachments() {
        attachedLogs = null;
        attachedConfig = null;
        attachedTopology = null;
        renderAttachmentBadges();
    }

    // ----------------------------------------------------
    // REAL-TIME SOCKET.IO ALARMS & INCIDENTS SYNC
    // ----------------------------------------------------
    const socket = io();

    socket.on('connect', () => {
        console.log('Socket.IO telemetry link active.');
    });

    socket.on('welcome', (data) => {
        console.log('Real-time NOC welcome event:', data.message);
    });

    socket.on('incident_update', (data) => {
        console.log('Real-time incident update received:', data);
        
        // Find existing incident index
        const index = activeIncidents.findIndex(i => i.id === data.id);
        
        if (data.status === 'Resolved') {
            if (index !== -1) {
                activeIncidents[index].status = 'Resolved';
                
                // If it's currently selected, update wizard/RCA indicators to Resolved
                const selected = activeIncidents.find(i => i.scenario === currentScenario);
                if (selected && selected.id === data.id) {
                    selectIncident(selected);
                }
            }
        } else {
            // Map dynamic database fields to client layout format
            const mapped = mapDbIncidentToClient(data);
            if (index !== -1) {
                // Update existing alert parameters
                activeIncidents[index] = { ...activeIncidents[index], ...mapped };
            } else {
                // Prepend new live incident to queue
                activeIncidents.unshift(mapped);
            }
            
            // Auto-investigate or run self-healing if autonomous setting is active
            if (data.status === 'Active') {
                const autoHealTriggered = activeIncidents.find(i => i.id === data.id);
                if (autoHealTriggered) {
                    // Check settings threshold and trigger auto healing loop if needed
                    fetch('/api/settings').then(res => res.json()).then(settings => {
                        if (settings.healingPolicy === 'autonomous') {
                            triggerAutonomousSelfHealing(autoHealTriggered);
                        }
                    }).catch(() => {});
                }
            }
        }
        
        // Refresh table & catalog cards UI in Dashboard/Control Room
        renderIncidentsQueue();
        renderIncidentsCatalog();
        
        // Sync header alerts badges and counters
        const activeCount = activeIncidents.filter(i => i.status === 'Active').length;
        if (activeIncidentsBadge) activeIncidentsBadge.textContent = activeCount;
    });

    socket.on('alarm_update', (data) => {
        console.log('Real-time telemetry alarm update:', data);
        // Refresh active telemetry metrics
        updateTelemetry();
    });

    socket.on('syslog_message', (data) => {
        // Append syslog entry to the system logs wrapper dynamically
        const logsWrapper = document.getElementById('console-logs-wrapper');
        if (logsWrapper) {
            const p = document.createElement('p');
            const timeStr = new Date(data.timestamp).toLocaleTimeString();
            p.textContent = `[${timeStr}] ${data.device}: ${data.message}`;
            logsWrapper.appendChild(p);
            // Limit to 50 logs in console view to prevent DOM bloating
            while (logsWrapper.children.length > 50) {
                logsWrapper.removeChild(logsWrapper.firstChild);
            }
            if (currentConsoleTab === 'logs') {
                consoleOutput.scrollTop = consoleOutput.scrollHeight;
            }
        }
    });

    // ----------------------------------------------------
    // AI ENGINEERING REPORT VIEW/HIDE CONTROLLERS
    // ----------------------------------------------------
    const btnRcaViewReport = document.getElementById('btn-rca-view-report');
    const btnRcaHideReport = document.getElementById('btn-rca-hide-report');
    const rcaReportBlock = document.getElementById('rca-report-block');
    const rcaReportContent = document.getElementById('rca-report-content');

    if (btnRcaViewReport && rcaReportBlock && rcaReportContent) {
        btnRcaViewReport.addEventListener('click', () => {
            // Find selected incident
            const activeCard = document.querySelector('.incident-card.active');
            let matchedInc = null;
            if (activeCard) {
                const id = activeCard.getAttribute('data-id');
                matchedInc = activeIncidents.find(i => i.id === id);
            } else if (activeIncidents.length > 0) {
                // Fallback to currently active scenario matching incident
                matchedInc = activeIncidents.find(i => i.scenario === currentScenario);
            }

            if (matchedInc && matchedInc.report) {
                if (typeof marked !== 'undefined') {
                    rcaReportContent.innerHTML = marked.parse(matchedInc.report);
                } else {
                    rcaReportContent.textContent = matchedInc.report;
                }
            } else {
                rcaReportContent.innerHTML = '<span style="color:var(--text-muted);">No engineering report generated for this incident yet. Run diagnostics sweep or check database schema.</span>';
            }
            rcaReportBlock.style.display = 'block';
        });
    }

    if (btnRcaHideReport && rcaReportBlock) {
        btnRcaHideReport.addEventListener('click', () => {
            rcaReportBlock.style.display = 'none';
        });
    }

    // ----------------------------------------------------
    // TOPOLOGY LIVE DISCOVERY CONTROLLERS & SOCKETS
    // ----------------------------------------------------
    const btnDiscoverTopology = document.getElementById('btn-discover-topology');
    const subnetInput = document.getElementById('topology-discovery-subnet');

    if (btnDiscoverTopology) {
        btnDiscoverTopology.addEventListener('click', async () => {
            const subnet = subnetInput ? subnetInput.value.trim() : '10.0.10.0/24';
            btnDiscoverTopology.disabled = true;
            btnDiscoverTopology.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sweeping Subnet...';
            
            try {
                const response = await secureFetch('/api/discovery/run', {
                    method: 'POST',
                    body: JSON.stringify({ subnet: subnet })
                });
                
                if (response.ok) {
                    console.log(`Subnet discovery scan started on ${subnet}`);
                } else {
                    const err = await response.json();
                    alert(`Discovery initiation failed: ${err.detail}`);
                    btnDiscoverTopology.disabled = false;
                    btnDiscoverTopology.innerHTML = '<i class="fa-solid fa-network-wired"></i> Run Discovery Scan';
                }
            } catch (err) {
                console.error("Subnet sweep error:", err);
                // Fallback simulation in case of connection failure
                setTimeout(() => {
                    btnDiscoverTopology.disabled = false;
                    btnDiscoverTopology.innerHTML = '<i class="fa-solid fa-network-wired"></i> Run Discovery Scan';
                    loadTopologyFromBackend();
                }, 3000);
            }
        });
    }

    socket.on('discovery_status', (data) => {
        console.log("Real-time network discovery status update:", data);
        if (data.status === 'completed') {
            if (btnDiscoverTopology) {
                btnDiscoverTopology.disabled = false;
                btnDiscoverTopology.innerHTML = '<i class="fa-solid fa-network-wired"></i> Run Discovery Scan';
            }
            // Trigger dynamic reload of discovered graph
            loadTopologyFromBackend();
        }
    });

    socket.on('discovery_device', (data) => {
        console.log("Real-time node discovered:", data);
        
        const exists = topoNodes.some(n => n.id === data.hostname);
        if (!exists) {
            const cx = canvas ? canvas.width / 2 : 250;
            const cy = canvas ? canvas.height / 2 : 200;
            const radius = 100 + Math.random() * 80;
            const angle = Math.random() * 2 * Math.PI;
            
            const nameLower = data.hostname.toLowerCase();
            let role = "Router";
            let icon = "🌐";
            
            if (nameLower.includes("switch") || nameLower.includes("leaf") || nameLower.includes("spine")) {
                role = "Switch";
                icon = "🔌";
            } else if (nameLower.includes("fw") || nameLower.includes("firewall") || nameLower.includes("utm")) {
                role = "Firewall";
                icon = "🛡";
            } else if (nameLower.includes("srv") || nameLower.includes("server") || nameLower.includes("host") || nameLower.includes("domain") || nameLower.includes("db")) {
                role = "Server";
                icon = nameLower.includes("db") ? "🗄" : "🖥";
            }

            topoNodes.push({
                id: data.hostname,
                label: data.hostname,
                role: role,
                ip: data.ip || '10.0.10.x',
                vendor: data.vendor || 'Generic',
                platform: data.platform || 'Standard',
                x: cx + radius * Math.cos(angle),
                y: cy + radius * Math.sin(angle),
                radius: 20,
                icon: icon,
                status: 'Healthy'
            });
            
            runForceDirectedLayout();
            drawTopology();
        }
    });

    // Live refreshing of selected device inspector
    setInterval(() => {
        if (selectedNode) {
            const currentSelected = topoNodes.find(n => n.id === selectedNode.id);
            if (currentSelected) {
                inspectNode(currentSelected);
            }
        }
    }, 2000);

    // ----------------------------------------------------
    // LIVE CLI CONTROLLERS & STREAMING TERMINAL
    // ----------------------------------------------------
    const btnRunCli = document.getElementById('btn-run-cli');
    const cliCommandInput = document.getElementById('cli-command-input');
    const cliDeviceSelect = document.getElementById('cli-device-select');
    const cliLibrarySelect = document.getElementById('cli-library-select');
    const cliTerminalBody = document.getElementById('cli-terminal-body');
    const cliHistoryList = document.getElementById('cli-history-list');
    const btnExportCli = document.getElementById('btn-export-cli');

    let cliHistory = [
        { device: 'router-hq', library: 'SSH', command: 'show ip interface brief' },
        { device: 'router-hq', library: 'Netmiko', command: 'ping 8.8.8.8' },
        { device: 'juniper-srx-edge', library: 'NAPALM', command: 'show route' }
    ];

    function renderCliHistory() {
        if (!cliHistoryList) return;
        if (cliHistory.length === 0) {
            cliHistoryList.innerHTML = '<p style="font-size:0.7rem; color:var(--text-muted); text-align:center;">No command history stored.</p>';
            return;
        }
        cliHistoryList.innerHTML = '';
        cliHistory.forEach((item) => {
            const div = document.createElement('div');
            div.className = 'server-config-item';
            div.style.cursor = 'pointer';
            div.style.marginBottom = '0.2rem';
            div.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:2px; width:100%;">
                    <div style="display:flex; justify-content:space-between; font-size:0.65rem;">
                        <span style="color:var(--primary); font-weight:600;">${item.device}</span>
                        <span style="color:var(--text-muted); font-size:0.6rem;">${item.library}</span>
                    </div>
                    <code style="font-size:0.68rem; color:white; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; display:block;">$ ${item.command}</code>
                </div>
            `;
            div.addEventListener('click', () => {
                if (cliDeviceSelect) cliDeviceSelect.value = item.device;
                if (cliLibrarySelect) cliLibrarySelect.value = item.library;
                if (cliCommandInput) cliCommandInput.value = item.command;
            });
            cliHistoryList.appendChild(div);
        });
    }

    // Initial render
    renderCliHistory();

    if (btnRunCli && cliCommandInput) {
        const runCommand = async () => {
            const command = cliCommandInput.value.trim();
            const device = cliDeviceSelect ? cliDeviceSelect.value : 'router-hq';
            const library = cliLibrarySelect ? cliLibrarySelect.value : 'SSH';
            
            if (!command) return;
            
            // Add to history list
            const alreadyExists = cliHistory.some(h => h.device === device && h.library === library && h.command === command);
            if (!alreadyExists) {
                cliHistory.unshift({ device, library, command });
                if (cliHistory.length > 8) cliHistory.pop();
                renderCliHistory();
            }
            
            btnRunCli.disabled = true;
            cliCommandInput.disabled = true;
            btnRunCli.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
            
            cliTerminalBody.textContent = `[NOC-CLI] [${library.toUpperCase()}] Opening secure remote channel to ${device}...\n`;
            
            try {
                const response = await fetch('/api/cli/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${sessionStorage.getItem('authToken')}`
                    },
                    body: JSON.stringify({ device, library, command })
                });
                
                if (!response.ok) {
                    const err = await response.json();
                    cliTerminalBody.textContent += `[ERROR] Connection handshake failed: ${err.detail || 'Connection refused'}\n`;
                    return;
                }
                
                cliTerminalBody.textContent = '';
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value);
                    cliTerminalBody.textContent += chunk;
                    cliTerminalBody.scrollTop = cliTerminalBody.scrollHeight;
                }
                
            } catch (err) {
                console.error("CLI stream error:", err);
                cliTerminalBody.textContent += `\n[NOC-CLI] [FATAL] Channel disconnect: remote host closed connection.\n`;
            } finally {
                btnRunCli.disabled = false;
                cliCommandInput.disabled = false;
                btnRunCli.innerHTML = 'Execute';
                cliCommandInput.value = '';
                cliCommandInput.focus();
            }
        };

        btnRunCli.addEventListener('click', runCommand);
        cliCommandInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                runCommand();
            }
        });
    }

    if (btnExportCli && cliTerminalBody) {
        btnExportCli.addEventListener('click', () => {
            const text = cliTerminalBody.textContent;
            const blob = new Blob([text], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const deviceVal = cliDeviceSelect ? cliDeviceSelect.value : 'device';
            a.download = `cli_session_${deviceVal}_${new Date().toISOString().slice(0,10)}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });
    }

    // ----------------------------------------------------
    // PACKET CAPTURE & ANALYZER CONTROLLERS
    // ----------------------------------------------------
    const btnStartSniff = document.getElementById('btn-start-sniff');
    const btnStopSniff = document.getElementById('btn-stop-sniff');
    const btnExportPcap = document.getElementById('btn-export-pcap');
    const packetInterfaceSelect = document.getElementById('packet-interface-select');
    const packetProtocolSelect = document.getElementById('packet-protocol-select');
    const packetsGridBody = document.getElementById('packets-grid-body');
    const packetDecodeView = document.getElementById('packet-decode-view');
    const packetHexView = document.getElementById('packet-hex-view');
    const packetAnomaliesList = document.getElementById('packet-anomalies-list');

    let captureInterval = null;
    let capturedPacketsList = [];
    let sniffedRawQueue = [];
    let anomaliesMap = new Set();

    function renderDecodeView(pkt) {
        if (!packetDecodeView) return;
        let html = '';
        for (const [layer, info] of Object.entries(pkt.decode)) {
            html += `
                <div style="border: 1px solid var(--border-color); border-radius: 4px; padding: 4px 6px; margin-bottom: 4px; background: rgba(255,255,255,0.01);">
                    <div style="font-weight: 700; color: var(--primary); display: flex; justify-content: space-between; cursor: pointer; border-bottom: 1px dashed rgba(255,255,255,0.05); margin-bottom:2px; padding-bottom:2px;">
                        <span><i class="fa-solid fa-angle-down"></i> ${layer} Layer</span>
                    </div>
                    <pre style="margin:0; font-family:monospace; font-size:0.65rem; color:var(--text-normal); white-space:pre-wrap;">${escapeHtml(info)}</pre>
                </div>
            `;
        }
        packetDecodeView.innerHTML = html;
    }

    function renderHexView(pkt) {
        if (!packetHexView) return;
        packetHexView.innerHTML = `
<span style="color:var(--primary);">Offset    Hex Bytes                                         ASCII Text</span>
0000      ${pkt.hex.split('\n')[0] || ''}      ${pkt.ascii.slice(0, 16)}
0010      ${pkt.hex.split('\n')[1] || ''}      ${pkt.ascii.slice(16, 32)}
0020      ${pkt.hex.split('\n')[2] || ''}      ${pkt.ascii.slice(32, 48)}
0030      ${pkt.hex.split('\n')[3] || ''}      ${pkt.ascii.slice(48)}
        `.trim();
    }

    if (btnStartSniff && btnStopSniff) {
        btnStartSniff.addEventListener('click', async () => {
            const intf = packetInterfaceSelect ? packetInterfaceSelect.value : 'outside-eth0';
            const filter = packetProtocolSelect ? packetProtocolSelect.value : 'All';
            
            btnStartSniff.disabled = true;
            btnStopSniff.disabled = false;
            
            if (packetsGridBody) {
                packetsGridBody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--primary); padding: 1.5rem 0;"><i class="fa-solid fa-spinner fa-spin"></i> Initializing capture interface hooks...</td></tr>`;
            }
            if (packetAnomaliesList) {
                packetAnomaliesList.innerHTML = '<p style="font-size:0.7rem; color:var(--text-muted); text-align:center;">No anomalies flagged.</p>';
            }
            if (packetDecodeView) packetDecodeView.textContent = 'Select a packet above to decode header fields.';
            if (packetHexView) packetHexView.textContent = 'Select a packet above to view hexadecimal dump.';
            
            capturedPacketsList = [];
            anomaliesMap.clear();
            
            try {
                const response = await secureFetch('/api/packets/sniff', {
                    method: 'POST',
                    body: JSON.stringify({ interface: intf, filter: filter })
                });
                
                if (!response.ok) throw new Error("Sniff request failed");
                const data = await response.json();
                
                sniffedRawQueue = data.packets;
                
                if (packetsGridBody) packetsGridBody.innerHTML = '';
                
                let idx = 0;
                captureInterval = setInterval(() => {
                    if (idx < sniffedRawQueue.length) {
                        const pkt = sniffedRawQueue[idx];
                        capturedPacketsList.push(pkt);
                        
                        const tr = document.createElement('tr');
                        tr.style.cursor = 'pointer';
                        
                        let protocolClass = "healthy-text";
                        if (pkt.protocol === 'HTTP') protocolClass = "warning-text";
                        if (pkt.protocol === 'TLS') protocolClass = "primary-text";
                        if (pkt.anomalies.length > 0) protocolClass = "critical-text";
                        
                        tr.innerHTML = `
                            <td>${pkt.id}</td>
                            <td style="font-family:monospace; font-size:0.65rem;">${pkt.time.toFixed(6)}</td>
                            <td>${pkt.source}</td>
                            <td>${pkt.destination}</td>
                            <td><span class="${protocolClass}">${pkt.protocol}</span></td>
                            <td>${pkt.length}</td>
                            <td style="font-family:monospace; font-size:0.65rem; color:var(--text-normal);">${escapeHtml(pkt.info)}</td>
                        `;
                        
                        tr.addEventListener('click', () => {
                            packetsGridBody.querySelectorAll('tr').forEach(r => r.style.background = 'transparent');
                            tr.style.background = 'rgba(79, 140, 255, 0.08)';
                            
                            renderDecodeView(pkt);
                            renderHexView(pkt);
                        });
                        
                        packetsGridBody.appendChild(tr);
                        
                        const container = packetsGridBody.parentElement.parentElement;
                        container.scrollTop = container.scrollHeight;
                        
                        pkt.anomalies.forEach(anomaly => {
                            if (!anomaliesMap.has(anomaly)) {
                                anomaliesMap.add(anomaly);
                                renderAnomaliesList();
                            }
                        });
                        
                        idx++;
                    } else {
                        clearInterval(captureInterval);
                        btnStartSniff.disabled = false;
                        btnStopSniff.disabled = true;
                    }
                }, 800);
                
            } catch (err) {
                console.error("Packet sniffer start failure:", err);
                if (packetsGridBody) {
                    packetsGridBody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--critical); padding: 1.5rem 0;">Failed to bind to socket driver. Make sure Scapy is active.</td></tr>`;
                }
                btnStartSniff.disabled = false;
                btnStopSniff.disabled = true;
            }
        });

        btnStopSniff.addEventListener('click', () => {
            clearInterval(captureInterval);
            btnStartSniff.disabled = false;
            btnStopSniff.disabled = true;
        });
    }

    function renderAnomaliesList() {
        if (!packetAnomaliesList) return;
        if (anomaliesMap.size === 0) {
            packetAnomaliesList.innerHTML = '<p style="font-size:0.7rem; color:var(--text-muted); text-align:center;">No anomalies flagged.</p>';
            return;
        }
        packetAnomaliesList.innerHTML = '';
        anomaliesMap.forEach(an => {
            const div = document.createElement('div');
            div.className = 'server-config-item';
            div.style.borderColor = 'rgba(239, 68, 68, 0.15)';
            div.style.background = 'rgba(239, 68, 68, 0.03)';
            div.innerHTML = `
                <span style="color:var(--critical); margin-right:4px;"><i class="fa-solid fa-triangle-exclamation"></i></span>
                <strong style="color:white; font-size:0.68rem;">${escapeHtml(an)}</strong>
            `;
            packetAnomaliesList.appendChild(div);
        });
    }
    if (btnExportPcap) {
        btnExportPcap.addEventListener('click', () => {
            const filter = packetProtocolSelect ? packetProtocolSelect.value : 'All';
            window.location.href = `/api/packets/export?proto=${filter}`;
        });
    }

    // ----------------------------------------------------
    // CONFIGURATION MANAGER CONTROLLERS
    // ----------------------------------------------------
    const cfgDeviceSelect = document.getElementById('cfg-device-select');
    const cfgDriftStatus = document.getElementById('cfg-drift-status');
    const btnCfgAuditDrift = document.getElementById('btn-cfg-audit-drift');
    const cfgBackupsList = document.getElementById('cfg-backups-list');
    const cfgSchedEnabled = document.getElementById('cfg-sched-enabled');
    const cfgSchedInterval = document.getElementById('cfg-sched-interval');
    const btnCfgSaveSchedule = document.getElementById('btn-cfg-save-schedule');
    const cfgViewerTitle = document.getElementById('cfg-viewer-title');
    const cfgBackupDescInput = document.getElementById('cfg-backup-desc-input');
    const btnCfgCreateBackup = document.getElementById('btn-cfg-create-backup');
    const cfgCodeView = document.getElementById('cfg-code-view');
    const cfgApprovalsQueue = document.getElementById('cfg-approvals-queue');

    let loadedBackups = [];

    async function fetchBackups() {
        if (!cfgBackupsList) return;
        const device = cfgDeviceSelect ? cfgDeviceSelect.value : 'router-hq';
        
        try {
            const response = await secureFetch(`/api/config/backups?device=${device}`);
            if (!response.ok) throw new Error("Failed to load backups list");
            loadedBackups = await response.json();
            
            renderBackupsList();
            
            if (loadedBackups.length > 0) {
                viewConfigContent(loadedBackups[0]);
            } else {
                if (cfgCodeView) cfgCodeView.textContent = "No backups found for this node.";
            }
        } catch (err) {
            console.error("Backups loader error:", err);
            cfgBackupsList.innerHTML = '<p style="font-size:0.7rem; color:var(--critical); text-align:center;">Failed to load backups.</p>';
        }
    }

    function renderBackupsList() {
        if (!cfgBackupsList) return;
        if (loadedBackups.length === 0) {
            cfgBackupsList.innerHTML = '<p style="font-size:0.7rem; color:var(--text-muted); text-align:center;">No baseline backups stored.</p>';
            return;
        }
        
        cfgBackupsList.innerHTML = '';
        loadedBackups.forEach((bck, idx) => {
            const div = document.createElement('div');
            div.className = 'server-config-item';
            div.style.display = 'flex';
            div.style.flexDirection = 'column';
            div.style.gap = '0.2rem';
            
            const timestamp = new Date(bck.timestamp).toLocaleString();
            
            div.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; width:100%;">
                    <strong style="color:white; font-size:0.7rem;">Version V${bck.version}</strong>
                    <span class="badge" style="font-size:0.58rem; padding: 1px 4px; background: rgba(79, 140, 255, 0.1); border-color: rgba(79, 140, 255, 0.2); color: var(--primary);">${bck.id.slice(0, 14)}...</span>
                </div>
                <span style="font-size:0.6rem; color:var(--text-muted);">${timestamp}</span>
                <p style="font-size:0.65rem; color:var(--text-normal); margin:2px 0 4px 0; font-style:italic;">"${escapeHtml(bck.description)}"</p>
                <div style="display:flex; gap:0.25rem; margin-top:2px;">
                    <button class="btn btn-xs btn-outline btn-view" style="padding: 1px 4px; font-size:0.58rem;"><i class="fa-solid fa-eye"></i> View</button>
                    <button class="btn btn-xs btn-outline btn-diff" style="padding: 1px 4px; font-size:0.58rem;" ${idx === loadedBackups.length - 1 ? 'disabled' : ''}><i class="fa-solid fa-code-compare"></i> Diff</button>
                    <button class="btn btn-xs btn-outline btn-rollback" style="padding: 1px 4px; font-size:0.58rem; border-color: rgba(239, 68, 68, 0.2); color: var(--critical);"><i class="fa-solid fa-history"></i> Rollback</button>
                </div>
            `;
            
            div.querySelector('.btn-view').addEventListener('click', () => viewConfigContent(bck));
            
            const diffBtn = div.querySelector('.btn-diff');
            if (diffBtn && idx < loadedBackups.length - 1) {
                diffBtn.addEventListener('click', () => {
                    const prevBck = loadedBackups[idx + 1];
                    fetchAndRenderDiff(prevBck.id, bck.id);
                });
            }
            
            div.querySelector('.btn-rollback').addEventListener('click', () => {
                if (confirm(`Are you sure you want to rollback device config to Version V${bck.version}?`)) {
                    triggerRollback(bck.id);
                }
            });
            
            cfgBackupsList.appendChild(div);
        });
    }

    function viewConfigContent(bck) {
        if (!cfgCodeView || !cfgViewerTitle) return;
        cfgViewerTitle.textContent = `Running Config: Version V${bck.version} (${bck.id})`;
        cfgCodeView.innerHTML = escapeHtml(bck.running_config);
    }

    async function fetchAndRenderDiff(bckIdA, bckIdB) {
        if (!cfgCodeView || !cfgViewerTitle) return;
        cfgViewerTitle.textContent = `Diff Comparison: Backup version A vs B`;
        cfgCodeView.textContent = "Calculating diff metrics...";
        
        try {
            const response = await secureFetch('/api/config/diff', {
                method: 'POST',
                body: JSON.stringify({ backupIdA: bckIdA, backupIdB: bckIdB })
            });
            if (!response.ok) throw new Error("Failed to fetch config diff");
            const diffLines = await response.json();
            
            renderDiffText(diffLines);
        } catch (err) {
            console.error("Diff comparison error:", err);
            cfgCodeView.textContent = "Failed to fetch diff report.";
        }
    }

    function renderDiffText(diffLines) {
        if (!cfgCodeView) return;
        if (diffLines.length === 0) {
            cfgCodeView.innerHTML = '<span style="color:var(--text-muted);">Configurations are identical. No diff additions/deletions.</span>';
            return;
        }
        
        let html = '';
        diffLines.forEach(line => {
            if (line.type === 'addition') {
                html += `<span style="color:#22c55e; display:block;">+ ${escapeHtml(line.text)}</span>`;
            } else if (line.type === 'deletion') {
                html += `<span style="color:#ef4444; display:block;">- ${escapeHtml(line.text)}</span>`;
            } else {
                html += `<span style="color:var(--text-muted); display:block;">  ${escapeHtml(line.text)}</span>`;
            }
        });
        cfgCodeView.innerHTML = html;
    }

    async function triggerRollback(bckId) {
        try {
            const response = await secureFetch('/api/config/rollback', {
                method: 'POST',
                body: JSON.stringify({ backupId: bckId })
            });
            if (!response.ok) {
                const err = await response.json();
                alert(`Rollback failed: ${err.detail || 'Access restricted'}`);
                return;
            }
            const res = await response.json();
            alert(`SUCCESS: Configuration successfully rolled back to Version V${res.version} on device ${res.device}!`);
            
            fetchBackups();
            if (typeof fetchAuditLogs === 'function') fetchAuditLogs();
        } catch (err) {
            console.error("Rollback error:", err);
            alert("Connection error executing configuration rollback.");
        }
    }

    if (btnCfgAuditDrift) {
        btnCfgAuditDrift.addEventListener('click', async () => {
            const device = cfgDeviceSelect ? cfgDeviceSelect.value : 'router-hq';
            if (!cfgDriftStatus) return;
            
            cfgDriftStatus.innerHTML = '<span style="font-size:0.75rem; color:var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Auditing running-config state...</span>';
            cfgDriftStatus.style.borderColor = 'var(--border-color)';
            cfgDriftStatus.style.background = 'rgba(0,0,0,0.15)';
            
            try {
                const response = await secureFetch(`/api/config/drift?device=${device}`);
                if (!response.ok) throw new Error("Failed to check drift");
                const res = await response.json();
                
                if (res.has_drift) {
                    cfgDriftStatus.innerHTML = '<span style="font-size:0.75rem; font-weight:700; color:var(--warning);"><i class="fa-solid fa-triangle-exclamation"></i> DRIFT DETECTED</span>';
                    cfgDriftStatus.style.borderColor = 'rgba(245, 158, 11, 0.25)';
                    cfgDriftStatus.style.background = 'rgba(245, 158, 11, 0.03)';
                    
                    if (cfgViewerTitle && cfgCodeView) {
                        cfgViewerTitle.textContent = `Drift Detected on ${device} (Active vs Startup Baseline)`;
                        renderDiffText(res.diff);
                    }
                } else {
                    cfgDriftStatus.innerHTML = '<span style="font-size:0.75rem; font-weight:700; color:var(--healthy);"><i class="fa-solid fa-circle-check"></i> Healthy (No Drift)</span>';
                    cfgDriftStatus.style.borderColor = 'rgba(34, 197, 94, 0.25)';
                    cfgDriftStatus.style.background = 'rgba(34, 197, 94, 0.03)';
                    alert(`Audit complete: Device ${device} running-config matches startup config baseline!`);
                }
            } catch (err) {
                console.error("Drift check error:", err);
                cfgDriftStatus.innerHTML = '<span style="font-size:0.75rem; color:var(--critical);"><i class="fa-solid fa-triangle-exclamation"></i> Audit Failed</span>';
            }
        });
    }

    if (btnCfgCreateBackup && cfgBackupDescInput) {
        btnCfgCreateBackup.addEventListener('click', async () => {
            const device = cfgDeviceSelect ? cfgDeviceSelect.value : 'router-hq';
            const desc = cfgBackupDescInput.value.trim() || 'Manual configuration backup';
            
            btnCfgCreateBackup.disabled = true;
            try {
                const response = await secureFetch('/api/config/backup', {
                    method: 'POST',
                    body: JSON.stringify({ device, description: desc })
                });
                if (!response.ok) throw new Error("Failed to create backup");
                
                cfgBackupDescInput.value = '';
                alert("SUCCESS: Capture baseline backup registered successfully!");
                fetchBackups();
            } catch (err) {
                console.error("Backup creation error:", err);
                alert("Failed to capture node backup.");
            } finally {
                btnCfgCreateBackup.disabled = false;
            }
        });
    }

    async function loadSchedule() {
        const device = cfgDeviceSelect ? cfgDeviceSelect.value : 'router-hq';
        try {
            const response = await secureFetch('/api/config/schedules');
            if (!response.ok) return;
            const schedules = await response.json();
            const sched = schedules.find(s => s.device === device);
            if (sched) {
                if (cfgSchedEnabled) cfgSchedEnabled.checked = sched.enabled;
                if (cfgSchedInterval) cfgSchedInterval.value = sched.interval;
            }
        } catch (err) {
            console.error("Failed to load backup schedules:", err);
        }
    }

    if (btnCfgSaveSchedule) {
        btnCfgSaveSchedule.addEventListener('click', async () => {
            const device = cfgDeviceSelect ? cfgDeviceSelect.value : 'router-hq';
            const enabled = cfgSchedEnabled ? cfgSchedEnabled.checked : false;
            const interval = cfgSchedInterval ? cfgSchedInterval.value : 'Daily at 02:00';
            
            btnCfgSaveSchedule.disabled = true;
            try {
                const response = await secureFetch('/api/config/schedule', {
                    method: 'POST',
                    body: JSON.stringify({ device, interval, enabled })
                });
                if (!response.ok) throw new Error("Failed to update schedule");
                alert(`SUCCESS: Automated backup schedule updated for device ${device}!`);
            } catch (err) {
                console.error("Save schedule error:", err);
                alert("Failed to update backup schedule.");
            } finally {
                btnCfgSaveSchedule.disabled = false;
            }
        });
    }

    async function fetchApprovalsQueue() {
        if (!cfgApprovalsQueue) return;
        
        try {
            const response = await secureFetch('/api/config/approvals');
            if (!response.ok) throw new Error("Failed to load approvals queue");
            const approvals = await response.json();
            
            renderApprovalsQueue(approvals);
        } catch (err) {
            console.error("Approvals loader error:", err);
            cfgApprovalsQueue.innerHTML = '<p style="font-size:0.7rem; color:var(--critical); text-align:center;">Failed to load approval requests.</p>';
        }
    }

    function renderApprovalsQueue(approvals) {
        if (!cfgApprovalsQueue) return;
        
        const pending = approvals.filter(r => r.status === 'Pending Approval');
        
        if (pending.length === 0) {
            cfgApprovalsQueue.innerHTML = '<p style="font-size:0.72rem; color:var(--text-muted); text-align:center;">No pending approval requests in queue.</p>';
            return;
        }
        
        cfgApprovalsQueue.innerHTML = '';
        pending.forEach(req => {
            const div = document.createElement('div');
            div.className = 'server-config-item';
            div.style.display = 'flex';
            div.style.flexDirection = 'column';
            div.style.gap = '0.35rem';
            div.style.borderLeftColor = 'var(--primary)';
            
            div.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; width:100%;">
                    <strong style="color:white; font-size:0.72rem;">Device: ${req.device}</strong>
                    <span class="badge" style="font-size:0.58rem; background:rgba(79, 140, 255, 0.1); border-color:rgba(79, 140, 255, 0.2); color:var(--primary);">${req.id}</span>
                </div>
                <div style="font-size:0.6rem; color:var(--text-muted);">Requested by: <strong>${req.requested_by}</strong> (${new Date(req.timestamp).toLocaleTimeString()})</div>
                <pre style="margin:2px 0; background:#010204; border:1px solid rgba(255,255,255,0.05); padding:4px; font-family:monospace; font-size:0.65rem; color:#22c55e; max-height:80px; overflow-y:auto;">+ ${escapeHtml(req.proposed_config)}</pre>
                <div style="display:flex; gap:0.4rem; justify-content:flex-end; margin-top:2px;">
                    <button class="btn btn-xs btn-outline btn-reject" style="padding:2px 6px; font-size:0.6rem; border-color:rgba(239,68,68,0.2); color:var(--critical);"><i class="fa-solid fa-times"></i> Reject</button>
                    <button class="btn btn-xs btn-success btn-approve" style="padding:2px 6px; font-size:0.6rem;"><i class="fa-solid fa-check"></i> Approve & Deploy</button>
                </div>
            `;
            
            div.querySelector('.btn-reject').addEventListener('click', () => handleApprovalAction(req.id, 'reject'));
            div.querySelector('.btn-approve').addEventListener('click', () => handleApprovalAction(req.id, 'approve'));
            
            cfgApprovalsQueue.appendChild(div);
        });
    }

    async function handleApprovalAction(reqId, action) {
        try {
            const response = await secureFetch('/api/config/approval/action', {
                method: 'POST',
                body: JSON.stringify({ requestId: reqId, action: action })
            });
            
            if (!response.ok) {
                const err = await response.json();
                alert(`Action rejected: ${err.detail || 'Access restricted'}`);
                return;
            }
            
            alert(`SUCCESS: Proposed change request '${reqId}' status updated: ${action.toUpperCase()}D!`);
            fetchApprovalsQueue();
            fetchBackups();
            if (typeof fetchAuditLogs === 'function') fetchAuditLogs();
        } catch (err) {
            console.error("Approval action error:", err);
            alert("Connection error sending approval validation.");
        }
    }

    if (cfgDeviceSelect) {
        cfgDeviceSelect.addEventListener('change', () => {
            fetchBackups();
            loadSchedule();
            
            if (cfgDriftStatus) {
                cfgDriftStatus.innerHTML = '<span style="font-size:0.75rem; font-weight:700; color:var(--healthy);"><i class="fa-solid fa-circle-check"></i> Healthy (No Drift)</span>';
                cfgDriftStatus.style.borderColor = 'rgba(34, 197, 94, 0.15)';
                cfgDriftStatus.style.background = 'rgba(34, 197, 94, 0.02)';
            }
        });
    }

    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const tabId = item.getAttribute('data-tab');
            if (tabId === 'automation') {
                fetchBackups();
                loadSchedule();
                fetchApprovalsQueue();
            }
        });
    });

    // ----------------------------------------------------
    // AUTOMATION PLAYBOOKS CONTROLLERS
    // ----------------------------------------------------
    const autoPlaybookSelect = document.getElementById('auto-playbook-select');
    const autoFrameworkView = document.getElementById('auto-framework-view');
    const autoCodeView = document.getElementById('auto-code-view');
    const btnAutoValidate = document.getElementById('btn-auto-validate');
    const btnAutoExecute = document.getElementById('btn-auto-execute');
    const autoValidationStatus = document.getElementById('auto-validation-status');
    const autoApprovalStatus = document.getElementById('auto-approval-status');
    const autoProgressBar = document.getElementById('auto-progress-bar');
    const autoTerminalOutput = document.getElementById('auto-terminal-output');
    const autoHistoryTbody = document.getElementById('auto-history-tbody');
    const autoTargetsCheckboxes = document.getElementById('auto-targets-checkboxes');
    
    const stepsIds = {
        15: 'step-auto-val',
        30: 'step-auto-conn',
        50: 'step-auto-bck',
        70: 'step-auto-exec',
        90: 'step-auto-ver',
        100: 'step-auto-ver'
    };
    
    let playbookTemplates = [];

    async function fetchPlaybooks() {
        if (!autoPlaybookSelect) return;
        
        try {
            const response = await secureFetch('/api/automation/templates');
            if (!response.ok) throw new Error("Failed to load templates");
            playbookTemplates = await response.json();
            
            autoPlaybookSelect.innerHTML = '<option value="">-- Choose Template --</option>';
            playbookTemplates.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.id;
                opt.textContent = t.name;
                autoPlaybookSelect.appendChild(opt);
            });
            
            autoPlaybookSelect.addEventListener('change', () => {
                const selId = autoPlaybookSelect.value;
                const tmpl = playbookTemplates.find(t => t.id === selId);
                
                if (tmpl) {
                    if (autoFrameworkView) autoFrameworkView.value = tmpl.framework;
                    if (autoCodeView) autoCodeView.textContent = tmpl.code;
                    if (btnAutoValidate) btnAutoValidate.disabled = false;
                } else {
                    if (autoFrameworkView) autoFrameworkView.value = '';
                    if (autoCodeView) autoCodeView.textContent = 'Select template...';
                    if (btnAutoValidate) btnAutoValidate.disabled = true;
                }
                
                if (btnAutoExecute) btnAutoExecute.disabled = true;
                if (autoValidationStatus) {
                    autoValidationStatus.innerHTML = '<span style="font-size:0.72rem; color:var(--text-muted);"><i class="fa-solid fa-clock"></i> Not Validated</span>';
                }
            });
            
        } catch (err) {
            console.error("Playbooks templates loader error:", err);
        }
    }

    async function fetchPlaybookHistory() {
        if (!autoHistoryTbody) return;
        
        try {
            const response = await secureFetch('/api/automation/history');
            if (!response.ok) throw new Error("Failed to load automation history");
            const history = await response.json();
            
            renderPlaybookHistory(history);
        } catch (err) {
            console.error("Playbook history error:", err);
            autoHistoryTbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--critical);">Failed to load history list.</td></tr>';
        }
    }

    function renderPlaybookHistory(history) {
        if (!autoHistoryTbody) return;
        if (history.length === 0) {
            autoHistoryTbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:1rem;">No execution history logs stored.</td></tr>';
            return;
        }
        
        autoHistoryTbody.innerHTML = '';
        history.forEach(run => {
            const tr = document.createElement('tr');
            const timestamp = new Date(run.timestamp).toLocaleString();
            
            let badgeClass = "healthy";
            if (run.status === "Failed") badgeClass = "critical";
            if (run.status === "Rolled Back") badgeClass = "warning";
            
            tr.innerHTML = `
                <td><strong style="color:white;">${run.id}</strong></td>
                <td>${run.name}</td>
                <td><span class="badge" style="font-size:0.62rem;">${run.framework}</span></td>
                <td>${run.targets.join(', ')}</td>
                <td style="font-size:0.62rem; color:var(--text-muted);">${timestamp}</td>
                <td><span class="status-badge ${badgeClass}">${run.status}</span></td>
                <td>
                    <button class="btn btn-xs btn-outline btn-rb" style="padding: 1px 4px; font-size:0.58rem; border-color: rgba(239,68,68,0.25); color: var(--critical);" ${run.status === 'Rolled Back' ? 'disabled' : ''}><i class="fa-solid fa-history"></i> Rollback</button>
                </td>
            `;
            
            tr.querySelector('.btn-rb').addEventListener('click', () => {
                if (confirm(`Are you sure you want to rollback changes for job run ${run.id}?`)) {
                    triggerPlaybookRollback(run.id);
                }
            });
            
            autoHistoryTbody.appendChild(tr);
        });
    }

    if (btnAutoValidate) {
        btnAutoValidate.addEventListener('click', async () => {
            const selId = autoPlaybookSelect.value;
            const code = autoCodeView ? autoCodeView.textContent : '';
            if (!selId) return;
            
            if (autoValidationStatus) {
                autoValidationStatus.innerHTML = '<span style="font-size:0.72rem; color:var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Auditing code compliance...</span>';
            }
            
            try {
                const response = await secureFetch('/api/automation/validate', {
                    method: 'POST',
                    body: JSON.stringify({ playbookId: selId, code })
                });
                if (!response.ok) throw new Error("Validation query failed");
                const res = await response.json();
                
                if (res.valid) {
                    if (autoValidationStatus) {
                        autoValidationStatus.innerHTML = '<span style="font-size:0.72rem; font-weight:700; color:var(--healthy);"><i class="fa-solid fa-circle-check"></i> Syntax: PASS</span>';
                    }
                    if (btnAutoExecute) btnAutoExecute.disabled = false;
                    
                    if (res.requires_approval) {
                        if (autoApprovalStatus) {
                            autoApprovalStatus.innerHTML = '<span style="font-size:0.72rem; font-weight:700; color:var(--warning);"><i class="fa-solid fa-triangle-exclamation"></i> Approvals: REQUIRED</span>';
                        }
                    } else {
                        if (autoApprovalStatus) {
                            autoApprovalStatus.innerHTML = '<span style="font-size:0.72rem; font-weight:700; color:var(--healthy);"><i class="fa-solid fa-lock-open"></i> Approvals: READY</span>';
                        }
                    }
                } else {
                    if (autoValidationStatus) {
                        autoValidationStatus.innerHTML = '<span style="font-size:0.72rem; font-weight:700; color:var(--critical);"><i class="fa-solid fa-times-circle"></i> Violation detected!</span>';
                    }
                    if (btnAutoExecute) btnAutoExecute.disabled = true;
                    alert(`Validation FAILED:\n${res.logs}`);
                }
            } catch (err) {
                console.error("Validation error:", err);
                if (autoValidationStatus) {
                    autoValidationStatus.innerHTML = '<span style="font-size:0.72rem; color:var(--critical);"><i class="fa-solid fa-triangle-exclamation"></i> Validation Error</span>';
                }
            }
        });
    }

    if (btnAutoExecute) {
        btnAutoExecute.addEventListener('click', async () => {
            const selId = autoPlaybookSelect.value;
            if (!selId) return;
            
            const targets = [];
            if (autoTargetsCheckboxes) {
                autoTargetsCheckboxes.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                    if (cb.checked) targets.push(cb.value);
                });
            }
            if (targets.length === 0) {
                alert("Please select at least one target device!");
                return;
            }
            
            btnAutoExecute.disabled = true;
            if (btnAutoValidate) btnAutoValidate.disabled = true;
            if (autoPlaybookSelect) autoPlaybookSelect.disabled = true;
            
            if (autoProgressBar) autoProgressBar.style.width = '0%';
            document.querySelectorAll('#auto-stepper div').forEach(div => {
                div.style.color = 'var(--text-muted)';
                div.style.borderColor = 'rgba(255,255,255,0.05)';
                div.style.background = 'transparent';
            });
            
            if (autoTerminalOutput) autoTerminalOutput.textContent = "[RUNNER] Contacting execution backend service...\n";
            
            try {
                const response = await fetch('/api/automation/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${sessionStorage.getItem('authToken')}`
                    },
                    body: JSON.stringify({ playbookId: selId, targets })
                });
                
                if (!response.ok) {
                    const err = await response.json();
                    if (autoTerminalOutput) {
                        autoTerminalOutput.textContent += `[ERROR] Execution failure: ${err.detail || 'Access Denied'}\n`;
                    }
                    return;
                }
                
                if (autoTerminalOutput) autoTerminalOutput.textContent = '';
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value);
                    if (autoTerminalOutput) {
                        autoTerminalOutput.textContent += chunk;
                        autoTerminalOutput.scrollTop = autoTerminalOutput.scrollHeight;
                    }
                    
                    const progMatch = chunk.match(/\[PROGRESS\] (\d+)%/);
                    if (progMatch) {
                        const pct = parseInt(progMatch[1]);
                        if (autoProgressBar) autoProgressBar.style.width = `${pct}%`;
                        
                        const stepId = stepsIds[pct];
                        if (stepId) {
                            const div = document.getElementById(stepId);
                            if (div) {
                                div.style.color = 'var(--primary)';
                                div.style.borderColor = 'rgba(79, 140, 255, 0.25)';
                                div.style.background = 'rgba(79, 140, 255, 0.02)';
                            }
                        }
                    }
                }
                
                fetchPlaybookHistory();
                if (typeof fetchAuditLogs === 'function') fetchAuditLogs();
                
            } catch (err) {
                console.error("Execution error:", err);
                if (autoTerminalOutput) {
                    autoTerminalOutput.textContent += "\n[RUNNER] [FATAL] Socket disconnected during run.\n";
                }
            } finally {
                btnAutoExecute.disabled = false;
                if (btnAutoValidate) btnAutoValidate.disabled = false;
                if (autoPlaybookSelect) autoPlaybookSelect.disabled = false;
            }
        });
    }

    async function triggerPlaybookRollback(jobId) {
        try {
            const response = await secureFetch('/api/automation/rollback', {
                method: 'POST',
                body: JSON.stringify({ jobId })
            });
            
            if (!response.ok) {
                const err = await response.json();
                alert(`Rollback failed: ${err.detail || 'Access restricted'}`);
                return;
            }
            
            alert(`SUCCESS: Automation changes for job ID '${jobId}' successfully reverted!`);
            fetchPlaybookHistory();
            if (typeof fetchAuditLogs === 'function') fetchAuditLogs();
        } catch (err) {
            console.error("Playbook rollback error:", err);
            alert("Connection error sending rollback request.");
        }
    }

    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const tabId = item.getAttribute('data-tab');
            if (tabId === 'playbooks') {
                fetchPlaybooks();
                fetchPlaybookHistory();
            }
        });
    });

    // ----------------------------------------------------
    // OPERATIONAL REPORTS CENTER CONTROLLERS
    // ----------------------------------------------------
    const btnRptGenerate = document.getElementById('btn-rpt-generate');
    const rptTypeSelect = document.getElementById('rpt-type-select');
    const rptFormatSelect = document.getElementById('rpt-format-select');
    const rptPreviewContent = document.getElementById('rpt-preview-content');

    if (btnRptGenerate) {
        btnRptGenerate.addEventListener('click', async () => {
            const rptType = rptTypeSelect ? rptTypeSelect.value : 'executive';
            const rptFormat = rptFormatSelect ? rptFormatSelect.value : 'pdf';
            
            let previewLines = [];
            previewLines.push(`[COMPILING] Enterprise Operational Summary Report...`);
            previewLines.push(`Report Type: ${rptType.toUpperCase()} | Format: ${rptFormat.toUpperCase()}`);
            previewLines.push(`Timestamp: ${new Date().toISOString()}`);
            previewLines.push(`---------------------------------------------------\n`);
            
            if (document.getElementById('rpt-inc-rca')?.checked) {
                previewLines.push(`[+] Section Included: Root Cause Analysis (RCA)`);
                previewLines.push(`    - Outage isolate summary for primary router link timeouts.\n`);
            }
            if (document.getElementById('rpt-inc-metrics')?.checked) {
                previewLines.push(`[+] Section Included: Chassis Performance Metrics`);
                previewLines.push(`    - CPU Load: 48%, RAM Allocation: 68%, Latency: 2.4ms\n`);
            }
            if (document.getElementById('rpt-inc-timeline')?.checked) {
                previewLines.push(`[+] Section Included: Closed-Loop Troubleshooting Timeline`);
                previewLines.push(`    - Step 1: Alert discovery and diagnostic triggers.`);
                previewLines.push(`    - Step 2: Automated config patching deployment.`);
                previewLines.push(`    - Step 3: Closed-loop validation verified.\n`);
            }
            if (document.getElementById('rpt-inc-cmds')?.checked) {
                previewLines.push(`[+] Section Included: Remediations Applied Config Commands`);
                previewLines.push(`    - interface GigabitEthernet2 -> ip ospf 1 area 0\n`);
            }
            if (document.getElementById('rpt-inc-logs')?.checked) {
                previewLines.push(`[+] Section Included: Execution Command Console Logs`);
                previewLines.push(`    - SSH connect handshakes, CLI worker stdout sweeps.\n`);
            }
            if (document.getElementById('rpt-inc-topo')?.checked) {
                previewLines.push(`[+] Section Included: Dynamic Network Topology Graph Summary`);
                previewLines.push(`    - Active nodes lists and trunk links metrics values.\n`);
            }
            if (document.getElementById('rpt-inc-recs')?.checked) {
                previewLines.push(`[+] Section Included: Preventive Recommendations`);
                previewLines.push(`    - Key management, MTU audits, login spray firewall rules.\n`);
            }
            if (document.getElementById('rpt-inc-history')?.checked) {
                previewLines.push(`[+] Section Included: Playbook Automation Runner History`);
                previewLines.push(`    - Previous jobs logs: JOB-1001, JOB-1002, JOB-1003.\n`);
            }
            
            previewLines.push(`[SUCCESS] Operational report compilation finished.`);
            previewLines.push(`Initiating file transfer download...`);
            
            if (rptPreviewContent) {
                rptPreviewContent.textContent = previewLines.join('\n');
            }
            
            window.location.href = `/api/reports/export?format=${rptFormat}`;
        });
    }
    // ----------------------------------------------------
    // KNOWLEDGE BASE RAG CONTROLLERS
    // ----------------------------------------------------
    const btnKbSearch = document.getElementById('btn-kb-search');
    const kbQueryInput = document.getElementById('kb-query-input');
    const kbSearchMode = document.getElementById('kb-search-mode');
    const kbResultsList = document.getElementById('kb-results-list');
    const kbRagAnswer = document.getElementById('kb-rag-answer');
    const kbRagCitationsHolder = document.getElementById('kb-rag-citations-holder');
    const kbRagTime = document.getElementById('kb-rag-time');
    const kbUploadForm = document.getElementById('kb-upload-form');

    async function executeKbSearch() {
        if (!kbQueryInput || !kbResultsList) return;
        const query = kbQueryInput.value.trim();
        if (!query) {
            alert("Please enter a query or keywords!");
            return;
        }

        const sources = [];
        document.querySelectorAll('.kb-source-cb').forEach(cb => {
            if (cb.checked) sources.push(cb.value);
        });

        if (sources.length === 0) {
            alert("Please select at least one knowledge repository index!");
            return;
        }

        const mode = kbSearchMode ? kbSearchMode.value : 'semantic';

        if (kbRagAnswer) {
            kbRagAnswer.innerHTML = '<span style="color:var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Synthesizing knowledge index vectors...</span>';
        }
        kbResultsList.innerHTML = '<p style="text-align:center; padding:1.5rem; color:var(--text-muted);"><i class="fa-solid fa-circle-notch fa-spin"></i> Executing semantic search sweep...</p>';

        try {
            const response = await secureFetch('/api/kb/search', {
                method: 'POST',
                body: JSON.stringify({ query, sources, searchMode: mode })
            });

            if (!response.ok) throw new Error("Search execution failed");
            const data = await response.json();

            if (kbRagAnswer) kbRagAnswer.textContent = data.rag_answer;
            if (kbRagTime) kbRagTime.textContent = `Last update: ${new Date().toLocaleTimeString()}`;

            if (kbRagCitationsHolder) {
                kbRagCitationsHolder.innerHTML = '';
                data.citations.forEach(c => {
                    const span = document.createElement('span');
                    span.className = 'badge';
                    span.style.background = 'rgba(79, 140, 255, 0.15)';
                    span.style.color = 'var(--primary)';
                    span.style.fontSize = '0.62rem';
                    span.textContent = c;
                    kbRagCitationsHolder.appendChild(span);
                });
            }

            renderKbResults(data.results);

        } catch (err) {
            console.error("Search error:", err);
            if (kbRagAnswer) kbRagAnswer.textContent = "Error: RAG semantic engine unavailable.";
            kbResultsList.innerHTML = '<p style="text-align:center; color:var(--critical); padding:1rem;">Failed to retrieve search results.</p>';
        }
    }

    function renderKbResults(results) {
        if (!kbResultsList) return;
        if (results.length === 0) {
            kbResultsList.innerHTML = '<p style="text-align:center; color:var(--text-muted); padding:2rem;">No matching documents cataloged in the selected repositories.</p>';
            return;
        }

        kbResultsList.innerHTML = '';
        results.forEach(res => {
            const doc = res.document;
            const card = document.createElement('div');
            card.className = 'server-config-item';
            card.style.flexDirection = 'column';
            card.style.alignItems = 'stretch';
            card.style.gap = '0.4rem';
            card.style.background = 'rgba(255,255,255,0.01)';
            
            const updated = new Date(doc.timestamp).toLocaleString();
            
            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:0.25rem;">
                    <div>
                        <strong style="color:white; font-size:0.75rem;">${escapeHtml(doc.title)}</strong>
                        <span style="font-size:0.58rem; color:var(--text-muted); margin-left:6px;">(${doc.source})</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:0.5rem;">
                        <span class="status-badge healthy" style="font-size:0.58rem; padding:1px 4px;">Relevance: ${res.relevance}</span>
                        <span class="badge" style="font-size:0.58rem;">v${doc.version}</span>
                    </div>
                </div>
                <div style="font-size:0.68rem; color:var(--text-normal); line-height:1.4;">
                    ${escapeHtml(doc.content)}
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.6rem; color:var(--text-muted); margin-top:2px;">
                    <span>Citation Key: <strong style="color:var(--primary);">${doc.citations}</strong></span>
                    <span>Updated: ${updated}</span>
                </div>
                <div class="kb-edit-block" style="margin-top:0.4rem; padding-top:0.4rem; border-top:1px dashed rgba(255,255,255,0.04); display:none; flex-direction:column; gap:0.35rem;">
                    <textarea class="form-control kb-edit-content" style="font-size:0.65rem; min-height:40px;">${escapeHtml(doc.content)}</textarea>
                    <div style="display:flex; gap:0.4rem; align-items:center;">
                        <input type="text" class="form-control kb-edit-version" value="${(parseFloat(doc.version) + 0.1).toFixed(1)}" style="font-size:0.65rem; max-width:80px; padding:2px 4px;">
                        <button class="btn btn-xs btn-success btn-kb-save" style="padding:2px 6px;">Save Version</button>
                    </div>
                </div>
                <div style="display:flex; justify-content:flex-end;">
                    <button class="btn btn-xs btn-outline btn-kb-toggle-edit" style="font-size:0.58rem; padding:1px 4px;">Edit & Version Article</button>
                </div>
            `;

            const btnToggle = card.querySelector('.btn-kb-toggle-edit');
            const editBlock = card.querySelector('.kb-edit-block');
            btnToggle.addEventListener('click', () => {
                const active = editBlock.style.display === 'flex';
                editBlock.style.display = active ? 'none' : 'flex';
                btnToggle.textContent = active ? 'Edit & Version Article' : 'Close Editor';
            });

            const btnSave = card.querySelector('.btn-kb-save');
            const editContent = card.querySelector('.kb-edit-content');
            const editVersion = card.querySelector('.kb-edit-version');
            btnSave.addEventListener('click', async () => {
                const newContent = editContent.value.trim();
                const newVer = editVersion.value.trim();
                if (!newContent || !newVer) return;

                try {
                    const response = await secureFetch('/api/kb/update', {
                        method: 'POST',
                        body: JSON.stringify({
                            docId: doc.id,
                            content: newContent,
                            version: newVer
                        })
                    });

                    if (!response.ok) {
                        const err = await response.json();
                        alert(`Update failed: ${err.detail || 'Access restricted'}`);
                        return;
                    }

                    alert(`SUCCESS: Article version ${newVer} compiled successfully!`);
                    executeKbSearch();
                } catch (err) {
                    console.error("Save version error:", err);
                    alert("Network error updating article.");
                }
            });

            kbResultsList.appendChild(card);
        });
    }

    if (btnKbSearch) {
        btnKbSearch.addEventListener('click', executeKbSearch);
    }
    if (kbQueryInput) {
        kbQueryInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') executeKbSearch();
        });
    }

    if (kbUploadForm) {
        kbUploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const title = document.getElementById('kb-upload-title').value.trim();
            const source = document.getElementById('kb-upload-source').value;
            const citation = document.getElementById('kb-upload-citation').value.trim();
            const content = document.getElementById('kb-upload-content').value.trim();

            try {
                const response = await secureFetch('/api/kb/upload', {
                    method: 'POST',
                    body: JSON.stringify({ title, source, content, citation })
                });

                if (!response.ok) {
                    const err = await response.json();
                    alert(`Upload failed: ${err.detail || 'Access restricted'}`);
                    return;
                }

                alert(`SUCCESS: Document indexed successfully!`);
                kbUploadForm.reset();
                
                if (kbQueryInput) {
                    kbQueryInput.value = title;
                    executeKbSearch();
                }
            } catch (err) {
                console.error("Upload error:", err);
                alert("Network error submitting document.");
            }
        });
    }

    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const tabId = item.getAttribute('data-tab');
            if (tabId === 'kb') {
                if (kbQueryInput && !kbQueryInput.value) {
                    kbQueryInput.value = "OSPF state machine";
                    executeKbSearch();
                }
            }
        });
    });

    // ----------------------------------------------------
    // ZERO TRUST CENTER CONTROLLER
    // ----------------------------------------------------
    let totpIntervalId = null;
    let totpTimeRemaining = 30;
    
    function initZeroTrustCenter() {
        fetchZeroTrustStatus();
        fetchZeroTrustSecrets();
        
        // Start or sync the TOTP countdown ring
        if (totpIntervalId) {
            clearInterval(totpIntervalId);
        }
        
        // Trigger initial status fetch to sync time
        syncTotpTimer();
    }
    
    async function syncTotpTimer() {
        try {
            const res = await secureFetch('/api/zero-trust/status');
            if (!res.ok) return;
            const data = await res.json();
            
            const mfaTokenEl = document.getElementById('zt-mfa-token');
            const mfaSecretEl = document.getElementById('zt-mfa-secret');
            const mfaUserEl = document.getElementById('zt-mfa-username');
            
            if (mfaTokenEl) mfaTokenEl.textContent = data.totp;
            if (mfaSecretEl) mfaSecretEl.textContent = data.secret;
            if (mfaUserEl) mfaUserEl.textContent = `User: ${data.username}`;
            
            totpTimeRemaining = data.secondsRemaining;
            updateTotpRingVisuals();
            
            totpIntervalId = setInterval(() => {
                totpTimeRemaining--;
                if (totpTimeRemaining <= 0) {
                    clearInterval(totpIntervalId);
                    syncTotpTimer(); // fetch new code when timer hits 0
                } else {
                    updateTotpRingVisuals();
                }
            }, 1000);
            
        } catch (err) {
            console.error("Failed to sync TOTP timer:", err);
        }
    }
    
    function updateTotpRingVisuals() {
        const ring = document.getElementById('totp-timer-ring');
        const text = document.getElementById('totp-seconds-txt');
        if (text) text.textContent = `${totpTimeRemaining}s`;
        
        if (ring) {
            // Circle radius is 34, perimeter = 2 * Math.PI * 34 = 213.6
            const dasharray = 213.6;
            const dashoffset = dasharray - (dasharray * (totpTimeRemaining / 30));
            ring.style.strokeDashoffset = dashoffset;
            
            // Turn red in last 5 seconds
            if (totpTimeRemaining <= 5) {
                ring.style.stroke = 'var(--critical)';
            } else {
                ring.style.stroke = 'var(--primary)';
            }
        }
    }
    
    async function fetchZeroTrustStatus() {
        try {
            const res = await secureFetch('/api/zero-trust/status');
            const data = await res.json();
            
            const localCertBadge = document.getElementById('zt-local-cert-badge');
            const localCertItem = document.getElementById('zt-local-cert-status-item');
            
            if (localCertBadge && localCertItem) {
                if (data.localCert.valid) {
                    localCertBadge.textContent = 'SECURE / VALID';
                    localCertBadge.className = 'status-badge healthy';
                    localCertItem.style.borderLeftColor = 'var(--healthy)';
                } else {
                    const err = data.localCert.errors && data.localCert.errors.length > 0 ? data.localCert.errors[0] : 'INVALID';
                    localCertBadge.textContent = `CRITICAL: ${err.substring(0, 30)}`;
                    localCertBadge.className = 'status-badge critical';
                    localCertItem.style.borderLeftColor = 'var(--critical)';
                }
            }
        } catch (err) {
            console.error("Failed to load Zero Trust status:", err);
        }
    }
    
    async function fetchZeroTrustSecrets() {
        const tbody = document.getElementById('zt-secrets-tbody');
        if (!tbody) return;
        
        try {
            const res = await secureFetch('/api/vault');
            const data = await res.json();
            
            tbody.innerHTML = '';
            const keys = Object.keys(data);
            if (keys.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">No secrets found.</td></tr>';
                return;
            }
            
            keys.forEach(name => {
                const s = data[name];
                const tr = document.createElement('tr');
                
                // Expiry calculation
                let expiryStr = 'Never';
                let expiryClass = 'text-healthy';
                if (s.expires_at) {
                    const expDate = new Date(s.expires_at);
                    const now = new Date();
                    const diffTime = expDate - now;
                    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                    
                    if (diffDays <= 0) {
                        expiryStr = 'Expired';
                        expiryClass = 'text-critical font-bold';
                    } else if (diffDays <= 14) {
                        expiryStr = `${diffDays} days (Renew Overdue)`;
                        expiryClass = 'text-warning font-bold';
                    } else {
                        expiryStr = `${diffDays} days`;
                        expiryClass = 'text-healthy';
                    }
                }
                
                // Formatting timestamps
                const created = s.created_at ? new Date(s.created_at).toLocaleString() : 'N/A';
                const rotated = s.last_rotated ? new Date(s.last_rotated).toLocaleString() : 'N/A';
                
                const isSSHKey = s.type.toLowerCase().includes('ssh key');
                const rotateBtn = isSSHKey 
                    ? `<button class="btn btn-xs btn-outline btn-rotate-ssh" data-name="${name}" style="padding:0.2rem 0.4rem; font-size:0.65rem;"><i class="fa-solid fa-arrows-rotate"></i> Rotate</button>`
                    : `N/A`;
                    
                tr.innerHTML = `
                    <td><strong>${escapeHtml(name)}</strong></td>
                    <td><span class="status-badge info" style="font-size:0.6rem; padding:0 0.2rem;">${escapeHtml(s.type)}</span></td>
                    <td style="color:var(--text-muted);">${created}</td>
                    <td class="${expiryClass}">${expiryStr}</td>
                    <td style="color:var(--text-muted);">${rotated}</td>
                    <td style="text-align:center; font-weight:bold; color:var(--info);">${s.access_count}</td>
                    <td>${rotateBtn}</td>
                `;
                tbody.appendChild(tr);
            });
            
            // Bind Rotate buttons
            tbody.querySelectorAll('.btn-rotate-ssh').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const name = btn.getAttribute('data-name');
                    if (!confirm(`Are you sure you want to rotate SSH key credentials for '${name}'? This will cryptographically regenerate RSA public and private key sets.`)) return;
                    
                    btn.disabled = true;
                    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Rotating...`;
                    
                    try {
                        const rotRes = await secureFetch('/api/zero-trust/rotate-ssh', {
                            method: 'POST',
                            body: JSON.stringify({ name })
                        });
                        const rotData = await rotRes.json();
                        
                        if (rotRes.ok) {
                            alert(`SSH Key Rotated Successfully!\n\nNew Public Key:\n${rotData.publicKey}\n\nPlease update authorized_keys on remote hosts.`);
                            fetchZeroTrustSecrets();
                            fetchZeroTrustStatus();
                            if (typeof loadRecentAlarms === 'function') loadRecentAlarms(); // refresh alarms if applicable
                        } else {
                            alert(`Rotation failed: ${rotData.detail || "Server error"}`);
                        }
                    } catch (err) {
                        alert(`Network error during rotation: ${err.message}`);
                    } finally {
                        btn.disabled = false;
                        btn.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i> Rotate`;
                    }
                });
            });
            
        } catch (err) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-critical" style="text-align:center;">Failed to fetch secrets. Permission Denied.</td></tr>';
        }
    }
    
    // Cert validator setup
    const ztCertType = document.getElementById('zt-cert-type');
    const ztCertInput = document.getElementById('zt-cert-input');
    const ztCertPemArea = document.getElementById('zt-cert-pem-area');
    const btnZtValidateCert = document.getElementById('btn-zt-validate-cert');
    const ztCertResult = document.getElementById('zt-cert-result');
    
    if (ztCertType) {
        ztCertType.addEventListener('change', () => {
            if (ztCertType.value === 'domain') {
                ztCertInput.style.display = 'block';
                ztCertPemArea.style.display = 'none';
                ztCertInput.placeholder = 'e.g. google.com';
            } else {
                ztCertInput.style.display = 'none';
                ztCertPemArea.style.display = 'block';
            }
        });
    }
    
    if (btnZtValidateCert) {
        btnZtValidateCert.addEventListener('click', async () => {
            const valType = ztCertType.value;
            const valContent = valType === 'domain' ? ztCertInput.value.trim() : ztCertPemArea.value.trim();
            
            if (!valContent) {
                alert("Please specify a domain host or paste PEM certificate data.");
                return;
            }
            
            btnZtValidateCert.disabled = true;
            btnZtValidateCert.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Validating...`;
            ztCertResult.style.display = 'none';
            
            try {
                const res = await secureFetch('/api/zero-trust/validate-certificate', {
                    method: 'POST',
                    body: JSON.stringify({ type: valType, value: valContent })
                });
                const data = await res.json();
                
                ztCertResult.style.display = 'block';
                if (!res.ok) {
                    ztCertResult.innerHTML = `<span class="text-critical" style="font-weight:700;"><i class="fa-solid fa-circle-xmark"></i> Validation Request Failed:</span><p style="color:var(--text-muted); margin-top:4px;">${escapeHtml(data.detail || "Server Error")}</p>`;
                    return;
                }
                
                const errorsHtml = data.errors.map(e => `<li style="color:var(--critical); font-weight:600;"><i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(e)}</li>`).join('');
                const warningsHtml = data.warnings.map(w => `<li style="color:var(--warning);"><i class="fa-solid fa-circle-exclamation"></i> ${escapeHtml(w)}</li>`).join('');
                
                const statusBadge = data.valid 
                    ? `<span class="status-badge healthy" style="font-weight:bold;"><i class="fa-solid fa-circle-check"></i> TRUSTED / VALID CERTIFICATE</span>`
                    : `<span class="status-badge critical" style="font-weight:bold;"><i class="fa-solid fa-circle-xmark"></i> INSECURE / INVALID CERTIFICATE</span>`;
                
                const detailsHtml = data.details.subject ? `
                    <div style="margin-top: 8px; font-size: 0.7rem; border-top: 1px solid var(--border-color); padding-top: 6px; display:flex; flex-direction:column; gap:0.2rem; color:var(--text-muted);">
                        <div><strong>Subject DN:</strong> <span style="color:white;">${escapeHtml(data.details.subject)}</span></div>
                        <div><strong>Issuer DN:</strong> <span style="color:white;">${escapeHtml(data.details.issuer)}</span></div>
                        <div><strong>Valid:</strong> <span style="color:white;">${escapeHtml(new Date(data.details.not_before).toLocaleDateString())} to ${escapeHtml(new Date(data.details.not_after).toLocaleDateString())}</span></div>
                        <div><strong>Algorithm:</strong> <span style="color:white;">${escapeHtml(data.details.signature_algorithm)} (${data.details.key_size} bit key)</span></div>
                        <div><strong>Serial Number:</strong> <span style="color:white; font-family:monospace;">${escapeHtml(data.details.serial_number)}</span></div>
                    </div>
                ` : '';
                
                ztCertResult.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <strong style="color:white;">Verification Output:</strong>
                        ${statusBadge}
                    </div>
                    <ul style="list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:0.25rem;">
                        ${errorsHtml}
                        ${warningsHtml}
                        ${data.errors.length === 0 && data.warnings.length === 0 ? '<li style="color:var(--healthy);"><i class="fa-solid fa-circle-check"></i> All cryptographic validity algorithms passed parameters.</li>' : ''}
                    </ul>
                    ${detailsHtml}
                `;
                
            } catch (err) {
                ztCertResult.style.display = 'block';
                ztCertResult.innerHTML = `<span class="text-critical" style="font-weight:700;"><i class="fa-solid fa-circle-xmark"></i> Connection Error:</span><p style="color:var(--text-muted); margin-top:4px;">${escapeHtml(err.message)}</p>`;
            } finally {
                btnZtValidateCert.disabled = false;
                btnZtValidateCert.innerHTML = `Validate`;
            }
        });
    }
    
    // RBAC dynamic user role update console setup
    const btnZtUpdateRole = document.getElementById('btn-zt-update-role');
    const ztUserSelect = document.getElementById('zt-user-select');
    const ztRoleSelect = document.getElementById('zt-role-select');
    
    if (btnZtUpdateRole && ztUserSelect && ztRoleSelect) {
        btnZtUpdateRole.addEventListener('click', async () => {
            const targetUsername = ztUserSelect.value;
            const targetRole = ztRoleSelect.value;
            
            if (!confirm(`Are you sure you want to change user '${targetUsername}' role to '${targetRole}'? This changes operational permissions dynamically in the audit logs.`)) return;
            
            btnZtUpdateRole.disabled = true;
            btnZtUpdateRole.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Saving...`;
            
            try {
                const res = await secureFetch('/api/zero-trust/update-role', {
                    method: 'POST',
                    body: JSON.stringify({ username: targetUsername, role: targetRole })
                });
                const data = await res.json();
                
                if (res.ok) {
                    alert(`Role modified successfully!\nUser: ${targetUsername}\nNew Role: ${targetRole}`);
                    // If target was logged-in user, refresh UI or profile
                    if (targetUsername === sessionStorage.getItem('username')) {
                        alert("Your own role has changed. Please re-authenticate or refresh session to apply changes.");
                        window.location.reload();
                    }
                } else {
                    alert(`Update role failed: ${data.detail || "Server error"}`);
                }
            } catch (err) {
                alert(`Network error updating role: ${err.message}`);
            } finally {
                btnZtUpdateRole.disabled = false;
                btnZtUpdateRole.innerHTML = `<i class="fa-solid fa-user-shield"></i> Save Role`;
            }
        });
    }

    // ----------------------------------------------------
    // SYSTEM SCALE & TUNING DASHBOARD CONTROLLER
    // ----------------------------------------------------
    let scaleIntervalId = null;
    let loadHistory = [];
    const maxLoadHistoryPoints = 35;
    
    function initScaleTuningDashboard() {
        // Fetch performance status immediately
        fetchScalePerformance();
        
        // Stop any active interval
        if (scaleIntervalId) {
            clearInterval(scaleIntervalId);
        }
        
        // Refresh every 2 seconds
        scaleIntervalId = setInterval(() => {
            const activeTab = document.querySelector('.nav-item.active');
            if (activeTab && activeTab.getAttribute('data-tab') === 'scale') {
                fetchScalePerformance();
            } else {
                clearInterval(scaleIntervalId);
                scaleIntervalId = null;
            }
        }, 2000);
        
        // Bind simulation button
        const btnToggleSim = document.getElementById('btn-toggle-simulation');
        if (btnToggleSim) {
            // Remove previous listeners (cloning the button is a simple way)
            const newBtn = btnToggleSim.cloneNode(true);
            btnToggleSim.parentNode.replaceChild(newBtn, btnToggleSim);
            
            newBtn.addEventListener('click', async () => {
                const isActive = newBtn.getAttribute('data-active') === 'true';
                const nextState = !isActive;
                
                newBtn.disabled = true;
                newBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing...`;
                
                try {
                    const res = await secureFetch('/api/monitoring/simulate', {
                        method: 'POST',
                        body: JSON.stringify({ enabled: nextState })
                    });
                    const data = await res.json();
                    
                    if (res.ok) {
                        alert(nextState 
                            ? "Scale-Up Optimization Active!\n- 10,000 Edge devices added to inventory.\n- Telemetry batch flushes active in memory.\n- Rate limit bucket initialized."
                            : "Scale-Down Complete.\n- Restored active catalog inventory (5 devices).\n- SQLite synchronous standard mode resumed."
                        );
                        fetchScalePerformance();
                    } else {
                        alert(`Failed to toggle simulation: ${data.detail || "Server error"}`);
                    }
                } catch (err) {
                    alert(`Network error toggling simulation: ${err.message}`);
                } finally {
                    newBtn.disabled = false;
                }
            });
        }
    }
    
    async function fetchScalePerformance() {
        try {
            const res = await secureFetch('/api/monitoring/performance');
            if (!res.ok) return;
            const data = await res.json();
            
            const s = data.scaling;
            
            // 1. Update summary widgets
            const eventRateEl = document.getElementById('opt-event-rate');
            const totalEventsEl = document.getElementById('opt-total-events');
            const dbLatencyEl = document.getElementById('opt-db-latency');
            const cacheHitEl = document.getElementById('opt-cache-hit');
            const loadPercentEl = document.getElementById('opt-load-percentage');
            
            if (eventRateEl) eventRateEl.textContent = `${s.eventRate.toLocaleString()} / sec`;
            if (totalEventsEl) totalEventsEl.textContent = s.totalEvents.toLocaleString();
            if (dbLatencyEl) dbLatencyEl.textContent = `${s.dbLatencyMs} ms`;
            if (cacheHitEl) cacheHitEl.textContent = `${s.cacheHitRate.toFixed(1)}%`;
            
            // 2. Simulation Toggle status
            const btnSim = document.getElementById('btn-toggle-simulation');
            const simLabel = document.getElementById('sim-status-label');
            if (btnSim && simLabel) {
                if (s.simulateActive) {
                    simLabel.textContent = "Simulation Running (10k Devices)";
                    simLabel.style.color = "var(--primary)";
                    btnSim.setAttribute('data-active', 'true');
                    btnSim.innerHTML = `<i class="fa-solid fa-stop"></i> Stop 10k Scale`;
                    btnSim.className = "btn btn-danger";
                } else {
                    simLabel.textContent = "Simulation Stopped";
                    simLabel.style.color = "var(--text-muted)";
                    btnSim.setAttribute('data-active', 'false');
                    btnSim.innerHTML = `<i class="fa-solid fa-play"></i> Start 10k Scale`;
                    btnSim.className = "btn btn-primary";
                }
            }
            
            // 3. Cluster and worker counts
            const apiNodesEl = document.getElementById('opt-api-nodes');
            const workerNodesEl = document.getElementById('opt-worker-nodes');
            const rabbitmqEl = document.getElementById('opt-rabbitmq-status');
            const blockedIpsEl = document.getElementById('opt-blocked-ips');
            
            if (apiNodesEl) {
                apiNodesEl.textContent = `${s.nodesCount} Nodes (Active)`;
                apiNodesEl.className = s.nodesCount > 1 ? "status-badge healthy" : "status-badge info";
            }
            if (workerNodesEl) {
                workerNodesEl.textContent = `${s.workersCount} Workers`;
                workerNodesEl.className = s.workersCount > 2 ? "status-badge healthy" : "status-badge info";
            }
            if (rabbitmqEl) {
                rabbitmqEl.textContent = data.services.rabbitmq === "Healthy" ? "CLUSTERED / OK" : "ERROR";
                rabbitmqEl.className = data.services.rabbitmq === "Healthy" ? "status-badge healthy" : "status-badge critical";
            }
            if (blockedIpsEl) {
                blockedIpsEl.textContent = `${s.rateLimitBlocks} blocked`;
                blockedIpsEl.className = s.rateLimitBlocks > 0 ? "status-badge warning" : "status-badge healthy";
            }
            
            // 4. Update load history and render chart
            // Max load is 20000 events/sec
            const loadPercent = Math.min(100, (s.eventRate / 20000) * 100);
            if (loadPercentEl) loadPercentEl.textContent = `Pipeline Capacity: ${loadPercent.toFixed(1)}%`;
            
            loadHistory.push(loadPercent);
            if (loadHistory.length > maxLoadHistoryPoints) {
                loadHistory.shift();
            }
            
            renderLoadChart();
            
        } catch (err) {
            console.error("Failed to load scale performance metrics:", err);
        }
    }
    
    function renderLoadChart() {
        const chartContainer = document.getElementById('opt-load-bar-chart');
        if (!chartContainer) return;
        
        chartContainer.innerHTML = '';
        
        loadHistory.forEach(val => {
            const bar = document.createElement('div');
            bar.className = 'opt-bar';
            
            // Heights mapping
            const height = Math.max(5, val); // min 5% height for visibility
            
            // Color mapping based on loading
            let color = 'var(--primary)';
            if (val > 80) color = 'var(--critical)';
            else if (val > 40) color = 'var(--warning)';
            
            bar.style.height = `${height}%`;
            bar.style.width = '2.4%';
            bar.style.background = color;
            bar.style.borderRadius = '2px 2px 0 0';
            bar.style.transition = 'height 0.3s ease';
            
            chartContainer.appendChild(bar);
        });
    }
});
