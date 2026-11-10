# 표준 구조 정리와 실제 재검증 · 2026-11-10

## 결론과 근거
최신 발제문 [프로젝트(2)](https://app.notion.com/p/2-API-7443559b23138235848201fc2cd01522)을 직접 읽고 `src/<기능>`의 4계층, `src/main.py`, `src/database.py`로 정리했습니다. 이전 문서는 다른 발제문을 참조했으므로 이번 경로 일치를 이전부터 완료했다고 기록하지 않습니다.

- 대상: LAPTOP-1OVO82TC의 premium-food-api, `work/premium-food-board`.
- 기존 HEAD: `89eba90b89fdb60f1aa8134144eae3a31bb459fd`. 변경은 로컬 미커밋입니다.
- 최초 변경 후 전체 테스트: **95 passed in 18.20s**. 기존 93개에 표준 디렉토리/옛 import 방지 2개 추가.
- Ruff E9/F63/F7/F82, compileall 통과. 전체 보안 감사 또는 모든 스타일 규칙 통과를 뜻하지 않습니다.
- 변경 전 백업 앱과 변경 후 앱의 OpenAPI 전체 및 ORM 테이블 메타데이터 일치: **17개 경로, 28개 API 동작, 8개 테이블**.
- 내부 읽기 전용 검수에서 서비스·인증·repository·트랜잭션의 함수/클래스 본문 누락 없음. Claude 추가 검수가 아닙니다.
- 최종 재실행 결과는 이 문서 마지막에 별도로 기록합니다.

## 기존 작업을 어떻게 보존했나
수정 전에 소스·문서·가상 테스트 148개를 프로젝트 밖 `_backups/premium-food-api-before-standard-layout-20261110-100207`에 복사하고 SHA-256을 전부 확인했습니다. 당시 Git 상태, HEAD, tracked 변경 patch도 함께 보관했습니다. 더 이전의 13파일 백업도 유지합니다.

`.env`, `.git`, `.venv`, 캐시, 실제 DB와 작업용 DB는 소스 백업에 포함하지 않았고 읽거나 덮어쓰지 않았습니다. 이 백업은 컴퓨터 전체 또는 DB 백업이라는 뜻이 아닙니다. 원래 사용자 파일이 전부 그대로 남아 있다고 주장하지 않습니다. 변경한 원본 내용이 백업에 보존된 것입니다.

## 무엇을 왜 바꿨나
| 이전 | 현재 | 이유 |
|---|---|---|
| src/premium_food_api/<기능> | src/<기능> | 발제문 표준과 동일하게, 중첩 한 단계 제거 |
| root/main.py, src/main.py 래퍼, 패키지 main.py | src/main.py 하나 | 실제 FastAPI 앱 진입점을 한 곳에서 읽기 |
| shared/core/database.py + models.py + 호환 database.py | src/database.py | 엔진·세션·Base·모델 등록을 한 파일에 정리 |
| presentation/routers/v1/router.py | presentation/router.py | 버전 폴더는 없애되 /v1 API URL은 유지 |
| products/orders application/services.py | application/service.py | 교안 파일명 통일 |
| board infrastructure/sqlalchemy/* 및 repository별 파일 | infrastructure/models.py, mappers.py, repositories.py | 사용하지 않는 추가 기술 분류와 파일 분산 감소 |
| board/domain/repository/ 세 파일 | board/domain/repositories.py | 같은 저장소 계약을 한 파일에서 확인 |
| web/templates, web/static | src/templates, src/static | 발제문 배치에 일치 |
| root의 check_db/create_tables/seed_product.py | scripts/ | 실행 보조 도구와 서비스 코드를 구분 |
| 설치용 중첩 패키지/콘솔 명령 | tool.uv.package=false | 교안의 --app-dir src 실행 방식으로 단순화 |

이동한 옛 진입점·호환 파일은 백업의 retired-layout에 보관했습니다. 무작정 지우지 않았습니다. Python 소스는 118→97개, 패키지 인식용 __init__.py는 45→32개입니다. 회원·인증·상품·주문·게시판 5개 모듈의 4계층은 모두 유지합니다.

`wiring`은 실제 Repository와 서비스 연결, 작은 TransactionManager는 같은 세션의 commit/rollback을 담당하므로 유지합니다. 일반화된 새 프레임워크는 추가하지 않았습니다. `web`은 읽기 전용 화면 표현이며 가짜 도메인/저장소 폴더를 추가하지 않았습니다.

## 데이터 격리와 실제 실행
- `PYTHON_DOTENV_DISABLED=1`. 임시 JWT 키는 프로세스에서 생성하고 출력하지 않았습니다.
- 기존 PostgreSQL 5432 대신 작업 전용 `127.0.0.1:55440` 사용.
- premium_food_test는 가상 fixture, premium_food_demo는 샘플 상품과 가상 회원·주문·게시글만 사용.
- 주문/취소/로그아웃 동시성은 실제 서로 다른 DB 연결 테스트를 포함합니다.
- 실제 DB migration, 기존 서비스 설정 변경, 공개 배포는 하지 않았습니다.

실행 명령:
```powershell
uv run python -m uvicorn main:app --app-dir src --host 127.0.0.1 --port 18084
```

교안의 `uv run uvicorn ...` 실행 파일 래퍼는 이 PC의 Windows App Control `os error 4551`로 차단됐습니다. 허용된 Python 모듈 실행은 성공했습니다. 보안 설정을 끄지 않았습니다.

처음 임시 PostgreSQL 재시작 때 포트 옵션을 빠뜨려 시작에 실패했습니다. 기존 작업 전용 옵션 `-h 127.0.0.1 -p 55440`을 명시한 뒤 시작 성공했습니다. 기존 5432 서비스는 변경하지 않았습니다.

## 실제 HTTP 결과
| 시나리오 | 결과 |
|---|---|
| Swagger /docs, Jinja2 /, CSS | 200 / 200 / 200 |
| 상품 목록 | 샘플 20개 유지 |
| 가상 회원가입 → OAuth2 폼 로그인 | 201 → 200 |
| 주문 생성 → 내 주문 조회 | 201 → 200, 재고 2개 차감 |
| 취소 → 같은 주문 다시 취소 | 200 → 409, 재고 원복 1회 |
| 없는 상품 | 404 |
| 본인 비밀번호 변경 시 잘못된 기존 비밀번호 | 400, 비밀번호 변경 없음 |
| 게시글 생성/조회/수정/삭제/재조회 | 201/200/200/204/404 |
| 로그아웃 → 동일 JWT로 보호 API | 204 → 401 |

400은 위 실제 시나리오로 확인했습니다. 공백 제목은 별도 시도에서 422였으므로 400 증거로 쓰지 않습니다. 재고 부족·중복 취소는 상태 충돌 409이며, 발제문 400 예시와 구분해 설명합니다.

## 검수와 미완료
11/9 Claude Code 읽기 전용 검수 2회는 당시 소스·가상 테스트에 대한 검수입니다. 이번 단순 경로 이동은 내부 AST/계약 비교와 실제 테스트로 검증했고, Claude에게 다시 보냈다고 기록하지 않습니다.

브라우저 생성 및 기존 탭 연결 모두 `Cannot read properties of undefined (reading 'timeoutMs')`로 실패했습니다. HTTP/HTML 테스트가 화면을 눈으로 본 증거는 아닙니다. 실제 시각 확인과 제출용 캡처는 [캡처 안내](DEMO_CAPTURE_GUIDE.md)에 따라 완료해야 합니다.

미완료: GitHub commit/push 및 제출 접근 확인, 공개 Notion, PPT/PDF, 현장 리허설, 시각 캡처. 선택인 배포·캐싱·BackgroundTasks/StreamingResponse도 완료로 표시하지 않습니다. 비밀번호 변경 후 모든 과거 JWT 일괄 철회는 기존 학습용 한계입니다.

## 최종 재실행 및 시연 상태
- database.py의 읽기 순서 정돈까지 반영 후 **95 passed in 18.09s**, Ruff 통과, compileall 통과, git diff --check 오류 없음(LF→CRLF 안내만 있음).
- 백업 원본 148개는 마지막 SHA-256 재확인에서도 모두 일치.
- 최종 코드로 서버 재시작 후 /health·/docs·웹·CSS200, 샘플20, OAuth2·주문·취소·중복취소·400·게시글 CRUD·블랙리스트 흐름을 다시 확인했습니다. 재시작 후에도 기존 가상 계정과 재고가 유지됐습니다.
- 사용자 화면 캡처를 위해 localhost18084 시연 서버와 작업 전용 PostgreSQL55440을 현재 열어둡니다. 공개 인터넷에 바인딩하지 않았습니다. 기존 postgresql-x64-17 서비스는 Running이며 건드리지 않았습니다.
- 시연 종료 시 해당 Uvicorn만 Ctrl+C로 종료하고, 작업 전용 클러스터만 아래 명령으로 중지합니다. 실제 PostgreSQL 서비스/5432를 중지하지 않습니다.
```powershell
& 'C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe' -D '.local-test\pgdata' -m fast -w stop
```
시연용 임시 DB 디렉터리는 보존하며 Git 제외 상태입니다. 이 문서의 실행 상태는 확인 시점의 결과이며 계속 켜져 있음을 보장하는 감시 설정은 아닙니다.
