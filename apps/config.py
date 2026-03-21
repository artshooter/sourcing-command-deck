#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT

# --- Server ---
HOST = os.environ.get('SOURCING_WEB_HOST', '0.0.0.0')
PORT = int(os.environ.get('SOURCING_WEB_PORT', '8765'))

# --- Paths ---
STATIC_DIR = ROOT / 'static'
UPLOADS_DIR = ROOT / 'uploads'
RUNS_DIR = ROOT / 'runs'
SECRETS_DIR = ROOT / 'secrets'
COOKIE_PATH = Path(os.environ.get('COOKIE_PATH', str(SECRETS_DIR / '1688-cookie.txt')))

PARSE_SCRIPT = ROOT / 'skills' / 'planning-brief-parser' / 'scripts' / 'parse_planning_xlsx.py'
AUTO_BATCH_SCRIPT = ROOT / 'skills' / 'supplier-scoring' / 'scripts' / 'run_auto_batch_workflow.py'

# --- LLM ---
LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_API_BASE = os.environ.get('LLM_API_BASE', 'https://api.edgefn.net/v1')
LLM_MODEL = os.environ.get('LLM_MODEL', 'MiniMax-M2.5')
ENABLE_LLM = os.environ.get('ENABLE_LLM', 'true').lower() in ('true', '1', 'yes')

# --- Vision LLM (智谱 GLM-4.6V) ---
VISION_API_KEY = os.environ.get('VISION_API_KEY', '')
VISION_API_BASE = os.environ.get('VISION_API_BASE', 'https://open.bigmodel.cn/api/paas/v4')
VISION_MODEL = os.environ.get('VISION_MODEL', 'glm-4.6v')

# --- Init dirs ---
for p in [UPLOADS_DIR, RUNS_DIR, SECRETS_DIR]:
    p.mkdir(parents=True, exist_ok=True)
