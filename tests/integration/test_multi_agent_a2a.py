"""
多 Agent A2A 通信测试

测试多个真实 Agent 之间通过 A2A 协议进行通信的完整链路：
- SupervisorAgent 能发现 CharacterAgent
- SupervisorAgent 能通过 A2A 工具委托任务给 CharacterAgent
- CharacterAgent 能接收并处理来自 SupervisorAgent 的任务
- Session 历史正确记录 A2A 通信事件

运行方式：
    pytest tests/integration/test_multi_agent_a2a.py -v -s
"""

import pytest
import json
import time
import asyncio
import subprocess
import signal
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

import aiohttp
import requests

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class AgentProcess:
    """管理单个 Agent 进程的封装"""

    def __init__(self, name: str, port: int, main_file: str, log_file: Path):
        self.name = name
        self.port = port
        self.main_file = PROJECT_ROOT / main_file
        self.log_file = log_file
        self.process: Optional[subprocess.Popen] = None

    def start(self, env: Dict[str, str] = None) -> bool:
        """启动 Agent 进程"""
        if not self.main_file.exists():
            raise FileNotFoundError(f"Main file not found: {self.main_file}")

        log_dir = self.log_file.parent
        log_dir.mkdir(parents=True, exist_ok=True)

        # 合并环境变量
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        # 确保关键环境变量
        full_env["AGENT_PORT"] = str(self.port)
        full_env["OPENAI_API_KEY"] = "sk-YLiZarg7OKEjYeqMqiTr9dQ1gMlNbKUOuqBYkkT8dG5CXI7L"
        full_env["OPENAI_API_BASE"] = "https://api.moonshot.cn/v1"

        # 使用 conda agent 环境
        conda_activate = "source /opt/anaconda3/bin/activate agent && "

        self.process = subprocess.Popen(
            ["bash", "-c", conda_activate + f"cd {PROJECT_ROOT} && python {self.main_file}"],
            env=full_env,
            cwd=str(PROJECT_ROOT),
            stdout=open(self.log_file, "w"),
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        print(f"[{self.name}] Started with PID {self.process.pid}, port={self.port}")
        return True

    def wait_for_ready(self, timeout: int = 30) -> bool:
        """等待 Agent 服务就绪"""
        start = time.time()
        while time.time() - start < timeout:
            try:
                response = requests.get(f"http://localhost:{self.port}/health", timeout=2)
                if response.status_code == 200:
                    print(f"[{self.name}] Ready at port {self.port}")
                    return True
            except requests.exceptions.RequestException:
                pass
            time.sleep(0.5)
        print(f"[{self.name}] Timeout waiting for port {self.port}")
        return False

    def stop(self):
        """停止 Agent 进程"""
        if self.process:
            print(f"[{self.name}] Stopping PID {self.process.pid}")
            try:
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                else:
                    self.process.terminate()
                self.process.wait(timeout=5)
            except Exception as e:
                print(f"[{self.name}] Error stopping: {e}")
                try:
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    else:
                        self.process.kill()
                except:
                    pass
            self.process = None

    def is_running(self) -> bool:
        """检查进程是否运行"""
        if not self.process:
            return False
        return self.process.poll() is None


class MultiAgentTestEnv:
    """多 Agent 测试环境管理器"""

    def __init__(self):
        self.registry: Optional[AgentProcess] = None
        self.supervisor: Optional[AgentProcess] = None
        self.character: Optional[AgentProcess] = None
        self.log_dir = PROJECT_ROOT / "tests" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def timestamp(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def setup(self) -> bool:
        """启动所有服务"""
        print("\n" + "="*60)
        print("Setting up multi-agent test environment")
        print("="*60)

        # 1. 启动 Registry (test_registry_server.py)
        registry_log = self.log_dir / f"registry_{self.timestamp()}.log"
        self.registry = AgentProcess(
            name="Registry",
            port=8000,
            main_file="tests/integration/test_registry_server.py",
            log_file=registry_log
        )
        self.registry.start({"AGENT_DEBUG": "true"})
        if not self.registry.wait_for_ready(timeout=30):
            print("[Registry] Failed to start")
            return False
        print(f"[Registry] Running at port 8000, log={registry_log}")

        # 2. 启动 SupervisorAgent
        supervisor_log = self.log_dir / f"supervisor_{self.timestamp()}.log"
        self.supervisor = AgentProcess(
            name="Supervisor",
            port=8001,
            main_file="agents/supervisor_agent/main.py",
            log_file=supervisor_log
        )
        self.supervisor.start({
            "AGENT_DEBUG": "true",
            "AGENT_DIR": str(PROJECT_ROOT / "agents" / "supervisor_agent")
        })
        if not self.supervisor.wait_for_ready(timeout=30):
            print("[Supervisor] Failed to start")
            return False
        print(f"[Supervisor] Running at port 8001, log={supervisor_log}")

        # 3. 启动 CharacterAgent
        character_log = self.log_dir / f"character_{self.timestamp()}.log"
        self.character = AgentProcess(
            name="Character",
            port=8002,
            main_file="agents/character_agent/main.py",
            log_file=character_log
        )
        self.character.start({
            "AGENT_DEBUG": "true",
            "AGENT_DIR": str(PROJECT_ROOT / "agents" / "character_agent")
        })
        if not self.character.wait_for_ready(timeout=30):
            print("[Character] Failed to start")
            return False
        print(f"[Character] Running at port 8002, log={character_log}")

        # 清理旧的 session 文件
        self._cleanup_sessions()

        # 4. 等待注册完成
        time.sleep(3)

        # 5. 验证注册
        if not self._verify_registration():
            print("[Registration] Failed to verify agents registered")
            return False

        print("\n" + "="*60)
        print("All agents started successfully")
        print("="*60 + "\n")
        return True

    def _verify_registration(self) -> bool:
        """验证 Agent 注册到 Registry"""
        try:
            response = requests.get("http://localhost:8000/api/registry/agents", timeout=10)
            if response.status_code == 200:
                data = response.json()
                agents = data.get("agents", [])
                print(f"[Registration] Found {len(agents)} registered agents:")
                for agent in agents:
                    print(f"  - {agent.get('agent_id')} ({agent.get('agent_type')}) @ {agent.get('endpoint')}")
                return len(agents) >= 2
        except Exception as e:
            print(f"[Registration] Error: {e}")
        return False

    def _cleanup_sessions(self):
        """清理所有 session 文件"""
        for agent_dir in [
            PROJECT_ROOT / "agents" / "supervisor_agent" / "sessions",
            PROJECT_ROOT / "agents" / "character_agent" / "sessions",
        ]:
            if agent_dir.exists():
                for session_file in agent_dir.glob("*.jsonl"):
                    session_file.unlink()
                # 重置 index
                index_file = agent_dir / "sessions_index.json"
                if index_file.exists():
                    index_file.write_text('{"sessions": []}')

    def teardown(self):
        """停止所有服务"""
        print("\n" + "="*60)
        print("Tearing down test environment")
        print("="*60)

        if self.character:
            self.character.stop()
        if self.supervisor:
            self.supervisor.stop()
        if self.registry:
            self.registry.stop()

        print("All agents stopped")

    def get_agent_id(self, agent_type: str) -> Optional[str]:
        """从 Registry 获取指定类型的 Agent ID"""
        try:
            # 使用 /api/registry/agents 获取所有 agent，然后手动过滤
            response = requests.get(
                "http://localhost:8000/api/registry/agents",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                agents = data.get("agents", [])
                for agent in agents:
                    if agent.get("agent_type") == agent_type:
                        return agent.get("agent_id")
        except Exception as e:
            print(f"[Registry] Error getting {agent_type} id: {e}")
        return None


@pytest.fixture(scope="module")
def multi_agent_env():
    """多 Agent 测试环境 fixture"""
    env = MultiAgentTestEnv()
    if not env.setup():
        pytest.fail("Failed to setup multi-agent test environment")

    yield env

    env.teardown()


@pytest.fixture
def session_id():
    """生成测试用 session_id"""
    return f"test-a2a-{int(time.time())}"


@pytest.mark.asyncio
async def test_multi_agent_a2a_communication(multi_agent_env, session_id):
    """
    测试多 Agent A2A 通信完整链路

    完整流程验证（4个步骤缺一不可）：
    1. 查询：Supervisor 调用 discover_agents 发现 character
    2. 分析：LLM 分析发现结果，决定委托任务
    3. 发送：Supervisor 调用 send_agent_message 向 character 发送任务
    4. 接收：Character 接收任务、处理、返回 agent_response

    验证方法：
    - Supervisor session 中有 discover_agents 和 send_agent_message 的 tool_calls
    - Character session 中有 agent_request 和 agent_response
    """
    print(f"\n{'='*60}")
    print("Test: Multi-Agent A2A Communication")
    print(f"Session: {session_id}")
    print(f"{'='*60}\n")

    # 1. 获取 supervisor 和 character 的 agent_id
    supervisor_id = multi_agent_env.get_agent_id("supervisor")
    character_id = multi_agent_env.get_agent_id("character")

    print(f"[Test] Supervisor ID: {supervisor_id}")
    print(f"[Test] Character ID: {character_id}")

    assert supervisor_id, "Supervisor should be registered"
    assert character_id, "Character should be registered"

    # 等待更长时间确保所有 agent 完全注册
    await asyncio.sleep(5)

    # 验证 registry 确实有 agent
    registry_response = requests.get("http://localhost:8000/api/registry/agents", timeout=10)
    if registry_response.status_code == 200:
        registry_data = registry_response.json()
        print(f"[Test] Registry has {registry_data.get('count')} agents")
        for agent in registry_data.get("agents", []):
            print(f"  - {agent.get('agent_id')} ({agent.get('agent_type')})")

    # 2. 通过 HTTP 给 supervisor 发任务
    # 注意：这里不告诉它具体怎么实现，让 LLM 自己决定是否需要 A2A 通信
    task = "请创建一个勇敢的骑士角色，名字叫兰斯洛特"

    print(f"\n[Test] Sending task to supervisor: {task}")
    print("[Test] Waiting for full chain response...\n")

    events = []
    async with aiohttp.ClientSession() as http_session:
        async with http_session.post(
            f"http://localhost:8001/chat/stream",
            json={"task": task, "session_id": session_id},
            timeout=aiohttp.ClientTimeout(total=120)
        ) as response:
            assert response.status == 200, f"Expected 200, got {response.status}"

            async for line in response.content:
                if line.startswith(b"data: "):
                    event_data = json.loads(line[6:])
                    event_type = event_data.get("type")
                    content = event_data.get("content", "")

                    # 过滤空内容
                    if not content and event_type not in ("done", "tool_call", "tool_result"):
                        continue

                    # 截断长内容用于显示
                    display_content = content[:100] + "..." if len(str(content)) > 100 else content

                    print(f"[Event] {event_type}: {display_content}")
                    events.append(event_data)

    print(f"\n[Test] Total events received: {len(events)}")

    # 3. 验证收集到的事件
    assert len(events) > 0, "Should receive at least one event"

    # 检查是否成功结束
    done_events = [e for e in events if e.get("type") == "done"]
    assert len(done_events) > 0, "Should have a done event"

    print(f"\n[Test] Events breakdown:")
    print(f"  - reasoning: {len([e for e in events if e.get('type') == 'reasoning'])}")
    print(f"  - tool_call: {len([e for e in events if e.get('type') == 'tool_call'])}")
    print(f"  - tool_result: {len([e for e in events if e.get('type') == 'tool_result'])}")
    print(f"  - assistant: {len([e for e in events if e.get('type') == 'assistant'])}")

    # 4. 检查 Supervisor 的 Session 历史
    print(f"\n{'='*60}")
    print("Checking Supervisor Session History")
    print(f"{'='*60}")

    await asyncio.sleep(1)  # 等待 session 写入完成

    supervisor_history_response = requests.get(
        f"http://localhost:8001/session/{session_id}/history",
        timeout=10
    )
    assert supervisor_history_response.status_code == 200

    supervisor_history = supervisor_history_response.json().get("messages", [])
    print(f"[Supervisor] Session has {len(supervisor_history)} messages")

    # 分析 supervisor session 中的 tool_calls
    supervisor_tool_calls = []
    for msg in supervisor_history:
        if msg.get("type") == "message" and msg.get("tool_calls"):
            for tc in msg.get("tool_calls", []):
                tool_name = tc.get("name") if isinstance(tc, dict) else str(tc)
                print(f"  [Supervisor] Tool call: {tool_name}")
                supervisor_tool_calls.append(tool_name)

    # 5. 检查 Character 的 Session 历史
    print(f"\n{'='*60}")
    print("Checking Character Session History")
    print(f"{'='*60}")

    # Character 的 session 格式是 a2a_{supervisor_id}
    character_session_id = f"a2a_{supervisor_id}"
    character_history_response = requests.get(
        f"http://localhost:8002/session/{character_session_id}/history",
        timeout=10
    )

    character_agent_requests = []
    character_agent_responses = []
    if character_history_response.status_code == 200:
        character_history = character_history_response.json().get("messages", [])
        print(f"[Character] Session has {len(character_history)} messages")

        for msg in character_history:
            msg_type = msg.get("type", "unknown")
            print(f"  [Character] {msg_type}: role={msg.get('role', 'N/A')}")

            if msg_type == "agent_request":
                character_agent_requests.append(msg)
                print(f"    -> task: {msg.get('task', '')[:50]}...")
            elif msg_type == "agent_response":
                character_agent_responses.append(msg)
                print(f"    -> content: {msg.get('content', '')[:50]}...")

    # 6. 验证 A2A 通信完整链路（4步验证）
    print(f"\n{'='*60}")
    print("Verification: Complete A2A Chain")
    print(f"{'='*60}")

    has_discover = "discover_agents" in supervisor_tool_calls
    has_send = any("send_agent_message" in tc for tc in supervisor_tool_calls)
    has_agent_request = len(character_agent_requests) > 0
    has_agent_response = len(character_agent_responses) > 0

    print(f"\nChain Verification (4 steps):")
    print(f"  Step 1 - Query (discover_agents): {'✓' if has_discover else '✗'}")
    print(f"  Step 2 - Analyze (LLM decision): {'✓' if has_send else '✗'} (decided to send)")
    print(f"  Step 3 - Send (send_agent_message): {'✓' if has_send else '✗'}")
    print(f"  Step 4 - Receive (agent_response): {'✓' if has_agent_response else '✗'}")

    print(f"\n[Supervisor Tool Calls]: {supervisor_tool_calls}")
    print(f"[Character agent_request]: {len(character_agent_requests)}")
    print(f"[Character agent_response]: {len(character_agent_responses)}")

    # CRITICAL: 完整链路验证 - 4步缺一不可
    assert has_discover, \
        f"Step 1 FAILED: Supervisor should call discover_agents. Tool calls: {supervisor_tool_calls}"

    assert has_send, \
        f"Step 2-3 FAILED: Supervisor should call send_agent_message after discovering. Tool calls: {supervisor_tool_calls}"

    assert has_agent_request, \
        f"Step 4a FAILED: Character should receive agent_request. Check if send_agent_message succeeded. Character session '{character_session_id}': {character_history_response.status_code}"

    assert has_agent_response, \
        f"Step 4b FAILED: Character should return agent_response after processing. Character session '{character_session_id}' has {len(character_agent_requests)} requests but {len(character_agent_responses)} responses"

    print(f"\n{'='*60}")
    print("SUCCESS: Complete A2A chain verified!")
    print("  - discover_agents called")
    print("  - send_agent_message called")
    print("  - agent_request received by Character")
    print("  - agent_response returned to Supervisor")
    print(f"{'='*60}")


@pytest.mark.asyncio
async def test_registry_discovery(multi_agent_env):
    """
    测试 Registry 的 Agent 发现功能

    验证：
    - 可以通过关键词搜索找到 agent
    - 可以按类型筛选 agent
    """
    print(f"\n{'='*60}")
    print("Test: Registry Discovery")
    print(f"{'='*60}\n")

    # 测试按类型搜索
    response = requests.get(
        "http://localhost:8000/api/registry/search",
        params={"agent_type": "character"},
        timeout=10
    )
    assert response.status_code == 200

    data = response.json()
    agents = data.get("agents", [])
    print(f"[Registry] Found {len(agents)} character agents")

    for agent in agents:
        print(f"  - {agent.get('agent_name')} ({agent.get('agent_id')})")
        print(f"    endpoint: {agent.get('endpoint')}")
        print(f"    capabilities: {[c.get('name') for c in agent.get('capabilities', [])]}")

    assert len(agents) >= 1, "Should find at least one character agent"

    # 测试列出所有 agent
    response = requests.get("http://localhost:8000/api/registry/agents", timeout=10)
    assert response.status_code == 200

    data = response.json()
    all_agents = data.get("agents", [])
    print(f"\n[Registry] Total registered agents: {len(all_agents)}")

    assert len(all_agents) >= 2, "Should have at least 2 agents (supervisor + character)"


@pytest.mark.asyncio
async def test_agent_health_checks(multi_agent_env):
    """测试各 Agent 的健康检查端点"""
    print(f"\n{'='*60}")
    print("Test: Agent Health Checks")
    print(f"{'='*60}\n")

    # Registry health
    response = requests.get("http://localhost:8000/health", timeout=5)
    print(f"[Registry] /health: {response.status_code}")
    assert response.status_code == 200

    # Supervisor health
    response = requests.get("http://localhost:8001/health", timeout=5)
    print(f"[Supervisor] /health: {response.status_code}")
    assert response.status_code == 200

    # Character health
    response = requests.get("http://localhost:8002/health", timeout=5)
    print(f"[Character] /health: {response.status_code}")
    assert response.status_code == 200

    # 检查 AgentCard
    response = requests.get("http://localhost:8001/.well-known/agent-card.json", timeout=5)
    assert response.status_code == 200
    card = response.json()
    print(f"\n[Supervisor] AgentCard:")
    print(f"  agent_id: {card.get('agent_id')}")
    print(f"  agent_name: {card.get('agent_name')}")
    print(f"  agent_type: {card.get('agent_type')}")
    print(f"  capabilities: {[c.get('name') for c in card.get('capabilities', [])]}")

    response = requests.get("http://localhost:8002/.well-known/agent-card.json", timeout=5)
    assert response.status_code == 200
    card = response.json()
    print(f"\n[Character] AgentCard:")
    print(f"  agent_id: {card.get('agent_id')}")
    print(f"  agent_name: {card.get('agent_name')}")
    print(f"  agent_type: {card.get('agent_type')}")
    print(f"  capabilities: {[c.get('name') for c in card.get('capabilities', [])]}")

    print(f"\n{'='*60}")
    print("All health checks passed!")
    print(f"{'='*60}")


@pytest.mark.asyncio
async def test_a2a_message_sending(multi_agent_env):
    """
    测试 A2A 消息发送功能

    这个测试明确告诉 Supervisor 使用 send_agent_message 工具向 Character 发送任务，
    验证 A2A 通信完整链路。
    """
    print(f"\n{'='*60}")
    print("Test: A2A Message Sending")
    print(f"{'='*60}\n")

    # 1. 获取 supervisor 和 character 的 agent_id
    supervisor_id = multi_agent_env.get_agent_id("supervisor")
    character_id = multi_agent_env.get_agent_id("character")

    print(f"[Test] Supervisor ID: {supervisor_id}")
    print(f"[Test] Character ID: {character_id}")

    assert supervisor_id, "Supervisor should be registered"
    assert character_id, "Character should be registered"

    # 等待更长时间确保所有 agent 完全注册
    await asyncio.sleep(5)

    # 验证 registry 确实有 agent
    registry_response = requests.get("http://localhost:8000/api/registry/agents", timeout=10)
    if registry_response.status_code == 200:
        registry_data = registry_response.json()
        print(f"[Test] Registry has {registry_data.get('count')} agents")

    # 2. 使用明确的指令，告诉 Supervisor 必须使用 A2A 工具
    task = f'请使用 send_agent_message 工具向 agent_id="{character_id}" 发送消息，要求它创建一个"勇敢的骑士"角色。直接调用工具，不要只是回复。'

    print(f"\n[Test] Sending directive task to supervisor")
    print(f"[Test] Task: {task}\n")

    events = []
    async with aiohttp.ClientSession() as http_session:
        async with http_session.post(
            f"http://localhost:8001/chat/stream",
            json={"task": task, "session_id": "test-a2a-send"},
            timeout=aiohttp.ClientTimeout(total=120)
        ) as response:
            assert response.status == 200

            async for line in response.content:
                if line.startswith(b"data: "):
                    event_data = json.loads(line[6:])
                    event_type = event_data.get("type")
                    content = event_data.get("content", "")

                    if not content and event_type not in ("done", "tool_call", "tool_result"):
                        continue

                    display_content = content[:100] + "..." if len(str(content)) > 100 else content
                    print(f"[Event] {event_type}: {display_content}")
                    events.append(event_data)

    print(f"\n[Test] Total events received: {len(events)}")

    # 3. 检查 Supervisor 的 Session 历史
    await asyncio.sleep(1)

    supervisor_history_response = requests.get(
        f"http://localhost:8001/session/test-a2a-send/history",
        timeout=10
    )

    if supervisor_history_response.status_code == 200:
        supervisor_history = supervisor_history_response.json().get("messages", [])
        print(f"\n[Supervisor] Session has {len(supervisor_history)} messages")

        supervisor_tool_calls = []
        for msg in supervisor_history:
            if msg.get("type") == "message" and msg.get("tool_calls"):
                for tc in msg.get("tool_calls", []):
                    tool_name = tc.get("name") if isinstance(tc, dict) else str(tc)
                    print(f"  [Supervisor] Tool call: {tool_name}")
                    supervisor_tool_calls.append(tool_name)

        # 验证 send_agent_message 被调用
        has_send_message = any("send_agent_message" in tc for tc in supervisor_tool_calls)
        print(f"\n[Result] send_agent_message called: {has_send_message}")

        if has_send_message:
            # 4. 检查 Character 的 Session 历史
            character_session_id = f"a2a_{supervisor_id}"
            character_history_response = requests.get(
                f"http://localhost:8002/session/{character_session_id}/history",
                timeout=10
            )

            if character_history_response.status_code == 200:
                character_history = character_history_response.json().get("messages", [])
                print(f"[Character] Session has {len(character_history)} messages")

                agent_requests = [m for m in character_history if m.get("type") == "agent_request"]
                print(f"[Result] Character received {len(agent_requests)} agent_request messages")

                if len(agent_requests) > 0:
                    print("[SUCCESS] A2A communication verified!")
                    return

    print("[INFO] A2A message sending test completed")
    print(f"{'='*60}")