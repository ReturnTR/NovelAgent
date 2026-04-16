const API_URL = (window.location.port === '8000') 
    ? '/chat/stream' 
    : `http://${window.location.hostname}:8000/chat/stream`;

const AGENTS_API = (window.location.port === '8000') 
    ? '/api/agents' 
    : `http://${window.location.hostname}:8000/api/agents`;

const API_BASE = (window.location.port === '8000') 
    ? '' 
    : `http://${window.location.hostname}:8000`;

let messages = [];
let isStreaming = false;
let currentAssistantMessage = null;
let currentAgentType = 'supervisor';
let currentSessionId = null;

// 通知系统
function showNotification(message, type = 'info') {
    // 创建通知元素
    let notification = document.getElementById('notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'notification';
        notification.className = 'notification';
        document.querySelector('.header').appendChild(notification);
    }

    // 设置消息和类型
    notification.textContent = message;
    notification.className = `notification ${type}`;

    // 显示通知
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);

    // 3秒后隐藏
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.textContent = '';
        }, 300);
    }, 3000);
}

// 主题切换功能
function initThemeToggle() {
    const themeToggle = document.getElementById('themeToggle');
    
    // 加载保存的主题
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-theme');
        updateThemeIcon(true);
    }

    // 主题切换事件
    themeToggle.addEventListener('click', () => {
        const isDark = document.body.classList.toggle('dark-theme');
        updateThemeIcon(isDark);
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
    });

    // 更新主题图标
    function updateThemeIcon(isDark) {
        const themeToggle = document.getElementById('themeToggle');
        if (isDark) {
            // 切换到月亮图标
            themeToggle.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                </svg>
            `;
        } else {
            // 切换到太阳图标
            themeToggle.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="5"></circle>
                    <line x1="12" y1="1" x2="12" y2="3"></line>
                    <line x1="12" y1="21" x2="12" y2="23"></line>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                    <line x1="1" y1="12" x2="3" y2="12"></line>
                    <line x1="21" y1="12" x2="23" y2="12"></line>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                </svg>
            `;
        }
    }
}

console.log('App.js loaded, API_URL:', API_URL);

function formatUpdateTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${year}-${month}-${day}-${hours}-${minutes}-${seconds}`;
}

marked.setOptions({
    highlight: function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            return hljs.highlight(code, { language: lang }).value;
        }
        return hljs.highlightAuto(code).value;
    },
    breaks: true,
    gfm: true
});

function renderMarkdown(content) {
    return marked.parse(content);
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

async function loadAgents() {
    try {
        const response = await fetch(AGENTS_API);
        const data = await response.json();
        
        const agentList = document.getElementById('agentList');
        agentList.innerHTML = '';
        
        data.agents.forEach(agent => {
            const agentItem = document.createElement('div');
            const isActive = agent.status === 'active';
            agentItem.className = `agent-item ${isActive ? 'agent-active' : 'agent-inactive'} ${agent.session_id === currentSessionId ? 'active' : ''}`;
            agentItem.dataset.sessionId = agent.session_id;
            agentItem.dataset.agentType = agent.agent_type;
            agentItem.dataset.agentStatus = agent.status;
            
            const statusDot = agent.status === 'active' ? '●' : '○';
            
            agentItem.innerHTML = `
                <div class="agent-info" onclick="switchAgent('${agent.session_id}')">
                    <div class="agent-name" ondblclick="startEditAgentName(event, '${agent.session_id}', '${agent.agent_name}')">${agent.agent_name}</div>
                    <div class="agent-type">${agent.agent_type.charAt(0).toUpperCase() + agent.agent_type.slice(1)}</div>
                </div>
                <div class="agent-actions">
                    ${agent.updated_at ? `<div class="agent-time">${formatUpdateTime(agent.updated_at)}</div>` : ''}
                    <button class="agent-menu-btn" onclick="toggleAgentMenu(event, '${agent.session_id}', '${agent.status}', '${agent.agent_name}')">...</button>
                </div>
                <span class="status-dot ${agent.status}">${statusDot}</span>
            `;
            
            agentList.appendChild(agentItem);
        });
    } catch (error) {
        console.error('加载Agent列表失败:', error);
        document.getElementById('agentList').innerHTML = '<div class="error">加载失败</div>';
    }
}

async function switchAgent(sessionId) {
    if (sessionId === currentSessionId) {
        return;
    }
    
    const editingInputs = document.querySelectorAll('.agent-name input');
    if (editingInputs.length > 0) {
        return;
    }
    
    currentSessionId = sessionId;
    messages = [];
    
    const currentAgentItem = document.querySelector(`.agent-item[data-session-id="${sessionId}"]`);
    const agentType = currentAgentItem ? currentAgentItem.dataset.agentType : 'unknown';
    
    document.getElementById('currentAgentTitle').textContent = 
        `${agentType.charAt(0).toUpperCase() + agentType.slice(1)} Agent`;
    
    try {
        const response = await fetch(`${API_BASE}/api/sessions/${sessionId}`);
        if (response.ok) {
            const sessionData = await response.json();
            currentAgentType = sessionData.metadata.agent_type;
            messages = sessionData.messages || [];
            
            const chatContainer = document.getElementById('chatContainer');
            chatContainer.innerHTML = '';
            
            if (messages.length > 0) {
                messages.forEach(msg => {
                    addMessage(msg.role, msg.content, msg.tool_calls, msg.tool_results);
                });
            } else {
                chatContainer.innerHTML = `
                    <div class="welcome-message">
                        <h2>已切换到 ${sessionData.metadata.agent_name}</h2>
                        <p>你可以开始与这个Agent对话了。</p>
                    </div>
                `;
            }
            
            console.log('Session loaded from backend:', sessionId);
        } else {
            console.error('Failed to load session from backend');
            document.getElementById('chatContainer').innerHTML = `
                <div class="welcome-message">
                    <h2>会话加载失败</h2>
                    <p>请重试。</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading session:', error);
        document.getElementById('chatContainer').innerHTML = `
            <div class="welcome-message">
                <h2>会话加载失败</h2>
                <p>请检查网络连接。</p>
            </div>
        `;
    }
    
    loadAgents();
}

