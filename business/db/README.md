# SQLite Database Server

提供 SQL 执行接口，供 Agent 通过 HTTP 调用。

## 启动

```bash
python -m business.db.server
```

服务地址：`http://127.0.0.1:3307`

## 接口

### POST /sql
执行 SQL 语句

```bash
curl -X POST http://127.0.0.1:3307/sql \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM person", "params": null}'
```

响应：
```json
{
  "success": true,
  "rows": [...],
  "columns": ["id", "name", "age", ...]
}
```

### GET /init
初始化数据库（建表+插入数据）

```bash
curl http://127.0.0.1:3307/init
```

### GET /health
健康检查

```bash
curl http://127.0.0.1:3307/health
```

## Agent 工具

Agent 通过 `execute_remote_mysql_command` 工具调用数据库：

```python
from core.base.tools.mysql_executor import execute_remote_mysql_command

result = execute_remote_mysql_command.invoke({
    "sql_command": "SELECT * FROM person WHERE age > 20",
    "host": "127.0.0.1",
    "port": 3307
})
```

## 表结构

### person（人物表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | VARCHAR(100) | 姓名 |
| worldview | TEXT | 世界观/时代背景 |
| race | TEXT | 种族 |
| hometown | VARCHAR(255) | 出生地 |
| gender | VARCHAR(50) | 性别 |
| biography | TEXT | 人生经历 |
| age | INTEGER | 年龄 |
| personality | TEXT | 性格 |
| cognition | TEXT | 对世界的认知 |
| keywords | VARCHAR(255) | 关键词 |

## 安全

- 仅允许 SELECT/INSERT/UPDATE/DELETE/SHOW/PRAGMA 语句
- 禁止 DROP/TRUNCATE/ALTER/GRANT/REVOKE/CREATE
- 不支持多语句执行（分号分隔）
