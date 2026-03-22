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

from config import (
    WORKSPACE, STATIC_DIR, UPLOADS_DIR, RUNS_DIR,
    COOKIE_PATH, PARSE_SCRIPT, AUTO_BATCH_SCRIPT,
    HOST, PORT, ENABLE_LLM, LLM_API_KEY,
)

JOBS = {}
JOBS_LOCK = threading.Lock()
JOBS_FILE = RUNS_DIR / '_jobs.json'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with io.open(str(path), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sanitize_filename(name):
    name = os.path.basename(name or 'planning.xlsx').strip()
    if not name:
        name = 'planning.xlsx'
    return name.replace('/', '_').replace('\\', '_')


# ---------------------------------------------------------------------------
# Job persistence
# ---------------------------------------------------------------------------

def _persist_jobs_locked():
    """Write JOBS to disk atomically. Must be called with JOBS_LOCK held."""
    try:
        snapshot = {}
        for jid, job in JOBS.items():
            slim = {k: v for k, v in job.items() if k not in ('result', 'auto_summary', 'raw_stdout', 'raw_stderr')}
            snapshot[jid] = slim
        tmp_path = str(JOBS_FILE) + '.tmp'
        with io.open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(JOBS_FILE))
    except Exception:
        pass


def _load_persisted_jobs():
    global JOBS
    data = read_json(JOBS_FILE, {})
    if isinstance(data, dict):
        JOBS = data


def update_job(job_id, **kwargs):
    with JOBS_LOCK:
        job = JOBS.get(job_id, {})
        job.update(kwargs)
        job['updated_at'] = now_ts()
        JOBS[job_id] = job
        _persist_jobs_locked()
    return job


def load_job(job_id):
    with JOBS_LOCK:
        return JOBS.get(job_id)


def probe_1688_cookie(cookie_str):
    """探针验证 cookie 是否被 1688 风控拦截，返回 (ok, ret_list)。"""
    import hashlib
    import re
    import urllib.parse
    import urllib.request
    APP_KEY = '12574478'
    API = 'mtop.relationrecommend.WirelessRecommend.recommend'
    query = '连衣裙'
    try:
        m = re.search(r'_m_h5_tk=([^_;]+)_', cookie_str) or re.search(r'_m_h5_tk=([^;]+)', cookie_str)
        if not m:
            return False, ['COOKIE_FORMAT_ERROR: missing _m_h5_tk']
        token = m.group(1)
        ts = str(int(time.time() * 1000))
        params_obj = {
            'beginPage': 1, 'pageSize': 10, 'method': 'getOfferList',
            'pageId': f'page_{ts}', 'keywords': query,
            'verticalProductFlag': 'pcmarket', 'searchScene': 'pcOfferSearch', 'charset': 'GBK',
        }
        data_obj = {'appId': 32517, 'params': json.dumps(params_obj, ensure_ascii=False)}
        data = json.dumps(data_obj, ensure_ascii=False, separators=(',', ':'))
        sig = hashlib.md5(f'{token}&{ts}&{APP_KEY}&{data}'.encode('utf-8')).hexdigest()
        qs = urllib.parse.urlencode({
            'jsv': '2.7.2', 'appKey': APP_KEY, 't': ts, 'sign': sig,
            'api': API, 'v': '2.0', 'type': 'originaljson', 'dataType': 'json',
            'timeout': '20000', 'ecode': '0', 'valueType': 'original', 'data': data,
        })
        url = f'https://h5api.m.1688.com/h5/{API.lower()}/2.0/?{qs}'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json,text/plain,*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cookie': cookie_str,
            'Referer': 'https://s.1688.com/selloffer/offer_search.htm?keywords=' + urllib.parse.quote(query),
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode('utf-8', errors='replace'))
        ret = raw.get('ret') or []
        blocked = any('FAIL_SYS_USER_VALIDATE' in r for r in ret)
        return not blocked, ret
    except Exception as e:
        return False, [f'PROBE_ERROR: {e}']


# ---------------------------------------------------------------------------
# Dashboard builder
# ---------------------------------------------------------------------------

