/**
 * AI 기업 마케팅 분석기 - 프론트엔드 비동기 제어 스크립트
 */

document.addEventListener("DOMContentLoaded", () => {
    // =========================================================================
    // 🔐 0. 보안 비밀번호(PIN) 잠금 제어 모듈
    // =========================================================================
    const lockOverlay = document.getElementById("lock-overlay");
    const lockModal = document.getElementById("lock-modal");
    const pinDots = [
        document.getElementById("dot-0"),
        document.getElementById("dot-1"),
        document.getElementById("dot-2"),
        document.getElementById("dot-3")
    ];
    const pinHiddenInput = document.getElementById("pin-hidden-input");
    const lockMessage = document.getElementById("lock-message");
    const lockTimerBox = document.getElementById("lock-timer-box");
    const lockCountdown = document.getElementById("lock-countdown");
    const pinKeypad = document.getElementById("pin-keypad");
    const pinSubmitBtn = document.getElementById("pin-submit-btn");
    const relockBtn = document.getElementById("relock-btn");

    let enteredPin = "";
    let lockTimerInterval = null;
    let isVerifying = false;

    /**
     * PIN 인디케이터 도트 UI 동기화
     */
    function updatePinDots() {
        pinDots.forEach((dot, idx) => {
            if (idx < enteredPin.length) {
                dot.classList.add("filled");
            } else {
                dot.classList.remove("filled");
            }
        });
        pinSubmitBtn.disabled = (enteredPin.length !== 4) || lockTimerInterval !== null;
    }

    /**
     * 잠금 모달 흔들림(shake) 애니메이션
     */
    function shakeLockModal() {
        lockModal.classList.remove("shake");
        // reflow 강제
        void lockModal.offsetWidth;
        lockModal.classList.add("shake");
        setTimeout(() => lockModal.classList.remove("shake"), 500);
    }

    /**
     * 잠금 상태 메시지 출력
     */
    function showLockMsg(msg, isSuccess = false) {
        lockMessage.textContent = msg;
        if (isSuccess) {
            lockMessage.classList.add("success");
        } else {
            lockMessage.classList.remove("success");
        }
    }

    /**
     * 1시간 잠금 카운트다운 타이머 시작
     */
    function startLockoutTimer(remainingSeconds) {
        if (lockTimerInterval) {
            clearInterval(lockTimerInterval);
        }

        // 입력 UI 비활성화
        pinKeypad.querySelectorAll(".key-btn").forEach(btn => btn.disabled = true);
        pinHiddenInput.disabled = true;
        pinSubmitBtn.disabled = true;
        lockTimerBox.classList.remove("hidden");

        let timeLeft = remainingSeconds;

        function renderTimer() {
            if (timeLeft <= 0) {
                clearInterval(lockTimerInterval);
                lockTimerInterval = null;
                lockTimerBox.classList.add("hidden");
                pinKeypad.querySelectorAll(".key-btn").forEach(btn => btn.disabled = false);
                pinHiddenInput.disabled = false;
                showLockMsg("1시간 잠금이 해제되었습니다. 다시 시도해 주세요.", true);
                enteredPin = "";
                updatePinDots();
                pinHiddenInput.focus();
                return;
            }

            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            const minStr = String(minutes).padStart(2, "0");
            const secStr = String(seconds).padStart(2, "0");
            lockCountdown.textContent = `${minStr}분 ${secStr}초`;
            timeLeft--;
        }

        renderTimer();
        lockTimerInterval = setInterval(renderTimer, 1000);
    }

    /**
     * 서버에 PIN 검증 요청
     */
    async function verifyPinOnServer() {
        if (isVerifying || enteredPin.length !== 4 || lockTimerInterval !== null) return;
        isVerifying = true;
        showLockMsg("비밀번호 확인 중...");

        try {
            const res = await fetch("/api/verify-pin", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pin: enteredPin })
            });

            const data = await res.json();

            if (res.ok && data.success) {
                showLockMsg("🔓 인증 성공! 24시간 동안 유지됩니다.", true);
                enteredPin = "";
                updatePinDots();
                
                // 24시간 후 자동 재잠금 타이머 등록
                scheduleAutoRelock(data.auth_remaining_seconds || 86400);

                setTimeout(() => {
                    lockOverlay.classList.add("unlocked");
                    showLockMsg("");
                }, 400);
            } else {
                shakeLockModal();
                enteredPin = "";
                updatePinDots();

                if (data.locked) {
                    showLockMsg("비밀번호를 5회 잘못 입력하여 계정이 잠겼습니다.");
                    startLockoutTimer(data.remaining_seconds || 3600);
                } else {
                    showLockMsg(data.error || "비밀번호가 올바르지 않습니다.");
                }
            }
        } catch (err) {
            console.error("PIN 검증 오류:", err);
            showLockMsg("서버 통신 중 오류가 발생했습니다. 다시 시도해 주세요.");
            shakeLockModal();
            enteredPin = "";
            updatePinDots();
        } finally {
            isVerifying = false;
        }
    }

    /**
     * 숫자 입력 처리
     */
    function appendDigit(digit) {
        if (lockTimerInterval !== null || isVerifying) return;
        if (enteredPin.length < 4) {
            enteredPin += digit;
            updatePinDots();
            if (enteredPin.length === 4) {
                verifyPinOnServer();
            }
        }
    }

    /**
     * 한 자리 지우기
     */
    function backspacePin() {
        if (lockTimerInterval !== null || isVerifying) return;
        if (enteredPin.length > 0) {
            enteredPin = enteredPin.slice(0, -1);
            updatePinDots();
        }
    }

    /**
     * 전체 지우기
     */
    function clearPin() {
        if (lockTimerInterval !== null || isVerifying) return;
        enteredPin = "";
        updatePinDots();
    }

    // 가상 키패드 클릭 이벤트 바인딩
    pinKeypad.querySelectorAll(".key-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const key = btn.getAttribute("data-key");
            if (key !== null) {
                appendDigit(key);
            }
        });
    });

    document.getElementById("key-clear")?.addEventListener("click", clearPin);
    document.getElementById("key-backspace")?.addEventListener("click", backspacePin);
    pinSubmitBtn?.addEventListener("click", verifyPinOnServer);

    // 하드웨어 키보드 입력 지원
    window.addEventListener("keydown", (e) => {
        // 잠금 화면이 활성화되어 있을 때만 가로채기
        if (lockOverlay.classList.contains("unlocked")) return;

        if (e.key >= "0" && e.key <= "9") {
            e.preventDefault();
            appendDigit(e.key);
        } else if (e.key === "Backspace") {
            e.preventDefault();
            backspacePin();
        } else if (e.key === "Escape" || e.key.toLowerCase() === "c") {
            e.preventDefault();
            clearPin();
        } else if (e.key === "Enter" && enteredPin.length === 4) {
            e.preventDefault();
            verifyPinOnServer();
        }
    });

    // 다시 잠그기(Relock) 버튼 이벤트
    relockBtn?.addEventListener("click", async () => {
        try {
            await fetch("/api/logout", { method: "POST" });
        } catch (e) {
            console.error("로그아웃 오류:", e);
        }
        if (autoRelockTimeout) {
            clearTimeout(autoRelockTimeout);
            autoRelockTimeout = null;
        }
        enteredPin = "";
        updatePinDots();
        showLockMsg("");
        lockOverlay.classList.remove("unlocked");
        pinHiddenInput.focus();
    });

    /**
     * 24시간 경과 시 클라이언트 자동 잠금 타이머 등록
     */
    let autoRelockTimeout = null;
    function scheduleAutoRelock(remainingSeconds) {
        if (autoRelockTimeout) {
            clearTimeout(autoRelockTimeout);
            autoRelockTimeout = null;
        }

        if (remainingSeconds > 0) {
            // 남은 초(최대 86400초 = 24시간) 후 잠금 화면 활성화
            // 안전한 타이머 설정 (밀리초 변환)
            autoRelockTimeout = setTimeout(() => {
                lockOverlay.classList.remove("unlocked");
                showLockMsg("24시간 유효 기간이 만료되어 다시 잠겼습니다. 비밀번호를 입력해 주세요.");
                enteredPin = "";
                updatePinDots();
                pinHiddenInput.focus();
            }, remainingSeconds * 1000);
        }
    }

    /**
     * 초기 인증 및 락아웃 상태 서버 동기화
     */
    async function checkInitialAuthStatus() {
        try {
            const res = await fetch("/api/auth-status");
            const data = await res.json();

            if (data.authenticated) {
                // 이미 인증된 세션 (24시간 이내)
                lockOverlay.classList.add("unlocked");
                // 24시간 남은 시간 타이머 스케줄링
                scheduleAutoRelock(data.auth_remaining_seconds);
            } else {
                lockOverlay.classList.remove("unlocked");
                if (data.locked) {
                    startLockoutTimer(data.remaining_seconds);
                    showLockMsg("비밀번호 5회 오류로 계정이 잠겨 있습니다.");
                } else if (data.attempts_left < 5) {
                    showLockMsg(`남은 비밀번호 입력 기회: ${data.attempts_left}회`);
                }
                pinHiddenInput.focus();
            }
        } catch (e) {
            console.error("인증 상태 확인 실패:", e);
            lockOverlay.classList.remove("unlocked");
        }
    }

    // 앱 시작 시 즉시 인증 상태 확인
    checkInitialAuthStatus();

    // =========================================================================
    // 1. DOM 요소 취득 및 메인 앱 로직
    // =========================================================================
    const form = document.getElementById("analyze-form");
    const submitBtn = document.getElementById("submit-btn");
    const btnText = submitBtn.querySelector(".btn-text");
    
    // 입력 필드
    const companyInput = document.getElementById("company_name");
    const purposeInput = document.getElementById("purpose");
    const targetAudienceInput = document.getElementById("target_audience");
    const competitorsInput = document.getElementById("competitors");
    const channelsInput = document.getElementById("channels");
    const campaignInput = document.getElementById("campaign");

    // 에러 표시 엘리먼트
    const errorCompany = document.getElementById("error-company_name");
    const errorPurpose = document.getElementById("error-purpose");
    const alertBox = document.getElementById("alert-box");
    const alertMessage = document.getElementById("alert-message");

    // 상태 및 결과 영역
    const loadingSpinner = document.getElementById("loading-spinner");
    const resultSection = document.getElementById("result-section");
    const reportContent = document.getElementById("report-content");
    const copyBtn = document.getElementById("copy-btn");
    const downloadBtn = document.getElementById("download-btn");

    // 현재 생성된 원본 보고서 마크다운 저장 변수
    let currentRawReport = "";
    let currentCompanyName = "";

    /**
     * 필드별 에러 초기화 함수
     */
    function clearErrors() {
        errorCompany.textContent = "";
        errorPurpose.textContent = "";
        companyInput.classList.remove("input-error");
        purposeInput.classList.remove("input-error");
        alertBox.classList.add("hidden");
        alertMessage.textContent = "";
    }

    /**
     * 프론트엔드 입력값 검증 (Frontend Validation)
     */
    function validateInputs() {
        clearErrors();
        let isValid = true;

        if (!companyInput.value.trim()) {
            errorCompany.textContent = "분석할 기업명을 입력해 주세요.";
            companyInput.classList.add("input-error");
            isValid = false;
        }

        if (!purposeInput.value.trim()) {
            errorPurpose.textContent = "분석 목적을 입력해 주세요.";
            purposeInput.classList.add("input-error");
            isValid = false;
        }

        return isValid;
    }

    /**
     * 에러 메시지 팝업 표시 함수
     */
    function showError(message) {
        alertMessage.textContent = message;
        alertBox.classList.remove("hidden");
        // 사용자가 볼 수 있도록 에러 영역으로 부드럽게 스크롤
        alertBox.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    /**
     * 로딩 상태 토글 함수
     */
    function setLoading(isLoading) {
        if (isLoading) {
            submitBtn.disabled = true;
            btnText.textContent = "⏳ 분석 보고서 생성 중...";
            loadingSpinner.classList.remove("hidden");
            resultSection.classList.add("hidden");
            alertBox.classList.add("hidden");
        } else {
            submitBtn.disabled = false;
            btnText.textContent = "사실 기반 마케팅 보고서 생성";
            loadingSpinner.classList.add("hidden");
        }
    }

    /**
     * 폼 제출(Submit) 이벤트 핸들러
     */
    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        // 1. 유효성 검사
        if (!validateInputs()) {
            return;
        }

        // 2. 요청 데이터 수집
        currentCompanyName = companyInput.value.trim();
        const requestData = {
            company_name: currentCompanyName,
            purpose: purposeInput.value.trim(),
            target_audience: targetAudienceInput.value.trim(),
            competitors: competitorsInput.value.trim(),
            channels: channelsInput.value.trim(),
            campaign: campaignInput.value.trim()
        };

        // 3. 로딩 상태 시작
        setLoading(true);

        try {
            // 4. Flask 백엔드 /generate 엔드포인트 비동기 요청 (Fetch)
            const response = await fetch("/generate", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(requestData)
            });

            const data = await response.json();

            // 5. 응답 결과 처리
            if (response.status === 401) {
                lockOverlay.classList.remove("unlocked");
                showLockMsg("인증이 만료되었거나 필요합니다. 비밀번호를 입력해 주세요.");
                return;
            }

            if (!response.ok || !data.success) {
                const errorMessage = data.error || `서버 오류가 발생했습니다. (상태 코드: ${response.status})`;
                showError(errorMessage);
                return;
            }

            // 보고서 저장 및 마크다운 렌더링
            currentRawReport = data.report;
            if (typeof marked !== "undefined") {
                reportContent.innerHTML = marked.parse(currentRawReport);
            } else {
                reportContent.textContent = currentRawReport;
            }

            // 결과 화면 표시 및 스크롤 이동
            resultSection.classList.remove("hidden");
            resultSection.scrollIntoView({ behavior: "smooth", block: "start" });

        } catch (err) {
            console.error("통신 오류:", err);
            showError("네트워크 통신 중 오류가 발생했습니다. Flask 서버가 실행 중인지 확인해 주세요.");
        } finally {
            setLoading(false);
        }
    });

    /**
     * 결과 클립보드 복사 버튼 핸들러
     */
    copyBtn.addEventListener("click", async () => {
        if (!currentRawReport) return;

        try {
            await navigator.clipboard.writeText(currentRawReport);
            const originalText = copyBtn.innerHTML;
            copyBtn.innerHTML = "✅ 복사 완료!";
            copyBtn.style.borderColor = "#10b981";
            copyBtn.style.color = "#059669";

            setTimeout(() => {
                copyBtn.innerHTML = originalText;
                copyBtn.style.borderColor = "";
                copyBtn.style.color = "";
            }, 2000);
        } catch (err) {
            console.error("클립보드 복사 실패:", err);
            alert("클립보드 복사에 실패했습니다. 브라우저 권한을 확인해 주세요.");
        }
    });

    /**
     * 마크다운(.md) 파일 다운로드 버튼 핸들러
     */
    downloadBtn.addEventListener("click", () => {
        if (!currentRawReport) return;

        // 파일명 생성 (특수문자 정제)
        const safeName = currentCompanyName.replace(/[^a-zA-Z0-9가-힣_-]/g, "_");
        const filename = `${safeName}_마케팅_분석_보고서.md`;

        // Blob 객체 생성 및 다운로드 트리거
        const blob = new Blob([currentRawReport], { type: "text/markdown;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });

    // 실시간 입력 시 에러 붉은 표시 자동 해제
    companyInput.addEventListener("input", () => {
        if (companyInput.value.trim()) {
            companyInput.classList.remove("input-error");
            errorCompany.textContent = "";
        }
    });

    purposeInput.addEventListener("input", () => {
        if (purposeInput.value.trim()) {
            purposeInput.classList.remove("input-error");
            errorPurpose.textContent = "";
        }
    });

    // PWA Service Worker 등록
    if ("serviceWorker" in navigator) {
        window.addEventListener("load", () => {
            navigator.serviceWorker
                .register("/sw.js")
                .then((registration) => {
                    console.log("PWA Service Worker 등록 성공:", registration.scope);
                })
                .catch((error) => {
                    console.warn("PWA Service Worker 등록 실패:", error);
                });
        });
    }
});
