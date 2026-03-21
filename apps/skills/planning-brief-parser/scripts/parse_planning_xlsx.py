#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS_MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'


def col_to_index(ref: str) -> int:
    letters = ''.join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch.upper()) - 64)
    return n


def parse_shared_strings(zf: zipfile.ZipFile):
    if 'xl/sharedStrings.xml' not in zf.namelist():
        return []
    root = ET.fromstring(zf.read('xl/sharedStrings.xml'))
    out = []
    for si in root.findall(f'{{{NS_MAIN}}}si'):
        texts = []
        for t in si.iter(f'{{{NS_MAIN}}}t'):
            texts.append(t.text or '')
        out.append(''.join(texts))
    return out


def parse_workbook(zf: zipfile.ZipFile):
    wb = ET.fromstring(zf.read('xl/workbook.xml'))
    rels = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
    rid_to_target = {r.attrib['Id']: r.attrib['Target'] for r in rels.findall(f'{{{NS_PKG}}}Relationship')}
    sheets = []
    sheets_node = wb.find(f'{{{NS_MAIN}}}sheets')
    for s in sheets_node:
        rid = s.attrib.get(f'{{{NS_REL}}}id')
        target = rid_to_target[rid]
        if not target.startswith('xl/'):
            target = 'xl/' + target.lstrip('/')
        sheets.append((s.attrib.get('name'), target))
    return sheets


def get_cell_value(cell, shared):
    t = cell.attrib.get('t')
    v = cell.find(f'{{{NS_MAIN}}}v')
    isel = cell.find(f'{{{NS_MAIN}}}is')
    if t == 's' and v is not None and v.text is not None:
        idx = int(v.text)
        return shared[idx] if idx < len(shared) else ''
    if t == 'inlineStr' and isel is not None:
        return ''.join((n.text or '') for n in isel.iter(f'{{{NS_MAIN}}}t'))
    if v is not None and v.text is not None:
        return v.text
    return ''


def parse_sheet_rows(zf: zipfile.ZipFile, sheet_target: str, shared):
    root = ET.fromstring(zf.read(sheet_target))
    rows = []
    for row in root.findall(f'.//{{{NS_MAIN}}}sheetData/{{{NS_MAIN}}}row'):
        cells = {}
        for c in row.findall(f'{{{NS_MAIN}}}c'):
            ref = c.attrib.get('r', '')
            idx = col_to_index(ref)
            cells[idx] = get_cell_value(c, shared).strip()
        rows.append(cells)
    return rows


def parse_monthly_qty(text: str):
    result = {}
    if not text:
        return result
    for month, qty in re.findall(r'(\d+)月[:：]\s*(\d+)', text):
        result[f'{month}月'] = int(qty)
    if not result:
        m = re.search(r'\d+', text)
        if m:
            result['raw'] = int(m.group())
    return result


def parse_price_band(text: str):
    text = (text or '').strip()
    if not text:
        return None, None
    m = re.search(r'(\d+(?:\.\d+)?)\s*[-~～]\s*(\d+(?:\.\d+)?)', text)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        return a, b
    m = re.search(r'(\d+(?:\.\d+)?)', text)
    if m:
        v = float(m.group(1))
        return v, v
    return None, None


def split_tokens(text: str):
    if not text:
        return []
    parts = re.split(r'[\/、,，\n|]+', text)
    return [p.strip() for p in parts if p and p.strip()]


