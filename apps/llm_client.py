#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal OpenAI-compatible LLM client using only Python stdlib.
Includes simple circuit breaker: after 3 consecutive failures,
disable LLM calls for 5 minutes.
"""
import json
import time
import urllib.request
import urllib.error

from config import LLM_API_KEY, LLM_API_BASE, LLM_MODEL

_TIMEOUT = 60
_MAX_RETRIES = 3

# Circuit breaker state
_fail_count = 0
_circuit_open_until = 0
_CIRCUIT_THRESHOLD = 3
_CIRCUIT_COOLDOWN = 300  # seconds


def is_healthy():
    """Return True if the LLM client is not in circuit-open state."""
    if _circuit_open_until and time.time() < _circuit_open_until:
        return False
    return True


def _record_success():
    global _fail_count, _circuit_open_until
    _fail_count = 0
    _circuit_open_until = 0


def _record_failure():
    global _fail_count, _circuit_open_until
    _fail_count += 1
    if _fail_count >= _CIRCUIT_THRESHOLD:
        _circuit_open_until = time.time() + _CIRCUIT_COOLDOWN


def chat_completion(messages, model=None, temperature=0.3, max_tokens=2048):
    """Send a chat completion request. Returns the content string."""
    if not is_healthy():
        raise RuntimeError('LLM circuit breaker open, skipping call (will retry after cooldown)')

    model = model or LLM_MODEL
    url = LLM_API_BASE.rstrip('/') + '/chat/completions'
    payload = json.dumps({
        'model': model,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }, ensure_ascii=False).encode('utf-8')

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + LLM_API_KEY,
    }

    last_err = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                body = json.loads(resp.read().decode('utf-8'))
            _record_success()
            return body['choices'][0]['message']['content']
        except urllib.error.HTTPError as e:
            last_err = e
            if 400 <= e.code < 500:
                # Client errors (bad request, auth, rate limit) — don't retry
                _record_failure()
                raise RuntimeError('LLM HTTP {}: {}'.format(e.code, e.reason))
        except Exception as e:
            last_err = e
            if attempt < _MAX_RETRIES:
                time.sleep(min(2 ** attempt, 8))

    _record_failure()
    raise RuntimeError('LLM request failed after {} retries: {}'.format(_MAX_RETRIES, last_err))


def chat_completion_json(messages, model=None, temperature=0.1, max_tokens=2048):
    """Send a chat completion request and parse the response as JSON dict."""
    content = chat_completion(messages, model=model, temperature=temperature, max_tokens=max_tokens)
    # Strip markdown code fence if present
    text = content.strip()
    if text.startswith('```'):
        first_nl = text.index('\n') if '\n' in text else 3
        text = text[first_nl + 1:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# Vision API (智谱 GLM-4.6V)
# ---------------------------------------------------------------------------

def vision_completion(messages, model=None, temperature=0.3, max_tokens=2048):
    """Send a vision chat completion to 智谱 API. Returns content string.
    Messages should contain image_url entries with data:image/... base64 URLs.
    """
    from config import VISION_API_KEY, VISION_API_BASE, VISION_MODEL

    if not VISION_API_KEY:
        raise RuntimeError('VISION_API_KEY not configured')

    model = model or VISION_MODEL
    url = VISION_API_BASE.rstrip('/') + '/chat/completions'
    payload = json.dumps({
        'model': model,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }, ensure_ascii=False).encode('utf-8')

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + VISION_API_KEY,
    }

    last_err = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                body = json.loads(resp.read().decode('utf-8'))
            return body['choices'][0]['message']['content']
        except urllib.error.HTTPError as e:
            last_err = e
            if 400 <= e.code < 500:
                raise RuntimeError('Vision HTTP {}: {}'.format(e.code, e.reason))
        except Exception as e:
            last_err = e
            if attempt < _MAX_RETRIES:
                time.sleep(min(2 ** attempt, 8))

    raise RuntimeError('Vision request failed after {} retries: {}'.format(_MAX_RETRIES, last_err))


def vision_completion_json(messages, model=None, temperature=0.1, max_tokens=2048):
    """Send a vision completion and parse response as JSON dict."""
    content = vision_completion(messages, model=model, temperature=temperature, max_tokens=max_tokens)
    text = content.strip()
    if text.startswith('```'):
        first_nl = text.index('\n') if '\n' in text else 3
        text = text[first_nl + 1:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)
