# 发布组统计插件设计文档

**创建日期**: 2026-06-18  
**插件名称**: ReleaseGroupStats  
**版本**: 1.0  

---

## 1. 项目概述

### 1.1 功能描述
开发一个 MoviePilot 插件，用于扫描用户配置的目录，通过文件名正则匹配识别影视资源的发布组，并按发布组进行分类统计。支持定时任务和手动触发，提供仪表板 Widget 和详细统计页面展示。

### 1.2 核心需求
- 支持配置多个扫描目录（分号分隔）
- 递归扫描所有子目录
- 仅扫描常见视频格式文件
- 基于正则表达式匹配发布组
- 统计每个发布组的文件数量、总大小、文件列表
- 无法匹配的文件归类为"其它"
- 扫描结果持久化保存到 JSON 文件
- 支持 Cron 定时任务自动扫描
- 支持手动触发扫描
- 仪表板 Widget 显示 Top 5 发布组
- 插件详情页显示完整统计信息

---

## 2. 技术架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────┐
│              用户界面层                       │
├──────────────┬──────────────┬───────────────┤
│  配置页面     │  Widget      │  详情页面      │
│  (get_form)  │ (get_dashboard)│  (get_page)   │
└──────────────┴──────────────┴───────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│              业务逻辑层                       │
├──────────────┬──────────────┬───────────────┤
│  定时调度     │  API 接口    │  扫描引擎      │
│ (get_service)│ (get_api)    │ (_execute_scan)│
└──────────────┴──────────────┴───────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│              数据处理层                       │
├──────────────┬──────────────┬───────────────┤
│  文件扫描     │  发布组匹配   │  统计分析      │
│(_scan_dir)   │(_match_group)│(_analyze_files)│
└──────────────┴──────────────┴───────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│              数据持久化层                     │
├─────────────────────────────────────────────┤
│         stats_data.json                      │
└─────────────────────────────────────────────┘
```

### 2.2 数据流

```
触发(定时/手动) → 读取配置 → 遍历目录 → 过滤视频文件 
→ 匹配发布组 → 统计数据 → 保存JSON → 更新UI
```

---

## 3. 核心组件设计

### 3.1 发布组字典 (RELEASE_GROUPS)

硬编码在代码中，包含 50+ 个发布组及其正则表达式别名：

```python
RELEASE_GROUPS: Dict[str, List[str]] = {
    "0ff": ['FF(?:(?:A|WE)B|CD|E(?:DU|B)|TV)'],
    "观众": ['Audies', r'\bAD(?:Audio|E(?:book|)|Music|Web)\b'],
    "馒头": ['MTeam(?:TV|)', 'MPAD', 'MWeb'],
    "朋友": ['FRDS', 'Yumi', 'cXcY'],
    # ... 更多发布组
    "anime": [r'\bANi\b', 'LoliHouse', ...],
    "others": ['B(?:MDru|eyondHD|TN)', ...]
}
```

**注意**: 部分发布组（如 1pt, 52pt, azusa 等）当前别名为空数组，后续可扩展。

### 3.2 发布组匹配引擎

**方法**: `_match_release_group(filename: str) -> str`

**算法流程**:
1. 提取文件名（不含扩展名）
2. 遍历 RELEASE_GROUPS 字典
3. 对每个发布组的别名列表：
   - 尝试使用 `re.search(alias, name_part, re.IGNORECASE)` 匹配
   - 捕获 `re.error` 异常，记录警告日志
   - 匹配成功立即返回发布组名
4. 检查组名本身是否出现在文件名中（大小写不敏感）
5. 未匹配则返回 "其它"

**示例**:
- 输入: `Movie.Name.2023.1080p.BluRay.x264-MTeam.mkv`
- 输出: `"馒头"`

### 3.3 文件扫描引擎

**方法**: `_scan_directory(directory: str, extensions: List[str]) -> List[Dict]`

**功能**:
- 递归遍历目录（`os.walk`）
- 过滤指定扩展名的文件
- 收集文件信息：路径、大小、修改时间

**默认视频扩展名**:
```python
DEFAULT_VIDEO_EXTENSIONS = [
    '.mkv', '.mp4', '.avi', '.iso', '.ts', 
    '.flv', '.wmv', '.mov', '.m4v', '.webm'
]
```

**返回值结构**:
```python
[
    {
        "path": "/media/movies/Movie.mkv",
        "size": 1234567890,
        "mtime": 1234567890.0
    },
    ...
]
```

### 3.4 统计分析器

**方法**: `_analyze_files(file_list: List[Dict]) -> Dict`

**处理流程**:
1. 初始化统计字典
2. 遍历文件列表：
   - 调用 `_match_release_group` 获取发布组
   - 累加该组的文件数量和大小
   - 记录文件路径到该组列表
3. 计算总计数据
4. 生成 Top 5 排行（按文件数量降序）

**返回数据结构**:
```python
{
    "total_files": 1234,
    "total_size_bytes": 9876543210,
    "groups": {
        "馒头": {
            "count": 100,
            "size_bytes": 123456789,
            "files": ["/path/to/file1.mkv", ...]
        },
        "朋友": {
            "count": 80,
            "size_bytes": 98765432,
            "files": [...]
        },
        "其它": {
            "count": 50,
            "size_bytes": 12345678,
            "files": [...]
        }
    },
    "top5": [
        {"name": "馒头", "count": 100, "percentage": 8.1},
        {"name": "朋友", "count": 80, "percentage": 6.5},
        ...
    ]
}
```

### 3.5 数据持久化

**存储位置**: 插件目录下的 `stats_data.json`

**文件结构**:
```json
{
    "last_scan_time": "2026-06-18 14:30:00",
    "scan_duration_seconds": 12.5,
    "total_files": 1234,
    "total_size_bytes": 9876543210,
    "groups": {
        "馒头": {
            "count": 100,
            "size_bytes": 123456789,
            "files": ["/path/to/file1.mkv", ...]
        }
    }
}
```

**读写方法**:
- `_save_stats(stats: Dict)` - 保存统计数据
- `_load_stats() -> Dict` - 加载统计数据

**错误处理**: 捕获 IO 异常，记录日志但不中断程序

### 3.6 定时任务调度

**方法**: `get_service() -> List[Dict[str, Any]]`

**配置**: 使用 MoviePilot 标准的 Cron 表达式

**示例配置**:
- 每天凌晨 2 点: `0 2 * * *`
- 每小时: `0 * * * *`
- 每周一上午 9 点: `0 9 * * 1`

**注册逻辑**:
```python
if self._enabled and self._cron:
    return [{
        "id": "ReleaseGroupStats",
        "name": "发布组统计定时任务",
        "trigger": "cron",
        "func": self._execute_scan,
        "args": [],
        "cron": self._cron
    }]
