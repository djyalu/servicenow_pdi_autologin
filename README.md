# ServiceNow PDI Auto-Login

여러 개의 ServiceNow PDI(Personal Developer Instance)를 GitHub Actions로 **2시간마다 자동 로그인**하여 비활성 회수와 휴면(Hibernation)을 방지하는 봇입니다.

PDI는 일정 기간 미사용 시 휴면되고 결국 회수됩니다. 이 프로젝트는 주기적 자동 로그인으로 인스턴스를 살아있게 유지하고, 휴면된 인스턴스는 개발자 계정으로 깨운 뒤 로그인합니다.

## ✨ 주요 기능

- **멀티 인스턴스**: GitHub Actions Matrix로 여러 PDI를 병렬 처리
- **인스턴스별 자격증명**: 인스턴스마다 다른 admin/개발자 계정 지원 (`SN_CREDENTIALS`)
- **휴면 자동 깨우기**: `developer.servicenow.com` 개발자 계정으로 SSO 로그인 → 폴링하며 인스턴스 기상 대기 → 로그인
- **깨운 뒤 재로그인**: 휴면을 깨운 경우 첫 로그인 30분 후 한 번 더 로그인하여 안정화
- **알림**: 각 인스턴스별 성공/실패를 Gmail로 발송
- **이력/스크린샷**: `login_history.json` 누적 + 결과 스크린샷 아티팩트

## 🗂️ 구성

| 파일 | 역할 |
| :--- | :--- |
| `main.py` | Playwright(Chromium headless) 로그인/깨우기 스크립트 |
| `.github/workflows/weekly_login.yml` | 2시간 주기 스케줄 + Matrix 실행 + 메일 알림 + 이력 병합 |
| `requirements.txt` | playwright, python-dotenv |
| `login_history.json` | 통합 로그인 이력 (최근 200건) |
| `GITHUB_SETUP.md` | GitHub Variables/Secrets 설정 가이드 |
| `GEMINI.md` | 프로젝트 진행 로그 |

## ⚙️ 동작 흐름

```
URL 접속
  ├─ 휴면 아님 → 표준 로그인 1회
  └─ 휴면 감지
        → 개발자 계정으로 SSO 로그인 (developer.servicenow.com)
        → 쿠키 배너 처리 + URL 폴링/Wake 버튼 클릭 (최대 ~6분)
        → 로그인 폼 등장 시 표준 로그인
        → 성공 시 30분 대기 후 재로그인
```

## 🔧 설정

자세한 설정은 **[GITHUB_SETUP.md](./GITHUB_SETUP.md)** 를 참고하세요. 요약:

### Variable
- `SN_PDI_URL` — 관리할 PDI URL을 콤마로 구분 (예: `https://devXXXXXX.service-now.com,https://devYYYYYY.service-now.com`)

### Secrets
| Secret | 용도 |
| :--- | :--- |
| `SN_USERNAME` / `SN_PASSWORD` | 기본 표준 로그인 계정 |
| `SN_DEV_USERNAME` / `SN_DEV_PASSWORD` | 전역 휴면 깨우기 개발자 계정 |
| `SN_CREDENTIALS` | 인스턴스별 자격증명 JSON (선택) |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | 알림용 Gmail 주소 / 앱 비밀번호 |

> 🔒 **비밀번호/계정은 반드시 Secret으로만 등록하세요.** Variable은 평문 노출되므로 URL 외 민감정보를 넣으면 안 됩니다.

### `SN_CREDENTIALS` 예시
```json
{
  "dev400970.service-now.com": { "username": "admin", "password": "<pw>" },
  "dev404357.service-now.com": {
    "username": "admin", "password": "<pw>",
    "dev_username": "owner@example.com", "dev_password": "<dev-pw>"
  }
}
```
- 표준 로그인: `username/password` → 없으면 `SN_USERNAME/SN_PASSWORD`
- 휴면 깨우기: `dev_username/dev_password` → `SN_DEV_*` → `SN_USERNAME/SN_PASSWORD`

> 💡 휴면 깨우기에는 인스턴스 `admin`이 아닌 **개발자 계정 이메일**(developer.servicenow.com 로그인)이 필요합니다.

## ▶️ 실행

- **자동**: 2시간마다(`0 */2 * * *`) 스케줄 실행
- **수동**: GitHub **Actions → ServiceNow Weekly Login → Run workflow**
- **로컬**:
  ```bash
  pip install -r requirements.txt
  playwright install chromium
  SN_PDI_URL=https://devXXXXXX.service-now.com \
  SN_USERNAME=admin SN_PASSWORD=*** \
  SN_DEV_USERNAME=you@example.com SN_DEV_PASSWORD=*** \
  python main.py
  ```

## 📊 결과 확인

- **메일**: 인스턴스별 성공/실패 알림
- **이력**: `login_history.json`에 누적
- **스크린샷**: Actions 실행 결과 하단 Artifacts(`result_*.png` / `error_*.png`)
