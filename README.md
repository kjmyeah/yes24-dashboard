# Yes24 수학 교재 판매지수 대시보드

## 📊 대시보드 접속

👉 **[대시보드 바로가기](https://share.streamlit.io/kjmyeah/yes24-dashboard/main/app.py)**

## 📖 설명

Yes24 사이트의 수학 교재 판매지수를 실시간으로 확인할 수 있는 대시보드입니다.

### 기능

- **판매지수 크롤링**: Yes24에서 최신 판매지수 수집
- **차트 분석**: 판매지수 추이 시각화
- **AI 인사이트 생성**: Google Gemini API를 이용한 자동 분석

## 🛠️ 로컬 실행 방법

```bash
# 1. 저장소 클론
git clone https://github.com/kjmyeah/yes24-dashboard.git
cd yes24-dashboard

# 2. 필수 라이브러리 설치
pip install -r requirements.txt

# 3. 대시보드 실행
streamlit run app.py
```

## 📋 필요한 환경 설정

`.env` 파일을 생성하고 Gemini API 키를 입력하세요:

```
GEMINI_API_KEY=your_api_key_here
```

---

**Made with Streamlit** 💙
