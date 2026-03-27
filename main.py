from flask import Flask, request, render_template_string
from bs4 import BeautifulSoup
import statistics
import re
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

app = Flask(__name__)

OLLAMA_MODEL = "qwen2.5-coder:3b"
OLLAMA_URL = "http://localhost:11434/api/chat"

HTML = """
<!doctype html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <title>RAM Price Agent</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1240px;
            margin: 36px auto;
            padding: 0 20px;
            background: #f6f7fb;
            color: #111827;
        }
        h1 {
            margin-bottom: 6px;
            font-size: 32px;
        }
        h2 {
            margin-top: 0;
        }
        .muted {
            color: #6b7280;
            font-size: 14px;
        }
        .box {
            background: white;
            border-radius: 18px;
            padding: 22px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.07);
            margin-bottom: 20px;
        }
        form {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 130px;
            gap: 10px;
        }
        input, select, button {
            padding: 13px;
            border: 1px solid #d1d5db;
            border-radius: 12px;
            font-size: 15px;
        }
        button {
            background: #111827;
            color: white;
            cursor: pointer;
            border: none;
            font-weight: 600;
        }
        button:hover {
            background: #1f2937;
        }
        .ok {
            color: #065f46;
            font-weight: 700;
        }
        .error {
            color: #b91c1c;
            font-weight: 700;
        }
        .summary {
            white-space: pre-wrap;
            line-height: 1.65;
            background: #f9fafb;
            padding: 16px;
            border-radius: 14px;
            border: 1px solid #e5e7eb;
        }
        .debug {
            white-space: pre-wrap;
            background: #fff7ed;
            border: 1px solid #fdba74;
            padding: 14px;
            border-radius: 12px;
            font-size: 13px;
            color: #7c2d12;
        }
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 12px;
            background: #eef2ff;
            color: #3730a3;
            margin-left: 8px;
            vertical-align: middle;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-top: 12px;
        }
        .stat {
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 14px;
        }
        .stat-label {
            font-size: 13px;
            color: #6b7280;
            margin-bottom: 6px;
        }
        .stat-value {
            font-size: 22px;
            font-weight: 800;
        }
        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
            gap: 14px;
        }
        .card {
            border-radius: 16px;
            padding: 16px;
            border: 1px solid #e5e7eb;
            background: #ffffff;
        }
        .card.best {
            border: 2px solid #2563eb;
            background: #eff6ff;
        }
        .rank {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background: #dbeafe;
            color: #1d4ed8;
            font-size: 12px;
            font-weight: 700;
            margin-bottom: 10px;
        }
        .card-title {
            font-size: 16px;
            font-weight: 700;
            line-height: 1.45;
            min-height: 72px;
        }
        .card-price {
            font-size: 26px;
            font-weight: 800;
            margin: 10px 0;
        }
        .card-reason {
            color: #1f2937;
            font-size: 14px;
            line-height: 1.55;
            background: rgba(255,255,255,0.65);
            border-radius: 12px;
            padding: 10px;
        }
        .link {
            display: inline-block;
            margin-top: 12px;
            text-decoration: none;
            color: #2563eb;
            font-weight: 600;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
        }
        th, td {
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid #eee;
            vertical-align: top;
        }
        th {
            background: #f3f4f6;
        }
        .small {
            font-size: 13px;
            color: #6b7280;
        }
        @media (max-width: 900px) {
            form {
                grid-template-columns: 1fr;
            }
            .stats {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <h1>RAM Price Agent</h1>
    <p class="muted">국내 PC RAM 시세 조회 단일 목적 에이전트 <span class="badge">AI 필터링 + TOP 5 추천</span></p>

    <div class="box">
        <form method="post">
            <select name="memory_type">
                <option value="DDR4" {% if memory_type == "DDR4" %}selected{% endif %}>DDR4</option>
                <option value="DDR5" {% if memory_type == "DDR5" %}selected{% endif %}>DDR5</option>
            </select>

            <select name="capacity">
                <option value="16GB" {% if capacity == "16GB" %}selected{% endif %}>16GB</option>
                <option value="32GB" {% if capacity == "32GB" %}selected{% endif %}>32GB</option>
            </select>

            <input type="text" name="clock" placeholder="예: 3200 / 5600 / 6000" value="{{ clock or '' }}">

            <button type="submit">조회</button>
        </form>
        <p class="small" style="margin-top:12px;">예시: DDR4 + 16GB + 3200 / DDR5 + 16GB + 5600</p>
    </div>

    {% if query %}
    <div class="box">
        <h2>검색 조건</h2>
        <p><strong>{{ query }}</strong></p>

        {% if error %}
            <p class="error">{{ error }}</p>
        {% else %}
            <p class="ok">AI 선별 후 상품 수: {{ products|length }}개</p>

            <div class="stats">
                <div class="stat">
                    <div class="stat-label">최저가</div>
                    <div class="stat-value">{{ min_price_text }}</div>
                </div>
                <div class="stat">
                    <div class="stat-label">평균가</div>
                    <div class="stat-value">{{ avg_price_text }}</div>
                </div>
                <div class="stat">
                    <div class="stat-label">최고가</div>
                    <div class="stat-value">{{ max_price_text }}</div>
                </div>
            </div>

            <h3 style="margin-top:18px;">시세 요약</h3>
            <div class="summary">{{ summary }}</div>
        {% endif %}
    </div>
    {% endif %}

    {% if top5 %}
    <div class="box">
        <h2>AI TOP 5 추천</h2>
        <div class="cards">
            {% for item in top5 %}
            <div class="card {% if loop.first %}best{% endif %}">
                <div class="rank">TOP {{ loop.index }}</div>
                <div class="card-title">{{ item.title }}</div>
                <div class="card-price">{{ item.price_text }}</div>
                <div class="card-reason">
                    <strong>{{ item.recommend_reason }}</strong><br>
                    {{ item.recommend_summary }}
                </div>
                {% if item.link %}
                <a class="link" href="{{ item.link }}" target="_blank">상품 보기</a>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    {% if products %}
    <div class="box">
        <h2>AI 선별 상품 목록</h2>
        <table>
            <thead>
                <tr>
                    <th style="width:70px;">순위</th>
                    <th>상품명</th>
                    <th style="width:140px;">가격</th>
                    <th style="width:180px;">AI 판정</th>
                    <th style="width:180px;">추천 상태</th>
                    <th>링크</th>
                </tr>
            </thead>
            <tbody>
                {% for p in products %}
                <tr>
                    <td>{{ p.rank_note }}</td>
                    <td>{{ p.title }}</td>
                    <td>{{ p.price_text }}</td>
                    <td>{{ p.ai_reason }}</td>
                    <td>{{ p.rank_state }}</td>
                    <td>
                        {% if p.link %}
                            <a class="link" href="{{ p.link }}" target="_blank">열기</a>
                        {% else %}
                            -
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

    {% if debug_info %}
    <div class="box">
        <h2>디버그</h2>
        <div class="debug">{{ debug_info }}</div>
    </div>
    {% endif %}
</body>
</html>
"""

