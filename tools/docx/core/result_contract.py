from __future__ import annotations
import json
import math
import os
import tempfile
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path
SCHEMA_VERSION = 1
def perceptual_hash(path):
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError('生成运行清单需要 Pillow') from exc
    with Image.open(path) as image:
        image = image.convert('RGB').resize((8, 8))
    raw_pixels = list(image.getdata())
    channels = zip(*raw_pixels)
    averages = []
    bits = []
    for pixels in channels:
        pixels = list(pixels)
        average = sum(pixels) / len(pixels)
        averages.append(int(round(average)))
        bits.append(''.join('1' if value >= average else '0' for value in pixels))
    return f"{averages[0]},{averages[1]},{averages[2]}|{''.join(bits)}"
from tools.common.io_utils import sha256_file

# 兼容名：外部调用方仍可按 file_sha256 引用
file_sha256 = sha256_file
def _relative(project, path):
    p = Path(path)
    # 相对路径一律以 project 为基准解析（不依赖调用方 cwd，跨目录调用安全）
    resolved = (project / p).resolve() if not p.is_absolute() else p.resolve()
    try:
        return resolved.relative_to(project).as_posix()
    except ValueError as exc:
        raise ValueError(f'运行产物必须位于 PROJECT_ROOT: {resolved}') from exc
def _artifact(project, path, source_script):
    relative = _relative(project, path)
    required_prefix = 'results/'
    if not relative.startswith(required_prefix):
        raise ValueError(f'本次运行产物必须位于 {required_prefix}: {relative}')
    source = _relative(project, source_script)
    if not source.startswith('code/'):
        raise ValueError(f'生成脚本必须位于 code/: {source}')
    result = {'path': relative, 'sha256': file_sha256(project / relative), 'source_script': source, 'source_sha256': file_sha256(project / source)}
    if Path(relative).suffix.lower() in {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}:
        result['phash'] = perceptual_hash(project / relative)
    return result
def write_run_manifest(project_root, *, figures, parameters, tables=(), claims=(), manual_stats=(), started_at=None, command=None, input_files=(), exit_code=0):
    project = Path(project_root).resolve()
    script_map = {}
    figure_rows = []
    seen_figure_paths = set()
    seen_figure_hashes = set()
    for item in figures:
        row = _artifact(project, item['path'], item['source_script'])
        if row['path'] in seen_figure_paths:
            raise ValueError(f"同一图片被重复登记: {row['path']}")
        if row['sha256'] in seen_figure_hashes:
            raise ValueError(f"内容相同的图片被重复登记: {row['path']}")
        seen_figure_paths.add(row['path'])
        seen_figure_hashes.add(row['sha256'])
        figure_rows.append(row)
        script_map[row['source_script']] = row['source_sha256']
    def numeric_rows(items, label):
        rows = []
        for item in items:
            name = str(item.get('name', '')).strip()
            unit = str(item.get('unit', '')).strip()
            if not name or not unit:
                raise ValueError(f'{label}必须填写 name 和 unit（无单位写‘无量纲’）')
            value = item.get('value')
            if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
                raise ValueError(f'{label} {name} 值必须为有限数值')
            finite = value.is_finite() if isinstance(value, Decimal) else math.isfinite(value)
            if not finite:
                raise ValueError(f'{label} {name} 不是有限数')
            source_info = _artifact(project, item['source'], item['source_script'])
            row = {'name': name, 'value': value, 'paper_value': item.get('paper_value', value), 'unit': unit, 'source': source_info['path'], 'source_sha256': source_info['sha256'], 'source_script': source_info['source_script'], 'source_script_sha256': source_info['source_sha256']}
            for bound in ('min', 'max'):
                if bound in item:
                    row[bound] = item[bound]
            rows.append(row)
            script_map[source_info['source_script']] = source_info['source_sha256']
        return rows
    def manual_rows(items, label):
        """人工工具（SPSS 等）核验结论：与参数/关键结论同格式，但来源不是 code 脚本，而是人工导出的结果文件。"""
        rows = []
        for item in items:
            name = str(item.get('name', '')).strip()
            unit = str(item.get('unit', '')).strip()
            if not name or not unit:
                raise ValueError(f'{label}必须填写 name 和 unit（无单位写‘无量纲’）')
            value = item.get('value')
            if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
                raise ValueError(f'{label} {name} 值必须为有限数值')
            finite = value.is_finite() if isinstance(value, Decimal) else math.isfinite(value)
            if not finite:
                raise ValueError(f'{label} {name} 不是有限数')
            rel = _relative(project, item['source'])
            if not rel.startswith('results/'):
                raise ValueError(f'{label} {name} 来源必须位于 results/: {rel}')
            tool = str(item.get('tool', '')).strip()
            if not tool:
                raise ValueError(f'{label} {name} 必须填写 tool（如 "SPSS 27 手动"）')
            row = {'name': name, 'value': value, 'paper_value': item.get('paper_value', value), 'unit': unit, 'source': rel, 'source_sha256': file_sha256(project / rel), 'tool': tool, 'verified_by': 'human'}
            for bound in ('min', 'max'):
                if bound in item:
                    row[bound] = item[bound]
            rows.append(row)
        return rows
    table_rows = []
    for item in tables:
        caption = str(item.get('caption', '')).strip()
        if not caption:
            raise ValueError('表格必须填写 caption')
        source_info = _artifact(project, item['source'], item['source_script'])
        table_rows.append({'caption': caption, 'rows': item.get('rows', []), 'source': source_info['path'], 'source_sha256': source_info['sha256'], 'source_script': source_info['source_script'], 'source_script_sha256': source_info['source_sha256']})
        script_map[source_info['source_script']] = source_info['source_sha256']
    now_dt = datetime.now(timezone.utc)
    if not started_at:
        artifact_root = project / 'results'
        artifact_times = [path.stat().st_mtime for path in artifact_root.rglob('*') if path.is_file()]
        started_at = datetime.fromtimestamp(min(artifact_times), tz=timezone.utc).isoformat() if artifact_times else now_dt.isoformat()
    elif not isinstance(started_at, str):
        raise TypeError(f'started_at 必须为 ISO 字符串或 None，收到 {type(started_at).__name__}')
    now = now_dt.isoformat()
    # 先算完所有组，script_map 才会包含参数/结论/表格引用的脚本；再组装 payload
    param_rows = numeric_rows(parameters, '参数')
    claim_rows = numeric_rows(claims, '关键结论')
    manual_rows_out = manual_rows(manual_stats, '人工核验结论')
    table_rows_out = table_rows
    payload = {'schema_version': SCHEMA_VERSION, 'status': 'success', 'started_at': started_at, 'completed_at': now, 'execution': {'command': command or '', 'input_files': [_relative(project, path) for path in input_files], 'exit_code': exit_code}, 'source_scripts': [{'path': path, 'sha256': digest} for path, digest in sorted(script_map.items())], 'figures': figure_rows, 'parameters': param_rows, 'claims': claim_rows, 'manual_stats': manual_rows_out, 'tables': table_rows_out}
    target = project / 'results' / 'run_manifest.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.run_manifest-', suffix='.json', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target