def summarize_suppliers(top_suppliers, llm_report=None, item_index=None):
    level_counts = {'A': 0, 'B': 0, 'C': 0, 'other': 0}
    grouped_cards = {'A': [], 'B': [], 'C': [], 'other': []}

    # Pre-build LLM judgement lookup
    llm_judgements = {}
    if llm_report and item_index:
        for j in llm_report.get('supplier_judgements', {}).get(item_index, []):
            llm_judgements[j.get('supplier_name', '')] = j.get('ai_judgement', '')

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

        # AI judgement: prefer LLM-generated, then per-row LLM, then rule-based default
        supplier_name = row.get('supplier_name', '')
        ai_judgement = llm_judgements.get(supplier_name) or row.get('llm_ai_judgement', '')
        if not ai_judgement:
            ai_judgement = '可作为补充储备，建议先保留观察'
            if level == 'A':
                ai_judgement = '风格与价格带匹配度较高，建议优先推进'
            elif level == 'B':
                ai_judgement = '已有一定匹配度，建议重点复核后推进'

        # Profile summary: prefer LLM-generated
        profile_summary = row.get('llm_profile_summary') or row.get('supplier_profile_summary', '')

        grouped_cards[level].append({
            'supplier_name': supplier_name,
            'product_title': row.get('product_title', ''),
            'product_image': row.get('product_image', ''),
            'price_fit_guess': row.get('price_fit_guess', ''),
            'score_total': row.get('score_total'),
            'recommendation_level': row.get('recommendation_level', ''),
            'recommend_reasons': row.get('recommend_reasons', [])[:3],
            'risk_warnings': row.get('risk_warnings', [])[:3],
            'source_url': row.get('source_url', ''),
            'shop_url': row.get('shop_url', ''),
            'supplier_profile_summary': profile_summary,
            'ai_judgement': ai_judgement,
            'profile_summary': row.get('profile_summary', ''),
            'radar': radar,
            'score_breakdown': score_breakdown,
            'style_fit_guess': row.get('style_fit_guess', ''),
            'style_fit_reason': row.get('style_fit_reason', ''),
            'market_fit_guess': row.get('market_fit_guess', ''),
            'market_fit_reason': row.get('market_fit_reason', ''),
        })
    return level_counts, grouped_cards


def build_dashboard(job_dir, auto_summary, llm_report=None):
    planning_brief = read_json(job_dir / 'planning-brief.json', {}) or {}
    batch_summary_path = auto_summary.get('batch_summary_json', '')
    batch_summary = read_json(Path(batch_summary_path), {}) if batch_summary_path else {}
    batch_results = batch_summary.get('batch_results', [])
    planned_items = auto_summary.get('selected_items', [])
    planned_lookup = {}
    for item in planning_brief.get('items', []):
        planned_lookup[item.get('item_index')] = item

    # LLM item summaries lookup
    llm_item_summaries = {}
    if llm_report:
        llm_item_summaries = llm_report.get('item_summaries', {})

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
        level_counts, supplier_groups = summarize_suppliers(top_suppliers, llm_report, item_index)
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

        # Use LLM summaries if available, otherwise rule-based defaults
        llm_item = llm_item_summaries.get(item_index, {}) or llm_item_summaries.get(str(item_index), {})

        recommended_action = llm_item.get('recommended_action', '')
        if not recommended_action:
            recommended_action = '建议继续观察'
            if quality == 'strong':
                recommended_action = '优先推进A类供应商'
            elif quality == 'weak':
                recommended_action = '重点复核后推进'
            elif quality == 'empty' and second_pass_used:
                recommended_action = '建议补其他渠道'

        if quality == 'empty' and second_pass_used:
            fallback_count += 1

        ai_summary = llm_item.get('ai_summary', '')
        if not ai_summary:
            ai_summary = '当前匹配度较高，建议优先推进' if quality == 'strong' else ('已有可跟进候选，建议重点复核' if quality == 'weak' else '当前渠道结果偏弱，建议补其他渠道')

        result_cards.append({
            'item_index': item_index,
            'theme': brief_item.get('theme') or (result.get('brief_summary', '').split('|')[2].strip() if '|' in result.get('brief_summary', '') else ''),
            'market': brief_item.get('market', ''),
            'category_l3': brief_item.get('category_l3', ''),
            'brief_summary': result.get('brief_summary', ''),
            'price_band_raw': brief_item.get('price_band_raw', ''),
            'styles': brief_item.get('styles', [])[:4] or [s.strip() for s in (brief_item.get('style_raw') or '').replace('，', ',').replace('/', ',').replace('、', ',').split(',') if s.strip()][:4],
            'colors': brief_item.get('colors', [])[:4],
            'fabrics': brief_item.get('fabrics', [])[:4],
            'elements': brief_item.get('elements', [])[:4],
            'demand_by_month': brief_item.get('demand_by_month', {}),
            'top_count': top_count,
            'quality': quality,
            'second_pass_used': second_pass_used,
            'second_pass_still_empty': bool(second_pass and not second_pass.get('top_count')),
            'recommended_action': recommended_action,
            'ai_summary': ai_summary,
            'a_count': level_counts['A'],
            'b_count': level_counts['B'],
            'c_count': level_counts['C'],
            'supplier_groups': supplier_groups,
            'shortlist_md': read_text(Path(result.get('shortlist_md'))) if result.get('shortlist_md') else '',
        })

    total_items = len(planning_brief.get('items', []))
    selected_count = len(planned_items)

    # Summary markdown: prefer LLM-generated batch summary
    summary_md = ''
    if llm_report and llm_report.get('batch_markdown'):
        summary_md = llm_report['batch_markdown']
    if not summary_md:
        summary_md = read_text(Path(auto_summary.get('batch_summary_v2_md', ''))) if auto_summary.get('batch_summary_v2_md') else ''

    # Parse validation
    parse_validation = read_json(job_dir / 'parse-validation.json')

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
        'parse_validation': parse_validation,
    }
    write_json(job_dir / 'dashboard.json', dashboard)
    return dashboard


