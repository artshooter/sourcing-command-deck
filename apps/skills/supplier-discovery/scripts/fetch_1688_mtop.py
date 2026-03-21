#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

APP_KEY = '12574478'
API = 'mtop.relationrecommend.WirelessRecommend.recommend'


def read_cookie(cookie_path: Path) -> str:
    text = cookie_path.read_text(encoding='utf-8').strip()
    if text.startswith('{'):
        text = json.loads(text).get('cookie', '').strip()
    return text


def extract_m_h5_token(cookie: str) -> str:
    m = re.search(r'_m_h5_tk=([^_;]+)_', cookie)
    if not m:
        m = re.search(r'_m_h5_tk=([^;]+)', cookie)
    if not m:
        raise ValueError('Could not find _m_h5_tk in cookie')
    return m.group(1)


def sign(token: str, ts: str, data: str) -> str:
    raw = f'{token}&{ts}&{APP_KEY}&{data}'
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def call_1688(query: str, cookie: str, begin_page: int, page_size: int):
    token = extract_m_h5_token(cookie)
    ts = str(int(time.time() * 1000))
    params_obj = {
        'beginPage': begin_page,
        'pageSize': page_size,
        'method': 'getOfferList',
        'pageId': f'page_{ts}',
        'keywords': query,
        'verticalProductFlag': 'pcmarket',
        'searchScene': 'pcOfferSearch',
        'charset': 'GBK',
    }
    data_obj = {'appId': 32517, 'params': json.dumps(params_obj, ensure_ascii=False)}
    data = json.dumps(data_obj, ensure_ascii=False, separators=(',', ':'))
    qs = urllib.parse.urlencode({
        'jsv': '2.7.2',
        'appKey': APP_KEY,
        't': ts,
        'sign': sign(token, ts, data),
        'api': API,
        'v': '2.0',
        'type': 'originaljson',
        'dataType': 'json',
        'timeout': '20000',
        'ecode': '0',
        'valueType': 'original',
        'data': data,
    })
    url = f'https://h5api.m.1688.com/h5/{API.lower()}/2.0/?{qs}'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json,text/plain,*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Cookie': cookie,
        'Referer': 'https://s.1688.com/selloffer/offer_search.htm?keywords=' + urllib.parse.quote(query),
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8', errors='replace'))


def main():
    ap = argparse.ArgumentParser(description='Fetch 1688 offer list via mtop using cookie session.')
    ap.add_argument('--query', required=True)
    ap.add_argument('--cookie-file', required=True)
    ap.add_argument('--begin-page', type=int, default=1)
    ap.add_argument('--page-size', type=int, default=60)
    ap.add_argument('--retries', type=int, default=3)
    ap.add_argument('--cache-dir')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    cache_path = None
    if args.cache_dir:
        cache_dir = Path(args.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        qhash = hashlib.md5((args.query + '|' + str(args.begin_page) + '|' + str(args.page_size)).encode('utf-8')).hexdigest()
        cache_path = cache_dir / f'{qhash}.json'

    cookie = read_cookie(Path(args.cookie_file))
    last_err = None
    obj = None
    for attempt in range(1, args.retries + 1):
        try:
            obj = call_1688(args.query, cookie, args.begin_page, args.page_size)
            # successful-looking payload: refresh cache
            try:
                offer = obj.get('data', {}).get('data', {}).get('OFFER', {})
                if cache_path and offer.get('items'):
                    cache_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
                    break
                else:
                    # got a response but not a usable offer list; keep trying / allow cache fallback
                    obj = None
            except Exception:
                obj = None
            if obj is not None:
                break
        except Exception as e:
            last_err = str(e)
            time.sleep(min(2 * attempt, 6))

    if obj is None and cache_path and cache_path.exists():
        obj = json.loads(cache_path.read_text(encoding='utf-8'))
        obj['_from_cache'] = True

    if obj is None:
        obj = {
            'ret': ['LOCAL_FETCH_ERROR'],
            'error': last_err or 'unknown',
            'query': args.query,
            'begin_page': args.begin_page,
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out))


if __name__ == '__main__':
    main()