def load_manifest(project_root):
    """读取 results/run_manifest.json，返回解析后的字典。

    供 consistency_audit 等审计模块使用。文件不存在时返回空字典，
    由调用方决定是报错还是跳过。
    """
    project = Path(project_root).resolve()
    path = project / 'results' / 'run_manifest.json'
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def load_spss_outputs(project_root):
    """读取 results/数据/spss_outputs.json，返回可直传 manual_stats 的条目列表。

    SPSS 等人工工具跑出的统计量是**一等公民的真结果**：人用 SPSS 点菜单跑出统计量后，
    把数值登记进该 JSON（字段 name/value/unit/tool），它与 Python 结果平级进入
    run_manifest，并被 structure_validation gate 逐字核对（要求论文出现该值、来源文件含该值）。
    这不是“仅供参考”——论文正式结论的一部分。

    条目可带 `required`（默认 false）：
    - required=true 且未填 value → 抛 ValueError，write_run_manifest 拒绝生成
      （声明了必须用 SPSS 的赛题，漏填就不许出论文）；
    - required=false（或不标）且未填 → 跳过（optional 补充项 / 纯理论赛题空文件）。
    用不到 SPSS 的赛题不建该文件或留空 stats 即可，完全放行。
    """
    project = Path(project_root).resolve()
    path = project / 'results' / '数据' / 'spss_outputs.json'
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('spss_outputs.json 顶层必须是对象')
    stats = data.get('stats')
    if not isinstance(stats, list):
        raise ValueError('spss_outputs.json 缺少 stats 数组')
    tool = str(data.get('tool', 'SPSS 27 手动')).strip() or 'SPSS 27 手动'
    out = []
    for item in stats:
        if not isinstance(item, dict):
            raise ValueError('spss_outputs.json 的 stats 条目必须是对象')
        name = str(item.get('name', '')).strip()
        value = item.get('value', None)
        required = bool(item.get('required', False))
        # required=true 且缺值 → 一等公民强制，漏填不许生成
        if value is None or value == '':
            if required:
                raise ValueError(f'spss_outputs.json 必填项未填写 value: {name or "<未命名>"}（required=true）')
            continue
        entry = dict(item)
        entry['name'] = name
        entry.setdefault('tool', tool)
        # source 统一为相对 PROJECT_ROOT 的路径，外部透传安全
        entry.setdefault('source', str(path.relative_to(project)).replace('\\', '/'))
        out.append(entry)
    return out
