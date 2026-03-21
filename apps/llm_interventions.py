#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM intervention orchestrator.
Each function reads pipeline JSON, calls LLM, writes enriched results.
All failures are caught — pipeline continues with rule-engine defaults.
"""
import base64
import io
import json
import traceback
from pathlib import Path

from config import ENABLE_LLM, LLM_API_KEY, VISION_API_KEY
from llm_client import chat_completion, chat_completion_json, vision_completion_json
from llm_prompts import (
    prompt_validate_brief,
    prompt_image_analysis,
    prompt_fit_guess,
    prompt_shop_profile,
    prompt_item_summary,
    prompt_supplier_judgements,
    prompt_batch_summary,
)


def _read_json(path):
    with io.open(str(path), 'r', encoding='utf-8') as f:
        return json.load(f)


def _write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with io.open(str(path), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _llm_available():
    return ENABLE_LLM and bool(LLM_API_KEY)


# ---------------------------------------------------------------------------
# Intervention 1: Post-parse validation
# ---------------------------------------------------------------------------

def validate_parsed_brief(job_dir):
    """Check parsed brief items for quality issues. Returns validation dict or None."""
    if not _llm_available():
        return None
    try:
        brief_path = job_dir / 'planning-brief.json'
        if not brief_path.exists():
            return None
        brief = _read_json(brief_path)
        items = brief.get('items', [])
        if not items:
            return None

        # Send only key fields to reduce token usage
        slim_items = []
        for i, item in enumerate(items, 1):
            slim_items.append({
                'item_index': i,
                'theme': item.get('theme', ''),
                'market': item.get('market', ''),
                'category_l3': item.get('category_l3', ''),
                'price_band_raw': item.get('price_band_raw', ''),
                'price_min': item.get('price_min'),
                'price_max': item.get('price_max'),
                'fabrics': item.get('fabrics', [])[:5],
                'elements': item.get('elements', [])[:5],
                'notes': (item.get('notes', '') or '')[:200],
            })

        messages = prompt_validate_brief(slim_items)
        result = chat_completion_json(messages)
        _write_json(job_dir / 'parse-validation.json', result)
        return result
    except Exception:
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Intervention 2: Image visual tagging (智谱 GLM-4.6V)
# ---------------------------------------------------------------------------

def _image_to_base64_data_url(image_path):
    """Read an image file and return a data:image/... base64 URL."""
    p = Path(image_path)
    if not p.exists():
        return None
    suffix = p.suffix.lower()
    mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.webp': 'image/webp', '.gif': 'image/gif'}.get(suffix, 'image/png')
    raw = p.read_bytes()
    b64 = base64.b64encode(raw).decode('ascii')
    return 'data:{};base64,{}'.format(mime, b64)


def analyze_brief_images(job_dir):
    """Analyze reference images for each brief item using vision model.
    Reads image paths from planning-brief.json, calls vision API, writes results.
    """
    if not VISION_API_KEY:
        return None
    try:
        brief_path = job_dir / 'planning-brief.json'
        if not brief_path.exists():
            return None
        brief = _read_json(brief_path)
        items = brief.get('items', [])
        if not items:
            return None

        results = []
        for i, item in enumerate(items):
            # Collect image paths from anchored_images
            anchored = item.get('anchored_images', [])
            if not anchored:
                results.append({'item_index': i + 1, 'status': 'no_images'})
                continue

            base64_images = []
            for img_info in anchored[:4]:
                img_path = img_info.get('path', '')
                if not img_path:
                    continue
                data_url = _image_to_base64_data_url(img_path)
                if data_url:
                    base64_images.append({
                        'data_url': data_url,
                        'cell_ref': img_info.get('cell_ref', ''),
                    })

            if not base64_images:
                results.append({'item_index': i + 1, 'status': 'images_not_found'})
                continue

            try:
                messages = prompt_image_analysis(item, base64_images)
                resp = vision_completion_json(messages)
                resp['item_index'] = i + 1
                resp['status'] = 'analyzed'
                results.append(resp)

                # Merge visual tags back into the brief item
                for key in ['garment_type_tags', 'silhouette_tags', 'neckline_tags',
                            'sleeve_tags', 'length_tags', 'fabric_visual_tags',
                            'pattern_tags', 'detail_tags', 'mood_tags',
                            'image_consensus_tags', 'image_conflict_tags', 'image_summary']:
                    if key in resp:
                        item[key] = resp[key]
                item['image_analysis_status'] = 'analyzed'
            except Exception:
                traceback.print_exc()
                results.append({'item_index': i + 1, 'status': 'error'})

        # Write enriched brief back
        _write_json(brief_path, brief)
        # Write image analysis results
        _write_json(job_dir / 'image-analysis.json', {'results': results})
        return results
    except Exception:
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Intervention 3: Fit guess enrichment
# ---------------------------------------------------------------------------

def enrich_fit_guesses(job_dir, auto_summary):
    """Add style_fit and market_fit guesses to top suppliers via LLM."""
    if not _llm_available():
        return
    try:
        brief_path = job_dir / 'planning-brief.json'
        if not brief_path.exists():
            return
        brief = _read_json(brief_path)
        brief_items = brief.get('items', [])

        batch_summary_path = auto_summary.get('batch_summary_json', '')
        if not batch_summary_path:
            return
        batch_summary = _read_json(Path(batch_summary_path))

        for result in batch_summary.get('batch_results', []):
            item_index = result.get('item_index')
            if item_index is None or item_index < 1:
                continue
            brief_item = brief_items[item_index - 1] if item_index <= len(brief_items) else {}

            top_json_path = result.get('top_json')
            if not top_json_path or not Path(top_json_path).exists():
                continue
            top_data = _read_json(Path(top_json_path))
            suppliers = top_data.get('top_suppliers', [])
            if not suppliers:
                continue

            # Batch: up to 10 at a time
            for batch_start in range(0, len(suppliers), 10):
                batch = suppliers[batch_start:batch_start + 10]
                try:
                    messages = prompt_fit_guess(brief_item, batch)
                    resp = chat_completion_json(messages)
                    for r in resp.get('results', []):
                        idx = r.get('index')
                        if idx is not None and 0 <= idx < len(batch):
                            batch[idx]['style_fit_guess'] = r.get('style_fit', '')
                            batch[idx]['style_fit_reason'] = r.get('style_reason', '')
                            batch[idx]['market_fit_guess'] = r.get('market_fit', '')
                            batch[idx]['market_fit_reason'] = r.get('market_reason', '')
                except Exception:
                    traceback.print_exc()

            # Write back
            _write_json(Path(top_json_path), top_data)
    except Exception:
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Intervention 4: Deep shop profiling
# ---------------------------------------------------------------------------

def enrich_shop_profiles(job_dir, auto_summary):
    """Generate richer profile summaries for top suppliers via LLM."""
    if not _llm_available():
        return
    try:
        batch_summary_path = auto_summary.get('batch_summary_json', '')
        if not batch_summary_path:
            return
        batch_summary = _read_json(Path(batch_summary_path))

        for result in batch_summary.get('batch_results', []):
            top_json_path = result.get('top_json')
            if not top_json_path or not Path(top_json_path).exists():
                continue
            top_data = _read_json(Path(top_json_path))
            suppliers = top_data.get('top_suppliers', [])
            if not suppliers:
                continue

            # Batch: up to 10 at a time
            for batch_start in range(0, len(suppliers), 10):
                batch = suppliers[batch_start:batch_start + 10]
                try:
                    messages = prompt_shop_profile(batch)
                    resp = chat_completion_json(messages)
                    for p in resp.get('profiles', []):
                        idx = p.get('index')
                        if idx is not None and 0 <= idx < len(batch):
                            batch[idx]['llm_profile_summary'] = p.get('profile_summary', '')
                            batch[idx]['llm_business_type'] = p.get('business_type', '')
                except Exception:
                    traceback.print_exc()

            _write_json(Path(top_json_path), top_data)
    except Exception:
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Intervention 5: Report generation
# ---------------------------------------------------------------------------

def generate_report_data(job_dir, auto_summary):
    """Generate AI summaries for items, suppliers, and batch overview.

    Returns a dict:
      {
        'item_summaries': {item_index: {'ai_summary': ..., 'recommended_action': ...}},
        'supplier_judgements': {item_index: [{'supplier_name': ..., 'ai_judgement': ...}]},
        'batch_markdown': '...',
      }
    or None if LLM unavailable.
    """
    if not _llm_available():
        return None
    try:
        brief_path = job_dir / 'planning-brief.json'
        if not brief_path.exists():
            return None
        brief = _read_json(brief_path)
        brief_items = brief.get('items', [])

        batch_summary_path = auto_summary.get('batch_summary_json', '')
        if not batch_summary_path:
            return None
        batch_summary = _read_json(Path(batch_summary_path))

        item_summaries = {}
        supplier_judgements = {}
        item_highlights = []

        for result in batch_summary.get('batch_results', []):
            item_index = result.get('item_index')
            if item_index is None or item_index < 1:
                continue
            brief_item = brief_items[item_index - 1] if item_index <= len(brief_items) else {}

            top_json_path = result.get('top_json')
            top_data = _read_json(Path(top_json_path)) if top_json_path and Path(top_json_path).exists() else {}
            suppliers = top_data.get('top_suppliers', [])

            top_count = result.get('top_count', 0) or 0
            quality = 'strong' if top_count >= 3 else ('weak' if top_count > 0 else 'empty')

            # Per-item result card for prompt
            result_card = {
                'quality': quality,
                'a_count': sum(1 for s in suppliers if s.get('recommendation_level') == 'A'),
                'b_count': sum(1 for s in suppliers if s.get('recommendation_level') == 'B'),
                'c_count': sum(1 for s in suppliers if s.get('recommendation_level') == 'C'),
                'top_count': top_count,
                'second_pass_used': bool(result.get('second_pass')),
            }

            # 5a: Item summary
            try:
                messages = prompt_item_summary(brief_item, result_card)
                resp = chat_completion_json(messages)
                item_summaries[item_index] = {
                    'ai_summary': resp.get('ai_summary', ''),
                    'recommended_action': resp.get('recommended_action', ''),
                }
            except Exception:
                traceback.print_exc()

            # 5b: Supplier judgements
            if suppliers:
                try:
                    messages = prompt_supplier_judgements(brief_item, suppliers[:10])
                    resp = chat_completion_json(messages)
                    judgement_list = []
                    for j in resp.get('judgements', []):
                        idx = j.get('index')
                        if idx is not None and 0 <= idx < len(suppliers):
                            suppliers[idx]['llm_ai_judgement'] = j.get('ai_judgement', '')
                            judgement_list.append({
                                'supplier_name': suppliers[idx].get('supplier_name', ''),
                                'ai_judgement': j.get('ai_judgement', ''),
                            })
                    supplier_judgements[item_index] = judgement_list
                    # Write back updated suppliers
                    if top_json_path:
                        _write_json(Path(top_json_path), top_data)
                except Exception:
                    traceback.print_exc()

            item_highlights.append({
                'item_index': item_index,
                'theme': brief_item.get('theme', ''),
                'quality': quality,
                'a_count': result_card['a_count'],
                'top_count': top_count,
            })

        # 5c: Batch executive summary
        batch_md = ''
        try:
            planned_items = auto_summary.get('selected_items', [])
            overview = {
                'total_items': len(brief_items),
                'selected_count': len(planned_items),
                'processed_count': len(batch_summary.get('batch_results', [])),
            }
            messages = prompt_batch_summary(overview, item_highlights)
            batch_md = chat_completion(messages)
        except Exception:
            traceback.print_exc()

        return {
            'item_summaries': item_summaries,
            'supplier_judgements': supplier_judgements,
            'batch_markdown': batch_md,
        }
    except Exception:
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def enrich_with_llm(job_dir, auto_summary, progress_callback=None):
    """Run all LLM enrichment steps. Returns report_data or None.
    Note: validate_parsed_brief is called separately in run_job before the batch workflow,
    not here, to avoid duplicate calls.
    """
    if not _llm_available():
        return None

    if progress_callback:
        progress_callback('LLM 评估供应商匹配度')
    enrich_fit_guesses(job_dir, auto_summary)

    if progress_callback:
        progress_callback('LLM 生成供应商画像')
    enrich_shop_profiles(job_dir, auto_summary)

    if progress_callback:
        progress_callback('LLM 生成业务报告')
    report_data = generate_report_data(job_dir, auto_summary)

    return report_data
