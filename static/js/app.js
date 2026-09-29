/**
 * AI 기업 마케팅 분석기 - 프론트엔드 비동기 제어 스크립트
 */

document.addEventListener("DOMContentLoaded", () => {
    // 1. DOM 요소 취득
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
            btnText.textContent = "🚀 사실 기반 마케팅 보고서 생성";
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
});
