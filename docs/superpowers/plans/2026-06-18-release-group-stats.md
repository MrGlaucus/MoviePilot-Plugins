# 发布组统计插件实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现 MoviePilot 发布组统计插件，支持扫描目录、按发布组分类统计、定时任务和可视化展示

**架构：** 基于 _PluginBase 的单体插件，包含配置页面、仪表板 Widget、详情页面三个 UI 组件，通过后台线程执行文件扫描和统计分析，结果持久化到 JSON 文件

**技术栈：** Python 3.x, MoviePilot Plugin API, Vuetify UI, 正则表达式, JSON 文件存储

---

## 文件结构

### 创建的文件
- `plugins/releasegroup/__init__.py` - 主插件类（约 600-800 行）
- `plugins/releasegroup/stats_data.json` - 统计数据文件（运行时生成）

### 参考文件
- `plugins.v2/nforeplacetool/__init__.py` - 代码格式参考
- `docs/superpowers/specs/2026-06-18-release-group-stats-design.md` - 设计文档

---

## 任务分解

### 任务 1：插件基础结构和元数据

**文件：**
- 创建：`plugins/releasegroup/__init__.py`

**目标：** 建立插件类框架，定义所有元数据和私有属性

- [ ] **步骤 1：创建插件类骨架**

```python
import os
import re
import json
import time
import threading
from datetime import datetime
from typing import Any, List, Dict, Tuple, Optional
from pathlib import Path

from app.log import logger
from app.plugins import _PluginBase


class ReleaseGroupStats(_PluginBase):
    """发布组统计插件"""
    
    # 插件名称
    plugin_name = "发布组统计"
    # 插件描述
    plugin_desc = "扫描目录并按发布组分类统计影视资源"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/MrGlaucus/MoviePilot-Plugins/main/icons/Ptools_B.png"
    # 主题色
    plugin_color = "#4CAF50"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "MrGlaucus"
    # 作者主页
    author_url = "https://github.com/MrGlaucus"
    # 插件配置项ID前缀
    plugin_config_prefix = "releasegroupstats_"
    # 加载顺序
    plugin_order = 10
    # 可使用的用户级别
    auth_level = 1
    
    # 私有属性
    _enabled = False
    _scan_paths = ""
    _cron = ""
    _custom_extensions = ""
    _is_scanning = False
    _stats_data = {}
    
    def init_plugin(self, config: dict = None):
        """初始化插件"""
        pass
    
    def get_state(self) -> bool:
        """获取插件状态"""
        return self._enabled
    
    def stop_service(self):
        """停止服务"""
        pass
```

- [ ] **步骤 2：验证文件创建成功**

检查文件是否存在且无语法错误：
```bash
python -m py_compile plugins/releasegroup/__init__.py
```

预期：无输出（编译成功）

---

### 任务 2：定义发布组字典和常量

**文件：**
- 修改：`plugins/releasegroup/__init__.py:60-80`

**目标：** 添加 RELEASE_GROUPS 字典和默认视频扩展名常量

- [ ] **步骤 1：添加常量和发布组字典**

在类定义中添加（在私有属性之后）：

