# G0 基线

- 日期：2026-10-31；分支 upgrade/steedatlas-v2；基线 162a28575d957e1248b7fa1f7380c68e30dd5ad1，初始工作树干净。
- 原站只有编译前端；独立 Next 原型缺实现。采用新增 frontend/ 可维护工程，旧前端保留 /legacy/。
- 只修改 baiqipu-github 副本，不修改原 wangzhan 运行目录或线上数据。
- 历史 SQLite 通过只读连接的 backup API 备份到 ignored runtime/backups/legacy.db，未复制凭据。
- 历史各文件哈希及数据表计数见 baseline-manifest.json。源码/媒体/数据均不删除。
- 默认 Python 指向 MSYS2；使用项目 .venv Python 3.13。FFmpeg/FFprobe/Node 已存在。
- 旧项目没有标准 pytest/CI；初始运行验证在依赖环境建立后进行，不能视为已通过。
