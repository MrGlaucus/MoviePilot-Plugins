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
from app.schemas.types import EventType
from app.core.event import eventmanager, Event
from app.core.cache import cached


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
    
    def get_state(self) -> bool:
        """获取插件状态"""
        return self._enabled
    
    def get_dashboard_meta(self) -> Optional[List[Dict[str, str]]]:
        """
        获取插件仪表盘元信息
        """
        return [{
            "key": "stats",  # 仪表盘的key
            "name": "发布组统计"  # 仪表盘的名称
        }]
    
    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        注册插件远程命令
        """
        return [{
            "cmd": "/release_group_scan",
            "event": EventType.PluginAction,
            "desc": "发布组统计扫描",
            "category": "插件功能",
            "data": {
                "action": "release_group_scan"
            }
        }]
    
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
            
            # 清除缓存，确保下次读取最新数据
            self._load_stats.cache_clear()
        except Exception as e:
            logger.error(f"保存统计数据失败: {e}", exc_info=True)
    
    @cached(region="releasegroup_stats", ttl=300, skip_none=True)
    def _load_stats(self) -> Dict:
        """
        从 JSON 文件加载统计数据（带缓存）
        
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
                     f"耗时 {stats['scan_duration_seconds']} 秒",
                buttons=[
                    [
                        {"text": "📊 查看详情", "callback_data": f"[PLUGIN]{self.__class__.__name__}|view_details"}
                    ]
                ]
            )
            
        except Exception as e:
            logger.error(f"扫描失败: {str(e)}", exc_info=True)
        finally:
            self._is_scanning = False
    
    def stop_service(self):
        """停止服务"""
        logger.info("发布组统计插件已停止")
        self._is_scanning = False
    
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
    
    def get_dashboard(self, key: str, **kwargs) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
        """
        获取插件仪表盘页面
        
        Args:
            key: 仪表盘key
        
        Returns:
            1. col配置字典 2.全局配置 3.页面元素配置json
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
        
        # 1. col配置
        cols = {
            "cols": 12,
            "md": 6
        }
        
        # 2. 全局配置
        attrs = {
            "refresh": 300,  # 5分钟自动刷新
            "border": True,
            "title": "发布组统计",
            "subtitle": f"最近扫描: {stats.get('last_scan_time', '从未')}"
        }
        
        # 3. 页面配置
        content = [
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
                    }
                ]
            }
        ]
        
        return cols, attrs, content
    
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