function refreshAgents() {
    loadAgents();
}

function openCreateAgentDialog() {
    document.getElementById('createAgentModal').classList.add('show');
    document.getElementById('agentNameInput').value = '';
    document.getElementById('agentTypeSelect').value = 'character';
    document.getElementById('agentNameInput').focus();
}

function closeCreateAgentDialog() {
    document.getElementById('createAgentModal').classList.remove('show');
}

function startEditAgentName(event, sessionId, currentName) {
    // 阻止事件冒泡，防止触发父元素的click事件
    event.stopPropagation();
    event.preventDefault();

    const agentInfo = event.target.closest('.agent-info');
    const agentNameElement = agentInfo.querySelector('.agent-name');

    // 保存原始名字，用于取消编辑
    agentNameElement.dataset.originalName = currentName;

    // 替换为输入框
    agentNameElement.innerHTML = `
        <input type="text" value="${currentName}" style="flex: 1; padding: 4px 8px; border: 1px solid #667eea; border-radius: 4px; font-size: 14px; font-weight: 500;"
               onblur="saveAgentName('${sessionId}')"
               onkeydown="if(event.key === 'Enter') { saveAgentName('${sessionId}'); } else if(event.key === 'Escape') { cancelEditAgentName('${sessionId}'); }">
    `;

    // 聚焦输入框
    setTimeout(() => {
        const input = agentNameElement.querySelector('input');
        if (input) {
            input.focus();
            input.select();
        }
    }, 0);
}

async function saveAgentName(sessionId) {
    loadAgents();
}

function cancelEditAgentName(sessionId) {
    loadAgents();
}

async function createAgent() {
    const agentName = document.getElementById('agentNameInput').value.trim();
    const agentType = document.getElementById('agentTypeSelect').value;
    
    if (!agentName) {
        showNotification('请输入Agent名称', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${AGENTS_API}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                agent_name: agentName,
                agent_type: agentType
            })
        });
        
        if (response.ok) {
            showNotification(`${agentName} 创建成功`, 'success');
            closeCreateAgentDialog();
            loadAgents();
        } else {
            const error = await response.json();
            showNotification(`${agentName} 创建失败: ${error.detail}`, 'error');
        }
    } catch (error) {
        console.error('创建Agent失败:', error);
        showNotification(`${agentName} 创建失败: ${error.message}`, 'error');
    }
}