def dedupe_keep_order(items):
    seen = set()
    out = []
    for item in items:
        if not item:
            continue
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def infer_tags(record):
    theme = record.get('theme', '') or ''
    notes = record.get('notes', '') or ''
    colors = record.get('colors', []) or []
    fabrics = record.get('fabrics', []) or []
    elements = record.get('elements', []) or []
    market = record.get('market', '') or ''

    style_tags = []
    silhouette_tags = []
    occasion_tags = []
    market_tags = []
    required_tags = []
    forbidden_tags = []

    for token in split_tokens(theme):
        style_tags.append(token)

    if '印花' in theme:
        style_tags.append('印花')
    if '小碎花' in theme:
        style_tags.append('小碎花')
    if '晕染' in theme:
        style_tags.append('晕染')
    if '基础' in theme:
        style_tags.append('基础款')
    if '轻礼服' in theme:
        style_tags += ['轻礼服', '场合感']
        occasion_tags += ['礼服', '宴会']
    if '度假' in theme:
        occasion_tags.append('度假')
    if 'Hijab' in theme:
        market_tags += ['中东风格', '保守覆盖', '长款偏好']
    if 'POLO' in theme:
        occasion_tags.append('休闲运动')

    for c in colors:
        if c in ('柔和色调',):
            style_tags.append(c)
    for f in fabrics:
        if f in ('雪纺', '欧根纱', '网纱'):
            style_tags.append('轻盈')
        style_tags.append(f)
    for e in elements:
        style_tags.append(e)

    if '大A摆' in theme:
        silhouette_tags.append('A摆')
    if '衬衫裙' in theme:
        silhouette_tags.append('衬衫裙')
    if '裙长到脚踝' in notes:
        silhouette_tags.append('及踝长裙')
        required_tags.append('及踝长度')
    if '收腰' in notes or '收腰' in theme:
        silhouette_tags.append('收腰')
        required_tags.append('收腰')

    market_tags.append(f'{market}市场') if market else None

    # note patterns
    for m in re.findall(r'避免([^，。；\n]+)', notes):
        forbidden_tags.append(m.strip())
    for m in re.findall(r'不要([^，。；\n]+)', notes):
        forbidden_tags.append(m.strip())
    for m in re.findall(r'款式要([^，。；\n]+)', notes):
        required_tags.append(m.strip())
    if '颜色不要过深' in notes:
        forbidden_tags.append('颜色过深')
        if '提花' in notes:
            forbidden_tags.append('深色提花')

    return {
        'style_tags': dedupe_keep_order(style_tags),
        'silhouette_tags': dedupe_keep_order(silhouette_tags),
        'occasion_tags': dedupe_keep_order(occasion_tags),
        'market_tags': dedupe_keep_order(market_tags),
        'required_tags': dedupe_keep_order(required_tags),
        'forbidden_tags': dedupe_keep_order(forbidden_tags),
    }


def derive_summary(record):
    bits = [record.get('market', ''), record.get('category_l3', '') or record.get('category_l2', ''), record.get('theme', '')]
    price = record.get('price_band_raw')
    if price:
        bits.append(f'价格带{price}')
    if record.get('fabrics'):
        bits.append('面料:' + '/'.join(record['fabrics'][:3]))
    if record.get('elements'):
        bits.append('元素:' + '/'.join(record['elements'][:3]))
    if record.get('forbidden_tags'):
        bits.append('禁忌:' + '/'.join(record['forbidden_tags'][:3]))
    if record.get('required_tags'):
        bits.append('要求:' + '/'.join(record['required_tags'][:3]))
    return ' | '.join([b for b in bits if b])


def detect_sheet_schema(rows):
    # Latest canonical template: fixed columns only.
    # A: 市场
    # B-E: 商品分类（四级类目）
    # F: 需求数量
    # G: 核心单品（企划款）
    # H: 爆款参考（主图）
    # I-P: 其他图片参考
    # Q: 风格
    # R: 颜色
    # S: 面料
    # T: 元素
    # U: 建议价格带
    # V: 备注
    return {
        'header_row_idx': 1,
        'market': 1,
        'category_l1': 2,
        'category_l2': 3,
        'category_l3': 4,
        'category_l4': 5,
        'demand': 6,
        'theme': 7,
        'reference_start': 8,
        'reference_end': 16,
        'primary_reference_col': 8,
        'style': 17,
        'colors': 18,
        'fabrics': 19,
        'elements': 20,
        'price': 21,
        'notes': 22,
    }


def load_image_map_from_manifest(manifest_path):
    image_map = {}
    if not manifest_path:
        return image_map
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    for img in manifest.get('images', []):
        image_map.setdefault(img.get('sheet'), []).append(img)
    return image_map


def auto_extract_image_manifest(xlsx_path):
    script_path = Path(__file__).with_name('extract_xlsx_images.py')
    if not script_path.exists():
        return None
    tmpdir = tempfile.mkdtemp(prefix='planning-images-')
    cmd = [sys.executable, str(script_path), str(xlsx_path), '--outdir', tmpdir]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if proc.returncode != 0:
        return None
    manifest_path = (proc.stdout or '').strip().splitlines()[-1].strip()
    if not manifest_path or not Path(manifest_path).exists():
        candidate = Path(tmpdir) / 'image-manifest.json'
        if candidate.exists():
            manifest_path = str(candidate)
        else:
            return None
    return manifest_path


