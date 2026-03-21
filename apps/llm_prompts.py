#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompt templates for each AI intervention point.
Each function returns a list of messages (OpenAI chat format).
"""
import json


def prompt_image_analysis(brief_item, base64_images):
    """Intervention 2: Analyze reference images for one brief item.
    base64_images: list of {'data_url': 'data:image/png;base64,...', 'cell_ref': 'H3'}
    """
    brief_text = json.dumps({
        'theme': brief_item.get('theme', ''),
        'market': brief_item.get('market', ''),
        'category': brief_item.get('category_l3') or brief_item.get('category_l2', ''),
        'fabrics': brief_item.get('fabrics', []),
        'elements': brief_item.get('elements', []),
        'notes': (brief_item.get('notes', '') or '')[:200],
    }, ensure_ascii=False, indent=2)

    content_parts = [
        {
            'type': 'text',
            'text': (
                '你是一个服装企划视觉分析专家。以下是一个企划款的文字描述和参考图片。\n\n'
                '企划款信息：\n{}\n\n'
                '请分析这些参考图片，提取以下视觉标签：\n'
                '- garment_type_tags（服装类型：连衣裙、衬衫裙、长裙等）\n'
                '- silhouette_tags（廓形：收腰、A摆、直筒、及踝等）\n'
                '- neckline_tags（领型：方领、V领、圆领、一字肩等）\n'
                '- sleeve_tags（袖型：泡泡袖、喇叭袖、长袖、无袖等）\n'
                '- length_tags（长度：短款、中长、及踝等）\n'
                '- fabric_visual_tags（面料视觉感：轻透、雪纺感、网纱感、针织感等）\n'
                '- pattern_tags（图案：晕染印花、小碎花、条纹、格子等）\n'
                '- detail_tags（细节：系带、荷叶边、立体花、拼接等）\n'
                '- mood_tags（风格氛围：浪漫、度假、轻礼服、复古等）\n\n'
                '同时判断图片与文字描述是否有冲突。\n\n'
                '请返回严格 JSON 格式：\n'
                '{{\n'
                '  "image_summary": "1-2句视觉方向总结",\n'
                '  "garment_type_tags": [],\n'
                '  "silhouette_tags": [],\n'
                '  "neckline_tags": [],\n'
                '  "sleeve_tags": [],\n'
                '  "length_tags": [],\n'
                '  "fabric_visual_tags": [],\n'
                '  "pattern_tags": [],\n'
                '  "detail_tags": [],\n'
                '  "mood_tags": [],\n'
                '  "image_consensus_tags": ["多张图共识的标签"],\n'
                '  "image_conflict_tags": ["与文字描述冲突的标签"],\n'
                '  "confidence": "high|medium|low"\n'
                '}}'
            ).format(brief_text)
        }
    ]

    # Add images (max 4 to control token cost)
    for img in base64_images[:4]:
        content_parts.append({
            'type': 'image_url',
            'image_url': {'url': img['data_url']}
        })

    return [{'role': 'user', 'content': content_parts}]


def prompt_validate_brief(items):
    """Intervention 1: Validate parsed planning brief items."""
    items_text = json.dumps(items, ensure_ascii=False, indent=2)
    return [
        {
            'role': 'system',
            'content': (
                '你是一个服装企划解析质检专家。你会收到从 Excel 企划表中解析出的结构化企划款数据，'
                '需要逐条检查解析结果是否合理。\n\n'
                '重点检查：\n'
                '1. theme（企划款主题）是否是真正的商品主题，而不是数量字段（如"1月：10"）、日期、列名等噪音数据\n'
                '2. price_min/price_max 价格带是否合理（服装正常范围大约 10-500 RMB）\n'
                '3. fabrics（面料）和 elements（元素）是否是真正的面料/工艺词，而不是其他字段串进来的\n'
                '4. 是否有明显的字段错位或异常模式\n\n'
                '请用中文回答，返回严格 JSON 格式。'
            )
        },
        {
            'role': 'user',
            'content': (
                '以下是从企划表解析出的企划款列表：\n\n'
                '{}\n\n'
                '请逐条检查并返回 JSON：\n'
                '{{\n'
                '  "validations": [\n'
                '    {{\n'
                '      "item_index": 1,\n'
                '      "status": "ok 或 warning 或 error",\n'
                '      "issues": ["问题描述"],\n'
                '      "suggested_fix": "建议修正（如有）"\n'
                '    }}\n'
                '  ],\n'
                '  "overall_quality": "good 或 needs_review 或 poor",\n'
                '  "summary": "一句话总结"\n'
                '}}'
            ).format(items_text)
        }
    ]


def prompt_fit_guess(brief_item, candidates):
    """Intervention 3: Style/market fit guess for a batch of candidates."""
    brief_text = json.dumps({
        'theme': brief_item.get('theme', ''),
        'market': brief_item.get('market', ''),
        'category': brief_item.get('category_l3') or brief_item.get('category_l2', ''),
        'price_band': brief_item.get('price_band_raw', ''),
        'fabrics': brief_item.get('fabrics', []),
        'elements': brief_item.get('elements', []),
        'style_tags': brief_item.get('style_tags', []),
        'notes': brief_item.get('notes', ''),
    }, ensure_ascii=False, indent=2)

    candidates_text = json.dumps([
        {
            'index': i,
            'product_title': c.get('product_title', ''),
            'supplier_name': c.get('supplier_name', ''),
            'price': c.get('price_fit_guess', ''),
            'score_total': c.get('score_total'),
            'recommendation_level': c.get('recommendation_level', ''),
            'recommend_reasons': c.get('recommend_reasons', [])[:3],
        }
        for i, c in enumerate(candidates)
    ], ensure_ascii=False, indent=2)

    return [
        {
            'role': 'system',
            'content': (
                '你是一个服装寻源专家。给定一个企划款的需求描述和一批候选供应商商品，'
                '判断每个候选的风格匹配度和市场匹配度。\n\n'
                '匹配度分为四级：高度匹配、部分匹配、勉强匹配、不匹配。\n'
                '请用中文回答，返回严格 JSON 格式。'
            )
        },
        {
            'role': 'user',
            'content': (
                '企划款需求：\n{}\n\n'
                '候选供应商商品列表：\n{}\n\n'
                '请对每个候选返回 JSON：\n'
                '{{\n'
                '  "results": [\n'
                '    {{\n'
                '      "index": 0,\n'
                '      "style_fit": "高度匹配|部分匹配|勉强匹配|不匹配",\n'
                '      "style_reason": "简要理由",\n'
                '      "market_fit": "高度匹配|部分匹配|勉强匹配|不匹配",\n'
                '      "market_reason": "简要理由"\n'
                '    }}\n'
                '  ]\n'
                '}}'
            ).format(brief_text, candidates_text)
        }
    ]


def prompt_shop_profile(suppliers):
    """Intervention 4: Deep shop profiling for a batch of suppliers."""
    suppliers_text = json.dumps([
        {
            'index': i,
            'supplier_name': s.get('supplier_name', ''),
            'product_title': s.get('product_title', ''),
            'price': s.get('price_fit_guess', ''),
            'score_total': s.get('score_total'),
            'recommendation_level': s.get('recommendation_level', ''),
            'shop_url': s.get('shop_url', ''),
            'supplier_profile_summary': s.get('supplier_profile_summary', ''),
            'recommend_reasons': s.get('recommend_reasons', [])[:3],
            'risk_warnings': s.get('risk_warnings', [])[:3],
        }
        for i, s in enumerate(suppliers)
    ], ensure_ascii=False, indent=2)

    return [
        {
            'role': 'system',
            'content': (
                '你是一个供应商分析专家。根据供应商的商品信息、评分数据和已有画像，'
                '为每个供应商写一段 2-3 句的深度画像总结。\n\n'
                '画像应涵盖：供应商类型（工厂/贸易商/品牌商）、产品聚焦度、可信度信号、主要风险。\n'
                '请用中文回答，返回严格 JSON 格式。'
            )
        },
        {
            'role': 'user',
            'content': (
                '以下是候选供应商列表：\n{}\n\n'
                '请为每个供应商返回 JSON：\n'
                '{{\n'
                '  "profiles": [\n'
                '    {{\n'
                '      "index": 0,\n'
                '      "profile_summary": "2-3句画像总结",\n'
                '      "business_type": "工厂|贸易商|品牌商|综合",\n'
                '      "confidence": "high|medium|low"\n'
                '    }}\n'
                '  ]\n'
                '}}'
            ).format(suppliers_text)
        }
    ]


def prompt_item_summary(brief_item, result_card):
    """Intervention 5a: Per-item sourcing summary."""
    context = json.dumps({
        'theme': brief_item.get('theme', ''),
        'market': brief_item.get('market', ''),
        'category': brief_item.get('category_l3', ''),
        'price_band': brief_item.get('price_band_raw', ''),
        'quality': result_card.get('quality', ''),
        'a_count': result_card.get('a_count', 0),
        'b_count': result_card.get('b_count', 0),
        'c_count': result_card.get('c_count', 0),
        'top_count': result_card.get('top_count', 0),
        'second_pass_used': result_card.get('second_pass_used', False),
    }, ensure_ascii=False, indent=2)

    return [
        {
            'role': 'system',
            'content': (
                '你是一个服装寻源顾问，负责为买手团队写简洁的寻源状态总结。\n'
                '要求：一句话总结当前企划款的寻源状态，一句话给出建议动作。\n'
                '风格：简洁、务实、可操作。请用中文回答，返回严格 JSON 格式。'
            )
        },
        {
            'role': 'user',
            'content': (
                '企划款寻源结果：\n{}\n\n'
                '请返回 JSON：\n'
                '{{\n'
                '  "ai_summary": "一句话寻源状态",\n'
                '  "recommended_action": "一句话建议动作"\n'
                '}}'
            ).format(context)
        }
    ]


def prompt_supplier_judgement(brief_item, supplier):
    """Intervention 5b: Per-supplier AI judgement (batched in prompt_supplier_judgements)."""
    # Used internally by prompt_supplier_judgements
    pass


def prompt_supplier_judgements(brief_item, suppliers):
    """Intervention 5b: Batch supplier judgements for one item."""
    brief_text = json.dumps({
        'theme': brief_item.get('theme', ''),
        'market': brief_item.get('market', ''),
        'price_band': brief_item.get('price_band_raw', ''),
        'fabrics': brief_item.get('fabrics', []),
        'elements': brief_item.get('elements', []),
    }, ensure_ascii=False, indent=2)

    suppliers_text = json.dumps([
        {
            'index': i,
            'supplier_name': s.get('supplier_name', ''),
            'product_title': s.get('product_title', ''),
            'recommendation_level': s.get('recommendation_level', ''),
            'score_total': s.get('score_total'),
            'recommend_reasons': s.get('recommend_reasons', [])[:3],
            'risk_warnings': s.get('risk_warnings', [])[:3],
        }
        for i, s in enumerate(suppliers)
    ], ensure_ascii=False, indent=2)

    return [
        {
            'role': 'system',
            'content': (
                '你是一个服装寻源顾问。为每个候选供应商写一句简洁的 AI 判断，'
                '说明该供应商相对于企划款需求的匹配情况和建议动作。\n'
                '请用中文回答，返回严格 JSON 格式。'
            )
        },
        {
            'role': 'user',
            'content': (
                '企划款：\n{}\n\n'
                '候选供应商：\n{}\n\n'
                '请返回 JSON：\n'
                '{{\n'
                '  "judgements": [\n'
                '    {{\n'
                '      "index": 0,\n'
                '      "ai_judgement": "一句话判断"\n'
                '    }}\n'
                '  ]\n'
                '}}'
            ).format(brief_text, suppliers_text)
        }
    ]


def prompt_batch_summary(overview, item_highlights):
    """Intervention 5c: Executive batch summary in markdown."""
    context = json.dumps({
        'overview': overview,
        'item_highlights': item_highlights,
    }, ensure_ascii=False, indent=2)

    return [
        {
            'role': 'system',
            'content': (
                '你是一个服装寻源项目经理，负责为买手团队写批量寻源的执行摘要。\n'
                '要求：3-5 段 markdown，涵盖整体成果、可推进的款、需要关注的款、建议下一步。\n'
                '风格：表格优先，简洁务实，不要冗长结论。请用中文回答。'
            )
        },
        {
            'role': 'user',
            'content': (
                '批量寻源结果数据：\n{}\n\n'
                '请直接返回 markdown 文本（不要包裹在 JSON 或代码块中）。'
            ).format(context)
        }
    ]
