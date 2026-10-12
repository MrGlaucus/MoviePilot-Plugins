"""Native Vuetify pages; no global CSS or frontend build artifacts."""
from pathlib import Path


def node(component, text=None, content=None, **props):
    """Build one renderer node using the host's text/content contract."""
    result = {'component': component}
    if props:
        result['props'] = props
    if text is not None:
        result['text'] = str(text)
    if content is not None:
        result['content'] = content
    return result


def size(value):
    """Format logical bytes with binary units."""
    value = max(0, value)
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']:
        if value < 1024 or unit == 'PiB':
            return f'{value:,.0f} {unit}' if unit == 'B' else f'{value:,.2f} {unit}'
        value /= 1024


def form(warnings):
    """Return editable settings and defaults, including legacy field names."""
    controls = [
        node('VCol', content=[node('VSwitch', model='enabled', label='启用插件', color='primary')], cols=12, sm=6),
        node('VCol', content=[node('VSwitch', model='onlyonce', label='保存后扫描一次', color='primary')], cols=12, sm=6),
        node('VCol', content=[node('VTextarea', model='scan_paths', label='媒体目录（容器内路径）', rows=3,
                                  placeholder='/media/movies\n/media/tv', hint='每行一个目录，也兼容分号分隔；重复和嵌套目录自动合并', persistentHint=True)], cols=12),
        node('VCol', content=[node('VCronField', model='cron', label='定时扫描', placeholder='0 2 * * *',
                                  hint='使用 MoviePilot 时区；留空仅手动扫描', persistentHint=True)], cols=12),
        node('VCol', content=[node('VTextarea', model='custom_extensions', label='视频扩展名', rows=2,
                                  placeholder='mkv,mp4,ts', hint='留空使用默认值；支持逗号、分号或换行', persistentHint=True)], cols=12),
        node('VCol', content=[node('VTextarea', model='custom_rules', label='自定义发布组规则（优先）', rows=3,
                                  placeholder='我的发布组|MYGROUP\n朋友|FRDS', hint='每行 分类名|正则表达式；以 # 开头的行忽略', persistentHint=True)], cols=12),
        node('VCol', content=[node('VTextField', model='ranking_filter', label='排名筛选关键词',
                                  hint='按分类名筛选详情表，保存后生效；留空显示全部', persistentHint=True)], cols=12),
    ]
    content = [node('VAlert', '按视频文件统计：剧集每集单独计数，容量为文件逻辑大小。请启用插件后扫描。',
                    type='info', variant='tonal', **{'class': 'mb-4'}),
               node('VRow', content=controls)]
    content += [node('VAlert', warning, type='warning', variant='tonal', **{'class': 'mt-2'}) for warning in warnings]
    return [node('VForm', content=content)], {
        'enabled': False, 'onlyonce': False, 'scan_paths': '', 'cron': '',
        'custom_extensions': '', 'custom_rules': '', 'ranking_filter': ''}


def rankings(stats):
    """Produce sortable table items with numeric counts and percentages."""
    total = stats.get('total_files', 0)
    capacity = stats.get('total_size_bytes', 0)
    ordered = sorted(stats.get('groups', {}).items(), key=lambda item: (-item[1]['count'], item[0]))
    return [{'rank': i, 'name': name, 'count': group['count'], 'bytes': group['size_bytes'],
             'size': size(group['size_bytes']),
             'percentage': round(group['count'] / total * 100, 1) if total else 0,
             'size_percentage': round(group['size_bytes'] / capacity * 100, 1) if capacity else 0}
            for i, (name, group) in enumerate(ordered, 1)]


def overview(stats, compact=False):
    """Responsive summary cards, with an explicit identification denominator."""
    total = stats.get('total_files', 0)
    unknown = stats.get('groups', {}).get('其它', {}).get('count', 0)
    labels = [('视频文件', f'{total:,}'), ('逻辑容量', size(stats.get('total_size_bytes', 0)))]
    if not compact:
        labels += [('已识别分类', len([g for g in stats.get('groups', {}) if g != '其它'])),
                   ('识别率', f'{(total - unknown) / total * 100:.1f}%' if total else '—')]
    return node('VRow', content=[node('VCol', content=[node('VCard', content=[node('VCardText', content=[
        node('div', label, **{'class': 'text-caption text-medium-emphasis mb-1'}),
        node('div', value, **{'class': 'text-h5 font-weight-bold'})])], variant='tonal', color='primary')],
        cols=6, md=6 if compact else 3) for label, value in labels])


