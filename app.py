import os
import json
import time
import logging
import requests
from flask import Flask, render_template, request, jsonify, send_from_directory, make_response, session
from dotenv import load_dotenv

# .env 파일에서 환경 변수 불러오기
load_dotenv()

app = Flask(__name__)
# 보안 세션 암호화 키 설정
app.secret_key = os.getenv("SECRET_KEY", "marketing-analyzer-auth-key-0927-secure")
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24시간 동안 세션 유지

# 로깅 설정 (Backend Log 포맷 지정)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ==============================================================================
# 비밀번호 보안 및 정책 상수 & 메모리 저장소
# ==============================================================================
CORRECT_PIN = "0927"         # 설정된 4자리 비밀번호
MAX_ATTEMPTS = 5            # 최대 허용 실패 횟수
LOCKOUT_SECONDS = 3600      # 5회 실패 시 잠금 시간 (1시간 = 3,600초)
AUTH_LIFETIME_SECONDS = 86400  # 1회 인증 시 유지 시간 (정확히 24시간 = 86,400초)

# IP 기반 락아웃 추적 딕셔너리 (세션 쿠키 삭제 우회 차단용 이중 방어)
# 형식: { ip_address: { "attempts": int, "locked_until": float } }
ip_lockout_store = {}

def get_client_ip():
    """클라이언트 IP 주소를 반환합니다 (프록시/Vercel X-Forwarded-For 지원)."""
    from flask import has_request_context
    if has_request_context():
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.remote_addr or "unknown_ip"
    return "127.0.0.1"

def get_auth_state():
    """현재 클라이언트의 세션 및 IP 기반 잠금/시도 상태를 통합 계산합니다."""
    ip = get_client_ip()
    now = time.time()
    
    # 1. 세션 데이터 확인
    session_attempts = session.get("pin_attempts", 0)
    session_locked_until = session.get("pin_locked_until", 0)
    
    # 2. IP 데이터 확인
    ip_data = ip_lockout_store.get(ip, {"attempts": 0, "locked_until": 0})
    ip_attempts = ip_data.get("attempts", 0)
    ip_locked_until = ip_data.get("locked_until", 0)
    
    # 세션과 IP 중 더 큰(엄격한) 제약 값을 적용
    max_locked_until = max(session_locked_until, ip_locked_until)
    max_attempts = max(session_attempts, ip_attempts)
    
    # 잠금 기간이 만료되었으면 자동 초기화
    if max_locked_until > 0 and now >= max_locked_until:
        session["pin_attempts"] = 0
        session["pin_locked_until"] = 0
        if ip in ip_lockout_store:
            ip_lockout_store[ip] = {"attempts": 0, "locked_until": 0}
        return {"locked": False, "attempts": 0, "remaining_seconds": 0}
        
    if max_locked_until > now:
        remaining = int(max_locked_until - now)
        return {"locked": True, "attempts": max_attempts, "remaining_seconds": remaining}
        
    return {"locked": False, "attempts": max_attempts, "remaining_seconds": 0}

def record_failed_attempt():
    """비밀번호 오답 시 실패 횟수를 1 증가시키고, 5회 도달 시 1시간 잠금을 적용합니다."""
    ip = get_client_ip()
    now = time.time()
    
    state = get_auth_state()
    new_attempts = state["attempts"] + 1
    
    if new_attempts >= MAX_ATTEMPTS:
        locked_until = now + LOCKOUT_SECONDS
        session["pin_attempts"] = new_attempts
        session["pin_locked_until"] = locked_until
        ip_lockout_store[ip] = {"attempts": new_attempts, "locked_until": locked_until}
        app.logger.warning(f"[보안 경고] IP {ip} 비밀번호 5회 연속 실패로 1시간 동안 잠금 처리됨")
        return {"locked": True, "attempts": new_attempts, "remaining_seconds": LOCKOUT_SECONDS}
    else:
        session["pin_attempts"] = new_attempts
        session["pin_locked_until"] = 0
        ip_lockout_store[ip] = {"attempts": new_attempts, "locked_until": 0}
        app.logger.info(f"[보안 알림] IP {ip} 비밀번호 오답 (시도 횟수: {new_attempts}/{MAX_ATTEMPTS})")
        return {"locked": False, "attempts": new_attempts, "remaining_seconds": 0}

