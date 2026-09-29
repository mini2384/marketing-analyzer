# 📊 AI 기업 마케팅 분석기 (MarketInsight AI)

실시간 공식 웹 데이터(Serper.dev)와 최신 인공지능(Google Gemini 3.5 Flash Lite)을 결합하여, 기업의 가치 체계와 최신 마케팅 활동을 팩트 기반으로 심층 분석하는 풀스택 웹 애플리케이션입니다.

---

## ✨ 주요 특징 및 핵심 기능

1. **실시간 공식 팩트 검색 (Serper.dev 연동)**
   - 기업의 공식 홈페이지, 블로그, 보도자료, 유튜브 등 공인된 웹 데이터를 실시간으로 수집합니다.
2. **환각(Hallucination) 방지 프롬프트 엔지니어링**
   - AI의 거짓 답변을 차단하고, 검색 결과에서 확인되지 않는 항목은 "확인 불가 (추가 리서치 필요)"로 명시하는 철저한 사실 기반 보고서를 생성합니다.
3. **기업 가치 체계 & 마케팅 연결성 심층 분석**
   - 기업의 미션, 비전, 핵심 가치, 사회적·환경적 가치(ESG), 고객 제공 가치 및 미래 방향성 도출
   - 최근 사업/마케팅 캠페인이 기업의 고유 철학과 어떻게 유기적으로 연계되어 있는지 분석
4. **사용자 친화적 인터페이스 (UI/UX)**
   - 프론트엔드/백엔드 이중 유효성 검증
   - 로딩 스피너 및 실시간 상태 피드백
   - **📋 원클릭 보고서 복사** 및 **💾 Markdown(.md) 파일 다운로드** 지원
5. **안전한 보안 아키텍처**
   - API Key 등 민감 정보는 `.env`로 격리 관리하며 `.gitignore`를 통해 Git 추적에서 제외

---

## 🛠 기술 스택

- **Backend**: Python 3, Flask, Requests, Python-dotenv
- **Frontend**: HTML5, Modern CSS (Responsive Design), Vanilla JavaScript (ES6+), Marked.js
- **AI & APIs**: Google Gemini 3.5 Flash Lite API, Serper.dev Google Search API
- **Version Control**: Git, GitHub

---

## 📁 프로젝트 구조

```text
marketing-analyzer/
├── app.py                  # Flask 백엔드 서버 (Serper 검색 & Gemini AI 분석 파이프라인)
├── requirements.txt        # 의존성 패키지 목록
├── .env.example            # 환경변수 설정 템플릿
├── .gitignore              # Git 무시 목록 (venv, .env 등 제외)
├── README.md               # 프로젝트 안내 문서
├── templates/
│   └── index.html          # 메인 웹 페이지 템플릿
└── static/
    ├── css/
    │   └── style.css       # 모던 반응형 스타일시트
    └── js/
        └── app.js          # 비동기 요청(Fetch) 및 클라이언트 인터랙션 로직
```

---

## 🚀 빠른 시작 가이드 (Quick Start)

### 1. 저장소 클론 및 이동
```bash
git clone https://github.com/mini2384/marketing-analyzer.git
cd marketing-analyzer
```

### 2. 가상환경 생성 및 활성화
```powershell
# 가상환경 생성
py -m venv venv

# Windows PowerShell에서 활성화
.\venv\Scripts\Activate.ps1
```

### 3. 필수 패키지 설치
```powershell
py -m pip install -r requirements.txt
```

### 4. 환경 변수(.env) 설정
`.env.example`을 복사하여 `.env` 파일을 생성하고 발급받은 API 키를 입력합니다:
```powershell
Copy-Item .env.example .env
notepad .env
```

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
SERPER_API_KEY=your_serper_api_key_here
```
- [Google AI Studio (Gemini API 키 무료 발급)](https://aistudio.google.com/)
- [Serper.dev (실시간 구글 검색 키 무료 2,500회 발급)](https://serper.dev/)

### 5. 서버 실행
```powershell
py app.py
```
브라우저에서 `http://127.0.0.1:5000` 으로 접속하여 마케팅 분석을 시작하세요!

---

## 📄 라이선스
MIT License