return []
```

### 3.7 API 接口

**手动触发扫描**:
- **路径**: `/start_scan`
- **方法**: POST
- **功能**: 启动后台扫描线程
- **返回**: `{"success": True, "message": "扫描已启动"}`

---

## 4. 用户界面设计

### 4.1 配置页面 (get_form)

**布局结构**:

```
┌────────────────────────────────────────┐
│  ☑ 启用插件                             │
├────────────────────────────────────────┤
│  扫描目录                               │
│  ┌──────────────────────────────────┐  │
│  │ /media/movies;/media/tvshows     │  │
│  └──────────────────────────────────┘  │
│  (分号分隔多个目录，使用容器路径)        │
├────────────────────────────────────────┤
│  定时任务 (Cron 表达式)                 │
│  ┌──────────────────────────────────┐  │
│  │ 0 2 * * *                        │  │
│  └──────────────────────────────────┘  │
├────────────────────────────────────────┤
│  视频文件扩展名 (可选)                   │
│  ┌──────────────────────────────────┐  │
│  │ .mkv                             │  │
│  │ .mp4                             │  │
│  └──────────────────────────────────┘  │
│  (每行一个，留空使用默认)                │
├────────────────────────────────────────┤
│  [立即扫描]  [清除统计数据]             │
├────────────────────────────────────────┤
│  ℹ️ 提示:                               │
│  • 目录使用容器路径                     │
│  • 扫描在后台执行，请查看日志           │
│  • 大目录可能需要较长时间               │
└────────────────────────────────────────┘
```

**配置项数据结构**:
```python
{
    "enabled": False,
    "scan_paths": "",
    "cron": "",
    "custom_extensions": ""
}
```

### 4.2 仪表板 Widget (get_dashboard)

**显示内容**:

```
┌────────────────────────────────────┐
│ 📊 发布组统计                       │
├────────────────────────────────────┤
│ 总文件: 1,234  |  总大小: 1.2 TB   │
├────────────────────────────────────┤
│ Top 5 发布组:                      │
│                                    │
│ 馒头  ████████████░░░░  100 (8.1%) │
│       123.4 GB                     │
│                                    │
│ 朋友  ██████████░░░░░░   80 (6.5%) │
│       98.7 GB                      │
│                                    │
│ 彩虹岛 ████████░░░░░░░░   60 (4.9%)│
│       76.5 GB                      │
│                                    │
│ 天空  ██████░░░░░░░░░░   50 (4.1%) │
│       65.4 GB                      │
│                                    │
│ 柠檬  ████░░░░░░░░░░░░   40 (3.2%) │
│       54.3 GB                      │
├────────────────────────────────────┤
│ 最近扫描: 2026-06-18 14:30         │
│ [查看详情 →]                       │
└────────────────────────────────────┘
```

**交互**: 点击 Widget 跳转到插件详情页

### 4.3 插件详情页面 (get_page)

**页面布局**:

#### A. 概览卡片区域

```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│  总文件数    │  总大小      │  发布组数量  │  扫描耗时    │
│  1,234      │  1.2 TB     │  25         │  12.5 秒    │
└─────────────┴─────────────┴─────────────┴─────────────┘
┌─────────────────────────────────────────────────────┐
│ 最近扫描时间: 2026-06-18 14:30:00                    │
│ [刷新统计]                                           │
└─────────────────────────────────────────────────────┘
```

#### B. 发布组详细列表（表格）

```
┌────┬────────┬──────┬──────┬────────┬────────┐
│排名│发布组  │文件数│占比  │大小    │操作    │
├────┼────────┼──────┼──────┼────────┼────────┤
│ 1  │馒头    │ 100  │ 8.1% │123.4GB │[查看]  │
│ 2  │朋友    │  80  │ 6.5% │ 98.7GB │[查看]  │
│ 3  │彩虹岛  │  60  │ 4.9% │ 76.5GB │[查看]  │
│... │...     │ ...  │ ...  │ ...    │ ...    │
└────┴────────┴──────┴──────┴────────┴────────┘
```

**功能**:
- 支持按文件数/大小排序
- 点击"查看"展开文件列表抽屉

#### C. 文件列表抽屉

```
┌────────────────────────────────────────┐
│ 馒头 (100 个文件)                       │
├────────────────────────────────────────┤
│ /media/movies/Movie1-MTeam.mkv         │
│ /media/movies/Movie2-MTeam.mkv         │
│ /media/tvshows/Show.S01E01-MTeam.mkv   │
│ ...                                    │
├────────────────────────────────────────┤
│ [复制全部路径]                         │
└────────────────────────────────────────┘
```

#### D. 图表展示（可选）

- **饼图**: 发布组占比分布（Top 10 + 其它）
- **柱状图**: Top 10 发布组文件数量对比

---

## 5. 类结构设计

```python
class ReleaseGroupStats(_PluginBase):
    """发布组统计插件"""
    
    # ===== 插件元数据 =====
    plugin_name = "发布组统计"
    plugin_desc = "扫描目录并按发布组分类统计影视资源"
    plugin_icon = "https://raw.githubusercontent.com/..."
    plugin_color = "#4CAF50"
    plugin_version = "1.0"
    plugin_author = "MrGlaucus"
    author_url = "https://github.com/MrGlaucus"
    plugin_config_prefix = "releasegroupstats_"
    plugin_order = 10
    auth_level = 1
    
    # ===== 常量定义 =====
    RELEASE_GROUPS: Dict[str, List[str]] = {...}
    DEFAULT_VIDEO_EXTENSIONS: List[str] = [...]
    STATS_FILE: str = "stats_data.json"
    
    # ===== 私有属性 =====
    _enabled: bool = False
    _scan_paths: str = ""
    _cron: str = ""
    _custom_extensions: str = ""
    _is_scanning: bool = False
    _stats_data: Dict = {}
    
    # ===== 生命周期方法 =====
    def init_plugin(self, config: dict = None)
    def get_state(self) -> bool
    def get_service(self) -> List[Dict[str, Any]]
    def stop_service(self)
    
    # ===== 配置和页面 =====
    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]
    def get_page(self) -> List[dict]
    def get_dashboard(self, key: str, **kwargs) -> Optional[dict]
    
    # ===== API 接口 =====
    def get_api(self) -> List[Dict[str, Any]]
    def start_scan(self) -> Dict
    
    # ===== 核心业务逻辑 =====
    def _match_release_group(self, filename: str) -> str
    def _scan_directory(self, directory: str, extensions: List[str]) -> List[Dict]
    def _analyze_files(self, file_list: List[Dict]) -> Dict
    def _execute_scan(self)
    
    # ===== 数据持久化 =====
    def _save_stats(self, stats: Dict)
    def _load_stats(self) -> Dict
    
    # ===== 工具方法 =====
    def _format_size(self, size_bytes: int) -> str
    def _get_video_extensions(self) -> List[str]
    def _calculate_percentage(self, count: int, total: int) -> float
