1. 生成theme.md文件

- 用户给出一个idea，通过idea生成一个核心部分，即世界观、核心爽点，即小说的核心部分
  - create_theme.md

2. 人物生成

- 基于世界观和核心爽点，生成适配的主角，和其他主要人物
  - create_main_character.md

3. 大纲编写循环

- 基于世界观和核心爽点，以及人物，生成适配的总纲+卷钢
  - create_outline.md
- 基于总纲+卷钢+之前的章纲，生成下一章的章纲，注意这是一个循环
  - generate_small_outline.md

4. 基于大纲编写小说内容

- 世界观+人物+总纲+卷纲+章纲+上一章的小说内容，生成下一章的小说内容，需要等待上一章的章纲生成完毕
  - generate_content.md


人物表格式：

```sql
CREATE TABLE IF NOT EXISTS person (
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '人物唯一标识，0表示主角',
    novel_id INTEGER NOT NULL COMMENT '小说ID，0表示没有实例小说，表示总人物库',
    worldview TEXT COMMENT '所处的世界观以及时代背景',
    name VARCHAR(100) NOT NULL COMMENT '人物的姓名',
    race TEXT COMMENT '人物的种族，非人类时需要描述种族特征',
    gender VARCHAR(50) COMMENT '人物的性别，男性，女性，其他种族可能有双性，无性',
    age INT COMMENT '该人物目前的年龄',
    hometown VARCHAR(255) COMMENT '出生地，小时候成长的地方',
    biography TEXT COMMENT '这个人做了哪些在他的人生中影响比较大的事，用python列表格式呈现',
    personality TEXT COMMENT '基本概括这个人性格',
    cognition TEXT COMMENT '这个人对世界的认知，包括：对世界的理解、对人物的理解等',
    relationship TEXT COMMENT '人物之间的关系，采用json格式,{"人物姓名":"关系描述"}',
    keywords VARCHAR(255) COMMENT '用3-5个词快速概括人物的本质特征，便于后续检索和归类'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

大纲表+小说内容格式：

```sql
CREATE TABLE outlines (
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    id INTEGER PRIMARY KEY COMMENT '大纲唯一标识',
    novel_id INTEGER NOT NULL COMMENT '小说ID',
    type TEXT CHECK(type IN ('master', 'volume', 'chapter')) COMMENT '大纲类型，master表示总纲，volume表示卷纲，chapter表示章纲',
    parent_id INTEGER COMMENT '父节点ID，总纲的parent_id为NULL',
    sequence INTEGER NOT NULL COMMENT '同一父节点下的排序从1开始，0表示总纲',
    version INTEGER DEFAULT 1 COMMENT '大纲的版本号，默认1',
    is_active BOOLEAN DEFAULT 1 COMMENT '是否激活，默认激活，一个大纲可以有多个版本，每个版本可以有不同的内容，不激活的属于废稿，不继续往下创建子纲',
    title TEXT COMMENT '大纲的标题',
    content TEXT COMMENT '大纲的内容',
    novel_content TEXT COMMENT '基于章纲的小说内容，默认为空',
    FOREIGN KEY (parent_id) REFERENCES outlines(id) ON DELETE CASCADE
);
-- 索引：加速按小说+父节点排序查询
CREATE INDEX idx_outlines_parent ON outlines(novel_id, parent_id, sequence);
```

需要改进的地方：

1. 不要让他一下就所有步骤生成，可以多个步骤，这样方便调试改进，类似claude code的操作
2. 不用的工具可以用不同的工具流，工具流可以是subagent，也可以是其他的

我理解可以是基于agent来让他做任务，不同的任务对应不同的工作流

避免上下文溢出的方式：

1. skill渐进式纰漏
2. subagent方式

想下最简单的功能：生成人物，需要用什么Agent来实现？

我需要不断你的叠加，不断的迭代，如何适配呢？



基本功能 + 经验

将经验变得可扩展化

首先，新的工具和agent一定是可以添加的模式



需要有一个总的agent来管理总项目


---

项目架构改进

有一个主agent，主agent负责管理所有的agent
subagent调用，调用其他agent来完成任务
1. 用agent通信协议(A2A)实现不同Agent的通信
2. 实现方式：直接新建新的进程来实现，每个进程都是一个agent，agent之间通过A2A协议通信，实现任务的分配和协调
3. 前端：类似网页的多个窗口，每个窗口都是一个agent，用户可以在前端操作


一个agent设置为一个文件夹，包括如下字文件夹：
1. cores：agent核心代码，python langgraph实现，包括agent的定义、执行、通信方式等，本质上和claude code的对话方式相同
1. skills：本质上渐进式披露md文件，agent会读取md文件获取相关知识，注意skills有嵌套，文件形式为skills-kill名称-skill.md、相关工具代码
2. tools：模型能直接访问的工具，即函数调用，就放在这里
2. prompts：涉及到的所有prompt文件，即固定的上下文添加内容，就放在这里
3. memories：agent的内存文件，用于存储agent的上下文信息，包括历史对话、任务分配、协调信息等


Agent服务端：Python
前端：React
数据库：MySQL