def podium(stats, compact=False):
    """Show the three leading groups as a responsive medal podium."""
    leaders = rankings(stats)[:3]
    if not leaders:
        return [node('VAlert', '暂无发布组排名', type='info', variant='tonal')]
    medals = [('🥇', '冠军', '#B88620'), ('🥈', '亚军', '#77899C'), ('🥉', '季军', '#AD7046')]
    cards = []
    for item in leaders:
        rank = item['rank']
        medal, label, color = medals[rank - 1]
        order = {1: 'order-1 order-sm-2', 2: 'order-2 order-sm-1', 3: 'order-3'}[rank]
        height = (174 if rank == 1 else 150) if compact else (218 if rank == 1 else 190)
        cards.append(node('VCol', content=[node('VCard', content=[node('VCardText', content=[
            node('div', medal, **{'class': 'text-h4 mb-1', 'aria-hidden': 'true'}),
            node('div', label, **{'class': 'text-caption font-weight-bold mb-2'}),
            node('div', item['name'], **{'class': 'text-subtitle-1 font-weight-bold',
                                       'style': 'overflow-wrap:anywhere;white-space:normal'}),
            node('div', f"{item['count']:,} 文件", **{'class': 'text-h6 font-weight-bold mt-2'}),
            node('div', f"占比 {item['percentage']}% · {item['size']}",
                 **{'class': 'text-caption mt-1'})], **{'class': 'text-center pa-3'})],
            color=color, variant='tonal', **{'style': f'min-height:{height}px;border:1px solid {color};border-radius:16px'})],
            cols=12, sm=4, **{'class': order}))
    return [node('VRow', content=cards, align='end', justify='center', **{'class': 'mt-1'})]


