"""
上下文管理器

负责构建和转换各种上下文：
- 构建带 skills 的 system prompt
- 注入 A2A 事件到消息列表
- 过滤空消息
- 历史消息与 LangChain 格式互转


session格式：

主agent：
{"type": "message", "role": "user", "content": "当前工作空间有哪些文件？请用 ls 命令查看", "timestamp": "2026-04-24T10:18:24.257408Z"}
{"type": "message", "role": "assistant", "content": "", "reasoning_content": "用户想了解当前工作空间有哪些文件，要求使用 ls 命令查看。我需要使用 execute_bash 工具来执行这个命令。", "timestamp": "2026-04-24T10:18:27.101500Z"}
{"type": "message", "role": "assistant", "tool_calls": [{"id": "execute_bash:0", "name": "execute_bash", "arguments": {"command": "ls -la"}}], "timestamp": "2026-04-24T10:18:27.102793Z"}
{"type": "message", "role": "tool", "tool_call_id": "execute_bash:0", "content": "{\"success\": true, \"stdout\": \"total 16\\ndrwxr-xr-x@ 10 seco  staff   320 Apr 23 02:18 .\\ndrwxr-xr-x@  9 seco  staff   288 Apr 23 00:24 ..\\n-rw-r--r--@  1 seco  staff     0 Apr 16 15:48 __init__.py\\ndrwxr-xr-x@  4 seco  staff   128 Apr 23 02:18 __pycache__\\n-rw-r--r--@  1 seco  staff  1298 Apr 22 19:02 agent_config.json\\ndrwxr-xr-x@  4 seco  staff   128 Apr 22 20:01 cores\\n-rw-r--r--@  1 seco  staff  1355 Apr 24 16:49 main.py\\ndrwxr-xr-x@  4 seco  staff   128 Apr 22 21:14 prompts\\ndrwxr-xr-x@  9 seco  staff   288 Apr 24 18:18 sessions\\ndrwxr-xr-x@  6 seco  staff   192 Apr 21 11:58 skills\\n\", \"stderr\": \"\", \"returncode\": 0, \"command\": \"ls -la\", \"cwd\": \"/Users/seco/AIProjects/NovelAgent/agents/supervisor_agent\"}", "timestamp": "2026-04-24T10:18:27.127664Z"}
{"type": "message", "role": "assistant", "content": "", "reasoning_content": "用户想了解当前工作空间有哪些文件，要求使用 ls 命令查看。我需要使用 execute_bash 工具来执行这个命令。", "timestamp": "2026-04-24T10:18:27.129327Z"}
{"type": "message", "role": "assistant", "tool_calls": [{"id": "execute_bash:0", "name": "execute_bash", "arguments": {"command": "ls -la"}}], "timestamp": "2026-04-24T10:18:27.129612Z"}
{"type": "message", "role": "user", "content": "当前工作空间有哪些文件？请用 ls 命令查看", "timestamp": "2026-04-24T10:39:10.326846Z"}

子agent：
{"type": "agent_request", "source_agent_id": "supervisor-001", "target_agent_id": "character-001", "task": "创建一个勇敢的骑士角色，名字叫兰斯洛特", "event_id": "evt-1e716450", "timestamp": "2026-04-24T10:54:24.712257Z"}
{"type": "message", "role": "assistant", "content": "### 人物基本信息\n\n- **姓名**：兰斯洛特（Lancelot）\n- **年龄**：30岁\n- **性别**：男\n- **职业**：骑士\n\n### 人物性格特点\n\n- **勇敢无畏**：兰斯洛特以无畏的勇气著称，无论面对何种困境和敌人，他总是勇往直前。\n- **忠诚正直**：他对国王和国家忠诚无比，他的剑只为正义和荣誉而挥舞。\n- **智慧与策略**：尽管他以武力著称，但他同样具备出色的智慧和战略眼光，能够在战场上制定和执行复杂的战术。\n- **深情而复杂**：兰斯洛特在情感上有着深刻的纠葛，他的爱情故事充满了悲剧色彩，这使他的角色更加立体和复杂。\n\n### 人物背景故事\n\n兰斯洛特出生于一个贵族家庭，自幼接受骑士训练，他的父亲是一位受人尊敬的骑士，母亲则是一位温柔的贵族女性。他在很小的时候就展现出了超乎常人的勇气和战斗天赋。成年后，他加入了国王的圆桌骑士团，迅速以其卓越的武艺和领导能力脱颖而出。\n\n兰斯洛特的名声不仅因为他的战斗能力，还因为他在一次致命的叛乱中拯救了国王的生命。然而，他的生活并非一帆风顺，他与王后之间的禁忌爱情让他陷入了道德和忠诚的两难境地。\n\n### 人物外貌特征\n\n- **身高**：6英尺2英寸（约188厘米），体型健壮，肌肉线条分明。\n- **发色**：深棕色，略带自然卷曲，通常束于脑后。\n- **眼色**：深邃的蓝色，似乎能洞察人心。\n- **面容**：棱角分明，下巴坚毅，鼻梁挺直，给人一种坚不可摧的印象。\n- **着装**：通常穿着精心打造的骑士铠甲，上面刻有象征他家族的纹章——一头跃起的狮子。\n\n### 人物在故事中的角色定位\n\n兰斯洛特是故事中的中心人物之一，他既是英勇的骑士，也是情感纠葛的核心。他的存在不仅推动了故事的发展，也体现了中世纪骑士精神的荣耀与悲剧。他的故事不仅是对勇气和荣誉的追求，也是对人性复杂性的深刻探讨。兰斯洛特的形象将激励读者思考忠诚、爱情和牺牲的真正含义。", "timestamp": "2026-04-24T10:54:33.878470Z"}
{"type": "agent_request", "source_agent_id": "supervisor-001", "target_agent_id": "character-001", "task": "创建一个勇敢的骑士角色，名字叫兰斯洛特", "event_id": "evt-d4ecc2d6", "timestamp": "2026-04-24T10:54:37.211996Z"}
{"type": "agent_request", "source_agent_id": "supervisor-001", "target_agent_id": "character-001", "task": "创建一个'勇敢的骑士'角色", "event_id": "evt-23af08d3", "timestamp": "2026-04-24T10:54:55.594802Z"}
{"type": "message", "role": "assistant", "content": "当然，让我们来创造一个勇敢的骑士角色：\n\n### 基本信息：\n- **姓名**：亚瑟·雷德温（Arthur Redwyn）\n- **年龄**：28岁\n- **性别**：男\n- **国籍**：来自一个中世纪风格的王国，名为艾瑞达尔（Eryndar）\n\n### 性格特点：\n- **勇敢**：亚瑟不惧任何挑战，总是勇敢地站在战斗的最前线。\n- **正义感强烈**：他坚信正义，愿意为了保护无辜者而战。\n- **忠诚**：对国王和国家极度忠诚，对他的骑士团同伴也充满了兄弟般的情谊。\n- **谦逊**：尽管他是个强大的战士，但他从不炫耀自己的成就。\n- **有同情心**：亚瑟对弱者和受苦之人有着深深的同情，经常帮助那些需要帮助的人。\n\n### 背景故事：\n亚瑟出生在一个贫穷的农家，但他从小就展现出了非凡的剑术天赋。他的勇敢和技巧吸引了一位路过的骑士的注意，这位骑士后来成为了他的导师。在经过多年的训练后，亚瑟成为了一名骑士，并因其在对抗边境野蛮人中的英勇表现而被国王赏识，提拔为皇家骑士团的一员。\n\n### 外貌特征：\n- **身高**：6英尺（约183厘米），身材魁梧。\n- **发色**：棕色的短发，经常藏在他的骑士头盔下。\n- **眼睛**：锐利的蓝色眼睛，透露出坚毅和智慧。\n- **服装**：穿着精心打造的银色铠甲，上面刻有艾瑞达尔的国徽——一头雄狮。\n- **武器**：一把名为“黎明之刃”的家族传承巨剑，以及一面坚固的橡木盾牌。\n\n### 人物在故事中的角色定位：\n亚瑟是故事中的主要英雄角色，他的勇敢和正义是推动故事发展的关键。他将面对来自邪恶巫师和黑暗势力的挑战，保护王国免受威胁。在冒险的过程中，亚瑟不仅需要用他的力量和技巧战斗，还需要用他的智慧和同情心来团结人民，克服障碍。\n\n这个角色设计旨在为读者提供一个立体、有深度的角色形象，他不仅是一个战斗机器，而是一个有着丰富情感和复杂动机的人。希望这个角色能够为你的小说增添色彩。", "timestamp": "2026-04-24T10:55:04.828512Z"}


| 字段路径 | 类型 | 必选 | 说明 | 示例值 |
|---------|------|------|------|--------|
| type| string | 是 | 本条消息的消息类型，"message"表示本agent内部的消息，"agent_request"表示来自其他agent的请求消息，"agent_response"表示发送给请求agent的消息 | "message" |
| role | string | 是 | 消息角色，"user"表示用户消息，"assistant"表示模型消息，"tool"表示系统调用的工具结果 | "user" |
| content | string | 否（只有在模型调用工具的时候可以没有该字段） | 消息内容/工具调用结果 | "Hello, how are you?" |
| timestamp | string | 是 | 时间戳 | "2026-04-24T10:18:24.257408Z" |
| tool_calls | List[Dict[str, Any]] | 否（只有在模型调用工具的时候出现该字段） | 模型请求工具调用列表 | [{"id": "execute_bash:0", "name": "execute_bash", "arguments": {"command": "ls -la"}}] |
| ttols_calls[i].id | string | 否 | 工具调用唯一标识，格式为 "工具名称:序号" | "execute_bash:0" |
| tools_calls[i].name | string | 否 | 工具名称，对应工具的注册函数名 | "execute_bash" |
| tools_calls[i].arguments | Dict[str, Any] | 否 | 工具调用参数字典，key表示函数参数名，value表示参数值 | {"command": "ls -la"} |
| reasoning_content | string | 否 | 模型的推理过程内容，用于解释模型的思路和决策过程，只有在调用思考模式的模型中才会出现，该模式下，role in ["user","tool"]的消息的下一行必须要有reasoning_content内容 | "用户想了解当前工作空间有哪些文件，我需要使用 ll 命令。" |
| source_agent_id | string | 否（仅在 type="agent_request" 时） | 请求消息的来源 agent_id | "supervisor-001" |
| target_agent_id | string | 否（仅在 type="agent_request" 时） | 请求消息的目标 agent_id | "character-001" |
| task | string | 否（仅在 type="agent_request" 时） | 请求任务内容 | "创建一个勇敢的骑士角色，名字叫兰斯洛特" |
| event_id | string | 否（仅在 type="agent_request" 时） | 请求消息的唯一事件 ID，用于追踪和关联请求与响应 | "evt-1e716450" |



"""