```python
    # 常量定义
    DEFAULT_VIDEO_EXTENSIONS = [
        '.mkv', '.mp4', '.avi', '.iso', '.ts',
        '.flv', '.wmv', '.mov', '.m4v', '.webm'
    ]
    
    # 统计数据文件路径
    STATS_FILE = "stats_data.json"
    
    # 发布组字典
    RELEASE_GROUPS: Dict[str, List[str]] = {
        "0ff": ['FF(?:(?:A|WE)B|CD|E(?:DU|B)|TV)'],
        "1pt": [],
        "52pt": [],
        "观众": ['Audies', r'\bAD(?:Audio|E(?:book|)|Music|Web)\b'],
        "azusa": [],
        "备胎": ['BeiTai'],
        "学校": ['Bts(?:CHOOL|HD|PAD|TV)', 'Zone'],
        "carpt": ['CarPT'],
        "彩虹岛": ['CHD(?:Bits|PAD|(?:|HK)TV|WEB|)', 'StBOX', 'OneHD', 'Lee', 'xiaopie'],
        "碟粉": ['discfan'],
        "dragonhd": [],
        "eastgame": ['(?:(?:iNT|(?:HALFC|Mini(?:S|H|FH)D))-|)TLF'],
        "filelist": [],
        "gainbound": ['(?:DG|GBWE)B'],
        "hares": ['Hares(?:(?:M|T)V|Web|)'],
        "hd4fans": [],
        "高清视界": ['HDA(?:pad|rea|TV)', 'EPiC'],
        "阿童木": ['hdatmos'],
        "hdbd": [],
        "hdchina": ['HDC(?:hina|TV|)', 'k9611', 'tudou', 'iHD'],
        "杜比": ['D(?:ream|BTV)', '(?:HD|QHstudI)o'],
        "红豆饭": ['beAst(?:TV|)', 'HDFans'],
        "家园": ['HDH(?:ome|Pad|TV|WEB|)'],
        "hdpt": ['HDPT(?:Web|)'],
        "天空": ['HDS(?:ky|TV|Pad|WEB|)', 'AQLJ'],
        "高清时间": ['hdtime'],
        "HDU": [],
        "hdvideo": [],
        "hdzone": ['HDZ(?:one|)'],
        "憨憨": ['HHWEB'],
        "末日": ['AGSV(PT|WEB|MUS)'],
        "hitpt": [],
        "htpt": ['HTPT'],
        "iptorrents": [],
        "joyhd": [],
        "朋友": ['FRDS', 'Yumi', 'cXcY'],
        "柠檬": ['L(?:eague(?:(?:C|H)D|(?:M|T)V|NF|WEB)|HD)', 'i18n', 'CiNT'],
        "馒头": ['MTeam(?:TV|)', 'MPAD', 'MWeb'],
        "nanyangpt": [],
        "老师": ['nicept'],
        "oshen": [],
        "我堡": ['Our(?:Bits|TV)', 'FLTTH', 'PbK', 'MGs', 'iLove(?:HD|TV)'],
        "猪猪": ['PiGo(?:NF|(?:H|WE)B)'],
        "铂金学院": ['ptchina'],
        "猫站": ['PTer(?:DIY|Game|(?:M|T)V|WEB|)'],
        "pthome": ['PTH(?:Audio|eBook|music|ome|tv|WEB|)'],
        "ptmsg": [],
        "烧包": ['PTsbao', 'OPS', 'F(?:Fans(?:AIeNcE|BD|D(?:VD|IY)|TV|WEB)|HDMv)', 'SGXT'],
        "pttime": [],
        "葡萄": ['PuTao'],
        "聆音": ['lingyin'],
        "春天": [r"CMCT(?:A|V)?", "Oldboys", "GTR", "CLV", "CatEDU", "Telesto", "iFree"],
        "鲨鱼": ['Shark(?:WEB|DIY|TV|MV|)'],
        "他吹吹风": ['tccf'],
        "北洋园": ['TJUPT'],
        "听听歌": ['TTG', 'WiKi', 'NGB', 'DoA', '(?:ARi|ExRE)N'],
        "U2": [],
        "ultrahd": [],
        "others": ['B(?:MDru|eyondHD|TN)', 'C(?:fandora|trlhd|MRG)', 'DON', 'EVO', 'FLUX', 'HONE(?:yG|)',
                   'N(?:oGroup|T(?:b|G))', 'PandaMoon', 'SMURF', 'T(?:EPES|aengoo|rollHD )'],
        "anime": [r'\bANi\b', r'\bHYSUB\b', r'\bKTXP\b', 'LoliHouse', r'\bMCE\b', 'Nekomoe kissaten', 'SweetSub', 'MingY',
                  '(?:Lilith|NC|AI)-Raws', 'VCB-Stuido', '织梦字幕组', '枫叶字幕组', '猎户手抄部', '喵萌奶茶屋', '漫猫字幕社',
                  '霜庭云花Sub', '北宇治字幕组', '氢气烤肉架', '云歌字幕组', '萌樱字幕组', '极影字幕社',
                  '悠哈璃羽字幕社',
                  '拨雪寻春', '沸羊羊(?:制作|字幕组)', '(?:桜|樱)都字幕组'],
        "青蛙": ['FROG(?:E|Web|)'],
        "ubits": ['UB(?:its|WEB|TV)'],
        "影巢": ['HiveWeb'],
    }
```

- [ ] **步骤 2：验证字典格式正确**

运行 Python 检查语法：
```bash
python -c "import ast; ast.parse(open('plugins/releasegroup/__init__.py').read())"
```

预期：无错误输出

---

### 任务 3：实现配置初始化方法

**文件：**
- 修改：`plugins/releasegroup/__init__.py:init_plugin`

**目标：** 实现 init_plugin 方法，从配置中读取参数并启动定时任务

