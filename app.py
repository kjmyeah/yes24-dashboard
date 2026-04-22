"""
yes24 수학 교재 판매지수 대시보드
실행: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import subprocess
import os
import sys
import json

DATA_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sales_data.csv")
INSIGHTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "insights.json")
SCRAPER      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper.py")
INSIGHT_GEN  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "insight_generator.py")

st.set_page_config(
    page_title="수학 교재 판매지수 대시보드",
    page_icon="📚",
    layout="wide",
)

# ── 데이터 로드 ────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame()
    df = pd.read_csv(DATA_FILE, dtype={"isbn": str})
    df["date"]        = pd.to_datetime(df["date"])
    df["sales_index"] = pd.to_numeric(df["sales_index"], errors="coerce")
    return df


def refresh():
    st.cache_data.clear()
    st.rerun()


# ── 사이드바 ───────────────────────────────────────────────────────
with st.sidebar:
    st.title("📚 교재 판매지수")
    st.divider()

    st.subheader("데이터 수집")
    if st.button("지금 크롤링 실행", use_container_width=True, type="primary"):
        with st.spinner("yes24 크롤링 중... (약 1~2분 소요)"):
            result = subprocess.run(
                [sys.executable, SCRAPER],
                capture_output=True, text=True
            )
        if result.returncode == 0:
            st.success("수집 완료!")
            st.text(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
        else:
            st.error("오류 발생")
            st.text(result.stderr[-300:])
        refresh()

    st.divider()
    st.subheader("AI 인사이트 생성")
    if st.button("인사이트 재생성 (Gemini)", use_container_width=True):
        with st.spinner("Gemini API로 인사이트 생성 중... (약 30초)"):
            result = subprocess.run(
                [sys.executable, INSIGHT_GEN],
                capture_output=True, text=True
            )
        if result.returncode == 0:
            st.success("인사이트 생성 완료!")
            st.text(result.stdout[-400:] if len(result.stdout) > 400 else result.stdout)
        else:
            st.error("오류 발생")
            st.text(result.stderr[-400:])
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.caption("매일 자동 수집은 Windows 작업 스케줄러로 run_scraper.bat을 등록하세요.")

# ── 데이터 로드 ────────────────────────────────────────────────────
df = load_data()

if df.empty:
    st.warning("데이터가 없습니다. 왼쪽 사이드바에서 '지금 크롤링 실행'을 눌러주세요.")
    st.stop()

# 날짜 정렬
dates      = sorted(df["date"].unique())
latest_dt  = dates[-1]
prev_dt    = dates[-2] if len(dates) >= 2 else None

# ── 오늘 + 증감 계산 ───────────────────────────────────────────────
today_df = df[df["date"] == latest_dt].copy()

if prev_dt is not None:
    prev_df  = (
        df[df["date"] == prev_dt][["isbn", "sales_index"]]
        .rename(columns={"sales_index": "prev_index"})
    )
    today_df = today_df.merge(prev_df, on="isbn", how="left")
    today_df["change"]     = today_df["sales_index"] - today_df["prev_index"]
    today_df["change_pct"] = (today_df["change"] / today_df["prev_index"] * 100).round(1)
else:
    today_df["prev_index"] = None
    today_df["change"]     = None
    today_df["change_pct"] = None

today_df = today_df.sort_values("sales_index", ascending=False, na_position="last").reset_index(drop=True)

# ── 헤더 ──────────────────────────────────────────────────────────
st.title("📚 수학 교재 판매지수 대시보드")
st.caption(f"최신 수집일: **{latest_dt.strftime('%Y-%m-%d')}**  |  누적 수집일: **{len(dates)}일**")
st.divider()

# ── KPI 카드 ──────────────────────────────────────────────────────
valid_today = today_df.dropna(subset=["sales_index"])
k1, k2, k3, k4 = st.columns(4)

with k1:
    top = valid_today.iloc[0] if not valid_today.empty else None
    st.metric("판매지수 1위", f"{top['series']} {top['subject']}" if top is not None else "-",
              f"{int(top['sales_index']):,}" if top is not None else "")

with k2:
    if top is not None and pd.notna(top.get("change")):
        delta_str = f"전일 대비 {'+' if top['change'] >= 0 else ''}{int(top['change']):,}"
    else:
        delta_str = ""
    st.metric("1위 판매지수", f"{int(top['sales_index']):,}" if top is not None else "-", delta_str)

with k3:
    if prev_dt and not today_df["change"].isna().all():
        most_up = today_df.loc[today_df["change"].idxmax()]
        st.metric("최대 상승", f"{most_up['series']} {most_up['subject']}",
                  f"+{int(most_up['change']):,} ({most_up['change_pct']:+.1f}%)")
    else:
        st.metric("최대 상승", "-")

with k4:
    if prev_dt and not today_df["change"].isna().all():
        most_dn = today_df.loc[today_df["change"].idxmin()]
        st.metric("최대 하락", f"{most_dn['series']} {most_dn['subject']}",
                  f"{int(most_dn['change']):,} ({most_dn['change_pct']:+.1f}%)")
    else:
        st.metric("최대 하락", "-")

st.divider()

# ── 탭 구성 ───────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📋 순위표", "📈 추이 차트", "🧠 시장 인사이트"])

# ════════════════════════════════════════════════════════════════
# Tab 1 – 순위표
# ════════════════════════════════════════════════════════════════
with tab1:
    t1_subj = st.radio("과목 필터", ["전체", "공수1", "공수2"], horizontal=True, key="tab1_subj")
    t1_today = today_df if t1_subj == "전체" else today_df[today_df["subject"] == t1_subj]
    t1_today = t1_today.reset_index(drop=True)

    def fmt_idx(v):
        return f"{int(v):,}" if pd.notna(v) else "N/A"

    def fmt_change(v):
        if pd.isna(v): return "-"
        return f"▲ {int(v):,}" if v > 0 else (f"▼ {abs(int(v)):,}" if v < 0 else "–")

    def fmt_pct(v):
        if pd.isna(v): return "-"
        return f"+{v:.1f}%" if v > 0 else (f"{v:.1f}%" if v < 0 else "0%")

    display = t1_today[["series", "subject", "sales_index", "change", "change_pct"]].copy()
    display.insert(0, "순위", range(1, len(display) + 1))
    display.columns = ["순위", "교재명", "과목", "판매지수", "증감", "증감(%)"]
    display["판매지수"] = display["판매지수"].apply(fmt_idx)
    display["증감"]    = display["증감"].apply(fmt_change)
    display["증감(%)"] = display["증감(%)"].apply(fmt_pct)

    # 증감 색상 (컬럼 순서: 순위·교재명·과목·판매지수·증감·증감(%) = 6개)
    def highlight_change(row):
        val = str(row["증감"])
        if "▲" in val:
            color = "color: #2ecc71; font-weight:bold"
        elif "▼" in val:
            color = "color: #e74c3c; font-weight:bold"
        else:
            color = ""
        return [""] * 4 + [color, color]

    st.dataframe(
        display.style.apply(highlight_change, axis=1),
        use_container_width=True,
        hide_index=True,
        height=700,
    )

# ════════════════════════════════════════════════════════════════
# Tab 2 – 추이 차트
# ════════════════════════════════════════════════════════════════
with tab2:
    t2_subj = st.radio("과목 필터", ["전체", "공수1", "공수2"], horizontal=True, key="tab2_subj")
    t2_df = df if t2_subj == "전체" else df[df["subject"] == t2_subj]

    if len(dates) < 2:
        st.info("추이 차트는 2일 이상 데이터가 수집되면 표시됩니다.")
    else:
        # 날짜 범위 슬라이더
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]
        range_sel = st.select_slider(
            "날짜 범위",
            options=date_strs,
            value=(date_strs[0], date_strs[-1]),
        )
        start_d = pd.to_datetime(range_sel[0])
        end_d   = pd.to_datetime(range_sel[1])

        chart_df = t2_df[(t2_df["date"] >= start_d) & (t2_df["date"] <= end_d)].copy()
        chart_df["label"] = chart_df["series"] + " " + chart_df["subject"]

        # 교재 선택
        all_labels = sorted(chart_df["label"].unique())
        sel_labels = st.multiselect(
            "교재 선택 (비워두면 전체 표시)",
            all_labels,
            placeholder="교재를 선택하세요...",
        )
        if sel_labels:
            chart_df = chart_df[chart_df["label"].isin(sel_labels)]

        fig = px.line(
            chart_df.sort_values("date"),
            x="date", y="sales_index", color="label",
            markers=True,
            labels={"date": "날짜", "sales_index": "판매지수", "label": "교재"},
            title="교재별 판매지수 추이",
        )
        fig.update_layout(
            hovermode="x unified",
            legend=dict(orientation="v", x=1.01, y=1),
            height=520,
        )
        fig.update_traces(marker=dict(size=6))
        st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════════
# Tab 3 – 시장 인사이트
# ════════════════════════════════════════════════════════════════
with tab3:

    # ── 정량 분석: 항상 최신 CSV에서 실시간 계산 ─────────────────
    from datetime import timedelta

    def calc_ranked(df_sub):
        rows = []
        for d, grp in df_sub.groupby("date"):
            grp = grp.sort_values("sales_index", ascending=False).copy()
            grp["rank"] = range(1, len(grp) + 1)
            rows.append(grp)
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

    st.subheader("📊 정량 분석")
    q_subj = st.radio("과목", ["공수1", "공수2"], horizontal=True, key="insight_subj")

    df_q = df[df["subject"] == q_subj].copy()
    ranked_q = calc_ranked(df_q)

    if not ranked_q.empty:
        latest_q = ranked_q["date"].max()

        # 최근 4주 vs 이전 4주 성장률
        recent4w = df_q[df_q["date"] >= latest_q - timedelta(days=28)]
        prev4w   = df_q[(df_q["date"] >= latest_q - timedelta(days=56)) &
                        (df_q["date"] <  latest_q - timedelta(days=28))]
        r4w_avg  = recent4w.groupby("series")["sales_index"].mean()
        p4w_avg  = prev4w.groupby("series")["sales_index"].mean()
        m4w_chg  = ((r4w_avg - p4w_avg) / p4w_avg * 100).round(1)

        # 최근 30일 순위 평균 + Top10 점유율
        r30    = ranked_q[ranked_q["date"] >= latest_q - timedelta(days=30)]
        days30 = max(r30["date"].nunique(), 1)
        avg_rank  = r30.groupby("series")["rank"].mean().round(1)
        top10_pct = (r30[r30["rank"] <= 10].groupby("series").size() / days30 * 100).round(0)

        summary = pd.DataFrame({
            "평균순위(30일)": avg_rank,
            "4주 성장률(%)": m4w_chg,
            "Top10 점유율(%)": top10_pct,
        }).dropna(subset=["평균순위(30일)"]).sort_values("평균순위(30일)")

        OUR_BOOK = "THE 개념"

        def highlight_own(row, own_idx):
            if row.name in own_idx:
                return ["background-color: #1a3a5c; color: #ffffff; font-weight: bold"] * len(row)
            return [""] * len(row)

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("**최근 급성장 교재 (최근4주 vs 이전4주, 상위 10)**")
            own_surge = summary[summary.index.str.contains(OUR_BOOK, na=False)].copy()
            other_surge = summary[~summary.index.str.contains(OUR_BOOK, na=False)].sort_values("4주 성장률(%)", ascending=False).head(10).copy()
            surge = pd.concat([own_surge, other_surge])
            own_idx_surge = set(own_surge.index)
            surge_disp = surge.copy()
            surge_disp["4주 성장률(%)"] = surge_disp["4주 성장률(%)"].apply(
                lambda v: f"+{v:.1f}%" if pd.notna(v) and v > 0 else (f"{v:.1f}%" if pd.notna(v) else "-")
            )
            surge_disp["평균순위(30일)"] = surge_disp["평균순위(30일)"].apply(
                lambda v: f"{v:.1f}위" if pd.notna(v) else "-"
            )
            st.dataframe(
                surge_disp[["평균순위(30일)", "4주 성장률(%)"]].style.apply(
                    highlight_own, own_idx=own_idx_surge, axis=1
                ),
                use_container_width=True,
            )

        with col_b:
            st.markdown("**상위권 고착 교재 (Top10 점유율)**")
            stable_all = summary[summary["Top10 점유율(%)"] >= 30].sort_values("Top10 점유율(%)", ascending=False)
            own_stable = stable_all[stable_all.index.str.contains(OUR_BOOK, na=False)].copy()
            other_stable = stable_all[~stable_all.index.str.contains(OUR_BOOK, na=False)].copy()
            stable = pd.concat([own_stable, other_stable])
            own_idx_stable = set(own_stable.index)
            stable_disp = stable.copy()
            stable_disp["Top10 점유율(%)"] = stable_disp["Top10 점유율(%)"].apply(lambda v: f"{v:.0f}%" if pd.notna(v) else "-")
            stable_disp["평균순위(30일)"]   = stable_disp["평균순위(30일)"].apply(lambda v: f"{v:.1f}위" if pd.notna(v) else "-")
            st.dataframe(
                stable_disp[["평균순위(30일)", "Top10 점유율(%)"]].style.apply(
                    highlight_own, own_idx=own_idx_stable, axis=1
                ),
                use_container_width=True,
            )

        # 4주 성장률 막대 차트
        chart_data = summary.dropna(subset=["4주 성장률(%)"]).sort_values("4주 성장률(%)", ascending=False).head(15)
        fig_4w = px.bar(
            chart_data.reset_index(),
            x="series", y="4주 성장률(%)",
            color="4주 성장률(%)",
            color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
            title=f"교재별 최근 4주 성장률 ({q_subj})",
            labels={"series": "교재", "4주 성장률(%)": "4주 성장률 (%)"},
        )
        fig_4w.update_layout(height=380, showlegend=False, coloraxis_showscale=False)
        fig_4w.add_hline(y=0, line_dash="dot", line_color="gray")
        st.plotly_chart(fig_4w, use_container_width=True)

    st.divider()

    # ── AI 인사이트: insights.json 읽기 ───────────────────────────
    st.subheader("🤖 AI 인사이트 (Gemini)")

    if not os.path.exists(INSIGHTS_FILE):
        st.info("아직 생성된 인사이트가 없습니다. 왼쪽 사이드바에서 **'인사이트 재생성'** 버튼을 눌러주세요.")
    else:
        with open(INSIGHTS_FILE, "r", encoding="utf-8") as f:
            ins = json.load(f)

        st.caption(
            f"마지막 생성: **{ins.get('generated_at', '-')}**  |  "
            f"데이터 기준: **{ins.get('data_as_of', '-')}**"
        )

        # 시장 트렌드
        trends = ins.get("market_trends", [])
        if trends:
            st.markdown("#### 📌 현재 시장 트렌드")
            for i, t in enumerate(trends, 1):
                st.markdown(f"**{i}.** {t}")
            st.divider()

        # 자사 교재 분석 (THE 개념)
        own_books = ins.get("own_books", [])
        if own_books:
            st.markdown("#### 🏠 자사 교재 분석 (THE 개념)")
            for book in own_books:
                status = book.get("status", "")
                status_icon = {"성장": "🟢", "정체": "🟡", "하락": "🔴"}.get(status, "⚪")
                with st.expander(f"{status_icon} **{book.get('series', '')} {book.get('subject', '')}** — {book.get('summary', '')}"):
                    st.markdown(f"**현황:** `{status_icon} {status}`")
                    st.markdown("**분석**")
                    st.markdown(book.get("analysis", "-"))
                    st.markdown("**개선 방향**")
                    st.markdown(book.get("action", "-"))
            st.divider()

        # 경쟁사 교재 분석
        top3_stable   = ins.get("top3_stable", [])
        # 구형 JSON(competitors)도 호환
        surge_comps   = ins.get("surge_competitors", ins.get("competitors", []))

        if top3_stable or surge_comps:
            st.markdown("#### 📖 경쟁사 교재 분석")

            # ── Top3 고착 교재: 간략 배지 ────────────────────────
            if top3_stable:
                st.markdown("**🏅 상위권 고착 교재**")
                badge_cols = st.columns(max(len(top3_stable), 1))
                for i, book in enumerate(top3_stable):
                    threat      = book.get("blacklabel_threat", "")
                    threat_icon = {"위협": "🔴", "기회": "🟢", "중립": "🟡"}.get(threat, "⚪")
                    with badge_cols[i]:
                        st.markdown(
                            f"{threat_icon} **{book.get('series', '')}**  \n"
                            f"<span style='font-size:0.8em; color:gray'>{book.get('subject', '')} | {book.get('summary', '')}</span>",
                            unsafe_allow_html=True,
                        )
                st.divider()

            # ── 급성장 경쟁 교재: 과목별 탭 + expander ───────────
            if surge_comps:
                st.markdown("**🚀 급성장 경쟁 교재**")
                tab_s1, tab_s2 = st.tabs(["공수1", "공수2"])
                for tab_s, subj in [(tab_s1, "공수1"), (tab_s2, "공수2")]:
                    with tab_s:
                        subj_books = [b for b in surge_comps if b.get("subject") == subj]
                        if not subj_books:
                            st.info(f"{subj} 급성장 교재가 없습니다.")
                        for book in subj_books:
                            threat      = book.get("blacklabel_threat", "")
                            threat_icon = {"위협": "🔴", "기회": "🟢", "중립": "🟡"}.get(threat, "⚪")
                            with st.expander(f"{threat_icon} **{book.get('series', '')}** — {book.get('summary', '')}"):
                                c1, c2 = st.columns([1, 1])
                                with c1:
                                    st.markdown("**상승 원인**")
                                    for j, r in enumerate(book.get("rise_reasons", []), 1):
                                        st.markdown(f"{j}) {r}")
                                    st.markdown(f"**트렌드 판단:** `{book.get('trend_judgment', '-')}`")
                                    st.markdown(f"**경쟁 분석:** {book.get('competition', '-')}")
                                with c2:
                                    st.markdown(f"**THE 개념 관점 — {threat_icon} {threat}**")
                                    st.markdown(book.get("blacklabel_insight", "-"))
                                    st.markdown("**대응 전략**")
                                    st.markdown(book.get("blacklabel_action", "-"))
        elif not own_books:
            st.warning("교재별 인사이트 데이터가 없습니다. 인사이트를 재생성해 주세요.")
