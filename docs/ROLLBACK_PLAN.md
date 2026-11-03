# 回退

旧站代码与原始数据库未改动，可继续使用原 wangzhan/start-site.bat。V2 仅在副本启动，默认外部调用和公开发布关闭。
V2 迁移采用新增表；先备份目标库，在数据库副本执行 alembic upgrade head；回退用 alembic downgrade -1 删除 V2 表（会丢失该副本的 V2 数据，须先导出，真实环境需授权）。
禁止 reset/clean/force push。通过切换已提交版本恢复代码，避免覆盖未提交用户更改。