- [ ] **步骤 1：实现 init_plugin 方法**

替换 `init_plugin` 方法：

```python
    def init_plugin(self, config: dict = None):
        """初始化插件"""
        if config:
            self._enabled = config.get("enabled", False)
            self._scan_paths = config.get("scan_paths", "")
            self._cron = config.get("cron", "")
            self._custom_extensions = config.get("custom_extensions", "")
        
        # 加载已保存的统计数据
        self._stats_data = self._load_stats()
        
        logger.info(f"发布组统计插件初始化完成，启用状态: {self._enabled}")
```

- [ ] **步骤 2：测试配置加载**

创建临时测试脚本验证逻辑（可选）：
```python
# 快速验证配置解析
config = {
    "enabled": True,
    "scan_paths": "/media/movies;/media/tvshows",
    "cron": "0 2 * * *"
}
# 手动调用 init_plugin 检查属性是否正确设置
```

---

### 任务 4：实现发布组匹配引擎

**文件：**
- 修改：`plugins/releasegroup/__init__.py`（在工具方法区域添加）

**目标：** 实现 `_match_release_group` 方法，基于正则表达式匹配文件名

- [ ] **步骤 1：编写测试用例**

先在文件末尾添加测试函数（临时）：

```python
def test_match_release_group():
    """测试发布组匹配"""
    plugin = ReleaseGroupStats()
    
    # 测试已知发布组
    assert plugin._match_release_group("Movie.2023.1080p.BluRay-MTeam.mkv") == "馒头"
    assert plugin._match_release_group("Show.S01E01.1080p-FRDS.mkv") == "朋友"
    assert plugin._match_release_group("Anime.E01.1080p-LoliHouse.mkv") == "anime"
    
    # 测试未匹配
    assert plugin._match_release_group("Unknown.File.mkv") == "其它"
    
    # 测试空输入
    assert plugin._match_release_group("") == "其它"
    
    print("所有测试通过！")

if __name__ == "__main__":
    test_match_release_group()
```

- [ ] **步骤 2：实现匹配方法**

在类中添加方法（在工具方法区域）：

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
        name_part = Path(filename).stem
        
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

- [ ] **步骤 3：运行测试验证**

```bash
cd plugins/releasegroup
python __init__.py
```

预期输出：`所有测试通过！`

- [ ] **步骤 4：移除测试代码**

删除文件末尾的 `test_match_release_group` 函数和 `if __name__ == "__main__"` 块

---

### 任务 5：实现文件扫描引擎

**文件：**
- 修改：`plugins/releasegroup/__init__.py`

**目标：** 实现 `_scan_directory` 方法，递归扫描目录并过滤视频文件

- [ ] **步骤 1：编写测试用例**

创建测试目录结构（手动或使用脚本）：
```
test_scan/
├── movie1.mkv
├── movie2.mp4
├── subtitle.srt
└── subdir/
    └── movie3.avi
```

- [ ] **步骤 2：实现扫描方法**

```python
    def _scan_directory(self, directory: str, extensions: List[str]) -> List[Dict]:
        """
        递归扫描目录中的视频文件
        
        Args:
            directory: 要扫描的目录路径
            extensions: 允许的文件扩展名列表
        
        Returns:
            文件信息列表，每项包含 path, size, mtime
        """
        files = []
        
        if not os.path.exists(directory):
            logger.warning(f"目录不存在: {directory}")
            return files
        
        try:
            for root, dirs, filenames in os.walk(directory):
                for filename in filenames:
                    # 检查扩展名
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in extensions:
                        filepath = os.path.join(root, filename)
                        try:
                            stat = os.stat(filepath)
                            files.append({
                                "path": filepath,
                                "size": stat.st_size,
                                "mtime": stat.st_mtime
                            })
                        except (PermissionError, OSError) as e:
                            logger.warning(f"无法访问文件 {filepath}: {e}")
        except Exception as e:
            logger.error(f"扫描目录 {directory} 失败: {e}", exc_info=True)
        
        logger.info(f"目录 {directory} 扫描完成，找到 {len(files)} 个文件")
        return files
```

- [ ] **步骤 3：手动测试扫描功能**

创建测试脚本：
```python
plugin = ReleaseGroupStats()
files = plugin._scan_directory("test_scan", plugin.DEFAULT_VIDEO_EXTENSIONS)
print(f"找到 {len(files)} 个文件:")
for f in files:
    print(f"  {f['path']} ({f['size']} bytes)")
```

