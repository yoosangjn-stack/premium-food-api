# 실제 검증 기록 · 2026-11-09

## 최종 결과
- 환경: LAPTOP-1OVO82TC, Python 3.13, PostgreSQL 17, uv.
- 대상: premium-food-api / work/premium-food-board. 기존 main HEAD는 89eba90b89fdb60f1aa8134144eae3a31bb459fd이며 이번 변경은 아직 로컬 미커밋입니다.
- 최종 명령: `uv run python -m pytest -q` → **93 passed in 17.74s**.
- `uv run ruff check .` → All checks passed. 설정된 범위(E9/F63/F7/F82)의 기본 오류 검사입니다. 전체 스타일/보안 감사라는 뜻은 아닙니다.
- `uv run python -m compileall -q src tests` → 성공.
- `git diff --check` → 오류 없음. uv.lock의 향후 LF→CRLF 안내만 있었습니다.

## 데이터 격리
실제 `.env`는 읽거나 덮어쓰지 않았습니다. PYTHON_DOTENV_DISABLED=1로 실행했고 DB와 JWT 테스트값은 프로세스 환경에만 넣었습니다. JWT 값은 출력·기록하지 않았습니다.

기존 PostgreSQL 서비스/5432 DB 대신 이 작업에서 새로 만든 `127.0.0.1:55440` 클러스터만 사용했습니다.
- premium_food_test: 일반 테스트마다 외부 rollback. 동시성은 서로 다른 PostgreSQL backend PID 확인 후 실제 독립 트랜잭션, 정확한 fixture 행만 정리.
- premium_food_demo: HTTP 서버 시연용 가상 회원·샘플 상품만 사용.
- 임시 DB/로그는 `.local-test/`에 있고 Git에서 제외됩니다. `.env`도 제외되며 추적되는 .env 파일은 없습니다.

## 무엇을 검증했나
1. 회원 필수 필드·아이디/이메일 중복·비밀번호 해시·민감 정보 비노출.
2. OAuth2 이메일 폼/JSON 로그인·잘못된 인증·만료/변조·탈퇴 차단·본인 비밀번호 변경·블랙리스트.
3. 상품 관리자 권한·정수/범위 검증·문자 그대로의 대소문자 무관 검색·재고/가격 필터·정렬/페이지·404.
4. 주문 소유권·서버 계산 가격·단가/상품명 스냅샷·재고 부족·잘못된/중복 항목.
5. 주문 저장 실패 및 취소 상태 저장 실패를 의도적으로 주입해 재고도 rollback되는지 확인.
6. 실제 서로 다른 연결: 재고 1개 동시 주문은 201/409, 같은 주문 동시 취소는 200/409, 재고 복구 1회, 동시 로그아웃은 둘 다 204.
7. 게시글/댓글 CRUD·작성자/관리자 권한·비회원 비밀번호·검색/페이지·소프트 삭제.
8. 게시판 공개명은 username이며 name/phone/email은 노출하지 않음. 30자 아이디 허용.
9. Jinja2 DB 목록/상세·필터/페이지·XSS escape·빈 값·404·재고 option 태그 파싱.
10. CORS·시간 헤더·INFO 로그·안전한 500 JSON·계층 import 가드.

## 실제 Uvicorn HTTP 검증
`uv run python -m uvicorn main:app --app-dir src --host 127.0.0.1 --port 18084`로 실제 서버를 실행했습니다. ASGI 테스트만으로 대체하지 않았습니다.

- `/docs` 200, `/` HTML 200, `/v1/products` 샘플 20개.
- 회원가입 201 → OAuth2 로그인 200 → 주문 201 → 재고 2개 차감.
- 취소 200 → 원래 재고 복구 → 같은 취소 409, 추가 복구 없음.
- 게시글 생성 201 → 조회/수정 200 → 삭제 204 → 조회 404.
- 공개 작성자 username 확인, 잘못된 기존 비밀번호 400.
- 로그아웃 204 → 같은 JWT로 보호 API 401.
- 서버를 종료하고 같은 가상 DB로 재시작한 뒤 재고·게시글 수가 유지되고 상품이 20개 그대로인지 확인. 샘플 재삽입/재고 리셋 없음.

검증 스크립트 초기에 게시글 생성 응답을 data.id/id로 잘못 가정해 중단했습니다. 실제 계약 post_id로 수정한 최종 시나리오가 위 결과입니다. 실패했던 시도를 성공으로 집계하지 않았습니다.

## Claude Code 검수
읽기 전용 검수 2회 수행. 원본 보고서는 CLAUDE_REVIEW.md, CLAUDE_REVIEW_FINAL.md, 실제 수정/조건부 지적 판정은 CLAUDE_REVIEW_RESOLUTION.md입니다. Claude는 소스를 검토했으며 앱 실행 검증은 위 별도 절차입니다.

## 미완료·한계
- 실제 브라우저 렌더링/조작과 스크린샷: 브라우저 연결 오류로 미완료. HTTP/Jinja/HTMLParser 통과는 눈으로 확인한 증거를 대체하지 않습니다.
- 기존 실제 DB migration은 수행하지 않았습니다. create_all은 컬럼 변경 도구가 아닙니다.
- 비밀번호 변경 시 모든 기존 JWT 철회는 미구현이며 문서화했습니다.
- GitHub commit/push, EC2 배포, 노션 직접 기록, 발표 자료는 미완료입니다.
- 검증용 서버/클러스터 종료 상태는 아래 정리 항목에 실제 확인 후 기록합니다.

## 검증 종료 정리
2026-11-09: 작업 전용 Uvicorn 18084와 PostgreSQL 55440을 중지하고 두 포트에 listener가 없음을 확인했습니다. 임시 가상 데이터 디렉터리는 재검증을 위해 보존했으며 Git 제외 상태입니다. 기존 postgresql-x64-17 서비스는 Running 상태이며 수정하지 않았습니다. 현재 검증 프리뷰 URL은 서버가 꺼져 있어 열리지 않습니다.
