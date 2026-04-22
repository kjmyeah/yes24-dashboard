"""
수학 교재 시장 인사이트 자동 생성
- 판매 데이터 정량 분석 → Gemini API 호출 → data/insights.json 저장
- 실행: python insight_generator.py
"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google import genai
from google.genai import types

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "sales_data.csv")
OUT_FILE  = os.path.join(BASE_DIR, "data", "insights.json")
OUR_BOOK  = "THE 개념"   # 자사 교재 시리즈명


# ── 데이터 로드 ────────────────────────────────────────────────────
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_FILE, dtype={"isbn": str}, encoding="utf-8-sig")
    df["date"]        = pd.to_datetime(df["date"])
    df["sales_index"] = pd.to_numeric(df["sales_index"], errors="coerce")
    return df


# ── 정량 지표 계산 ─────────────────────────────────────────────────
def compute_metrics(df: pd.DataFrame, subject: str) -> pd.DataFrame:
    df1    = df[df["subject"] == subject].copy()
    latest = df1["date"].max()

    # 날짜별 순위 부여
    all_rows = []
    for d, grp in df1.groupby("date"):
        grp = grp.sort_values("sales_index", ascending=False).copy()
        grp["rank"] = range(1, len(grp) + 1)
        all_rows.append(grp)
    ranked = pd.concat(all_rows, ignore_index=True)

    # 최근 7일 vs 이전 7일 (단기 증감)
    dates14 = sorted(ranked[ranked["date"] >= latest - timedelta(days=14)]["date"].unique())
    if len(dates14) >= 4:
        mid     = dates14[len(dates14) // 2]
        recent7 = ranked[ranked["date"] >= mid]
        prev7   = ranked[(ranked["date"] >= latest - timedelta(days=14)) & (ranked["date"] < mid)]
    else:
        recent7 = ranked[ranked["date"] == latest]
        prev7   = ranked[ranked["date"] != latest]

    r7avg  = recent7.groupby("series")["sales_index"].mean().rename("recent7_avg")
    p7avg  = prev7.groupby("series")["sales_index"].mean().rename("prev7_avg")
    r7rank = recent7.groupby("series")["rank"].mean().rename("recent7_rank")

    # 최근 4주 vs 이전 4주 (단기 급성장)
    recent4w = df1[df1["date"] >= latest - timedelta(days=28)]
    prev4w   = df1[(df1["date"] >= latest - timedelta(days=56)) &
                   (df1["date"] <  latest - timedelta(days=28))]
    r4w_avg  = recent4w.groupby("series")["sales_index"].mean().rename("recent4w_avg")
    p4w_avg  = prev4w.groupby("series")["sales_index"].mean().rename("prev4w_avg")

    # Top 유지율 (최근 30일)
    r30    = ranked[ranked["date"] >= latest - timedelta(days=30)]
    days30 = max(r30["date"].nunique(), 1)
    top10  = (r30[r30["rank"] <= 10].groupby("series").size() / days30 * 100).round(1).rename("top10_pct")
    top20  = (r30[r30["rank"] <= 20].groupby("series").size() / days30 * 100).round(1).rename("top20_pct")

    comp = pd.concat([r7avg, p7avg, r7rank, r4w_avg, p4w_avg, top10, top20], axis=1)
    comp["idx_chg_pct"] = ((comp["recent7_avg"] - comp["prev7_avg"]) / comp["prev7_avg"] * 100).round(1)
    comp["m4w_chg_pct"] = ((comp["recent4w_avg"] - comp["prev4w_avg"]) / comp["prev4w_avg"] * 100).round(1)
    return comp.sort_values("recent7_rank")


# ── Gemini 프롬프트 생성 ───────────────────────────────────────────
def build_prompt(m1: pd.DataFrame, m2: pd.DataFrame, latest_date: str) -> str:

    def fmt(m: pd.DataFrame, top_n: int = 15) -> str:
        lines = []
        for series, row in m.head(top_n).iterrows():
            lines.append(
                f"  {series}: 평균순위={row.get('recent7_rank', 0):.1f}위, "
                f"최근4주증감={row.get('m4w_chg_pct', 0):+.1f}%, "
                f"Top10점유={row.get('top10_pct', 0):.0f}%"
            )
        return "\n".join(lines)

    return f"""당신은 교육 출판사의 수석 마케팅 분석가입니다.
"THE 개념" 시리즈(더 개념 블랙라벨)는 분석 주체인 자사 교재입니다.

아래는 YES24 수학 개념서 판매지수 실측 데이터({latest_date} 기준)입니다.
※ 최근4주증감 = 최근 4주 평균 판매지수 vs 그 이전 4주 평균 판매지수 대비 변화율

[공통수학1 현황 — 판매지수 순위 상위 10종]
{fmt(m1)}

[공통수학2 현황 — 판매지수 순위 상위 10종]
{fmt(m2)}

---
다음 규칙을 지켜서 반드시 유효한 JSON만 출력하세요 (마크다운 코드블록 없이).