# ---------------------------------------------------------------------------
# Job runner
# ---------------------------------------------------------------------------

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
        # --- Stage 1: Parse ---
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

        # --- Stage 1.5: LLM validation (non-blocking) ---
        validation_result = None
        try:
            from llm_interventions import validate_parsed_brief
            update_job(job_id, stage='AI 校验解析结果', progress=15)
            validation_result = validate_parsed_brief(job_dir)
        except Exception:
            traceback.print_exc()

        # --- Stage 1.6: Image analysis (non-blocking) ---
        try:
            from llm_interventions import analyze_brief_images
            update_job(job_id, stage='AI 分析企划参考图片', progress=20)
            analyze_brief_images(job_dir)
        except Exception:
            traceback.print_exc()

        preview = {
            'item_count': item_count,
            'preview_items': [
                {
                    'theme': x.get('theme', ''),
                    'price_band_raw': x.get('price_band_raw', ''),
                    'brief_summary': x.get('brief_summary', '')
                }
                for x in brief.get('items', [])[:5]
            ],
            'validation': validation_result,
        }
        update_job(job_id, status='running', stage='企划解析完成，开始寻源', progress=25, preview=preview)

        # --- Stage 2: Batch workflow ---
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
        print(f'[job:{job_id}] batch workflow starting', file=sys.stderr)
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=str(WORKSPACE),
            env=env,
        )
        if proc.stderr:
            for line in proc.stderr.splitlines():
                print(f'[job:{job_id}] {line}', file=sys.stderr)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or 'Workflow failed')
        out_path = (proc.stdout or '').strip().splitlines()[-1].strip()
        if not out_path:
            raise RuntimeError('Workflow finished but did not return summary path')
        auto_summary = read_json(Path(out_path))
        if not auto_summary:
            raise RuntimeError('Failed to load workflow summary: {}'.format(out_path))
        shutil.copyfile(str(Path(out_path)), str(job_dir / 'auto-batch-summary.json'))

        # --- Stage 3: LLM enrichment (non-blocking) ---
        llm_report = None
        try:
            from llm_interventions import enrich_with_llm
            update_job(job_id, stage='AI 分析供应商数据', progress=75)

            def _progress_cb(stage_text):
                update_job(job_id, stage=stage_text)

            llm_report = enrich_with_llm(job_dir, auto_summary, progress_callback=_progress_cb)
        except Exception:
            traceback.print_exc()

        # --- Stage 4: Build dashboard ---
        update_job(job_id, stage='正在生成视觉化结果页', progress=90)
        dashboard = build_dashboard(job_dir, auto_summary, llm_report=llm_report)
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


