"""
技能管理器 - 支持渐进式技能披露

技能存储在 agent_dir/skills/ 目录下，每个技能一个子目录：
- SKILL.md: 包含 frontmatter 元数据和正文
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List, Tuple

import frontmatter


@dataclass
class SkillMetadata:
    """技能元数据"""
    name: str  # 技能名称
    description: str  # 技能描述
    license: Optional[str] = None  # 许可证
    allowed_tools: Optional[List[str]] = None  # 允许使用的工具


class SkillManager:
    """
    Skill 管理器 - 支持渐进式披露
    """

    @staticmethod
    def parse_skill_metadata(skill_md_path: Path) -> Tuple[SkillMetadata, str]:
        """
        解析 SKILL.md，返回 (元数据, 正文内容)

        Args:
            skill_md_path: SKILL.md 文件路径

        Returns:
            (SkillMetadata, 正文内容) 元组
        """
        post = frontmatter.load(skill_md_path)
        metadata = SkillMetadata(
            name=post.metadata.get('name', ''),
            description=post.metadata.get('description', ''),
            license=post.metadata.get('license'),
            allowed_tools=post.metadata.get('allowed_tools')
        )
        return metadata, post.content

    @staticmethod
    def load_all_skills(skills_dir: Path) -> List[str]:
        """
        加载所有技能

        Args:
            skills_dir: skills 目录路径

        Returns:
            {skill_name: (metadata, content)} 字典
        """
        skills = []
        if skills_dir.exists():
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        try:
                            metadata, content = SkillManager.parse_skill_metadata(skill_file)
                            skills.append(metadata)
                        except Exception as e:
                            print(f"加载 Skill 失败 {skill_file}: {e}")
        return skills

    @staticmethod
    def get_skill_intro(skills_metadata: List[SkillMetadata]) -> str:
        """
        将技能元数据列表格式化为字符串

        Args:
            skills_metadata: 技能元数据列表

        Returns:
            格式化的技能介绍字符串
        """
        if not skills_metadata:
            return ""
        return "\n".join([f"- **{m.name}**: {m.description}" for m in skills_metadata])