async function sendMessage() {
    console.log('sendMessage called');
    
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    console.log('Message:', message);
    
    if (!message || isStreaming) {
        console.log('Empty message or already streaming');
        return;
    }
    
    messages.push({ role: 'user', content: message });
    addMessage('user', message);
    
    // 用户消息由服务器端保存
    
    input.value = '';
    isStreaming = true;
    updateStatus(true);
    disableInput(true);
    
    currentAssistantMessage = { role: 'assistant', content: '', toolCalls: [], toolResults: [] };
    messages.push(currentAssistantMessage);
    const messageElement = addMessage('assistant', '');
    
    try {
        console.log('Sending request to:', API_URL);

        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                history: messages.slice(0, -1).map(msg => {
                    const item = { role: msg.role };

                    if (msg.role === 'user') {
                        item.content = msg.content;
                    }
                    else if (msg.role === 'assistant') {
                        item.content = msg.content;
                        if (msg.toolCalls && msg.toolCalls.length > 0) {
                            item.tool_calls = msg.toolCalls;
                        }
                    }
                    else if (msg.role === 'tool') {
                        item.content = msg.content;
                        item.tool_call_id = msg.tool_call_id;
                    }

                    return item;
                }),
                session_id: currentSessionId
            })
        });
        
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Error response:', errorText);
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    try {
                        const parsed = JSON.parse(data);
                        
                        // 处理不同类型的 SSE 事件
                    if (parsed.type === 'content') {
                        // AI 普通回复内容
                        currentAssistantMessage.content += parsed.content;
                        updateMessageContent(messageElement, currentAssistantMessage.content);
                    }
                    else if (parsed.type === 'tool_call') {
                        // AI 请求调用工具
                        console.log('Tool call:', parsed.tool_calls);
                        currentAssistantMessage.toolCalls = parsed.tool_calls;
                        addToolCallUI(messageElement, parsed.tool_calls);
                    }
                    else if (parsed.type === 'tool_result') {
                        // 工具执行结果
                        console.log('Tool result:', parsed);
                        const toolResult = {
                            tool_call_id: parsed.tool_call_id,
                            content: parsed.content
                        };
                        currentAssistantMessage.toolResults.push(toolResult);
                        // 创建独立的 tool 消息
                        const toolMessage = {
                            role: 'tool',
                            content: parsed.content,
                            tool_call_id: parsed.tool_call_id
                        };
                        messages.push(toolMessage);
                        updateToolResultUI(messageElement, parsed.tool_call_id, parsed.content);
                    }
                    else if (parsed.type === 'error') {
                        console.error('Stream error:', parsed.error);
                        currentAssistantMessage.content = `错误: ${parsed.error}`;
                        updateMessageContent(messageElement, currentAssistantMessage.content);
                    }
                    else {
                        // 未知类型，记录日志但不显示错误
                        console.log('Unknown event type:', parsed.type, parsed);
                    }
                    } catch (e) {
                        console.error('Parse error:', e, data);
                    }
                }
            }
        }
        
    } catch (error) {
        console.error('Request failed:', error);
        currentAssistantMessage.content = `请求失败: ${error.message}`;
        updateMessageContent(messageElement, currentAssistantMessage.content);
    } finally {
        isStreaming = false;
        updateStatus(false);
        disableInput(false);
    }
}

function addMessage(role, content, toolCalls, toolResults) {
    const container = document.getElementById('chatContainer');
    
    const welcomeMessage = container.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = role === 'user' ? '👤' : '🤖';
    
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    
    if (role === 'user') {
        bubble.textContent = content;
    } else if (role === 'tool') {
        // Tool 消息添加折叠功能
        bubble.innerHTML = `
            <div class="tool-message-header">
                <span class="tool-icon">🔧</span>
                <span class="tool-message-title">工具执行结果</span>
                <span class="tool-toggle" onclick="toggleToolResult(this)">▼</span>
            </div>
            <div class="tool-message-content" style="display: none;">
                ${content}
            </div>
        `;
    } else {
        bubble.innerHTML = renderMarkdown(content || '思考中...');
    }
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(bubble);
    container.appendChild(messageDiv);
    
    // 处理工具调用
    if (toolCalls && Array.isArray(toolCalls) && toolCalls.length > 0) {
        addToolCallUI(messageDiv, toolCalls);
        
        // 处理工具结果
        if (toolResults && Array.isArray(toolResults) && toolResults.length > 0) {
            toolResults.forEach(result => {
                updateToolResultUI(messageDiv, result.tool_call_id, result.content);
            });
        }
    }
    
    container.scrollTop = container.scrollHeight;
    
    return messageDiv;
}

function updateMessageContent(messageElement, content) {
    const bubble = messageElement.querySelector('.bubble');
    if (bubble) {
        bubble.innerHTML = renderMarkdown(content);
    }
    
    const container = document.getElementById('chatContainer');
    container.scrollTop = container.scrollHeight;
}

