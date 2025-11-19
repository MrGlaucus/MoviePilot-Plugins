import os
import re
import threading
from typing import Any, List, Dict, Tuple

from app.log import logger
from app.plugins import _PluginBase


class NfoReplaceTool(_PluginBase):
    # 插件名称
    plugin_name = "NFO标签内容替换"
    # 插件描述
    plugin_desc = "对NFO文件的标签内容进行替换"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/MrGlaucus/MoviePilot-Plugins/main/icons/nfo.png"
    # 主题色
    plugin_color = "#32699D"
    # 插件版本
    plugin_version = "1.1"
    # 插件作者
    plugin_author = "MrGlaucus"
    # 作者主页
    author_url = "https://github.com/MrGlaucus"
    # 插件配置项ID前缀
    plugin_config_prefix = "nforeplacetool_"
    # 加载顺序
    plugin_order = 1
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _all_path = ""
    _is_running = False
    _threads = []

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._all_path = config.get("all_path")

        if self._enabled and not self._is_running:
            self._is_running = True
            for path_line in self._all_path.split('\n'):
                # 解析格式为 "path|tag_name|old_value|new_value" 的行
                parts = path_line.split('|')
                if len(parts) >= 4:
                    path = parts[0].strip()
                    tag_name = parts[1].strip()
                    old_value = parts[2].strip()
                    new_value = parts[3].strip()

                    # 检查必要参数是否为空
                    if not tag_name or not old_value:
                        logger.warn(f"跳过无效行: {path_line} (标签名或旧值为空)")
                        continue
                        
                    if os.path.exists(path):
                        thread = threading.Thread(target=self.process_all_nfo_files, args=(path, tag_name, old_value, new_value))
                        thread.start()
                        self._threads.append(thread)
            self.update_config({
                "enabled": False,
                "all_path": self._all_path,
            })

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    # 插件配置页面
    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
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
                                            'model': 'all_path',
                                            'label': 'nfo标签内容替换配置',
                                            'rows': 5,
                                            'placeholder': '每一行一个配置，格式为：path|tag_name|old_value|new_value'
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
                                            'text': 'path：nfo文件父目录路径（容器路径）,tag_name：标签名称（不含<>），old_value：旧值，new_value：新值，可为空，即替换为空，如：/media/电影|actor|jack|杰克，old_value可填写正则表达式'
                                        }
                                    }
                                ]
                            },
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
                                            'text': '执行结束后会自动禁用插件'
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
            "all_path": "",
        }

    def get_page(self) -> List[dict]:
        pass

    @staticmethod
    def replace_tag_content(file_path, tag_name, old_value, new_value):
        logger.info(f'正在处理 {file_path}...')
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # 使用正则表达式匹配指定标签内的内容
        # 匹配<tag_name>...</tag_name>格式的标签
        pattern = f'<{tag_name}>(.*?)</{tag_name}>'
        
        def replace_func(match):
            inner_content = match.group(1)
            # 尝试将old_value作为正则表达式处理
            try:
                # 编译正则表达式以检查其有效性
                re.compile(old_value)
                # 如果编译成功，则使用正则表达式替换
                replaced_content = re.sub(old_value, new_value, inner_content)
                return f'<{tag_name}>{replaced_content}</{tag_name}>'
            except re.error:
                # 如果编译失败，则使用普通字符串替换
                if old_value in inner_content:
                    return f'<{tag_name}>{inner_content.replace(old_value, new_value)}</{tag_name}>'
                else:
                    return match.group(0)
        
        # 应用替换
        content = re.sub(pattern, replace_func, content, flags=re.DOTALL)
        
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        logger.info(f'{file_path} 处理完成')

    def process_all_nfo_files(self, directory, tag_name, old_value, new_value):
        logger.info(f'正在处理 {directory} 下的所有 nfo 文件...')
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.nfo'):
                    file_path = os.path.join(root, file)
                    self.replace_tag_content(file_path, tag_name, old_value, new_value)

        logger.info(f'{directory} - 处理完成')
        self._threads.pop(0)
        logger.info(f'正在移除线程... 剩余 {len(self._threads)} 个线程')
        if len(self._threads) == 0:
            self._is_running = False
            logger.info(f'任务完成')


    def stop_service(self):
        """
        退出插件
        """
        pass