```

---

## 6. 关键算法实现

### 6.1 发布组匹配

```python
def _match_release_group(self, filename: str) -> str:
    """
    基于文件名匹配发布组
    
    Args:
        filename: 文件名（含扩展名）
    
    Returns:
        发布组名称，未匹配返回"其它"
    """
    if not filename:
        return "其它"
    
    # 提取文件名（不含扩展名）
    name_part = os.path.splitext(filename)[0]
    
    # 遍历发布组字典
    for group_name, alias_list in self.RELEASE_GROUPS.items():
        # 尝试匹配每个别名
        for alias in alias_list:
            try:
                if re.search(alias, name_part, re.IGNORECASE):
                    return group_name
            except re.error as e:
                logger.warning(
                    f"无效正则表达式: '{alias}' for group '{group_name}'. "
                    f"Error: {e}"
                )
                continue
        
        # 检查组名本身
        if group_name.upper() in name_part.upper():
            return group_name
    
    return "其它"
```

### 6.2 后台扫描流程

```python
def _execute_scan(self):
    """执行扫描任务（后台线程）"""
    if self._is_scanning:
        logger.warn("扫描正在进行中，请勿重复触发")
        return
    
    self._is_scanning = True
    start_time = time.time()
    
    try:
        # 1. 解析配置
        paths = [
            p.strip() 
            for p in self._scan_paths.split(';') 
            if p.strip()
        ]
        extensions = self._get_video_extensions()
        
        if not paths:
            logger.warn("未配置扫描目录")
            return
        
        # 2. 扫描所有目录
        all_files = []
        for path in paths:
            if not os.path.exists(path):
                logger.warn(f"目录不存在: {path}，跳过")
                continue
            
            try:
                files = self._scan_directory(path, extensions)
                all_files.extend(files)
                logger.info(f"目录 {path} 扫描完成，找到 {len(files)} 个文件")
            except Exception as e:
                logger.error(f"扫描目录 {path} 失败: {str(e)}", exc_info=True)
        
        # 3. 统计分析
        if not all_files:
            logger.info("未找到任何视频文件")
            return
        
        stats = self._analyze_files(all_files)
        
        # 4. 添加元数据
        stats['last_scan_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        stats['scan_duration_seconds'] = round(
            time.time() - start_time, 2
        )
        
        # 5. 保存结果
        self._save_stats(stats)
        
        # 6. 发送通知
        logger.info(
            f"扫描完成: {stats['total_files']} 个文件, "
            f"耗时 {stats['scan_duration_seconds']} 秒"
        )
        self.post_message(
            title="发布组统计完成",
            text=f"共扫描 {stats['total_files']} 个文件，"
                 f"耗时 {stats['scan_duration_seconds']} 秒"
        )
        
    except Exception as e:
        logger.error(f"扫描失败: {str(e)}", exc_info=True)
    finally:
        self._is_scanning = False