// 添加工具调用 UI
function addToolCallUI(messageElement, toolCalls) {
    const bubble = messageElement.querySelector('.bubble');
    if (!bubble) return;
    
    // 创建工具调用容器
    const toolContainer = document.createElement('div');
    toolContainer.className = 'tool-calls-container';
    
    toolCalls.forEach(toolCall => {
        try {
            const toolId = toolCall.id || `tool-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            const toolName = toolCall.name || 'unknown-tool';
            const toolArgs = toolCall.arguments || {};
            
            const toolDiv = document.createElement('div');
            toolDiv.className = 'tool-call-item';
            toolDiv.id = `tool-call-${toolId}`;
            toolDiv.innerHTML = `
                <div class="tool-call-header">
                    <span class="tool-icon">🔧</span>
                    <span class="tool-name">${toolName}</span>
                    <span class="tool-status">执行中...</span>
                </div>
                <div class="tool-call-args">
                    <pre>${JSON.stringify(toolArgs, null, 2)}</pre>
                </div>
                <div class="tool-call-result" style="display: none;">
                    <div class="tool-result-toggle">▲ 查看结果</div>
                    <div class="tool-result-content"></div>
                </div>
            `;
            const resultDiv = toolDiv.querySelector('.tool-call-result');
            const toggleBtn = resultDiv.querySelector('.tool-result-toggle');
            toggleBtn.onclick = () => {
                const isHidden = resultDiv.style.display === 'none';
                resultDiv.style.display = isHidden ? 'block' : 'none';
                toggleBtn.textContent = isHidden ? '▲ 隐藏结果' : '▼ 查看结果';
            };
            toolContainer.appendChild(toolDiv);
        } catch (error) {
            console.error('Error rendering tool call:', error, toolCall);
        }
    });
    
    bubble.appendChild(toolContainer);
    
    const container = document.getElementById('chatContainer');
    container.scrollTop = container.scrollHeight;
}

// 更新工具执行结果 UI
function updateToolResultUI(messageElement, toolCallId, result) {
    try {
        if (!messageElement || !toolCallId) return;
        
        const toolDiv = messageElement.querySelector(`#tool-call-${toolCallId}`);
        if (!toolDiv) return;
        
        const statusSpan = toolDiv.querySelector('.tool-status');
        const resultDiv = toolDiv.querySelector('.tool-call-result');
        const resultContent = toolDiv.querySelector('.tool-result-content');
        
        if (!statusSpan || !resultDiv || !resultContent) return;
        
        // 更新状态
        statusSpan.textContent = '已完成';
        statusSpan.className = 'tool-status completed';
        
        // 显示结果
        try {
            const parsedResult = JSON.parse(result);
            const highlightedJson = syntaxHighlightJson(parsedResult);
            resultContent.innerHTML = `<pre>${highlightedJson}</pre>`;
        } catch (e) {
            resultContent.textContent = result || '无结果';
        }
        
        const container = document.getElementById('chatContainer');
        container.scrollTop = container.scrollHeight;
    } catch (error) {
        console.error('Error updating tool result:', error);
    }
}

// 切换工具结果的显示/隐藏
function toggleToolResult(toggleBtn) {
    const contentDiv = toggleBtn.closest('.tool-message-header').nextElementSibling;
    const isHidden = contentDiv.style.display === 'none';
    contentDiv.style.display = isHidden ? 'block' : 'none';
    toggleBtn.textContent = isHidden ? '▲' : '▼';
}

function syntaxHighlightJson(obj) {
    const json = JSON.stringify(obj, null, 2);
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        let cls = 'json-number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'json-key';
                match = match.slice(0, -1) + '</span>:';
                return `<span class="${cls}">${match}`;
            } else {
                cls = 'json-string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'json-boolean';
        } else if (/null/.test(match)) {
            cls = 'json-null';
        }
        return `<span class="${cls}">${match}</span>`;
    });
}

function updateStatus(streaming) {
    const status = document.getElementById('status');
    if (streaming) {
        status.textContent = '● 处理中...';
        status.className = 'status streaming';
    } else {
        status.textContent = '● 就绪';
        status.className = 'status';
    }
}

function disableInput(disabled) {
    const input = document.getElementById('messageInput');
    const button = document.getElementById('sendButton');
    
    input.disabled = disabled;
    button.disabled = disabled;
}

