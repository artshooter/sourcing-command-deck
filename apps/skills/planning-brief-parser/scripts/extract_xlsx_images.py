#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS_MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
NS_XDR = 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing'
NS_A = 'http://schemas.openxmlformats.org/drawingml/2006/main'


def idx_to_col(n: int) -> str:
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def parse_workbook(zf):
    wb = ET.fromstring(zf.read('xl/workbook.xml'))
    rels = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
    rid_to_target = {r.attrib['Id']: r.attrib['Target'] for r in rels.findall(f'{{{NS_PKG}}}Relationship')}
    sheets = []
    for s in wb.find(f'{{{NS_MAIN}}}sheets'):
        rid = s.attrib.get(f'{{{NS_REL}}}id')
        target = rid_to_target[rid]
        if not target.startswith('xl/'):
            target = 'xl/' + target.lstrip('/')
        sheets.append((s.attrib.get('name'), target))
    return sheets


def rel_target_map(zf, rel_path):
    if rel_path not in zf.namelist():
        return {}
    root = ET.fromstring(zf.read(rel_path))
    return {r.attrib['Id']: r.attrib['Target'] for r in root.findall(f'{{{NS_PKG}}}Relationship')}


def normalize_rel_target(base_dir: str, target: str) -> str:
    joined = os.path.normpath(os.path.join(base_dir, target))
    return joined.replace('\\', '/')


def main():
    ap = argparse.ArgumentParser(description='Extract embedded images from XLSX and map them to sheet anchors.')
    ap.add_argument('xlsx_path')
    ap.add_argument('--outdir', required=True)
    args = ap.parse_args()

    xlsx_path = Path(args.xlsx_path)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    images_dir = outdir / 'images'
    images_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        'source_file': str(xlsx_path),
        'images': []
    }

    with zipfile.ZipFile(xlsx_path) as zf:
        sheets = parse_workbook(zf)
        for sheet_name, sheet_target in sheets:
            sheet_filename = Path(sheet_target).name
            sheet_rels = f"xl/worksheets/_rels/{sheet_filename}.rels"
            sheet_rel_map = rel_target_map(zf, sheet_rels)

            drawing_targets = []
            for rid, target in sheet_rel_map.items():
                if 'drawing' in target:
                    drawing_targets.append(normalize_rel_target('xl/worksheets', target))

            for drawing_target in drawing_targets:
                drawing_rels = f"{str(Path(drawing_target).parent)}/_rels/{Path(drawing_target).name}.rels"
                draw_rel_map = rel_target_map(zf, drawing_rels)
                root = ET.fromstring(zf.read(drawing_target))
                for anchor in root:
                    pic = anchor.find(f'{{{NS_XDR}}}pic')
                    if pic is None:
                        continue
                    frm = anchor.find(f'{{{NS_XDR}}}from')
                    to = anchor.find(f'{{{NS_XDR}}}to')
                    blip = pic.find(f'.//{{{NS_A}}}blip')
                    if blip is None:
                        continue
                    rid = blip.attrib.get(f'{{{NS_REL}}}embed')
                    media_target = draw_rel_map.get(rid)
                    if not media_target:
                        continue
                    media_path = normalize_rel_target(str(Path(drawing_target).parent), media_target)
                    ext = Path(media_path).suffix or '.bin'

                    from_col0 = int(frm.find(f'{{{NS_XDR}}}col').text)
                    from_row0 = int(frm.find(f'{{{NS_XDR}}}row').text)
                    to_col0 = int(to.find(f'{{{NS_XDR}}}col').text)
                    to_row0 = int(to.find(f'{{{NS_XDR}}}row').text)
                    from_col = from_col0 + 1
                    from_row = from_row0 + 1
                    to_col = to_col0 + 1
                    to_row = to_row0 + 1

                    outfile = images_dir / f"{sheet_name}_r{from_row}_c{idx_to_col(from_col)}{ext}"
                    with zf.open(media_path) as src, open(outfile, 'wb') as dst:
                        shutil.copyfileobj(src, dst)

                    manifest['images'].append({
                        'sheet': sheet_name,
                        'drawing': drawing_target,
                        'anchor_from_row': from_row,
                        'anchor_from_col': from_col,
                        'anchor_from_col_letter': idx_to_col(from_col),
                        'anchor_to_row': to_row,
                        'anchor_to_col': to_col,
                        'anchor_to_col_letter': idx_to_col(to_col),
                        'cell_ref': f"{idx_to_col(from_col)}{from_row}",
                        'image_path': str(outfile),
                        'media_path_in_xlsx': media_path,
                    })

    manifest_path = outdir / 'image-manifest.json'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(str(manifest_path))


if __name__ == '__main__':
    main()