预期：找到 3 个视频文件（movie1.mkv, movie2.mp4, movie3.avi），排除 subtitle.srt

---

### 任务 6：实现统计分析器

**文件：**
- 修改：`plugins/releasegroup/__init__.py`

**目标：** 实现 `_analyze_files` 方法，按发布组统计文件数量和大小

- [ ] **步骤 1：实现分析方法**

```python
    def _analyze_files(self, file_list: List[Dict]) -> Dict:
        """
        分析文件列表，按发布组统计
        
        Args:
            file_list: 文件信息列表
        
        Returns:
            统计结果字典
        """
        stats = {
            "total_files": 0,
            "total_size_bytes": 0,
            "groups": {}
        }
        
        # 遍历所有文件
        for file_info in file_list:
            filename = os.path.basename(file_info["path"])
            group_name = self._match_release_group(filename)
            
            # 初始化组统计
            if group_name not in stats["groups"]:
                stats["groups"][group_name] = {
                    "count": 0,
                    "size_bytes": 0,
                    "files": []
                }
            
            # 累加统计
            stats["groups"][group_name]["count"] += 1
            stats["groups"][group_name]["size_bytes"] += file_info["size"]
            stats["groups"][group_name]["files"].append(file_info["path"])
            
            # 更新总计
            stats["total_files"] += 1
            stats["total_size_bytes"] += file_info["size"]
        
        # 生成 Top 5（按文件数量降序）
        sorted_groups = sorted(
            stats["groups"].items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
        
        stats["top5"] = []
        for name, data in sorted_groups[:5]:
            percentage = (data["count"] / stats["total_files"] * 100) if stats["total_files"] > 0 else 0
            stats["top5"].append({
                "name": name,
                "count": data["count"],
                "percentage": round(percentage, 1),
                "size_bytes": data["size_bytes"]
            })
        
        return stats
```

- [ ] **步骤 2：编写集成测试**

```python
def test_analyze_files():
    plugin = ReleaseGroupStats()
    
    # 模拟文件列表
    file_list = [
        {"path": "/test/Movie1-MTeam.mkv", "size": 1000000},
        {"path": "/test/Movie2-MTeam.mkv", "size": 2000000},
        {"path": "/test/Show-FRDS.mkv", "size": 1500000},
        {"path": "/test/Unknown.mkv", "size": 500000},
    ]
    
    stats = plugin._analyze_files(file_list)
    
    assert stats["total_files"] == 4
    assert stats["total_size_bytes"] == 5000000
    assert "馒头" in stats["groups"]
    assert stats["groups"]["馒头"]["count"] == 2
    assert len(stats["top5"]) <= 5
    
    print("分析测试通过！")
```

- [ ] **步骤 3：运行测试**

预期：测试通过，统计正确

---

### 任务 7：实现数据持久化

**文件：**
- 修改：`plugins/releasegroup/__init__.py`

**目标：** 实现 `_save_stats` 和 `_load_stats` 方法

- [ ] **步骤 1：实现保存方法**

```python
    def _save_stats(self, stats: Dict):
        """
        保存统计数据到 JSON 文件
        
        Args:
            stats: 统计数据字典
        """
        try:
            stats_path = os.path.join(self.get_data_path(), self.STATS_FILE)
            with open(stats_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            logger.info(f"统计数据已保存到 {stats_path}")
        except Exception as e:
            logger.error(f"保存统计数据失败: {e}", exc_info=True)
    
    def _load_stats(self) -> Dict:
        """
        从 JSON 文件加载统计数据
        
        Returns:
            统计数据字典，失败返回空字典
        """
        try:
            stats_path = os.path.join(self.get_data_path(), self.STATS_FILE)
            if os.path.exists(stats_path):
                with open(stats_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载统计数据失败: {e}", exc_info=True)
        
        return {}
```

- [ ] **步骤 2：测试持久化功能**

```python
def test_persistence():
    plugin = ReleaseGroupStats()
    
    # 模拟统计数据
    test_stats = {
        "total_files": 10,
        "total_size_bytes": 1000000,
        "groups": {}
    }
    
    # 保存
    plugin._save_stats(test_stats)
    
    # 加载
    loaded = plugin._load_stats()
    
    assert loaded["total_files"] == 10
    assert loaded["total_size_bytes"] == 1000000
    
    print("持久化测试通过！")
```

- [ ] **步骤 3：验证文件生成**