```

### 6.3 文件大小格式化

```python
def _format_size(self, size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 字节数
    
    Returns:
        格式化字符串，如 "1.2 GB", "500 MB"
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    elif size_bytes < 1024 ** 4:
        return f"{size_bytes / 1024 ** 3:.1f} GB"
    else:
        return f"{size_bytes / 1024 ** 4:.2f} TB"
```

---

## 7. 错误处理和边界情况

### 7.1 异常处理策略

| 场景 | 处理方式 | 日志级别 |
|------|---------|---------|
| 目录不存在 | 跳过该目录，继续扫描其他 | WARN |
| 权限不足 | 捕获 PermissionError，跳过 | ERROR |
| 正则表达式错误 | 捕获 re.error，跳过该规则 | WARNING |
| JSON 读写失败 | 捕获 IOError，记录错误 | ERROR |
| 扫描中断 | try-finally 重置标志 | INFO |
| 空目录 | 正常处理，返回空列表 | INFO |
| 无视频文件 | 正常处理，统计为 0 | INFO |

### 7.2 并发控制

- 使用 `_is_scanning` 标志防止重复扫描
- 所有扫描操作在独立线程中执行
- 线程安全的数据读写（JSON 文件操作加锁）

### 7.3 性能优化

- 后台线程避免阻塞 UI
- 分批处理大目录（后续优化）
- 缓存扫描结果避免重复计算
- 增量扫描（V2 版本规划）

---

## 8. 测试计划

### 8.1 单元测试

1. **发布组匹配测试**
   - 测试已知发布组的正确匹配
   - 测试未匹配文件返回"其它"
   - 测试正则表达式错误处理
   - 测试大小写不敏感匹配

2. **文件扫描测试**
   - 测试递归扫描
   - 测试文件扩展名过滤
   - 测试空目录处理
   - 测试不存在目录处理

3. **统计分析测试**
   - 测试文件数量统计
   - 测试文件大小计算
   - 测试 Top 5 排序
   - 测试百分比计算

4. **数据持久化测试**
   - 测试 JSON 写入
   - 测试 JSON 读取
   - 测试文件损坏恢复

### 8.2 集成测试

1. **端到端扫描测试**
   - 配置测试目录
   - 触发扫描
   - 验证统计结果

2. **定时任务测试**
   - 配置 Cron 表达式
   - 等待触发
   - 验证自动执行

3. **API 测试**
   - 调用手动触发 API
   - 验证响应
   - 验证后台执行

### 8.3 UI 测试

1. **配置页面**
   - 验证表单渲染
   - 验证配置保存
   - 验证输入校验

2. **Widget 测试**
   - 验证数据显示
   - 验证跳转功能
   - 验证空状态显示

3. **详情页面**
   - 验证表格渲染
   - 验证排序功能
   - 验证文件列表展开

---

## 9. 部署和配置

### 9.1 插件安装

1. 将插件目录复制到 `plugins/releasegroup/`
2. 重启 MoviePilot
3. 在插件市场启用插件

### 9.2 初始配置

1. 配置扫描目录（容器路径）
2. 配置 Cron 定时任务（可选）
3. 点击"立即扫描"测试

### 9.3 目录路径说明

**重要**: 必须使用容器内的路径，而非宿主机路径

示例:
- ✅ 正确: `/media/movies`
- ❌ 错误: `D:\Movies` 或 `/mnt/user/movies`

---

## 10. 未来扩展

### 10.1 V2 版本规划

1. **增量扫描**
   - 记录文件 hash 或修改时间
   - 只扫描新增/修改的文件
   - 大幅提升大目录扫描速度

2. **发布组字典管理**
   - 在 UI 上编辑发布组别名
   - 导入/导出发布组配置
   - 社区共享发布组字典

3. **高级统计**
   - 按年份统计
   - 按分辨率统计
   - 按文件格式统计
   - 趋势图表（历史数据对比）

4. **导出功能**
   - CSV 导出
   - JSON 导出
   - Excel 导出

5. **通知增强**
   - 扫描完成通知
   - 异常情况通知
   - 可配置通知模板

### 10.2 性能优化

1. **多线程扫描**
   - 并行扫描多个目录
   - 提升多目录场景速度

2. **数据库存储**
   - 使用 SQLite 替代 JSON
   - 支持更复杂的查询
   - 更好的大数据性能

3. **缓存机制**
   - 内存缓存热点数据
   - 减少磁盘 IO

---

## 11. 参考资料

- MoviePilot 插件开发文档: `docs/V2_Plugin_Development.md`
- 参考插件: `plugins.v2/nforeplacetool/__init__.py`
- Python 正则表达式文档
- MoviePilot API 文档

---

## 12. 变更记录

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|---------|
| 1.0 | 2026-06-18 | MrGlaucus | 初始设计文档 |

---

**设计文档状态**: ✅ 已完成  
**下一步**: 调用 writing-plans 技能创建实现计划
