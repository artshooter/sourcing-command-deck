#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def is_valid(obj):
    try:
        offer = obj['data']['data']['OFFER']
        items = offer.get('items') or []
        found = offer.get('found', 0)
        return len(items) > 0 and found >= 0
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description='Validate whether a 1688 mtop response contains usable offer items.')
    ap.add_argument('mtop_json')
    args = ap.parse_args()

    obj = json.loads(Path(args.mtop_json).read_text(encoding='utf-8'))
    print('valid' if is_valid(obj) else 'invalid')


if __name__ == '__main__':
    main()