# ---------------------------------------------------------------------------
# HTTP Server
# ---------------------------------------------------------------------------

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class AppHandler(BaseHTTPRequestHandler):
    server_version = 'SourcingWeb/0.2'

    def log_message(self, format, *args):
        sys.stderr.write('[%s] %s\n' % (time.strftime('%H:%M:%S'), format % args))

    def _send_json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(payload)

    def _send_text(self, text, status=200, content_type='text/plain; charset=utf-8'):
        payload = text.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length) if length > 0 else b''

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
            '.webp': 'image/webp',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }.get(suffix, 'application/octet-stream')
        data = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        if suffix == '.html':
            self.send_header('Cache-Control', 'no-store')
        else:
            self.send_header('Cache-Control', 'public, max-age=31536000, immutable')
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/health':
            llm_healthy = False
            try:
                from llm_client import is_healthy
                llm_healthy = ENABLE_LLM and bool(LLM_API_KEY) and is_healthy()
            except Exception:
                pass
            return self._send_json({
                'ok': True,
                'cookie_exists': COOKIE_PATH.exists(),
                'llm_enabled': ENABLE_LLM,
                'llm_healthy': llm_healthy,
            })

        if path == '/api/cookie/status':
            info = {'exists': False, 'updated_at': None, 'length': 0}
            if COOKIE_PATH.exists():
                try:
                    content = COOKIE_PATH.read_text(encoding='utf-8').strip()
                    if content:
                        stat = COOKIE_PATH.stat()
                        info['exists'] = True
                        info['updated_at'] = int(stat.st_mtime)
                        info['length'] = len(content)
                except Exception:
                    pass
            return self._send_json(info)

        if path == '/api/template-spec':
            return self._send_json({
                'accepted_extensions': ['.xlsx'],
                'requirements': [
                    '请上传固定企划模板（Excel .xlsx）',
                    '系统会先校验是否能解析出 item/theme/price/fabrics/elements',
                    '如果没有解析出任何 item，会直接提示模板不符合要求',
                ]
            })

        if path == '/api/jobs':
            jobs_list = []
            with JOBS_LOCK:
                for jid, job in sorted(JOBS.items(), key=lambda x: x[1].get('created_at', 0), reverse=True):
                    jobs_list.append({
                        'job_id': jid,
                        'status': job.get('status', ''),
                        'stage': job.get('stage', ''),
                        'progress': job.get('progress', 0),
                        'created_at': job.get('created_at'),
                        'original_filename': job.get('original_filename', ''),
                    })
            return self._send_json({'jobs': jobs_list[:50]})

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

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/cookie':
            try:
                if COOKIE_PATH.exists():
                    COOKIE_PATH.unlink()
                return self._send_json({'ok': True})
            except Exception as e:
                return self._send_json({'error': str(e)}, 500)

        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/cookie':
            try:
                body = self._read_body()
                data = json.loads(body.decode('utf-8'))
                cookie_str = (data.get('cookie') or '').strip()
                if not cookie_str:
                    return self._send_json({'error': 'cookie 不能为空'}, 400)
                COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
                with io.open(str(COOKIE_PATH), 'w', encoding='utf-8') as f:
                    f.write(cookie_str)
                return self._send_json({'ok': True, 'length': len(cookie_str)})
            except Exception as e:
                return self._send_json({'error': str(e)}, 400)

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

            # Cookie: prefer form-submitted value, fallback to server file
            cookie_value = (form.getfirst('cookie_value', '') or '').strip()
            if cookie_value:
                probe_str = cookie_value
            elif COOKIE_PATH.exists():
                probe_str = COOKIE_PATH.read_text(encoding='utf-8').strip()
            else:
                return self._send_json({'error': '1688 Cookie 未填写，请在页面上配置 Cookie'}, 400)

            # 探针验证 cookie，失败直接拒绝，不创建 job
            ok, ret = probe_1688_cookie(probe_str)
            if not ok:
                return self._send_json({
                    'error': 'Cookie 已失效，1688 验证不通过，请重新获取',
                    'detail': ret,
                }, 422)

            job_id = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
            job_dir = RUNS_DIR / job_id
            job_dir.mkdir(parents=True, exist_ok=True)

            if cookie_value:
                cookie_file = job_dir / 'cookie.txt'
                with io.open(str(cookie_file), 'w', encoding='utf-8') as f:
                    f.write(cookie_value)
                cookie_path = str(cookie_file)
                print(f'[cookie] source=form length={len(cookie_value)} path={cookie_path}', file=sys.stderr)
            else:
                cookie_path = str(COOKIE_PATH)
                cookie_len = COOKIE_PATH.stat().st_size
                print(f'[cookie] source=server_file length={cookie_len} path={cookie_path}', file=sys.stderr)

            xlsx_path = job_dir / filename
            with io.open(str(xlsx_path), 'wb') as f:
                f.write(upload.file.read())

            try:
                max_items = max(1, min(20, int(form.getfirst('max_items', '5'))))
                queries = max(1, min(5, int(form.getfirst('queries', '2'))))
                pages = max(1, min(3, int(form.getfirst('pages', '1'))))
                top_k = max(1, min(20, int(form.getfirst('top_k', '10'))))
            except (ValueError, TypeError):
                return self._send_json({'error': '参数格式错误'}, 400)

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
    _load_persisted_jobs()
    httpd = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print('Sourcing web app running at http://{}:{}/'.format(HOST, PORT))
    print('LLM enabled: {}'.format(ENABLE_LLM))
    print('Cookie path: {}'.format(COOKIE_PATH))
    httpd.serve_forever()


if __name__ == '__main__':
    main()