BAD_TITLE_KEYWORDS = [
    "통합검색", "관심상품", "상품리뷰", "가격정보", "이미지보기", "대량구매",
    "상품분류", "의견", "배송비", "최저가", "더보기", "등록", "리뷰수",
    "별점", "닫기", "VS상품비교", "와우할인", "마이페이지"
]

HARD_BLOCK_KEYWORDS = [
    "조립컴퓨터", "게이밍 컴퓨터", "풀세트", "본체", "게이밍PC",
    "라이젠", "인텔", "노트북", "중고", "서버용", "SODIMM", "SO-DIMM"
]

BRAND_PRIORITY = [
    "삼성", "SK하이닉스", "하이닉스", "마이크론", "CRUCIAL",
    "TEAMGROUP", "ADATA", "ESSENCORE", "KLEVV", "GEIL", "APACER", "PATRIOT", "G.SKILL"
]

COMMON_CAPACITIES = ["8GB", "16GB", "24GB", "32GB", "48GB", "64GB", "96GB", "128GB"]
COMMON_CLOCKS = ["3200", "4800", "5200", "5600", "6000", "6400", "7200"]

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()

def extract_price_number(text: str) -> Optional[int]:
    if not text:
        return None
    if "/1GB" in text or "원/1GB" in text:
        return None
    match = re.search(r"(\d{1,3}(?:,\d{3})+)\s*원", text)
    if not match:
        return None
    value = int(match.group(1).replace(",", ""))
    if value < 5000 or value > 1000000:
        return None
    return value