function toggleAgentMenu(event, sessionId, status, agentName) {
    event.stopPropagation();

    // 移除其他所有打开的菜单
    document.querySelectorAll('.agent-dropdown').forEach(menu => {
        menu.remove();
    });

    // 创建下拉菜单
    const dropdown = document.createElement('div');
    dropdown.className = 'agent-dropdown show';

    // 根据状态显示不同的选项
    if (status === 'active') {
        dropdown.innerHTML = `
            <div class="agent-dropdown-item suspend" onclick="suspendAgent('${sessionId}', '${agentName}')">挂起</div>
            <div class="agent-dropdown-item delete" onclick="deleteAgent('${sessionId}', '${agentName}')">删除</div>
        `;
    } else {
        dropdown.innerHTML = `
            <div class="agent-dropdown-item resume" onclick="resumeAgent('${sessionId}', '${agentName}')">恢复</div>
            <div class="agent-dropdown-item delete" onclick="deleteAgent('${sessionId}', '${agentName}')">删除</div>
        `;
    }

    // 将菜单添加到文档根级别
    document.body.appendChild(dropdown);

    // 定位下拉菜单
    const button = event.target;
    const buttonRect = button.getBoundingClientRect();
    dropdown.style.position = 'fixed';
    dropdown.style.right = `${window.innerWidth - buttonRect.right}px`;
    dropdown.style.top = `${buttonRect.bottom + window.scrollY}px`;
    dropdown.style.zIndex = '1000';

    // 点击其他地方关闭菜单
    setTimeout(() => {
        document.addEventListener('click', closeAgentMenu);
    }, 0);
}

function closeAgentMenu() {
    document.querySelectorAll('.agent-dropdown').forEach(menu => {
        menu.remove();
    });
    document.removeEventListener('click', closeAgentMenu);
}

async function suspendAgent(sessionId, agentName) {
    closeAgentMenu();

    try {
        const response = await fetch(`${API_BASE}/api/agents/${sessionId}/suspend`, {
            method: 'POST'
        });

        if (response.ok) {
            showNotification(`${agentName} 已挂起`, 'info');
            loadAgents();
        } else {
            const error = await response.json();
            showNotification(`${agentName} 挂起失败: ${error.detail}`, 'error');
        }
    } catch (error) {
        console.error('挂起Agent失败:', error);
        showNotification(`${agentName} 挂起失败: ${error.message}`, 'error');
    }
}

async function resumeAgent(sessionId, agentName) {
    closeAgentMenu();

    try {
        const response = await fetch(`${API_BASE}/api/agents/${sessionId}/resume`, {
            method: 'POST'
        });

        if (response.ok) {
            showNotification(`${agentName} 已恢复`, 'success');
            loadAgents();
        } else {
            const error = await response.json();
            showNotification(`${agentName} 恢复失败: ${error.detail}`, 'error');
        }
    } catch (error) {
        console.error('恢复Agent失败:', error);
        showNotification(`${agentName} 恢复失败: ${error.message}`, 'error');
    }
}

async function deleteAgent(sessionId, agentName) {
    closeAgentMenu();

    if (!confirm(`确定要删除 ${agentName} 吗？此操作不可恢复！`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/agents/${sessionId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showNotification(`${agentName} 已删除`, 'info');
            loadAgents();
            if (currentSessionId === sessionId) {
                currentSessionId = null;
                messages = [];
                document.getElementById('chatContainer').innerHTML = `
                    <div class="welcome-message">
                        <h2>Agent 已删除</h2>
                        <p>请选择一个Agent开始对话。</p>
                    </div>
                `;
            }
        } else {
            const error = await response.json();
            showNotification(`${agentName} 删除失败: ${error.detail}`, 'error');
        }
    } catch (error) {
        console.error('删除Agent失败:', error);
        showNotification(`${agentName} 删除失败: ${error.message}`, 'error');
    }
}

document.addEventListener('DOMContentLoaded', async function() {
    await loadAgents();

    const firstAgent = document.querySelector('.agent-item');
    if (firstAgent) {
        switchAgent(firstAgent.dataset.sessionId);
    }

    // 初始化主题切换
    initThemeToggle();

    // 初始化调整大小功能
    initResize();
});

function initResize() {
    const resizeHandle = document.getElementById('resizeHandle');
    const sidebar = document.querySelector('.sidebar');
    let isResizing = false;

    if (!resizeHandle || !sidebar) {
        return;
    }

    function startResize(e) {
        isResizing = true;
        resizeHandle.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    }

    function resize(e) {
        if (!isResizing) return;

        const container = document.querySelector('.app-container');
        if (!container) return;

        const containerRect = container.getBoundingClientRect();
        const sidebarWidth = e.clientX - containerRect.left;

        if (sidebarWidth > 150 && sidebarWidth < containerRect.width - 200) {
            sidebar.style.width = sidebarWidth + 'px';
        }
    }

    function stopResize() {
        if (isResizing) {
            isResizing = false;
            resizeHandle.classList.remove('dragging');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    }

    resizeHandle.addEventListener('mousedown', startResize);
    document.addEventListener('mousemove', resize);
    document.addEventListener('mouseup', stopResize);
    document.addEventListener('mouseleave', stopResize);
}