检查插件数据目录是否生成 `stats_data.json` 文件

---

### 任务 8：实现辅助工具方法

**文件：**
- 修改：`plugins/releasegroup/__init__.py`

**目标：** 实现文件大小格式化、扩展名获取等工具方法

- [ ] **步骤 1：实现工具方法**

```python
    def _format_size(self, size_bytes: int) -> str:
        """
        格式化文件大小
        
        Args:
            size_bytes: 字节数
        
        Returns:
            格式化字符串，如 "1.2 GB"
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
    
    def _get_video_extensions(self) -> List[str]:
        """
        获取视频文件扩展名列表
        
        Returns:
            扩展名列表（小写）
        """
        if self._custom_extensions and self._custom_extensions.strip():
            # 解析用户自定义扩展名（每行一个）
            extensions = []
            for line in self._custom_extensions.split('\n'):
                ext = line.strip().lower()
                if ext and not ext.startswith('#'):
                    # 确保以 . 开头
                    if not ext.startswith('.'):
                        ext = '.' + ext
                    extensions.append(ext)
            return extensions if extensions else self.DEFAULT_VIDEO_EXTENSIONS
        
        return self.DEFAULT_VIDEO_EXTENSIONS
```

- [ ] **步骤 2：测试工具方法**

```python
def test_utils():
    plugin = ReleaseGroupStats()
    
    # 测试文件大小格式化
    assert plugin._format_size(500) == "500 B"
    assert plugin._format_size(1024) == "1.0 KB"
    assert plugin._format_size(1048576) == "1.0 MB"
    assert plugin._format_size(1073741824) == "1.0 GB"
    
    # 测试扩展名获取
    plugin._custom_extensions = ".mkv\n.mp4"
    exts = plugin._get_video_extensions()
    assert ".mkv" in exts
    assert ".mp4" in exts
    
    print("工具方法测试通过！")
```

---

### 任务 9：实现核心扫描流程

**文件：**
- 修改：`plugins/releasegroup/__init__.py`

**目标：** 实现 `_execute_scan` 方法，整合扫描、分析、保存流程