def build_query(memory_type: str, capacity: str, clock: str) -> str:
    memory_type = memory_type.strip().upper()
    capacity = capacity.strip().upper().replace(" ", "")
    clock = clock.strip()

    if memory_type == "DDR5":
        if clock in ("", "2666", "2933", "3200"):
            return f"{memory_type} {capacity} RAM"
        return f"{memory_type} {capacity} {clock} RAM"

    if memory_type == "DDR4":
        if clock:
            return f"{memory_type} {capacity} {clock} RAM"
        return f"{memory_type} {capacity} RAM"

    return f"{memory_type} {capacity} RAM"

def get_rendered_html_with_selenium(query: str) -> Tuple[str, str]:
    url = f"https://search.danawa.com/dsearch.php?query={query.replace(' ', '+')}"
    options = Options()
    options.add_argument("--window-size=1400,1600")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=ko-KR")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        wait.until(
            lambda d: (
                len(d.find_elements(By.CSS_SELECTOR, "li.prod_item")) > 0
                or len(d.find_elements(By.CSS_SELECTOR, "a[href*='prod.danawa.com']")) > 5
                or "DDR5" in d.page_source
                or "DDR4" in d.page_source
            )
        )
        time.sleep(2)
        html = driver.page_source
        Path("debug_danawa_rendered.html").write_text(html, encoding="utf-8", errors="ignore")
        return html, url
    finally:
        driver.quit()

def brand_bonus(title: str) -> int:
    t = title.upper()
    for i, brand in enumerate(BRAND_PRIORITY):
        if brand.upper() in t:
            return max(1, 6 - (i // 2))
    return 0

def has_explicit_capacity_mismatch(text: str, selected_capacity: str) -> bool:
    t = text.upper()
    matches = [c for c in COMMON_CAPACITIES if c in t]
    if not matches:
        return False
    return selected_capacity not in matches

def has_explicit_clock_mismatch(text: str, selected_clock: str) -> bool:
    if not selected_clock:
        return False
    t = text.upper()
    matches = [c for c in COMMON_CLOCKS if c in t]
    if not matches:
        return False
    return selected_clock not in matches

def get_min_reasonable_price(memory_type: str, capacity: str) -> int:
    if memory_type == "DDR5" and capacity == "16GB":
        return 40000
    if memory_type == "DDR5" and capacity == "32GB":
        return 85000
    if memory_type == "DDR4" and capacity == "16GB":
        return 18000
    if memory_type == "DDR4" and capacity == "32GB":
        return 38000
    return 15000

def score_candidate(title: str, block_text: str, memory_type: str, capacity: str, clock: str) -> int:
    score = 0
    t = title.upper()
    b = block_text.upper()

    if memory_type in t or memory_type in b:
        score += 3
    if capacity in t or capacity in b:
        score += 3
    if "RAM" in t or "메모리" in t or "PC5-" in t or "PC4-" in t:
        score += 2
    if clock and (clock in t or clock in b):
        score += 2
    if "DESKTOP" in t or "데스크탑" in t:
        score += 1
    if "CL" in t:
        score += 1
    if has_explicit_capacity_mismatch(title + " " + block_text, capacity):
        score -= 5
    if has_explicit_clock_mismatch(title + " " + block_text, clock):
        score -= 3

    for bad in HARD_BLOCK_KEYWORDS:
        if bad.upper() in t or bad.upper() in b:
            score -= 6

    return score

def parse_products_from_rendered_html(
    html: str,
    memory_type: str,
    capacity: str,
    clock: str,
    limit: int = 80
) -> Tuple[List[Dict[str, Any]], List[str], int]:
    soup = BeautifulSoup(html, "html.parser")
    products = []
    seen = set()
    debug_hits = []
    cards = soup.select("li.prod_item")

    for card in cards:
        title = None
        link = None

        title_tag = (
            card.select_one("p.prod_name a")
            or card.select_one("a.prod_name")
            or card.select_one("a[name='productName']")
            or card.select_one("a[href*='prod.danawa.com']")
        )

        if title_tag:
            title = clean_text(title_tag.get_text(" ", strip=True))
            link = title_tag.get("href")

        if not title:
            continue
        if any(bad in title for bad in BAD_TITLE_KEYWORDS):
            continue

        block_text = clean_text(card.get_text(" ", strip=True))
        title_up = title.upper()
        block_up = block_text.upper()

        if memory_type not in title_up and memory_type not in block_up:
            continue

        price = None
        candidate_tags = card.find_all(string=re.compile(r"\d{1,3}(?:,\d{3})+\s*원"))
        for raw in candidate_tags:
            value = extract_price_number(str(raw))
            if value is not None and (price is None or value < price):
                price = value

        if price is None:
            for m in re.finditer(r"\d{1,3}(?:,\d{3})+\s*원", block_text):
                value = extract_price_number(m.group(0))
                if value is not None and (price is None or value < price):
                    price = value

        if price is None:
            continue

        if link and link.startswith("//"):
            link = "https:" + link

        score = score_candidate(title, block_text, memory_type, capacity, clock)
        if score < 1:
            continue

        key = (title, price)
        if key in seen:
            continue
        seen.add(key)

        products.append({
            "title": title,
            "price": price,
            "price_text": f"{price:,}원",
            "link": link,
            "raw_score": score,
            "block_text": block_text[:700]
        })
        debug_hits.append(f"[RAW s={score}] {title} -> {price:,}원")

    products.sort(key=lambda x: (-x["raw_score"], x["price"]))
    return products[:limit], debug_hits, len(cards)

def extract_first_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])

    raise ValueError("JSON 객체를 찾지 못했습니다.")