def clear_auth_failures():
    """인증 성공 시 시도 횟수 및 잠금 상태를 초기화합니다."""
    from flask import has_request_context
    ip = get_client_ip()
    if has_request_context():
        session["pin_attempts"] = 0
        session["pin_locked_until"] = 0
    if ip in ip_lockout_store:
        ip_lockout_store[ip] = {"attempts": 0, "locked_until": 0}

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

def find_official_channels(company_name, api_key):
    """
    기업의 공식 홈페이지, 공식 인스타그램, 공식 유튜브 채널 링크를 실시간 검색으로 추출합니다.
    """
    channels = {"homepage": None, "instagram": None, "youtube": None}
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }
    
    # 1. 1차 종합 검색
    query = f"{company_name} 공식 홈페이지 인스타그램 유튜브"
    try:
        res = requests.post(url, headers=headers, json={"q": query, "gl": "kr", "hl": "ko", "num": 10}, timeout=10)
        if res.status_code == 200:
            for item in res.json().get("organic", []):
                link = item.get("link", "")
                # 인스타그램 공식 프로필
                if "instagram.com/" in link and not channels["instagram"] and "/p/" not in link:
                    channels["instagram"] = link
                # 유튜브 공식 채널
                elif ("youtube.com/@" in link or "youtube.com/channel" in link or "youtube.com/c/" in link) and not channels["youtube"] and "/watch" not in link:
                    channels["youtube"] = link
                # 공식 홈페이지
                elif not channels["homepage"] and not any(x in link for x in ["instagram.com", "youtube.com", "facebook.com", "namu.wiki", "blog.naver.com", "tistory.com", "news", "brunch.co.kr"]):
                    channels["homepage"] = link

        # 2. 누락된 소셜 채널이 있는 경우 타깃 검색 보강
        missing = [k for k in ["youtube", "instagram"] if not channels[k]]
        if missing:
            target_q = f"{company_name} 공식 " + " ".join(missing) + " 바로가기"
            res_extra = requests.post(url, headers=headers, json={"q": target_q, "gl": "kr", "hl": "ko", "num": 5}, timeout=10)
            if res_extra.status_code == 200:
                for item in res_extra.json().get("organic", []):
                    link = item.get("link", "")
                    if "instagram.com/" in link and not channels["instagram"] and "/p/" not in link:
                        channels["instagram"] = link
                    elif "youtube.com/" in link and not channels["youtube"]:
                        channels["youtube"] = link
    except Exception as e:
        app.logger.warning(f"[공식 채널 탐색 경고] {e}")

    app.logger.info(f"[공식 채널 탐색 결과] {company_name} -> {channels}")
    return channels

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
def is_session_authenticated():
    """
    세션 인증 여부 및 24시간 만료 여부를 판별합니다.
    - 인증 시점으로부터 24시간(86,400초) 초과 시 자동 만료 및 세션 제거
    """
    if not session.get("authenticated"):
        return False, 0
        
    now = time.time()
    expires_at = session.get("auth_expires_at", 0)
    
    # 24시간 만료 검증
    if expires_at <= 0 or now >= expires_at:
        session.pop("authenticated", None)
        session.pop("auth_expires_at", None)
        session.pop("authenticated_at", None)
        app.logger.info(f"[보안 세션 만료] 24시간이 경과하여 세션이 자동 잠금되었습니다. (IP: {get_client_ip()})")
        return False, 0
        
    remaining_seconds = int(expires_at - now)
    return True, remaining_seconds

@app.route("/api/auth-status", methods=["GET"])
def auth_status():
    """현재 사용자의 세션 인증 상태, 24시간 만료 시간 및 잠금 상태를 반환합니다."""
    state = get_auth_state()
    is_authenticated, auth_remaining = is_session_authenticated()
    attempts_left = max(0, MAX_ATTEMPTS - state["attempts"])
    
    return jsonify({
        "success": True,
        "authenticated": is_authenticated,
        "auth_remaining_seconds": auth_remaining,  # 24시간 중 남은 유효 시간 (초)
        "locked": state["locked"],
        "remaining_seconds": state["remaining_seconds"],
        "attempts_left": attempts_left,
        "max_attempts": MAX_ATTEMPTS
    })

