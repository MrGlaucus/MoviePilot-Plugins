# 发布组统计回归测试

测试使用 Python 3.12、Pydantic 2 和 APScheduler 3；在 MoviePilot 宿主虚拟环境中运行时可复用这些依赖。仓库没有独立宿主：插件入口测试显式提供 MoviePilot 基类、配置和事件的最小替身，扫描测试使用真实临时目录，Cron 使用真实 APScheduler。

```powershell
python -m unittest discover -s tests -v
python -m compileall -q plugins.v2/releasegroupstats plugins.v3/releasegroupstats scripts tests
git diff --check
```

本次桌面验证的额外测试依赖放在忽略目录 `.cache/test-deps`，测试会在该目录存在时优先查找；临时文件位于 `.cache/tests`，避免 Windows 沙箱系统临时目录的权限限制。

验证范围：识别规则、目录合并、流式统计、取消与重载、错误恢复、持久化、Cron、API 声明、页面 JSON、索引版本、代际打包。

真实宿主验收仍需完成：安装/重载插件、bearer 路由权限、定时服务出现在服务列表、实际远程消息、V3 分身、原生配置页和仪表板。Vue/Vuetify 本地预览检查不能替代宿主联调。