def call_ollama_json(prompt: str) -> Dict[str, Any]:
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": "json",
        "messages": [{"role": "user", "content": prompt}],
        "options": {"temperature": 0.1}
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    content = data.get("message", {}).get("content", "").strip()
    if not content:
        raise ValueError("Ollama 응답이 비어 있음")
    return extract_first_json_object(content)

def fallback_rule_filter(
    candidates: List[Dict[str, Any]],
    memory_type: str,
    capacity: str,
    clock: str
) -> Tuple[List[Dict[str, Any]], List[str]]:
    filtered = []
    debug = []
    min_price = get_min_reasonable_price(memory_type, capacity)

    for item in candidates:
        t = item["title"].upper()
        b = item.get("block_text", "").upper()
        merged = t + " " + b

        if any(bad.upper() in merged for bad in HARD_BLOCK_KEYWORDS):
            continue
        if memory_type not in merged:
            continue
        if has_explicit_capacity_mismatch(merged, capacity):
            continue
        if has_explicit_clock_mismatch(merged, clock):
            continue
        if item["price"] < min_price:
            continue

        new_item = dict(item)
        new_item["ai_reason"] = "규칙 기반 보완 후보"
        new_item["rank_note"] = "-"
        new_item["rank_state"] = "후보 유지"
        filtered.append(new_item)
        debug.append(f"[RULE KEEP] {item['title']}")

    unique_items = []
    seen = set()
    for item in filtered:
        key = (item["title"], item["price"])
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)

    unique_items.sort(key=lambda x: x["price"])
    return unique_items[:15], debug

