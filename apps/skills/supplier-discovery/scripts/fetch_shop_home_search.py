#!/usr/bin/env python3
import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path


def read_cookie(path: Path) -> str:
    text = path.read_text(encoding='utf-8').strip()
    if text.startswith('{'):
        text = json.loads(text).get('cookie', '').strip()
    return text


def main():
    ap = argparse.ArgumentParser(description='Fetch 1688 shop homepage HTML for shop expansion.')
    ap.add_argument('--shop-url', required=True)
    ap.add_argument('--cookie-file')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    url = args.shop_url
    if url.startswith('http://'):
        url = 'https://' + url[len('http://'):]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    if args.cookie_file:
        headers['Cookie'] = read_cookie(Path(args.cookie_file))

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode('utf-8', errors='replace')
        final_url = resp.geturl()
        status = getattr(resp, 'status', 200)

    out = {'shop_url': url, 'final_url': final_url, 'http_status': status, 'html': body}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(out_path))


if __name__ == '__main__':
    main()