{{
  "market_trends": [
    "트렌드1: 구체적 데이터 수치 포함",
    "트렌드2",
    "트렌드3"
  ],
  "own_books": [
    {{
      "series": "THE 개념",
      "subject": "공수1 또는 공수2",
      "summary": "한 줄 현황 요약 (수치 포함)",
      "status": "성장 또는 정체 또는 하락",
      "analysis": "자사 교재 현황 분석 — 시장 내 포지션, 성장/정체 원인 추론 (2문장)",
      "action": "개선 방향 또는 강화 전략 — 내부 기획자가 바로 활용 가능한 수준 (2문장)"
    }}
  ],
  "top3_stable": [
    {{
      "series": "고착 교재 시리즈명",
      "subject": "공수1 또는 공수2",
      "summary": "한 줄 요약 (순위·점유율 수치 포함)",
      "blacklabel_threat": "위협 또는 기회 또는 중립"
    }}
  ],
  "surge_competitors": [
    {{
      "series": "급성장 타사 교재 시리즈명",
      "subject": "공수1 또는 공수2",
      "summary": "한 줄 요약 (수치 포함)",
      "rise_reasons": ["원인1 (가설 기반)", "원인2", "원인3"],
      "trend_judgment": "단기 또는 중기 또는 장기",
      "competition": "포지션·타겟·특징 한 문장",
      "blacklabel_threat": "위협 또는 기회 또는 중립",
      "blacklabel_insight": "이 교재의 성장이 THE 개념에 미치는 영향 (2문장)",
      "blacklabel_action": "THE 개념의 대응 전략 및 콘텐츠/마케팅 액션 (2문장)"
    }}
  ]
}}

분석 대상 선정 기준:
- own_books: THE 개념 공수1, 공수2 반드시 포함 (총 2개)
- top3_stable: 최근 30일 Top10 점유율 80% 이상이고 순위가 고착된 교재 (개념원리·기본정석·개념+유형 등)
  (THE 개념 제외, 공수1·공수2 각 최대 3종)
- surge_competitors: 아래 중 하나 이상 해당하는 교재
  ① 최근 4주 증감이 타사 교재 중 상위 3위 이내 (증감이 작더라도 상대적으로 높은 교재)
  ② 최근 7일 평균순위 Top 5 이내 교재
  ③ 최근 4주 증감이 +0% 이상이면서 최근 7일 평균순위 10위 이내 교재
  (THE 개념 제외, top3_stable 교재 제외, 공수1·공수2 합산 최대 8종)
  → 절대적 성장률이 낮더라도 시장이 전반적으로 정체일 경우 상대적 강세 교재를 분석 대상으로 선정할 것

작성 원칙:
- 근거 없는 확신 대신 "가능성 기반 가설"로 작성
- 단순 요약 금지, "왜 그런지" 추론 포함
- 내부 기획자가 바로 활용 가능한 수준으로 구체화
"""


# ── Gemini API 호출 ────────────────────────────────────────────────
def call_gemini(prompt: str) -> dict:
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(".env 파일에 GEMINI_API_KEY가 없습니다.")

    client = genai.Client(api_key=api_key)

    # 모델 우선순위: 2.5-flash → 2.0-flash-lite → 2.0-flash
    for model_name in ("models/gemini-2.5-flash", "models/gemini-2.0-flash-lite", "models/gemini-2.0-flash"):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            raw = response.text.strip()
            print(f"  사용 모델: {model_name}")
            break
        except Exception as e:
            print(f"  {model_name} 실패: {e}")
            raw = None

    if not raw:
        raise RuntimeError("Gemini API 호출 실패 — API 키 또는 네트워크를 확인하세요.")

    # 마크다운 코드블록 제거
    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1] if len(parts) >= 2 else parts[0]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


# ── 메인 실행 ──────────────────────────────────────────────────────
def run():
    print("=== 시장 인사이트 생성 시작 ===\n")
    df     = load_data()
    latest = df["date"].max().strftime("%Y-%m-%d")
    print(f"데이터 기준일: {latest}")

    m1 = compute_metrics(df, "공수1")
    m2 = compute_metrics(df, "공수2")

    prompt = build_prompt(m1, m2, latest)

    print("Gemini API 호출 중...")
    result = call_gemini(prompt)

    # 메타데이터 추가
    result["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    result["data_as_of"]   = latest

    # 정량 지표도 함께 저장 (대시보드에서 테이블 렌더링용)
    def df_to_records(m: pd.DataFrame) -> list:
        m = m.reset_index()
        # NaN → None 변환 (JSON 직렬화)
        return json.loads(m.where(m.notna(), other=None).to_json(
            orient="records", force_ascii=False
        ))

    result["quantitative"] = {
        "공수1": df_to_records(m1),
        "공수2": df_to_records(m2),
    }

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    n_books = len(result.get("books", []))
    print(f"\n완료 → {OUT_FILE}")
    print(f"분석 교재: {n_books}종 | 생성 시각: {result['generated_at']}")


if __name__ == "__main__":
    run()
