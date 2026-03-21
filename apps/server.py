#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import cgi
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1]
STATIC_DIR = ROOT / 'static'
UPLOADS_DIR = ROOT / 'uploads'
RUNS_DIR = ROOT / 'runs'
DEFAULT_COOKIE = WORKSPACE / 'secrets' / '1688-cookie.txt'
PARSE_SCRIPT = WORKSPACE / 'skills' / 'planning-brief-parser' / 'scripts' / 'parse_planning_xlsx.py'
AUTO_BATCH_SCRIPT = WORKSPACE / 'skills' / 'supplier-scoring' / 'scripts' / 'run_auto_batch_workflow.py'

for p in [UPLOADS_DIR, RUNS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

JOBS = {}
JOBS_LOCK = threading.Lock()


def now_ts():
    return int(time.time())


def read_json(path, default=None):
    try:
        with io.open(str(path), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def read_text(path, default=''):
    try:
        with io.open(str(path), 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(str(path), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sanitize_filename(name):
    name = os.path.basename(name or 'planning.xlsx').strip()
    if not name:
        name = 'planning.xlsx'
    return name.replace('/', '_').replace('\\', '_')


def update_job(job_id, **kwargs):
    with JOBS_LOCK:
        job = JOBS.get(job_id, {})
        job.update(kwargs)
        job['updated_at'] = now_ts()
        JOBS[job_id] = job
    return job


def load_job(job_id):
    with JOBS_LOCK:
        return JOBS.get(job_id)


def summarize_suppliers(top_suppliers):
    level_counts = {'A': 0, 'B': 0, 'C': 0, 'other': 0}
    grouped_cards = {'A': [], 'B': [], 'C': [], 'other': []}
    for row in top_suppliers or []:
        level = row.get('recommendation_level') or 'other'
        if level not in level_counts:
            level = 'other'
        level_counts[level] += 1

        score_breakdown = row.get('score_breakdown', {}) or {}
        risk_penalty = abs(score_breakdown.get('risk_penalty', 0) or 0)
        radar = {
            '风格匹配度': max(5, min(100, int((score_breakdown.get('theme_style', 0) or 0) / 40.0 * 100))),
            '价格匹配度': max(5, min(100, int((score_breakdown.get('price_fit', 0) or 0) / 15.0 * 100))),
            '细节契合度': max(5, min(100, int((score_breakdown.get('fabric_detail', 0) or 0) / 15.0 * 100))),
            '供应可靠度': max(5, min(100, int((score_breakdown.get('credibility', 0) or 0) / 10.0 * 100))),
            '风险可控度': max(5, min(100, 100 - int(risk_penalty / 15.0 * 100))),
        }

        ai_judgement = '可作为补充储备，建议先保留观察'
        if level == 'A':
            ai_judgement = '风格与价格带匹配度较高，建议优先推进'
        elif level == 'B':
            ai_judgement = '已有一定匹配度，建议重点复核后推进'

        grouped_cards[level].append({
            'supplier_name': row.get('supplier_name', ''),
            'product_title': row.get('product_title', ''),
            'product_image': row.get('product_image', ''),
            'price_fit_guess': row.get('price_fit_guess', ''),
            'score_total': row.get('score_total'),
            'recommendation_level': row.get('recommendation_level', ''),
            'recommend_reasons': row.get('recommend_reasons', [])[:3],
            'risk_warnings': row.get('risk_warnings', [])[:3],
            'source_url': row.get('source_url', ''),
            'shop_url': row.get('shop_url', ''),
            'supplier_profile_summary': row.get('supplier_profile_summary', ''),
            'ai_judgement': ai_judgement,
            'profile_summary': row.get('profile_summary', ''),
            'radar': radar,
            'score_breakdown': score_breakdown,
        })
    return level_counts, grouped_cards


def build_dashboard(job_dir, auto_summary):
    planning_brief = read_json(job_dir / 'planning-brief.json', {}) or {}
    batch_summary_path = auto_summary.get('batch_summary_json', '')
    batch_summary = read_json(Path(batch_summary_path), {}) if batch_summary_path else {}
    batch_results = batch_summary.get('batch_results', [])
    planned_items = auto_summary.get('selected_items', [])
    planned_lookup = {}
    for item in planning_brief.get('items', []):
        planned_lookup[item.get('item_index')] = item

    result_cards = []
    total_a = total_b = total_c = total_other = 0
    strong_count = weak_count = empty_count = rerun_count = 0
    matched_count = 0
    fallback_count = 0

    for result in batch_results:
        item_index = result.get('item_index')
        brief_item = planned_lookup.get(item_index, {})
        top_json = result.get('top_json')
        top_data = read_json(Path(top_json), {}) if top_json else {}
        top_suppliers = top_data.get('top_suppliers', []) or []
        level_counts, supplier_groups = summarize_suppliers(top_suppliers)
        total_a += level_counts['A']
        total_b += level_counts['B']
        total_c += level_counts['C']
        total_other += level_counts['other']
        top_count = result.get('top_count', 0) or 0
        second_pass = result.get('second_pass') or {}
        second_pass_used = bool(second_pass)
        if second_pass_used:
            rerun_count += 1
        if top_count >= 3:
            quality = 'strong'
            strong_count += 1
            matched_count += 1
        elif top_count > 0:
            quality = 'weak'
            weak_count += 1
            matched_count += 1
        else:
            quality = 'empty'
            empty_count += 1

        recommended_action = '建议继续观察'
        if quality == 'strong':
            recommended_action = '优先推进A类供应商'
        elif quality == 'weak':
            recommended_action = '重点复核后推进'
        elif quality == 'empty' and second_pass_used:
            recommended_action = '建议补其他渠道'
            fallback_count += 1

        result_cards.append({
            'item_index': item_index,
            'theme': brief_item.get('theme') or (result.get('brief_summary', '').split('|')[2].strip() if '|' in result.get('brief_summary', '') else ''),
            'market': brief_item.get('market', ''),
            'category_l3': brief_item.get('category_l3', ''),
            'brief_summary': result.get('brief_summary', ''),
            'price_band_raw': brief_item.get('price_band_raw', ''),
            'fabrics': brief_item.get('fabrics', [])[:4],
            'elements': brief_item.get('elements', [])[:4],
            'demand_by_month': brief_item.get('demand_by_month', {}),
            'top_count': top_count,
            'quality': quality,
            'second_pass_used': second_pass_used,
            'second_pass_still_empty': bool(second_pass and not second_pass.get('top_count')),
            'recommended_action': recommended_action,
            'ai_summary': '当前匹配度较高，建议优先推进' if quality == 'strong' else ('已有可跟进候选，建议重点复核' if quality == 'weak' else '当前渠道结果偏弱，建议补其他渠道'),
            'a_count': level_counts['A'],
            'b_count': level_counts['B'],
            'c_count': level_counts['C'],
            'supplier_groups': supplier_groups,
            'shortlist_md': read_text(Path(result.get('shortlist_md'))) if result.get('shortlist_md') else '',
        })

    total_items = len(planning_brief.get('items', []))
    selected_count = len(planned_items)
    summary_md = read_text(Path(auto_summary.get('batch_summary_v2_md', ''))) if auto_summary.get('batch_summary_v2_md') else ''

    dashboard = {
        'job_id': job_dir.name,
        'generated_at': now_ts(),
        'upload_name': read_json(job_dir / 'meta.json', {}).get('original_filename', ''),
        'overview': {
            'total_items': total_items,
            'selected_count': selected_count,
            'strong_count': strong_count,
            'weak_count': weak_count,
            'empty_count': empty_count,
            'rerun_count': rerun_count,
            'matched_count': matched_count,
            'fallback_count': fallback_count,
            'supplier_counts': {
                'A': total_a,
                'B': total_b,
                'C': total_c,
                'other': total_other,
            }
        },
        'planned_items': planned_items,
        'result_cards': result_cards,
        'summary_markdown': summary_md,
        'planning_brief': planning_brief,
    }
    write_json(job_dir / 'dashboard.json', dashboard)
    return dashboard


def run_job(job_id):
    job = load_job(job_id)
    if not job:
        return
    job_dir = Path(job['job_dir'])
    xlsx_path = Path(job['xlsx_path'])
    cookie_path = Path(job['cookie_path'])
    workdir = job_dir / 'workflow-output'

    env = os.environ.copy()
    env['OPENCLAW_WORKSPACE'] = str(WORKSPACE)
    env['PYTHONIOENCODING'] = 'utf-8'

    try:
        update_job(job_id, status='validating', stage='校验企划文件', progress=10)
        parse_proc = subprocess.run(
            [sys.executable, str(PARSE_SCRIPT), str(xlsx_path), '--pretty'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=str(WORKSPACE),
            env=env,
        )
        if parse_proc.returncode != 0:
            raise RuntimeError(parse_proc.stderr or 'Parser failed')
        brief = json.loads(parse_proc.stdout)
        item_count = brief.get('item_count', 0)
        if item_count <= 0:
            raise RuntimeError('模板识别失败：没有解析出任何企划 item，请确认使用固定企划模板。')
        write_json(job_dir / 'planning-brief.json', brief)
        preview = {
            'item_count': item_count,
            'preview_items': [
                {
                    'theme': x.get('theme', ''),
                    'price_band_raw': x.get('price_band_raw', ''),
                    'brief_summary': x.get('brief_summary', '')
                }
                for x in brief.get('items', [])[:5]
            ]
        }
        update_job(job_id, status='running', stage='企划解析完成，开始寻源', progress=25, preview=preview)

        cmd = [
            sys.executable, str(AUTO_BATCH_SCRIPT),
            '--xlsx', str(xlsx_path),
            '--cookie-file', str(cookie_path),
            '--max-items', str(job.get('max_items', 5)),
            '--queries', str(job.get('queries', 2)),
            '--pages', str(job.get('pages', 1)),
            '--top-k', str(job.get('top_k', 10)),
            '--workdir', str(workdir),
        ]
        update_job(job_id, stage='正在执行自动批量 workflow', progress=55)
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=str(WORKSPACE),
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or 'Workflow failed')
        out_path = (proc.stdout or '').strip().splitlines()[-1].strip()
        if not out_path:
            raise RuntimeError('Workflow finished but did not return summary path')
        auto_summary = read_json(Path(out_path))
        if not auto_summary:
            raise RuntimeError('Failed to load workflow summary: {}'.format(out_path))
        shutil.copyfile(str(Path(out_path)), str(job_dir / 'auto-batch-summary.json'))

        update_job(job_id, stage='正在生成视觉化结果页', progress=88)
        dashboard = build_dashboard(job_dir, auto_summary)
        update_job(
            job_id,
            status='done',
            stage='完成',
            progress=100,
            result=dashboard,
            auto_summary=auto_summary,
            raw_stdout=proc.stdout,
            raw_stderr=proc.stderr,
        )
    except Exception as e:
        err = '{}\n\n{}'.format(str(e), traceback.format_exc())
        update_job(job_id, status='error', stage='执行失败', progress=100, error=err)


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class AppHandler(BaseHTTPRequestHandler):
    server_version = 'SourcingWeb/0.1'

    def _send_json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_text(self, text, status=200, content_type='text/plain; charset=utf-8'):
        payload = text.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_static(self, path):
        target = (STATIC_DIR / path.lstrip('/')).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.exists() or not target.is_file():
            return self._send_text('Not found', 404)
        suffix = target.suffix.lower()
        ctype = {
            '.html': 'text/html; charset=utf-8',
            '.css': 'text/css; charset=utf-8',
            '.js': 'application/javascript; charset=utf-8',
            '.json': 'application/json; charset=utf-8',
            '.svg': 'image/svg+xml',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
        }.get(suffix, 'application/octet-stream')
        data = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/health':
            return self._send_json({'ok': True, 'cookie_exists': DEFAULT_COOKIE.exists()})

        if path == '/api/template-spec':
            return self._send_json({
                'accepted_extensions': ['.xlsx'],
                'requirements': [
                    '请上传固定企划模板（Excel .xlsx）',
                    '系统会先校验是否能解析出 item/theme/price/fabrics/elements',
                    '如果没有解析出任何 item，会直接提示模板不符合要求',
                    '默认使用 workspace/secrets/1688-cookie.txt 作为 1688 cookie 文件'
                ]
            })

        if path.startswith('/api/jobs/'):
            job_id = path.split('/')[-1]
            job = load_job(job_id)
            if not job:
                return self._send_json({'error': 'Job not found'}, 404)
            safe_job = dict(job)
            return self._send_json(safe_job)

        if path == '/' or path == '/index.html':
            return self._serve_static('index.html')

        static_path = path.lstrip('/')
        return self._serve_static(static_path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/jobs':
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    'REQUEST_METHOD': 'POST',
                    'CONTENT_TYPE': self.headers.get('Content-Type', ''),
                },
            )
            if 'planning_file' not in form:
                return self._send_json({'error': 'missing planning_file'}, 400)
            upload = form['planning_file']
            filename = sanitize_filename(getattr(upload, 'filename', 'planning.xlsx'))
            if not filename.lower().endswith('.xlsx'):
                return self._send_json({'error': '只支持 .xlsx 文件'}, 400)

            job_id = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
            job_dir = RUNS_DIR / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            xlsx_path = job_dir / filename
            with io.open(str(xlsx_path), 'wb') as f:
                f.write(upload.file.read())

            max_items = int(form.getfirst('max_items', '5'))
            queries = int(form.getfirst('queries', '2'))
            pages = int(form.getfirst('pages', '1'))
            top_k = int(form.getfirst('top_k', '10'))
            cookie_path = form.getfirst('cookie_path', str(DEFAULT_COOKIE)).strip() or str(DEFAULT_COOKIE)

            if not Path(cookie_path).exists():
                return self._send_json({'error': 'cookie 文件不存在: {}'.format(cookie_path)}, 400)

            meta = {
                'job_id': job_id,
                'original_filename': filename,
                'created_at': now_ts(),
                'xlsx_path': str(xlsx_path),
                'cookie_path': cookie_path,
                'max_items': max_items,
                'queries': queries,
                'pages': pages,
                'top_k': top_k,
            }
            write_json(job_dir / 'meta.json', meta)
            job = {
                'job_id': job_id,
                'status': 'queued',
                'stage': '已接收文件，等待启动',
                'progress': 0,
                'created_at': now_ts(),
                'updated_at': now_ts(),
                'job_dir': str(job_dir),
                'xlsx_path': str(xlsx_path),
                'cookie_path': cookie_path,
                'max_items': max_items,
                'queries': queries,
                'pages': pages,
                'top_k': top_k,
                'original_filename': filename,
            }
            update_job(job_id, **job)
            t = threading.Thread(target=run_job, args=(job_id,))
            t.daemon = True
            t.start()
            return self._send_json({'job_id': job_id, 'status': 'queued'})

        return self._send_json({'error': 'Not found'}, 404)


def main():
    host = os.environ.get('SOURCING_WEB_HOST', '127.0.0.1')
    port = int(os.environ.get('SOURCING_WEB_PORT', '8765'))
    httpd = ThreadingHTTPServer((host, port), AppHandler)
    print('Sourcing web app running at http://{}:{}/'.format(host, port))
    httpd.serve_forever()


if __name__ == '__main__':
    main()
