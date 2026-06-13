# ⚙️ ServiceNow PDI Auto-Login GitHub Setup Guide

이 가이드는 여러 개의 ServiceNow PDI를 GitHub Actions를 통해 자동으로 관리하기 위한 설정 방법을 안내합니다.

## 1. GitHub Variables 설정 (PDI URL 리스트)
로그인을 시도할 PDI 주소들을 등록합니다.

1.  GitHub 저장소의 **Settings** 메뉴로 이동합니다.
2.  왼쪽 사이드바에서 **Secrets and variables > Actions**를 클릭합니다.
3.  **Variables** 탭을 선택하고 **New repository variable** 버튼을 누릅니다.
4.  다음 정보를 입력합니다:
    *   **Name**: `SN_PDI_URL`
    *   **Value**: 관리할 PDI URL들을 콤마(`,`)로 구분하여 입력 (예: `https://dev12345.service-now.com, https://dev67890.service-now.com`)
5.  **Add variable**을 클릭하여 저장합니다.

> ⚠️ URL은 민감정보가 아니므로 Variable에 둡니다. **비밀번호/계정은 절대 Variable에 넣지 마세요** — 로그·UI에 평문 노출됩니다. 반드시 아래 Secrets로 등록하세요.

## 2. GitHub Secrets 설정 (인증 및 알림 정보)
비밀번호와 같은 민감한 정보를 안전하게 등록합니다.

**Settings > Secrets and variables > Actions > Secrets** 탭에서 **New repository secret** 버튼으로 다음 항목들을 등록합니다.

| Secret Name | 설명 | 비고 |
| :--- | :--- | :--- |
| `SN_USERNAME` | 기본 표준 로그인 계정 (보통 `admin`) | 인스턴스별 지정이 없을 때 사용 |
| `SN_PASSWORD` | 기본 표준 로그인 비밀번호 | 인스턴스별 지정이 없을 때 사용 |
| `SN_DEV_USERNAME` | 휴면 깨우기용 **개발자 계정 이메일** (전역) | developer.servicenow.com 로그인 계정 |
| `SN_DEV_PASSWORD` | 휴면 깨우기용 개발자 계정 비밀번호 (전역) | |
| `SN_CREDENTIALS` | **인스턴스별** 자격증명 JSON (선택) | 아래 형식 참고 |
| `MAIL_USERNAME` | 알림을 보낼 Gmail 주소 | (예: your-name@gmail.com) |
| `MAIL_PASSWORD` | Gmail **앱 비밀번호** | [Google 앱 비밀번호 생성 가이드](https://support.google.com/accounts/answer/185833) 참고 |

### `SN_CREDENTIALS` 형식 (인스턴스별 계정 분리)
인스턴스마다 표준 로그인 계정이나 깨우기용 개발자 계정이 다를 때 사용합니다. host(도메인)별로 다음 키를 지정합니다.

```json
{
  "dev400970.service-now.com": {
    "username": "admin",
    "password": "<instance-admin-password>"
  },
  "dev404357.service-now.com": {
    "username": "admin",
    "password": "<instance-admin-password>",
    "dev_username": "owner@example.com",
    "dev_password": "<developer-account-password>"
  }
}
```

자격증명 우선순위:
- **표준 로그인**: `SN_CREDENTIALS[host].username/password` → 없으면 `SN_USERNAME`/`SN_PASSWORD`
- **휴면 깨우기**: `SN_CREDENTIALS[host].dev_username/dev_password` → `SN_DEV_USERNAME`/`SN_DEV_PASSWORD` → `SN_USERNAME`/`SN_PASSWORD`

> 💡 **휴면 깨우기에는 인스턴스 `admin`이 아니라 `developer.servicenow.com` 개발자 계정(이메일)** 이 필요합니다. 인스턴스 admin 계정으로는 휴면 PDI를 깨울 수 없습니다.

## 3. 워크플로우 실행 및 테스트
설정이 완료되었는지 확인합니다.

1.  저장소 상단의 **Actions** 탭으로 이동합니다.
2.  왼쪽 워크플로우 목록에서 **ServiceNow Weekly Login**을 클릭합니다.
3.  오른쪽의 **Run workflow** 버튼을 눌러 수동으로 실행합니다.
4.  등록한 URL 개수만큼 작업(Job)이 생성되어 병렬로 실행되는지 확인합니다.

> 스케줄은 **2시간마다**(`0 */2 * * *`) 자동 실행됩니다. 인스턴스가 휴면 상태였다면 깨운 뒤 첫 로그인 성공 후 **30분 뒤 한 번 더 로그인**하여 인스턴스를 안정적으로 유지합니다.

## 4. 결과 확인
*   **Email**: 각 PDI 로그인 성공/실패 여부가 메일로 발송됩니다.
*   **History**: 각 실행 기록은 저장소의 `login_history.json` 파일에 자동으로 누적되어 저장됩니다.
*   **Artifacts**: Actions 실행 결과 상세 페이지 하단에서 로그인 성공/실패 화면 스크린샷을 다운로드할 수 있습니다.
