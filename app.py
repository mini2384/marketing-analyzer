import os
import json
import logging
import requests
from flask import Flask, render_template, request, jsonify, send_from_directory, make_response
from dotenv import load_dotenv

# .env 파일에서 환경 변수 불러오기
load_dotenv()

app = Flask(__name__)

# 로깅 설정 (Backend Log 포맷 지정)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def search_serper(query, api_key):
    """
    Serper.dev API를 사용하여 구글 검색 결과를 가져옵니다.
    """
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "gl": "kr",
        "hl": "ko",
        "num": 10
    }
    
    app.logger.info(f"[Serper 검색 요청] 검색어: '{query}'")
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    
    if response.status_code != 200:
        app.logger.error(f"[Serper 검색 실패] 상태 코드: {response.status_code}, 내용: {response.text}")
        raise Exception(f"Serper 검색 중 오류가 발생했습니다. (상태 코드: {response.status_code})")
        
    data = response.json()
    app.logger.info(f"[Serper 검색 완료] 성공적으로 검색 결과를 수신했습니다.")
    return data

def call_gemini(prompt, api_key):
    """
    Gemini REST API를 호출하여 프롬프트에 따른 마케팅 분석 보고서를 생성합니다.
    """
    # 가볍고 빠른 Gemini 3.5 Flash Lite 모델 사용
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,  # 환각(거짓말)을 최소화하기 위해 낮은 온도값 적용
            "topP": 0.8
        }
    }
    
    app.logger.info(f"[Gemini API 호출] 모델: {model_name}, 프롬프트 전송 시작")
    response = requests.post(url, headers=headers, json=payload, timeout=40)
    
    if response.status_code != 200:
        app.logger.error(f"[Gemini API 오류] 상태 코드: {response.status_code}, 내용: {response.text}")
        # 키 오류 친절 안내
        if response.status_code == 400 or response.status_code == 403:
            raise Exception("Gemini API Key가 유효하지 않거나 만료되었습니다. .env 파일의 키를 확인해 주세요.")
        raise Exception(f"Gemini API 호출 중 오류가 발생했습니다. (상태 코드: {response.status_code})")
        
    result_json = response.json()
    try:
        candidate_text = result_json["candidates"][0]["content"]["parts"][0]["text"]
        app.logger.info("[Gemini API 응답 완료] 마케팅 보고서 텍스트 생성 성공")
        return candidate_text
    except (KeyError, IndexError) as e:
        app.logger.error(f"[Gemini 응답 파싱 실패] 예상치 못한 응답 구조: {result_json}")
        raise Exception("Gemini API 응답을 처리하는 중 문제가 발생했습니다.")

@app.route("/")
def index():
    """메인 화면을 렌더링합니다."""
    return render_template("index.html")

@app.route("/manifest.json")
def manifest():
    """PWA 매니페스트 파일을 제공합니다."""
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")

@app.route("/sw.js")
def service_worker():
    """PWA 서비스 워커를 루트 스코프로 제공합니다."""
    response = make_response(send_from_directory("static", "sw.js"))
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Content-Type"] = "application/javascript"
    return response

@app.route("/generate", methods=["POST"])
def generate():
    """
    사용자의 입력을 받아 Serper 검색 후 Gemini로 사실 기반 마케팅 보고서를 생성합니다.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "요청 데이터가 전달되지 않았습니다."}), 400
        
        # 1. 입력값 수신 및 검증 (Backend Validation)
        company_name = data.get("company_name", "").strip()
        purpose = data.get("purpose", "").strip()
        target_audience = data.get("target_audience", "").strip()
        competitors = data.get("competitors", "").strip()
        channels = data.get("channels", "").strip()
        campaign = data.get("campaign", "").strip()
        
        if not company_name:
            return jsonify({"success": False, "error": "기업명을 입력해 주세요."}), 400
        if not purpose:
            return jsonify({"success": False, "error": "분석 목적을 입력해 주세요."}), 400

        app.logger.info(f"[새로운 분석 요청 접수] 기업: {company_name}, 목적: {purpose}")
        
        # 2. 환경 변수에서 API 키 확인
        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        serper_api_key = os.getenv("SERPER_API_KEY", "").strip()
        
        # 기본 예시 키이거나 비어있는 경우 친절하게 안내
        if not gemini_api_key or gemini_api_key == "your_gemini_api_key_here":
            return jsonify({
                "success": False, 
                "error": ".env 파일에 GEMINI_API_KEY가 올바르게 설정되지 않았습니다. 실제 발급받은 키를 .env 파일에 입력해 주세요."
            }), 400
            
        if not serper_api_key or serper_api_key == "your_serper_api_key_here":
            return jsonify({
                "success": False, 
                "error": ".env 파일에 SERPER_API_KEY가 올바르게 설정되지 않았습니다. 실제 발급받은 키를 .env 파일에 입력해 주세요."
            }), 400

        # 3. Serper.dev를 통한 실시간 공식/팩트 검색
        # 기업의 미션, 비전, 핵심가치, 사회·환경적 가치, 마케팅 활동 등 다각도 검색 쿼리 구성
        search_query = f"{company_name} 미션 비전 핵심가치 사회적 환경적 가치 마케팅 {campaign}".strip()
        search_results = search_serper(search_query, serper_api_key)
        
        # 검색 결과에서 유용한 텍스트 발췌 (최대 8개)
        organic_results = search_results.get("organic", [])
        snippets = []
        for idx, item in enumerate(organic_results[:8], 1):
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            snippets.append(f"[{idx}] 제목: {title}\n링크: {link}\n내용: {snippet}\n")
        
        search_context = "\n".join(snippets) if snippets else "검색 결과가 충분하지 않습니다."
        app.logger.info(f"[검색 결과 요약 완료] 총 {len(snippets)}개의 팩트 정보 추출")

        # 4. 팩트 기반 프롬프트 엔지니어링 (가치 체계 및 마케팅 연결성 분석 포함)
        prompt = f"""당신은 기업 철학과 브랜드 전략을 데이터와 사실에 기반하여 심층 분석하는 Senior 마케팅 전략 컨설턴트입니다.

