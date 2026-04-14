import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    print("测试导入...")
    
    try:
        from agent_commons.a2a.identity import AgentIdentity
        print("✓ AgentIdentity 导入成功")
    except Exception as e:
        print(f"✗ AgentIdentity 导入失败: {e}")
        return False
    
    try:
        from agent_commons.a2a.message_schema import A2AMessage, MessageType
        print("✓ A2AMessage 导入成功")
    except Exception as e:
        print(f"✗ A2AMessage 导入失败: {e}")
        return False
    
    try:
        from agent_commons.a2a.protocol import A2AProtocol
        print("✓ A2AProtocol 导入成功")
    except Exception as e:
        print(f"✗ A2AProtocol 导入失败: {e}")
        return False
    
    try:
        from agent_commons.process.manager import ProcessManager
        print("✓ ProcessManager 导入成功")
    except Exception as e:
        print(f"✗ ProcessManager 导入失败: {e}")
        return False
    
    try:
        from agent_commons.registry.agent_registry import AgentRegistry
        print("✓ AgentRegistry 导入成功")
    except Exception as e:
        print(f"✗ AgentRegistry 导入失败: {e}")
        return False
    
    try:
        from agent_commons.sessions.manager import SessionManager
        print("✓ SessionManager 导入成功")
    except Exception as e:
        print(f"✗ SessionManager 导入失败: {e}")
        return False
    
    try:
        from agent_commons.base.agent_base import BaseAgent
        print("✓ BaseAgent 导入成功")
    except Exception as e:
        print(f"✗ BaseAgent 导入失败: {e}")
        return False
    
    try:
        from agent_commons.factory.agent_factory import AgentFactory
        print("✓ AgentFactory 导入成功")
    except Exception as e:
        print(f"✗ AgentFactory 导入失败: {e}")
        return False
    
    try:
        from agent_commons.coordinator import AgentCoordinator
        print("✓ AgentCoordinator 导入成功")
    except Exception as e:
        print(f"✗ AgentCoordinator 导入失败: {e}")
        return False
    
    return True

def test_session_manager():
    print("\n测试 SessionManager...")
    
    try:
        from agent_commons.sessions.manager import SessionManager
        
        sm = SessionManager("sessions")
        session_id = sm.create_session("supervisor")
        print(f"✓ 创建会话成功: {session_id}")
        
        sm.append_event("supervisor", session_id, {
            "type": "message",
            "role": "user",
            "content": "测试消息"
        })
        print("✓ 追加事件成功")
        
        events = sm.get_session_events("supervisor", session_id)
        print(f"✓ 获取事件成功，共 {len(events)} 个事件")
        
        return True
    except Exception as e:
        print(f"✗ SessionManager 测试失败: {e}")
        return False

def test_agent_factory():
    print("\n测试 AgentFactory...")
    
    try:
        from agent_commons.factory.agent_factory import AgentFactory
        
        available_agents = AgentFactory.list_available_agents()
        print(f"✓ 可用的Agent: {available_agents}")
        
        return True
    except Exception as e:
        print(f"✗ AgentFactory 测试失败: {e}")
        return False

def main():
    print("=" * 50)
    print("开始测试新架构")
    print("=" * 50)
    
    success = True
    
    if not test_imports():
        success = False
    
    if not test_session_manager():
        success = False
    
    if not test_agent_factory():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✓ 所有测试通过！")
    else:
        print("✗ 部分测试失败")
    print("=" * 50)
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