def ai_filter_products(
    candidates: List[Dict[str, Any]],
    memory_type: str,
    capacity: str,
    clock: str
) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not candidates:
        return [], ["후보 상품 없음"]

    base_candidates = candidates[:40]
    items_for_ai = []
    for idx, item in enumerate(base_candidates, start=1):
        items_for_ai.append({
            "id": idx,
            "title": item["title"],
            "price_text": item["price_text"]
        })

    prompt = f"""
너는 RAM 상품 판별 전용 에이전트다.

목표:
입력된 상품 목록에서 아래 조건에 맞는 "진짜 데스크탑 RAM 상품"만 골라라.

조건:
- 메모리 종류: {memory_type}
- 용량: {capacity}
- 클럭: {clock if clock else "미지정"}
- 데스크탑용 RAM 위주

제외 대상:
- 노트북용 RAM
- SO-DIMM / SODIMM
- 조립PC / 완본체 / 풀세트 / 게이밍PC
- CPU, 노트북 본체, 세트 상품
- RAM이 아닌 주변상품
- 명백히 검색 조건과 안 맞는 것

중요:
- 조건에 맞는 정상적인 데스크탑 RAM이면 최대한 살려라.
- 일부만 답하지 말고 가능한 한 많은 항목에 대해 판정해라.
- JSON만 출력

반드시 아래 형식:
{{
  "results": [
    {{
      "id": 1,
      "product_keep": true,
      "reason": "DDR5 데스크탑 RAM"
    }}
  ]
}}

상품 목록:
{json.dumps(items_for_ai, ensure_ascii=False, indent=2)}
""".strip()

    ai_kept = []
    ai_debug = []
    ai_drop_keys = set()

    try:
        result = call_ollama_json(prompt)
        rows = result.get("results", [])
        keep_map = {}

        for row in rows:
            try:
                pid = int(row.get("id"))
                keep_map[pid] = {
                    "keep": bool(row.get("product_keep")),
                    "reason": str(row.get("reason", "")).strip() or "AI 판정"
                }
            except Exception:
                continue

        for idx, item in enumerate(base_candidates, start=1):
            row = keep_map.get(idx)

            if not row:
                ai_debug.append(f"[AI MISS] {item['title']}")
                continue

            if row["keep"]:
                new_item = dict(item)
                new_item["ai_reason"] = row["reason"]
                new_item["rank_note"] = "-"
                new_item["rank_state"] = "후보 유지"
                ai_kept.append(new_item)
                ai_debug.append(f"[AI KEEP] {item['title']} -> {row['reason']}")
            else:
                ai_drop_keys.add((item["title"], item["price"]))
                ai_debug.append(f"[AI DROP] {item['title']} -> {row['reason']}")

    except Exception as e:
        ai_debug.append(f"[AI FILTER ERROR] {e}")

    fallback_items, fallback_debug = fallback_rule_filter(candidates, memory_type, capacity, clock)

    merged = []
    seen = set()

    for item in ai_kept:
        key = (item["title"], item["price"])
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    for item in fallback_items:
        key = (item["title"], item["price"])
        if key in seen:
            continue
        if key in ai_drop_keys:
            continue
        seen.add(key)
        merged.append(item)

    if len(merged) >= 5:
        median_price = statistics.median([x["price"] for x in merged])
        lower = median_price * 0.45
        upper = median_price * 2.2
        merged = [x for x in merged if lower <= x["price"] <= upper]

    merged.sort(key=lambda x: x["price"])

    if not merged:
        return [], ai_debug + ["[MERGE RESULT] 0 items"] + fallback_debug[:10]

    return merged[:15], ai_debug + [f"[MERGE RESULT] {len(merged)} items"] + fallback_debug[:10]

