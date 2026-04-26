try:
    from .prompts import Prompts
except ImportError:
    class Prompts:
        pass
try:
    from .theme_agent import ThemeAgent
except ImportError:
    ThemeAgent = None
try:
    from .character_agent import CharacterAgent
except ImportError:
    CharacterAgent = None
try:
    from .outline_agent import OutlineAgent
except ImportError:
    OutlineAgent = None
try:
    from .content_agent import ContentAgent
except ImportError:
    ContentAgent = None
try:
    from .supervisor import NovelSupervisor
except ImportError:
    NovelSupervisor = None

__all__ = [
    'Prompts',
    'ThemeAgent',
    'CharacterAgent',
    'OutlineAgent',
    'ContentAgent',
    'NovelSupervisor'
]