- [ ] **步骤 1：实现扫描流程**

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
                except Exception as e:
                    logger.error(f"扫描目录 {path} 失败: {str(e)}", exc_info=True)
            
            # 3. 统计分析
            if not all_files:
                logger.info("未找到任何视频文件")
                stats = {
                    "total_files": 0,
                    "total_size_bytes": 0,
                    "groups": {},
                    "top5": []
                }
            else:
                stats = self._analyze_files(all_files)
            
            # 4. 添加元数据
            stats['last_scan_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            stats['scan_duration_seconds'] = round(time.time() - start_time, 2)
            
            # 5. 保存结果
            self._save_stats(stats)
            self._stats_data = stats
            
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

- [ ] **步骤 2：测试完整流程**

手动触发一次扫描，检查日志和生成的 JSON 文件

---

### 任务 10：实现配置页面

**文件：**
- 修改：`plugins/releasegroup/__init__.py`

**目标：** 实现 `get_form` 方法，创建插件配置界面

- [ ] **步骤 1：实现配置表单**

```python
    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面
        
        Returns:
            表单配置和数据结构的元组
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'scan_paths',
                                            'label': '扫描目录',
                                            'rows': 3,
                                            'placeholder': '多个目录用分号分隔，如：/media/movies;/media/tvshows'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VCronField',
                                        'props': {
                                            'model': 'cron',
                                            'label': '定时任务 (Cron 表达式)',
                                            'placeholder': '例如: 0 2 * * * (每天凌晨2点)'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'custom_extensions',
                                            'label': '视频文件扩展名 (可选)',
                                            'rows': 3,
                                            'placeholder': '每行一个扩展名，留空使用默认值\n.mkv\n.mp4\n.avi'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'flat',
                                            'text': '提示：目录需使用容器内路径，扫描在后台执行，可在日志查看进度。大目录可能需要较长时间。'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "scan_paths": "",
            "cron": "",
            "custom_extensions": ""
        }
```

---

### 任务 11：实现定时任务注册

**文件：**
- 修改：`plugins/releasegroup/__init__.py`

**目标：** 实现 `get_service` 方法，注册 Cron 定时任务

- [ ] **步骤 1：实现定时服务**

```python
    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册定时服务
        
        Returns:
            定时任务配置列表
        """
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

- [ ] **步骤 2：验证定时任务配置**

启用插件并配置 Cron 后重启 MoviePilot，检查日志确认定时任务注册成功

---

### 任务 12：实现 API 接口

**文件：**
- 修改：`plugins/releasegroup/__init__.py`

**目标：** 实现 `get_api` 方法和 `start_scan` 端点，支持手动触发扫描

- [ ] **步骤 1：实现 API 方法**

```python
    def get_api(self) -> List[Dict[str, Any]]:
        """
        注册 API 接口
        
        Returns:
            API 配置列表
        """
        return [{
            "path": "/start_scan",
            "endpoint": self.start_scan,
            "methods": ["POST"],
            "summary": "手动触发扫描"
        }]
    
    def start_scan(self):
        """
        手动触发扫描
        
        Returns:
            响应字典
        """
        if self._is_scanning:
            return {"success": False, "message": "扫描正在进行中"}
        
        # 在后台线程中执行扫描
        threading.Thread(target=self._execute_scan, daemon=True).start()
        return {"success": True, "message": "扫描已启动"}
```

- [ ] **步骤 2：测试 API 调用**

使用 curl 或浏览器测试：
```bash
curl -X POST http://localhost:3000/api/v1/plugin/ReleaseGroupStats/start_scan
```

预期返回：`{"success": true, "message": "扫描已启动"}`

---

### 任务 13：实现仪表板 Widget

**文件：**
- 修改：`plugins/releasegroup/__init__.py`

**目标：** 实现 `get_dashboard` 方法，显示 Top 5 发布组统计

- [ ] **步骤 1：实现 Widget**

```python
    def get_dashboard(self, key: str, **kwargs) -> Optional[dict]:
        """
        获取仪表板 Widget
        
        Args:
            key: Widget 键名
        
        Returns:
            Widget 配置字典
        """
        if not self._stats_data:
            return None
        
        stats = self._stats_data
        
        # 构建 Top 5 列表
        top5_items = []
        for item in stats.get("top5", [])[:5]:
            top5_items.append({
                'component': 'VListItem',
                'props': {'density': 'compact'},
                'content': [
                    {
                        'component': 'VListItemTitle',
                        'content': [
                            {
                                'component': 'span',
                                'props': {'class': 'font-weight-bold'},
                                'content': [item['name']]
                            },
                            {
                                'component': 'span',
                                'props': {'class': 'text-grey ml-2'},
                                'content': [f"{item['count']} ({item['percentage']}%)"]
                            }
                        ]
                    },
                    {
                        'component': 'VListItemSubtitle',
                        'content': [self._format_size(item['size_bytes'])]
                    },
                    {
                        'component': 'VProgressLinear',
                        'props': {
                            'modelValue': item['percentage'],
                            'height': 4,
                            'color': 'primary',
                            'class': 'mt-1'
                        }
                    }
                ]
            })
        
        return {
            'component': 'VCard',
            'props': {
                'class': 'shadow-none border-round',
                'variant': 'tonal'
            },
            'content': [
                {
                    'component': 'VCardTitle',
                    'props': {'class': 'pa-3'},
                    'content': [
                        {
                            'component': 'span',
                            'content': ['📊 发布组统计']
                        }
                    ]
                },
                {
                    'component': 'VCardText',
                    'props': {'class': 'pa-3 pt-0'},
                    'content': [
                        {
                            'component': 'VRow',
                            'content': [
                                {
                                    'component': 'VCol',
                                    'props': {'cols': 6},
                                    'content': [
                                        {
                                            'component': 'div',
                                            'props': {'class': 'text-caption text-grey'},
                                            'content': ['总文件数']
                                        },
                                        {
                                            'component': 'div',
                                            'props': {'class': 'text-h6'},
                                            'content': [str(stats.get('total_files', 0))]
                                        }
                                    ]
                                },
                                {
                                    'component': 'VCol',
                                    'props': {'cols': 6},
                                    'content': [
                                        {
                                            'component': 'div',
                                            'props': {'class': 'text-caption text-grey'},
                                            'content': ['总大小']
                                        },
                                        {
                                            'component': 'div',
                                            'props': {'class': 'text-h6'},
                                            'content': [self._format_size(stats.get('total_size_bytes', 0))]
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            'component': 'VDivider',
                            'props': {'class': 'my-2'}
                        },
                        {
                            'component': 'div',
                            'props': {'class': 'text-subtitle-2 mb-2'},
                            'content': ['Top 5 发布组']
                        },
                        {
                            'component': 'VList',
                            'props': {'density': 'compact'},
                            'content': top5_items
                        },
                        {
                            'component': 'VDivider',
                            'props': {'class': 'my-2'}
                        },
                        {
                            'component': 'div',
                            'props': {'class': 'text-caption text-grey'},
                            'content': [f"最近扫描: {stats.get('last_scan_time', '从未')}"]
                        }
                    ]
                }
            ]
        }
```

---

### 任务 14：实现详情页面

**文件：**
- 修改：`plugins/releasegroup/__init__.py`

**目标：** 实现 `get_page` 方法，显示完整统计信息和文件列表

- [ ] **步骤 1：实现详情页面**

```python
    def get_page(self) -> List[dict]:
        """
        获取插件详情页面
        
        Returns:
            页面配置列表
        """
        if not self._stats_data:
            return [
                {
                    'component': 'VAlert',
                    'props': {
                        'type': 'info',
                        'variant': 'tonal'
                    },
                    'content': [
                        {
                            'component': 'span',
                            'content': ['暂无统计数据，请先执行扫描']
                        }
                    ]
                }
            ]
        
        stats = self._stats_data
        
        # 构建发布组表格行
        group_rows = []
        sorted_groups = sorted(
            stats.get("groups", {}).items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
        
        for rank, (name, data) in enumerate(sorted_groups, 1):
            percentage = (data["count"] / stats["total_files"] * 100) if stats["total_files"] > 0 else 0
            group_rows.append({
                'component': 'VTr',
                'content': [
                    {
                        'component': 'VTd',
                        'content': [str(rank)]
                    },
                    {
                        'component': 'VTd',
                        'content': [name]
                    },
                    {
                        'component': 'VTd',
                        'content': [str(data["count"])]
                    },
                    {
                        'component': 'VTd',
                        'content': [f"{percentage:.1f}%"]
                    },
                    {
                        'component': 'VTd',
                        'content': [self._format_size(data["size_bytes"])]
                    },
                    {
                        'component': 'VTd',
                        'content': [
                            {
                                'component': 'VBtn',
                                'props': {
                                    'size': 'x-small',
                                    'variant': 'text',
                                    'color': 'primary'
                                },
                                'events': {
                                    'click': f"showFiles('{name}')"
                                },
                                'content': [
                                    {
                                        'component': 'VIcon',
                                        'content': ['mdi-eye']
                                    }
                                ]
                            }
                        ]
                    }
                ]
            })
        
        return [
            {
                'component': 'VContainer',
                'content': [
                    # 概览卡片
                    {
                        'component': 'VRow',
                        'props': {'class': 'mb-3'},
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 3},
                                'content': [
                                    {
                                        'component': 'VCard',
                                        'props': {'variant': 'tonal'},
                                        'content': [
                                            {
                                                'component': 'VCardText',
                                                'content': [
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-caption text-grey'},
                                                        'content': ['总文件数']
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-h4'},
                                                        'content': [str(stats.get('total_files', 0))]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 3},
                                'content': [
                                    {
                                        'component': 'VCard',
                                        'props': {'variant': 'tonal'},
                                        'content': [
                                            {
                                                'component': 'VCardText',
                                                'content': [
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-caption text-grey'},
                                                        'content': ['总大小']
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-h4'},
                                                        'content': [self._format_size(stats.get('total_size_bytes', 0))]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 3},
                                'content': [
                                    {
                                        'component': 'VCard',
                                        'props': {'variant': 'tonal'},
                                        'content': [
                                            {
                                                'component': 'VCardText',
                                                'content': [
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-caption text-grey'},
                                                        'content': ['发布组数量']
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-h4'},
                                                        'content': [str(len(stats.get('groups', {})))]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 3},
                                'content': [
                                    {
                                        'component': 'VCard',
                                        'props': {'variant': 'tonal'},
                                        'content': [
                                            {
                                                'component': 'VCardText',
                                                'content': [
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-caption text-grey'},
                                                        'content': ['扫描耗时']
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-h4'},
                                                        'content': [f"{stats.get('scan_duration_seconds', 0)} 秒"]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    
                    # 最近扫描时间
                    {
                        'component': 'VRow',
                        'props': {'class': 'mb-3'},
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {'cols': 12},
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal'
                                        },
                                        'content': [
                                            {
                                                'component': 'span',
                                                'content': [f"最近扫描时间: {stats.get('last_scan_time', '从未')}"]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    
                    # 发布组表格
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {'cols': 12},
                                'content': [
                                    {
                                        'component': 'VCard',
                                        'content': [
                                            {
                                                'component': 'VCardTitle',
                                                'content': [
                                                    {
                                                        'component': 'span',
                                                        'content': ['发布组详细列表']
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VCardText',
                                                'content': [
                                                    {
                                                        'component': 'VTable',
                                                        'content': [
                                                            {
                                                                'component': 'THead',
                                                                'content': [
                                                                    {
                                                                        'component': 'VTr',
                                                                        'content': [
                                                                            {'component': 'VTh', 'content': ['排名']},
                                                                            {'component': 'VTh', 'content': ['发布组']},
                                                                            {'component': 'VTh', 'content': ['文件数']},
                                                                            {'component': 'VTh', 'content': ['占比']},
                                                                            {'component': 'VTh', 'content': ['大小']},
                                                                            {'component': 'VTh', 'content': ['操作']}
                                                                        ]
                                                                    }
                                                                ]
                                                            },
                                                            {
                                                                'component': 'TBody',
                                                                'content': group_rows
                                                            }
                                                        ]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
```

---

### 任务 15：完善 stop_service 方法

**文件：**
- 修改：`plugins/releasegroup/__init__.py:stop_service`

**目标：** 实现插件停止时的清理逻辑

- [ ] **步骤 1：实现停止方法**

```python
    def stop_service(self):
        """停止服务"""
        logger.info("发布组统计插件已停止")
        self._is_scanning = False
```

---

### 任务 16：最终测试和验证

**文件：**
- 所有文件

**目标：** 全面测试插件功能

- [ ] **步骤 1：语法检查**

```bash
python -m py_compile plugins/releasegroup/__init__.py
```

- [ ] **步骤 2：启动 MoviePilot 测试**

1. 重启 MoviePilot
2. 在插件市场找到"发布组统计"
3. 启用插件
4. 配置扫描目录和 Cron
5. 点击"立即扫描"测试
6. 检查 Widget 显示
7. 检查详情页面
8. 查看日志确认无错误

- [ ] **步骤 3：验证数据持久化**

检查插件数据目录是否生成 `stats_data.json`，内容是否正确

- [ ] **步骤 4：验证定时任务**

配置一个近期的 Cron 时间（如 2 分钟后），等待自动触发，检查日志

---

## 依赖关系

```
任务 1 (基础结构)
  ↓
任务 2 (常量定义)
  ↓
任务 3 (初始化)
  ↓
任务 4 (匹配引擎) ← 独立
任务 5 (扫描引擎) ← 独立
任务 6 (分析器) → 依赖任务 4, 5
  ↓
任务 7 (持久化) ← 独立
  ↓
任务 8 (工具方法) ← 独立
  ↓
任务 9 (核心流程) → 依赖任务 5, 6, 7, 8
  ↓
任务 10 (配置页面) ← 独立
任务 11 (定时任务) → 依赖任务 9
任务 12 (API) → 依赖任务 9
任务 13 (Widget) → 依赖任务 7, 8
任务 14 (详情页) → 依赖任务 7, 8
任务 15 (停止方法) ← 独立
  ↓
任务 16 (最终测试) → 依赖所有任务
```

---

## 优先级

**P0 (必须):** 任务 1-9, 16 - 核心功能  
**P1 (重要):** 任务 10-12 - 配置和触发机制  
**P2 (增强):** 任务 13-14 - UI 展示  

---

## 测试策略

1. **单元测试:** 任务 4, 5, 6, 7, 8 中的测试用例
2. **集成测试:** 任务 9, 16 - 端到端扫描流程
3. **UI 测试:** 任务 16 - 手动验证页面渲染

---

## Commit 策略

每个任务完成后单独 commit：
```bash
git add plugins/releasegroup/__init__.py
git commit -m "feat: [任务描述]"
```

示例：
- `feat: add plugin skeleton and metadata`
- `feat: implement release group matching engine`
- `feat: add file scanning functionality`
- `feat: implement statistics analyzer`
- `feat: add data persistence`
- `feat: implement configuration page`
- `feat: add dashboard widget`
- `feat: implement detail page`

---

计划已完成并保存到 `docs/superpowers/plans/2026-06-18-release-group-stats.md`。两种执行方式：

**1. 子代理驱动（推荐）** - 每个任务调度一个新的子代理，任务间进行审查，快速迭代

**2. 内联执行** - 在当前会话中使用 executing-plans 执行任务，批量执行并设有检查点

**选哪种方式？**