def fallback_rank_top5(
    products: List[Dict[str, Any]],
    memory_type: str,
    capacity: str,
    clock: str
) -> Tuple[List[Dict[str, Any]], List[str]]:
    prices = [p["price"] for p in products]
    median_price = statistics.median(prices) if prices else 0
    scored = []

    for item in products:
        s = 0.0
        title_up = item["title"].upper()

        if memory_type in title_up:
            s += 3
        if capacity in title_up or not has_explicit_capacity_mismatch(title_up, capacity):
            s += 3
        if clock and (clock in title_up or not has_explicit_clock_mismatch(title_up, clock)):
            s += 2

        s += brand_bonus(item["title"])
        s += item.get("raw_score", 0) * 0.3

        if median_price > 0:
            gap = abs(item["price"] - median_price) / median_price
            s -= gap * 2.2

        scored.append((s, item))

    scored.sort(key=lambda x: (-x[0], x[1]["price"]))
    top = []
    debug = []

    for idx, (_, item) in enumerate(scored[:5], start=1):
        new_item = dict(item)
        if idx == 1:
            new_item["recommend_reason"] = "조건과 브랜드·가격 균형이 가장 좋음"
            new_item["recommend_summary"] = "AI 추천이 충분하지 않을 때를 대비한 대체 로직 기준으로도 가장 무난한 후보입니다."
        else:
            new_item["recommend_reason"] = "상위 후보로 유지할 가치가 있음"
            new_item["recommend_summary"] = "조건 적합성과 가격 균형을 기준으로 상위권 후보로 유지했습니다."
        top.append(new_item)
        debug.append(f"[FALLBACK TOP{idx}] {item['title']}")

    return top, debug

def ai_rank_top5(
    products: List[Dict[str, Any]],
    memory_type: str,
    capacity: str,
    clock: str
) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not products:
        return [], ["추천 후보 없음"]

    items_for_ai = []
    for idx, item in enumerate(products[:12], start=1):
        items_for_ai.append({
            "id": idx,
            "title": item["title"],
            "price_text": item["price_text"],
            "filter_reason": item.get("ai_reason", "")
        })

    prompt = f"""
너는 RAM 추천 전용 에이전트다.

목표:
아래 RAM 후보들 중에서 TOP 5를 순서대로 골라라.

조건:
- 메모리 종류: {memory_type}
- 용량: {capacity}
- 클럭: {clock if clock else "미지정"}

추천 기준:
1. 검색 조건과의 일치도
2. 정상적인 데스크탑 RAM 여부
3. 브랜드 신뢰감
4. 가격이 너무 튀지 않는지
5. 전체적으로 가장 무난하고 추천할 만한지

주의:
- id 중복 금지
- TOP 5를 가능한 한 채워라
- JSON만 출력

반드시 아래 형식:
{{
  "ranked": [
    {{
      "id": 2,
      "reason_short": "가격과 브랜드 밸런스 좋음",
      "summary": "검색 조건에 잘 맞고 브랜드와 가격 균형이 좋아 상위 추천입니다."
    }}
  ]
}}

후보 목록:
{json.dumps(items_for_ai, ensure_ascii=False, indent=2)}
""".strip()

    try:
        result = call_ollama_json(prompt)
        ranked = result.get("ranked", [])
        top = []
        debug = []
        used = set()

        for row in ranked:
            try:
                rid = int(row.get("id"))
                if rid < 1 or rid > len(products[:12]) or rid in used:
                    continue
                used.add(rid)

                picked = dict(products[rid - 1])
                picked["recommend_reason"] = str(row.get("reason_short", "")).strip() or "AI 추천"
                picked["recommend_summary"] = str(row.get("summary", "")).strip() or "AI가 상위 추천으로 판단했습니다."
                top.append(picked)
                debug.append(f"[AI TOP{len(top)}] {picked['title']} -> {picked['recommend_reason']}")
            except Exception:
                continue

        if len(top) < 3:
            fallback, fallback_debug = fallback_rank_top5(products, memory_type, capacity, clock)
            fallback_debug.insert(0, "[AI RANK TOO FEW -> FALLBACK]")
            return fallback, debug + fallback_debug

        return top[:5], debug

    except Exception as e:
        fallback, debug = fallback_rank_top5(products, memory_type, capacity, clock)
        debug.insert(0, f"[AI RANK ERROR] {e}")
        return fallback, debug

