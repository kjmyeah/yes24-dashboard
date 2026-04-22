"""
yes24 수학 교재 판매지수 크롤러 (Playwright 기반)
- 실행 시 오늘 날짜 데이터를 수집하여 data/sales_data.csv에 누적 저장
- 같은 날 이미 수집된 경우 skip
- 최초 실행 시 2026-04-15 시드 데이터 자동 삽입
"""

import re
import pandas as pd
from datetime import datetime
import os
import sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from books import BOOKS, SEED_DATA

BASE_URL  = "https://www.yes24.com/Product/Search?domain=BOOK&query={isbn}"
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sales_data.csv")


def scrape_all(books: list) -> dict:
    """
    Playwright 브라우저를 한 번 열어 모든 ISBN 순서대로 수집.
    반환: {isbn: sales_index or None}
    """
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # yes24 홈 방문 → 세션 쿠키 획득 (봇 차단 우회)
        page.goto("https://www.yes24.com", timeout=30000)
        page.wait_for_timeout(2000)

        for i, book in enumerate(books, 1):
            isbn  = book["isbn"]
            label = f"{book['series']} {book['subject']}"
            try:
                page.goto(BASE_URL.format(isbn=isbn), timeout=20000)
                page.wait_for_timeout(1500)

                tag = page.query_selector("span.saleNum")
                if tag:
                    m = re.search(r"[\d,]+", tag.inner_text())
                    index = int(m.group().replace(",", "")) if m else None
                else:
                    index = None

                status = f"{index:,}" if index is not None else "N/A"
                print(f"  [{i:02d}/{len(books)}] {label:<22} → {status}")
                results[isbn] = index

            except Exception as e:
                print(f"  [{i:02d}/{len(books)}] {label:<22} → 오류: {e}")
                results[isbn] = None

        browser.close()
    return results


def load_or_create_df() -> pd.DataFrame:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE, dtype={"isbn": str})

    # CSV 없으면 시드 데이터로 초기화
    print("최초 실행: 2026-04-15 시드 데이터를 삽입합니다.")
    rows = [
        {
            "date":        "2026-04-15",
            "isbn":        b["isbn"],
            "series":      b["series"],
            "subject":     b["subject"],
            "sales_index": SEED_DATA.get(b["isbn"]),
        }
        for b in BOOKS
    ]
    df = pd.DataFrame(rows)
    df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")
    print(f"시드 데이터 저장 완료 → {DATA_FILE}")
    return df


def run_scraper():
    today = datetime.now().strftime("%Y-%m-%d")
    df    = load_or_create_df()

    if today in df["date"].values:
        print(f"[완료] {today} 데이터가 이미 존재합니다. 재수집하려면 CSV에서 해당 날짜 행을 삭제하세요.")
        return

    print(f"\n=== {today} 판매지수 수집 시작 (총 {len(BOOKS)}종) ===\n")
    index_map = scrape_all(BOOKS)

    rows = [
        {
            "date":        today,
            "isbn":        b["isbn"],
            "series":      b["series"],
            "subject":     b["subject"],
            "sales_index": index_map.get(b["isbn"]),
        }
        for b in BOOKS
    ]
    new_df = pd.DataFrame(rows)
    df     = pd.concat([df, new_df], ignore_index=True)
    df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")

    success = sum(1 for r in rows if r["sales_index"] is not None)
    print(f"\n=== 수집 완료: {success}/{len(BOOKS)}종 성공  |  저장: {DATA_FILE} ===")


if __name__ == "__main__":
    run_scraper()
