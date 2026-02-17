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

## 2. GitHub Secrets 설정 (인증 및 알림 정보)
비밀번호와 같은 민감한 정보를 안전하게 등록합니다.

**Settings > Secrets and variables > Actions > Secrets** 탭에서 **New repository secret** 버튼으로 다음 항목들을 등록합니다.

| Secret Name | 설명 | 비고 |
| :--- | :--- | :--- |
| `SN_USERNAME` | ServiceNow 계정 이메일 | 모든 PDI 공통 사용 |
| `SN_PASSWORD` | ServiceNow 계정 비밀번호 | 모든 PDI 공통 사용 |
| `MAIL_USERNAME` | 알림을 보낼 Gmail 주소 | (예: your-name@gmail.com) |
| `MAIL_PASSWORD` | Gmail **앱 비밀번호** | [Google 앱 비밀번호 생성 가이드](https://support.google.com/accounts/answer/185833) 참고 |

## 3. 워크플로우 실행 및 테스트
설정이 완료되었는지 확인합니다.

1.  저장소 상단의 **Actions** 탭으로 이동합니다.
2.  왼쪽 워크플로우 목록에서 **ServiceNow Weekly Login**을 클릭합니다.
3.  오른쪽의 **Run workflow** 버튼을 눌러 수동으로 실행합니다.
4.  등록한 URL 개수만큼 작업(Job)이 생성되어 병렬로 실행되는지 확인합니다.

## 4. 결과 확인
*   **Email**: 각 PDI 로그인 성공/실패 여부가 메일로 발송됩니다.
*   **History**: 각 실행 기록은 저장소의 `login_history.json` 파일에 자동으로 누적되어 저장됩니다.
*   **Artifacts**: Actions 실행 결과 상세 페이지 하단에서 로그인 성공/실패 화면 스크린샷을 다운로드할 수 있습니다.