def summarize_products(query: str, products: List[Dict[str, Any]], top5: List[Dict[str, Any]]) -> str:
    if not products:
        return "검색 결과가 없어 요약을 만들지 못했습니다."

    prices = [p["price"] for p in products]
    low = min(prices)
    avg = int(statistics.mean(prices))
    high = max(prices)

    if top5:
        top_names = ", ".join([item["title"] for item in top5[:3]])
        return (
            f"{query} 기준으로 AI 선별 후 최저가는 {low:,}원, 평균가는 약 {avg:,}원입니다.\n"
            f"현재 반영된 상품 가격대는 {low:,}원 ~ {high:,}원 범위입니다.\n"
            f"AI는 조건 적합성과 가격/브랜드 균형을 바탕으로 TOP 5를 추렸고, 상위 후보 예시는 {top_names} 입니다."
        )

    return (
        f"{query} 기준으로 AI 선별 후 최저가는 {low:,}원, 평균가는 약 {avg:,}원입니다.\n"
        f"현재 반영된 상품 가격대는 {low:,}원 ~ {high:,}원 범위입니다."
    )

@app.route("/", methods=["GET", "POST"])
def index():
    memory_type = "DDR5"
    capacity = "16GB"
    clock = ""
    query = None
    products = []
    top5 = []
    summary = ""
    error = None
    min_price_text = "-"
    avg_price_text = "-"
    max_price_text = "-"
    debug_info = ""

    if request.method == "POST":
        memory_type = request.form.get("memory_type", "DDR5").strip().upper()
        capacity = request.form.get("capacity", "16GB").strip().upper()
        clock = request.form.get("clock", "").strip()

        query = build_query(memory_type, capacity, clock)

        try:
            html, search_url = get_rendered_html_with_selenium(query)

            raw_candidates, raw_debug, card_count = parse_products_from_rendered_html(
                html=html,
                memory_type=memory_type,
                capacity=capacity,
                clock=clock,
                limit=80
            )

            products, ai_filter_debug = ai_filter_products(
                candidates=raw_candidates,
                memory_type=memory_type,
                capacity=capacity,
                clock=clock
            )

            ai_rank_debug = ["추천 단계 생략"]
            if products:
                top5, ai_rank_debug = ai_rank_top5(
                    products=products,
                    memory_type=memory_type,
                    capacity=capacity,
                    clock=clock
                )

            rank_map = {}
            for idx, item in enumerate(top5, start=1):
                rank_map[(item["title"], item["price"])] = f"TOP {idx}"

            for p in products:
                key = (p["title"], p["price"])
                if key in rank_map:
                    p["rank_note"] = rank_map[key]
                    p["rank_state"] = "상위 추천"
                else:
                    p["rank_note"] = "-"
                    p["rank_state"] = "후보 유지"

            debug_lines = []
            debug_lines.append(f"search_url = {search_url}")
            debug_lines.append(f"query = {query}")
            debug_lines.append(f"card_count = {card_count}")
            debug_lines.append(f"raw_candidates = {len(raw_candidates)}")
            debug_lines.append(f"final_products = {len(products)}")
            debug_lines.append(f"top5_count = {len(top5)}")
            debug_lines.append("")
            debug_lines.append("[RAW TOP 20]")
            debug_lines.extend(raw_debug[:20])
            debug_lines.append("")
            debug_lines.append("[AI FILTER TOP 20]")
            debug_lines.extend(ai_filter_debug[:20])
            debug_lines.append("")
            debug_lines.append("[AI RANK TOP 10]")
            debug_lines.extend(ai_rank_debug[:10])

            debug_info = "\n".join(debug_lines)

            if not products:
                error = "AI 필터링 후 남은 RAM 상품이 없습니다. debug_danawa_rendered.html과 디버그 박스를 확인하세요."
            else:
                prices = [p["price"] for p in products]
                min_price_text = f"{min(prices):,}원"
                avg_price_text = f"{int(statistics.mean(prices)):,}원"
                max_price_text = f"{max(prices):,}원"
                summary = summarize_products(query, products, top5)

        except Exception as e:
            error = f"처리 중 오류가 발생했습니다: {e}"

    return render_template_string(
        HTML,
        memory_type=memory_type,
        capacity=capacity,
        clock=clock,
        query=query,
        products=products,
        top5=top5,
        summary=summary,
        error=error,
        min_price_text=min_price_text,
        avg_price_text=avg_price_text,
        max_price_text=max_price_text,
        debug_info=debug_info,
    )

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