def page(stats, status, plugin_id, keyword='', view=None):
    """Render controls, snapshot summary, ranking table and unknown examples."""
    state_labels = {'idle': '等待扫描', 'running': '扫描中', 'cancelling': '正在取消',
                    'completed': '扫描完成', 'partial': '部分完成', 'failed': '扫描失败',
                    'cancelled': '已取消', 'stopped': '已停止'}
    controls = []
    for label, endpoint, method, disabled, icon in [
        ('开始扫描', 'start_scan', 'post', status.running or not status.enabled, 'mdi-play'),
        ('取消扫描', 'cancel_scan', 'post', not status.running, 'mdi-stop'),
        ('刷新状态', 'status', 'get', False, 'mdi-refresh')]:
        button = node('VBtn', label, variant='tonal', color='primary', disabled=disabled,
                      prependIcon=icon, **{'class': 'mr-2 mb-2'})
        button['events'] = {'click': {'api': f'plugin/{plugin_id}/{endpoint}', 'method': method}}
        controls.append(button)
    content = [node('div', content=[node('div', '媒体库 · 发布组分布', **{'class': 'text-h5 font-weight-bold mb-2'}),
                                   node('VChip', state_labels.get(status.state, status.state), color='primary', variant='tonal',
                                        **{'class': 'mb-3'})] + controls),
               node('div', f'最近成功扫描：{stats.get("last_scan_time", "尚未扫描")} · 按文件计数，容量为逻辑大小',
                    **{'class': 'text-caption text-medium-emphasis mb-4'})]
    if status.running:
        content += [node('VProgressLinear', indeterminate=True, color='primary', **{'class': 'mb-3'}),
                    node('VAlert', f'已检查 {status.checked_files:,} 个文件，发现 {status.video_files:,} 个视频，读取错误 {status.error_count}',
                         type='info', variant='tonal', **{'class': 'mb-3'})]
    if status.message:
        content.append(node('VAlert', status.message, type='warning' if status.state in ['failed', 'cancelled'] else 'info',
                            variant='tonal', **{'class': 'mb-3'}))
    for warning in status.warnings:
        content.append(node('VAlert', warning, type='warning', variant='tonal', **{'class': 'mb-3'}))
    if not stats:
        content.append(node('VAlert', '暂无统计数据。在配置中添加媒体目录并启用插件，然后点击“开始扫描”。', type='info', variant='tonal'))
        return [node('div', content=content)]
    content.append(overview(stats))
    if stats.get('partial'):
        content.append(node('VAlert', f'本次统计不完整：{stats.get("error_count", 0)} 个读取错误。请检查挂载目录和权限后重新扫描。',
                            type='warning', variant='tonal', **{'class': 'mt-4'}))
    content.append(node('VCard', content=[node('VCardTitle', '发布组领奖台 · Top 3'),
                                          node('VCardText', content=podium(stats))], variant='outlined', **{'class': 'mt-4'}))
    rows = [r for r in rankings(stats) if keyword.casefold() in r['name'].casefold()]
    view = view or {'sort': 'count', 'descending': True, 'page': 1}
    rows.sort(key=lambda row: row[view['sort']], reverse=view['descending'])
    pages = max(1, (len(rows) + 9) // 10)
    current_page = min(view['page'], pages)

    def view_button(label, params, disabled=False):
        button = node('VBtn', label, size='small', variant='text', color='primary', disabled=disabled)
        button['events'] = {'click': {'api': f'plugin/{plugin_id}/ranking_view', 'method': 'post', 'params': params}}
        return button

    headers = []
    for title, key in [('排名', None), ('发布组 / 分类', 'name'), ('文件数', 'count'),
                       ('数量占比', None), ('逻辑容量', 'bytes'), ('容量占比', None)]:
        if key:
            active = view['sort'] == key
            label = title + (' ↓' if view['descending'] else ' ↑') if active else title + ' ↕'
            headers.append(node('th', content=[view_button(label, {'sort': key, 'page': 1,
                'descending': not view['descending'] if active else True})]))
        else:
            headers.append(node('th', title))
    table_rows = []
    for row in rows[(current_page - 1) * 10:current_page * 10]:
        table_rows.append(node('tr', content=[node('td', text) for text in [row['rank'], row['name'],
            f"{row['count']:,}", f"{row['percentage']}%", row['size'], f"{row['size_percentage']}%"]]))
    if not rows:
        table_rows.append(node('tr', content=[node('td', '没有符合筛选条件的发布组', colspan=6)]))
    table = node('VTable', content=[node('thead', content=[node('tr', content=headers)]),
                                  node('tbody', content=table_rows)], density='comfortable', hover=True)
    navigation = node('div', content=[
        view_button('上一页', {**view, 'page': max(1, current_page - 1)}, current_page == 1),
        node('span', f'第 {current_page} / {pages} 页 · {len(rows)} 个分类', **{'class': 'text-caption mx-3'}),
        view_button('下一页', {**view, 'page': current_page + 1}, current_page == pages)],
        **{'class': 'd-flex align-center justify-end pa-3 flex-wrap'})
    content.append(node('VCard', content=[node('VCardTitle', '发布组排名' + (f' · 筛选：{keyword}' if keyword else '')),
        table, navigation], variant='outlined', **{'class': 'mt-4'}))
    unknown = stats.get('groups', {}).get('其它', {})
    if unknown.get('files'):
        content.append(node('VExpansionPanels', content=[node('VExpansionPanel', content=[
            node('VExpansionPanelTitle', f"未识别文件示例 · 最多 10 条（共 {unknown['count']} 个）"),
            node('VExpansionPanelText', content=[node('VList', content=[
                node('VListItem', title=Path(path).name, subtitle=path) for path in unknown['files'][:10]], density='compact')])])],
            **{'class': 'mt-4'}))
    return [node('div', content=content)]


def dashboard(stats, status):
    """Always expose an empty state so the widget can be added before scanning."""
    content = [overview(stats, compact=True)]
    if stats:
        content.append(node('div', '发布组 · Top 3', **{'class': 'text-subtitle-2 mt-4'}))
        content += podium(stats, compact=True)
    else:
        content.append(node('VAlert', '暂无结果，请在插件详情页开始扫描。', type='info', variant='tonal', **{'class': 'mt-3'}))
    if status.running:
        content.append(node('VProgressLinear', indeterminate=True, color='primary', **{'class': 'mt-3'}))
    if stats.get('partial') or status.state in ['failed', 'cancelled']:
        content.append(node('VAlert', '扫描不完整或未成功，请到详情页检查。', type='warning', variant='tonal', **{'class': 'mt-3'}))
    return {'cols': 12, 'md': 6}, {'refresh': 10, 'title': '发布组统计',
        'subtitle': stats.get('last_scan_time', '等待首次扫描')}, [node('VCardText', content=content)]