@app.route("/api/verify-pin", methods=["POST"])
def verify_pin():
    """
    4자리 비밀번호(PIN)를 검증합니다.
    - 정답: '0927'
    - 인증 성공 시: 정확히 24시간(86,400초) 동안만 인증 유지
    - 5회 이상 오답 시: 1시간(3,600초) 잠금 적용
    """
    state = get_auth_state()
    if state["locked"]:
        rem_sec = state["remaining_seconds"]
        minutes = rem_sec // 60
        seconds = rem_sec % 60
        return jsonify({
            "success": False,
            "locked": True,
            "remaining_seconds": rem_sec,
            "error": f"비밀번호를 5회 잘못 입력하여 계정이 잠겼습니다. ({minutes}분 {seconds}초 후 재시도 가능)"
        }), 429

    data = request.get_json() or {}
    pin = str(data.get("pin", "")).strip()

    if not pin:
        return jsonify({
            "success": False,
            "locked": False,
            "error": "비밀번호를 입력해 주세요."
        }), 400

    # 비밀번호 검증 (0927)
    if pin == CORRECT_PIN:
        # 인증 성공: 24시간 유효 기간 설정
        now = time.time()
        session["authenticated"] = True
        session["authenticated_at"] = now
        session["auth_expires_at"] = now + AUTH_LIFETIME_SECONDS  # 24시간 후 만료
        session.permanent = True
        clear_auth_failures()
        app.logger.info(f"[보안 인증 성공] IP {get_client_ip()} 정상 인증 완료 (24시간 동안 유지)")
        return jsonify({
            "success": True,
            "authenticated": True,
            "auth_remaining_seconds": AUTH_LIFETIME_SECONDS,
            "message": "인증에 성공했습니다. 24시간 동안 유지됩니다."
        })
    else:
        # 비밀번호 오답: 실패 기록 및 5회 초과 시 1시간 잠금
        fail_state = record_failed_attempt()
        if fail_state["locked"]:
            rem_sec = fail_state["remaining_seconds"]
            return jsonify({
                "success": False,
                "locked": True,
                "remaining_seconds": rem_sec,
                "error": "비밀번호를 5회 연속 잘못 입력하여 1시간 동안 입력이 차단되었습니다."
            }), 429
        else:
            attempts_left = MAX_ATTEMPTS - fail_state["attempts"]
            return jsonify({
                "success": False,
                "locked": False,
                "attempts_left": attempts_left,
                "error": f"비밀번호가 올바르지 않습니다. (남은 기회: {attempts_left}회)"
            }), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    """세션 인증을 해제하고 즉시 다시 잠금 상태로 전환합니다."""
    session.pop("authenticated", None)
    session.pop("auth_expires_at", None)
    session.pop("authenticated_at", None)
    return jsonify({"success": True, "message": "로그아웃되었습니다."})