제공된 [실시간 검색 데이터]를 철저히 바탕으로 다음 기업의 마케팅 분석 보고서 초안을 작성하십시오.

### 분석 대상 정보
- 대상 기업명: {company_name}
- 분석 목적: {purpose}
- 주요 관심 타깃: {target_audience if target_audience else '미지정 (일반 타깃)'}
- 주요 경쟁사: {competitors if competitors else '미지정'}
- 관심 마케팅 채널: {channels if channels else '미지정 (주요 공식 채널 위주)'}
- 분석 희망 캠페인: {campaign if campaign else '최신 주요 마케팅 활동'}

### [실시간 검색 데이터]
{search_context}

---
### ⚠️ 작성 규칙 및 안전 가이드라인 (엄격 준수)
1. **절대 없는 사실을 지어내거나 과장(환각)하지 마십시오.**
2. 검색 데이터에 명확한 근거가 없는 내용은 추측하지 말고 **"검색 결과에서 확인 불가 (추가 리서치 필요)"**라고 솔직하고 명확하게 기록하십시오.
3. 숫자가 언급될 경우 출처 데이터에 있는 수치만 인용하십시오.
4. 분석 보고서는 가독성이 좋은 Markdown 형식으로 깔끔하게 작성하십시오.

### 보고서 필수 목차
# [{company_name}] 마케팅 분석 및 기업 가치 연계 보고서

## 1. 기업 가치 체계 (Philosophy & Value System)
- **기업의 미션(Mission)과 비전(Vision)**: 기업이 존재하는 근본 목적과 미래 도달 목표
- **핵심 가치(Core Values)**: 기업 조직과 구성원이 지키는 최우선 원칙과 신념
- **사회적·환경적 가치 (ESG & Sustainability)**: 사회 기여, 친환경, 상생 등 기업의 책임 활동
- **고객에게 제공하려는 핵심 가치 (Customer Value Proposition)**: 고객이 이 브랜드를 통해 실질적으로 얻는 혜택 및 효용
- **기업이 앞으로 추구하는 미래 방향**: 향후 확장하고자 하는 비즈니스 지향점 및 성장 축

## 2. 최근 사업 및 마케팅 활동과 가치의 연결성 분석
- 최근 전개된 주요 사업(신제품/서비스)과 마케팅 캠페인이 기업의 미션 및 핵심 가치와 어떻게 유기적으로 연계되어 있는지 구체적 분석
- 표방하는 철학이 실제 마케팅 메시지 및 고객 경험에 잘 구현되고 있는지에 대한 팩트 기반 평가

## 3. 타깃 고객 및 주요 마케팅 채널 분석
- 핵심 타깃 세그먼트와 실제 활발하게 운영 중인 공식 마케팅 채널(SNS, 유튜브, 블로그, 온·오프라인 등) 분석

## 4. 최근 주요 캠페인 및 차별화 포인트
- 최근 실행된 대표 캠페인 사례 및 경쟁사 대비 독보적인 강점/차별점

## 5. 분석 목적에 맞춘 전략적 제언
- 요청된 분석 목적: '{purpose}'을 달성하기 위한 기업 가치 기반의 구체적인 액션 플랜

## 6. 확인 불가 항목 및 한계점
- 검색 데이터에서 명확히 확인되지 않은 미션/가치/수치 등 추가 검증이 필요한 항목 솔직 명시

## 7. 참고한 공식 출처 및 링크
- 위 검색 결과에 포함된 실제 URL 링크 목록
"""

        # 5. Gemini API 호출
        report = call_gemini(prompt, gemini_api_key)
        
        app.logger.info(f"[보고서 생성 완료] '{company_name}' 분석 보고서 반환")
        return jsonify({
            "success": True,
            "report": report
        })

    except Exception as e:
        app.logger.error(f"[오류 발생] {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    # 개발 서버 실행
    app.logger.info("AI 마케팅 분석기 웹 서버를 시작합니다. (http://127.0.0.1:5000)")
    app.run(host="127.0.0.1", port=5000, debug=True)