def normalize_rows(sheet_name, rows, image_map=None):
    records = []
    schema = detect_sheet_schema(rows)
    market_col = schema.get('market', 1)
    c1 = schema['category_l1']
    c2 = schema['category_l2']
    c3 = schema['category_l3']
    c4 = schema.get('category_l4')
    current = {market_col: '', c1: '', c2: '', c3: '', c4: ''}

    for row_idx, row in enumerate(rows, 1):
        if row_idx <= schema.get('header_row_idx', 0):
            continue

        market_val = row.get(market_col, '') or current[market_col]
        a = row.get(c1, '') or current[c1]
        b = row.get(c2, '') or current[c2]
        c = row.get(c3, '') or current[c3]
        d = row.get(c4, '') if c4 else ''
        if row.get(market_col, ''):
            current[market_col] = row[market_col]
        if row.get(c1, ''):
            current[c1] = row[c1]
        if row.get(c2, ''):
            current[c2] = row[c2]
        if row.get(c3, ''):
            current[c3] = row[c3]
        if c4 and row.get(c4, ''):
            current[c4] = row[c4]
        d = d or current.get(c4, '') if c4 else ''

        theme = row.get(schema['theme'], '')
        if not theme:
            continue
        if theme in {'重点提炼', '商品分类', '一级类目', '二级类目', '三级类目', '四级类目', '需求数量', '核心单品'}:
            continue
        if '月：' in theme and not re.search(r'[A-Za-z\u4e00-\u9fff]{2,}', theme.replace('月', '')):
            continue

        qty_raw = row.get(schema['demand'], '')
        price_raw = row.get(schema['price'], '')
        price_min, price_max = parse_price_band(price_raw)
        rs = schema.get('reference_start')
        re_col = schema.get('reference_end')
        image_refs = [row.get(i, '') for i in range(rs, re_col + 1) if rs and re_col and row.get(i, '')]
        anchored_images = []
        primary_reference = None
        secondary_references = []
        if image_map:
            for img in image_map.get(sheet_name, []):
                anchor_col = img.get('anchor_from_col', 0)
                if img.get('anchor_from_row') == row_idx and rs <= anchor_col <= re_col:
                    anchored_images.append(img)
            anchored_images = sorted(anchored_images, key=lambda x: (x.get('anchor_from_col', 999), x.get('anchor_from_row', 999)))
            primary_col = schema.get('primary_reference_col', rs)
            for img in anchored_images:
                if img.get('anchor_from_col') == primary_col and primary_reference is None:
                    primary_reference = img
                else:
                    secondary_references.append(img)

        style_raw = row.get(schema.get('style'), '') if schema.get('style') else ''
        colors_raw = row.get(schema['colors'], '')
        fabrics_raw = row.get(schema['fabrics'], '')
        elements_raw = row.get(schema['elements'], '')

        record = {
            'market': market_val or sheet_name,
            'category_l1': a,
            'category_l2': b,
            'category_l3': c,
            'category_l4': d,
            'demand_raw': qty_raw,
            'demand_by_month': parse_monthly_qty(qty_raw),
            'theme': theme,
            'reference_slots': len(image_refs),
            'reference_values': image_refs,
            'anchored_image_count': len(anchored_images),
            'anchored_images': anchored_images,
            'primary_reference_image': primary_reference,
            'secondary_reference_images': secondary_references,
            'style_raw': style_raw,
            'colors_raw': colors_raw,
            'colors': split_tokens(colors_raw),
            'fabrics_raw': fabrics_raw,
            'fabrics': split_tokens(fabrics_raw),
            'elements_raw': elements_raw,
            'elements': split_tokens(elements_raw),
            'price_band_raw': price_raw,
            'price_min': price_min,
            'price_max': price_max,
            'notes': row.get(schema['notes'], ''),
        }
        record.update(infer_tags(record))
        record['brief_summary'] = derive_summary(record)
        records.append(record)
    return records


def main():
    ap = argparse.ArgumentParser(description='Parse planning XLSX into normalized brief items JSON.')
    ap.add_argument('xlsx_path', help='Path to .xlsx file')
    ap.add_argument('--pretty', action='store_true', help='Pretty-print JSON')
    ap.add_argument('--summary', action='store_true', help='Print compact human summary instead of JSON')
    ap.add_argument('--image-manifest', help='Path to image-manifest.json from extract_xlsx_images.py')
    args = ap.parse_args()

    path = Path(args.xlsx_path)
    if not path.exists():
        print(f'File not found: {path}', file=sys.stderr)
        sys.exit(1)

    manifest_path = args.image_manifest
    if not manifest_path:
        manifest_path = auto_extract_image_manifest(path)
    image_map = load_image_map_from_manifest(manifest_path) if manifest_path else {}

    with zipfile.ZipFile(path) as zf:
        shared = parse_shared_strings(zf)
        sheets = parse_workbook(zf)
        all_records = []
        for sheet_name, target in sheets:
            rows = parse_sheet_rows(zf, target, shared)
            all_records.extend(normalize_rows(sheet_name, rows, image_map=image_map))

    output = {
        'source_file': str(path),
        'item_count': len(all_records),
        'items': all_records,
    }

    if args.summary:
        print(f"source_file: {output['source_file']}")
        print(f"item_count: {output['item_count']}")
        for i, item in enumerate(all_records, 1):
            price = item['price_band_raw'] or 'N/A'
            print(f"[{i}] {item['market']} | {item['category_l3'] or item['category_l2'] or item['category_l1']} | {item['theme']} | 价格带 {price}")
    else:
        if args.pretty:
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