@app.route("/generate", methods=["POST"])
def generate():
    """
    사용자의 입력을 받아 Serper 검색 후 Gemini로 사실 기반 마케팅 보고서를 생성합니다.
    (24시간 내 유효한 비밀번호 인증 필수)
    """
    # 0. 보안 인증 및 24시간 유효성 확인
    is_authenticated, _ = is_session_authenticated()
    if not is_authenticated:
        return jsonify({
            "success": False,
            "error": "보안 인증이 필요하거나 24시간 유효 기간이 만료되었습니다. 비밀번호를 다시 입력해 주세요."
        }), 401

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

        # 3. Serper.dev를 통한 실시간 공식/팩트 검색 & 공식 채널(홈페이지, 인스타, 유튜브) 탐색
        # 3-1. 기업 가치 체계 및 마케팅 전략 검색
        search_query = f"{company_name} 미션 비전 핵심가치 사회적 환경적 가치 마케팅 {campaign}".strip()
        search_results = search_serper(search_query, serper_api_key)
        
        # 3-2. 기업의 공식 홈페이지, 공식 인스타그램, 공식 유튜브 채널 링크 정밀 추출
        official_channels = find_official_channels(company_name, serper_api_key)
        
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

        hp_link = official_channels.get('homepage')
        insta_link = official_channels.get('instagram')
        yt_link = official_channels.get('youtube')

        channels_text = f"""- 공식 홈페이지: {hp_link if hp_link else '검색 결과 없음 (추가 리서치 필요)'}
- 공식 인스타그램: {insta_link if insta_link else '검색 결과 없음 (추가 리서치 필요)'}
- 공식 유튜브 채널: {yt_link if yt_link else '검색 결과 없음 (추가 리서치 필요)'}"""

        # 4. 팩트 기반 프롬프트 엔지니어링 (가치 체계 및 마케팅 연결성 분석 포함)
        prompt = f"""당신은 기업 철학과 브랜드 전략을 데이터와 사실에 기반하여 심층 분석하는 Senior 마케팅 전략 컨설턴트입니다.

제공된 [실시간 검색 데이터]와 [기업 공식 채널 링크 데이터]를 철저히 바탕으로 다음 기업의 마케팅 분석 보고서 초안을 작성하십시오.

### 분석 대상 정보
- 대상 기업명: {company_name}
- 분석 목적: {purpose}
- 주요 관심 타깃: {target_audience if target_audience else '미지정 (일반 타깃)'}
- 주요 경쟁사: {competitors if competitors else '미지정'}
- 관심 마케팅 채널: {channels if channels else '미지정 (주요 공식 채널 위주)'}
- 분석 희망 캠페인: {campaign if campaign else '최신 주요 마케팅 활동'}

### [기업 공식 채널 링크 데이터]
{channels_text}

### [실시간 검색 데이터]
{search_context}

---
### ⚠️ 작성 규칙 및 안전 가이드라인 (엄격 준수)
1. **절대 없는 사실을 지어내거나 과장(환각)하지 마십시오.**
2. 검색 데이터에 명확한 근거가 없는 내용은 추측하지 말고 **"검색 결과에서 확인 불가 (추가 리서치 필요)"**라고 솔직하고 명확하게 기록하십시오.
3. 숫자가 언급될 경우 출처 데이터에 있는 수치만 인용하십시오.
4. 분석 보고서는 가독성이 좋은 Markdown 형식으로 깔끔하게 작성하십시오.
5. **보고서의 맨 마지막 목차에는 제공된 공식 홈페이지, 공식 인스타그램, 공식 유튜브 링크를 반드시 클릭 가능한 마크다운 링크로 명시하십시오.**

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

## 7. 참고한 공식 출처 및 기사 링크
- 위 검색 결과에 포함된 실제 URL 링크 목록

## 8. 기업 공식 채널 바로가기 (Official Channels)
- 🌐 **공식 홈페이지**: {f'[{company_name} 공식 홈페이지 바로가기]({hp_link})' if hp_link else '확인 불가 (추가 리서치 필요)'}
- 📸 **공식 인스타그램**: {f'[{company_name} 공식 인스타그램 바로가기]({insta_link})' if insta_link else '확인 불가 (추가 리서치 필요)'}
- 📺 **공식 유튜브**: {f'[{company_name} 공식 유튜브 채널 바로가기]({yt_link})' if yt_link else '확인 불가 (추가 리서치 필요)'}
"""

        # 5. Gemini API 호출
        report = call_gemini(prompt, gemini_api_key)
        
        # 6. 보고서 맨 마지막에 공식 채널 링크가 누락되지 않도록 보장하는 후처리
        official_channel_block = f"""\n\n---\n\n## 8. 기업 공식 채널 바로가기\n- 🌐 **공식 홈페이지**: {f'[{company_name} 공식 홈페이지 바로가기]({hp_link})' if hp_link else '확인 불가 (추가 리서치 필요)'}\n- 📸 **공식 인스타그램**: {f'[{company_name} 공식 인스타그램 바로가기]({insta_link})' if insta_link else '확인 불가 (추가 리서치 필요)'}\n- 📺 **공식 유튜브**: {f'[{company_name} 공식 유튜브 채널 바로가기]({yt_link})' if yt_link else '확인 불가 (추가 리서치 필요)'}\n"""

        if "기업 공식 채널 바로가기" not in report:
            report += official_channel_block
        
        app.logger.info(f"[보고서 생성 완료] '{company_name}' 분석 보고서 반환 (최하단 공식 채널 링크 포함)")
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