from typing import List, Dict, Any, Optional, Set

from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    AIMessage,
    ToolMessage,
    HumanMessage
)


class ContextManager:
    """
    上下文管理器
    """

    @staticmethod
    def build_system_message(
        system_prompt: str,
        skills_metadata: List[Any],
        received_events: Optional[List[Dict[str, Any]]] = None
    ) -> List[SystemMessage]:
        """
        构建 system message，包含 skills 和 A2A events

        Args:
            system_prompt: system prompt 内容
            skills_metadata: 技能元数据列表
            received_events: 接收到的 A2A 事件列表

        Returns:
            SystemMessage 列表
        """
        from .skill_manager import SkillManager

        messages = []

        # 1. 构建带 skills 的 system prompt
        if system_prompt:
            if skills_metadata:
                skill_intro = SkillManager.get_skill_intro(skills_metadata)
                system_content = system_prompt + "\n\n可用技能:\n" + skill_intro
            else:
                system_content = system_prompt
            messages.append(SystemMessage(content=system_content))

        # 2. 注入 A2A 事件
        if received_events:
            events_summary = "\n".join([
                f"- [{e.get('event_type')}] from {e.get('source')}: {e.get('content', '')}"
                for e in received_events
            ])
            events_msg = f"\n\n最近收到的 Agent 事件:\n{events_summary}"
            if messages and isinstance(messages[0], SystemMessage):
                messages[0] = SystemMessage(content=messages[0].content + events_msg)
            else:
                messages.append(SystemMessage(content=events_msg))

        return messages

    @staticmethod
    def filter_empty_messages(messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        过滤空消息（content 为空且没有有效 tool_calls 的 assistant 消息）

        Args:
            messages: 消息列表

        Returns:
            过滤后的消息列表
        """
        filtered = []
        for m in messages:
            if isinstance(m, AIMessage):
                has_content = bool(m.content)
                has_tc = getattr(m, "tool_calls", None)
                has_valid_tc = has_tc and any(
                    (isinstance(t, dict) and t.get("id")) or (hasattr(t, "id") and t.id)
                    for t in has_tc
                ) if has_tc else False
                if not has_content and not has_valid_tc:
                    continue
            filtered.append(m)
        return filtered

    @staticmethod
    def format_history_to_messages(
        context: List[Dict[str, Any]]
    ) -> tuple[List[BaseMessage], Set[str]]:
        """
        将历史消息字典列表转换为 LangChain 消息格式

        Args:
            context: 历史消息列表，每项包含 role, content, tool_calls 等

        Returns:
            (messages, existing_tool_ids) 元组
        """
        import logging
        logger = logging.getLogger(__name__)

        messages = []
        existing_tool_ids: Set[str] = set()

        logger.debug(f"[format_history_to_messages] context length: {len(context)}")

        for msg in context:
            msg_type = msg.get("type", "")
            msg_role = msg.get("role", "")

            logger.debug(f"[format_history_to_messages] processing msg type={msg_type}, role={msg_role}")

            # agent_request: 来自其他 Agent 的请求 → 当作 user 消息处理
            if msg_type == "agent_request":
                task_content = msg.get("task", "")
                if task_content:
                    messages.append(HumanMessage(content=task_content))
                continue

            # agent_response: 发回给请求 Agent 的响应 → 当作 assistant 消息处理
            if msg_type == "agent_response":
                resp_content = msg.get("content", "")
                if resp_content:
                    messages.append(AIMessage(content=resp_content))
                continue

            # 标准的 role 字段处理
            if msg_role == "user":
                messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg_role == "assistant":
                content = msg.get("content", "")
                tool_calls = msg.get("tool_calls", [])

                # 过滤掉已有响应的 tool_calls（它们已经执行过了）
                valid_tool_calls = []
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        tc_id = tc.get("id")
                        # 只保留没有对应 tool result 的 tool_calls
                        if tc_id and tc_id not in existing_tool_ids:
                            valid_tool_calls.append({
                                "id": tc_id,
                                "name": tc.get("name", ""),
                                "args": tc.get("args", tc.get("arguments", {}))
                            })
                    elif tc and tc not in existing_tool_ids:
                        valid_tool_calls.append({
                            "id": tc,
                            "name": "",
                            "args": {}
                        })

                # 跳过空消息（但保留有 reasoning_content 的消息）
                has_reasoning = bool(msg.get("reasoning_content"))
                if not content and not valid_tool_calls and not has_reasoning:
                    continue

                # reasoning_content 应该只在 additional_kwargs 中，不应该在 content 中
                messages.append(AIMessage(
                    content=content or "",
                    tool_calls=valid_tool_calls,
                    reasoning_content=msg.get("reasoning_content") or ""
                ))
            elif msg.get("role") == "tool":
                tool_call_id = msg.get("tool_call_id")
                if tool_call_id:
                    messages.append(ToolMessage(
                        content=msg.get("content", ""),
                        tool_call_id=tool_call_id,
                        additional_kwargs={"reasoning_content": ""}
                    ))
                    existing_tool_ids.add(tool_call_id)

        logger.debug(f"[format_history_to_messages] returning {len(messages)} messages, existing_tool_ids={existing_tool_ids}")
        for i, m in enumerate(messages):
            tc = getattr(m, "tool_calls", None) if isinstance(m, AIMessage) else None
            logger.debug(f"[format_history_to_messages] msg[{i}] type={type(m).__name__}, has_tool_calls={bool(tc)}")
            if tc:
                for t in tc:
                    tc_id = t.get("id") if isinstance(t, dict) else getattr(t, "id", None)
                    logger.debug(f"  tool_call id={tc_id}, name={t.get('name') if isinstance(t, dict) else getattr(t, 'name', None)}")

        return messages, existing_tool_ids

    @staticmethod
    def messages_to_dict(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        将 LangChain 消息列表转换为字典格式

        Args:
            messages: LangChain 消息列表

        Returns:
            字典列表
        """
        result = []
        for msg in messages:
            msg_dict = {"role": "", "content": msg.content or ""}

            if isinstance(msg, HumanMessage):
                msg_dict["role"] = "user"
            elif isinstance(msg, AIMessage):
                msg_dict["role"] = "assistant"
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    tool_calls_list = []
                    for tc in msg.tool_calls:
                        if isinstance(tc, dict):
                            tool_calls_list.append({
                                "id": tc.get("id"),
                                "name": tc.get("name"),
                                "arguments": tc.get("args", tc.get("arguments", {}))
                            })
                        else:
                            tool_calls_list.append({
                                "id": tc.id,
                                "name": tc.name,
                                "arguments": tc.args
                            })
                    msg_dict["tool_calls"] = tool_calls_list
            elif isinstance(msg, ToolMessage):
                msg_dict["role"] = "tool"
                msg_dict["tool_call_id"] = msg.tool_call_id

            result.append(msg_dict)

        return result

    @staticmethod
    def has_valid_tool_calls(messages: List[BaseMessage]) -> bool:
        """
        检查消息列表中是否有有效的 tool_calls

        Args:
            messages: 消息列表

        Returns:
            是否有有效 tool_calls
        """
        for m in messages:
            if isinstance(m, AIMessage):
                tc = getattr(m, "tool_calls", None)
                if tc:
                    for t in tc:
                        tc_id = t.get("id") if isinstance(t, dict) else getattr(t, "id", None)
                        if tc_id:
                            return True
        return False

    @staticmethod
    def has_tool_results(messages: List[BaseMessage]) -> bool:
        """
        检查消息列表中是否有 ToolMessage

        Args:
            messages: 消息列表

        Returns:
            是否有 ToolMessage
        """
        return any(isinstance(m, ToolMessage) for m in messages)
