# Claude Code 검수 대응 (2026-11-09)

사용자 승인 범위인 소스와 가상 테스트만 전달해 읽기 전용 검수를 두 차례 실행했습니다. .env, 키, 실DB, 개인정보 파일은 전달하지 않았습니다. 자동 수정이 아니라 지적을 원본 코드와 대조한 뒤 필요한 부분만 반영했습니다.

| 지적 | 판단 및 조치 | 근거 |
|---|---|---|
| 재고 option 태그 오류 | 실제 버그 수정. HTMLParser로 실제 option 3개 검증 | test_web.py |
| 상품/주문 presentation이 infrastructure 생성 | wiring/commerce.py로 조립 통일 | test_architecture.py |
| 게시판 작성자에 실명 사용 | username 표시, 회원 30자 허용, 개인 연락처 미공개 | test_member_auth.py |
| 동시 로그아웃 중복 insert | PostgreSQL ON CONFLICT DO NOTHING | test_concurrency.py |
| 500 CORS/로그 | 안전한 오류 경계 안에 로깅, 바깥 CORS. traceback 프레임만 남기며 예외 본문/locals 미기록 | test_member_auth.py |
| 비밀번호 변경 시 기존 JWT | 현재 제한을 README·학습 문서에 명시, 범위 확대하지 않음 | README |
| 후속: None 입력값 표시 가능성 | 이미 router가 q를 빈 문자열로, 가격 기본값을 빈 문자열로 처리. 별도 회귀 테스트 추가 | test_web.py |
| 후속: INFO 로그 없음 가능성 | shared/core/logger.py에 basicConfig 존재. 실제 서버 로그와 caplog 검사 | test_web.py |
| 후속: 비회원 비번 72바이트 | 기존 BcryptPasswordHasher에서 검증하며 75바이트 한글 입력 422 테스트 존재 | test_api.py |
| check_db import 시 실행 | __main__ 가드 추가 | check_db.py |

검수는 코드 리뷰이며 Claude가 앱을 실행한 것은 아닙니다. 실제 실행 증거는 VERIFICATION.md로 분리합니다. 선택적 취향 정리나 새 프레임워크 도입은 하지 않았습니다.
