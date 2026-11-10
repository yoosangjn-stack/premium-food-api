# 완성된 프로젝트로 배우는 학습 가이드

이 문서는 premium-food-api의 코드를 이해하고 직접 확인하는 안내서예요. AX Engineer에게 중요한 연습은 AI가 만든 코드도 **요구사항 → 실행 경로 → 실패 조건 → 증거**로 설명하는 것입니다.

## 먼저 범위를 나눠요

- [단계별 자료](https://app.notion.com/p/3273559b2313821cbd53812797e518d0), [ORM 자료](https://app.notion.com/p/SQLAlchemy-ORM-0713559b231383358f5281eaf2dbf757), [프로젝트 요구사항](https://app.notion.com/p/2-API-7443559b23138235848201fc2cd01522)은 각각 순서, 기술 개념, 만들 결과를 확인할 출처예요.
- 수업의 common/user/auth 흐름과 [선생님 저장소](https://github.com/yonggyo1125/backend_project_ax1)의 게시판 구조를 참고했어요. 비어 있는 수업 게시판 페이지의 세부 내용을 추측한 설명은 아닙니다.
- 상품·주문·재고·취소, 행 잠금, 주문 당시 가격 보관, 트랜잭션 관리자는 이 프로젝트 요구에 맞춘 확장입니다. 최신 발제문에서 동시성 방어는 도전 A(선택)이고, 트랜잭션 조율은 필수예요. 주문 스냅샷과 취소 규칙은 우리 Use Case의 설계입니다.
- 아래 코드 경로는 모두 `src/` 기준입니다. 실행 준비는 루트 README를 보세요. 실제 DB나 기존 `.env`를 실습용으로 덮어쓰지 마세요.

최신 발제문의 필수 흐름은 4계층·순수 도메인·비동기 ORM·입출력 검증·OAuth2/JWT 블랙리스트·CORS/로깅·Jinja2입니다. BackgroundTasks·스트리밍은 도전 B, 캐싱·배포는 도전 C로 구분해요. `src/database.py`에는 세션뿐 아니라 `Base`, `DateTimeBase`, `init_models()`도 함께 있습니다.

## 1. 네 계층을 주문 한 번으로 이해해요

**개념:** 일을 네 역할로 나누면 고칠 곳을 찾기 쉬워요.
- Presentation: 주문서를 받는 창구. HTTP 요청, Pydantic 입력 검사, 응답 형태를 담당해요.
- Application: 처리 순서를 정하는 담당자. 상품 확인 → 재고 차감 → 주문 저장 → 확정을 연결해요.
- Domain: 가게의 규칙. 재고보다 많이 주문하거나 같은 주문을 두 번 취소하지 못하게 해요.
- Infrastructure: 실제 DB와 기술 담당자. SQLAlchemy로 읽고 저장하고 잠급니다.

**기능·코드:** `POST /v1/orders`는 `orders/presentation/router.py`에서 `orders/application/service.py`의 `create_order()`를 부릅니다. 상품 저장소에서 읽은 뒤 `products/domain/entities.py`의 `reduce_stock()`으로 규칙을 검사하고 저장해요.

Application은 Domain의 저장소 약속에 의존하고 Infrastructure가 이를 구현해요. `orders/presentation/dependencies.py`는 서비스가 들어올 자리를 선언하고, `wiring/commerce.py`가 실제 상품·주문 객체를 조립해 연결합니다. `wiring/`은 객체 연결 장소이지 다섯 번째 업무 계층은 아니에요.

**직접 확인:** 수량 1을 2로 바꿨을 때 어느 함수가 재고 부족을 판단할까요? 라우터에 SQL을 넣지 않고 설명해 보세요.

## 2. Product가 세 모습인 이유

**개념:** 같은 상품도 규칙, DB 저장 모양, 요청·응답 모양은 달라요.
- Domain `Product`: `products/domain/entities.py`. 재고 차감·복구 규칙이 있는 Python 객체.
- ORM `ProductModel`: `products/infrastructure/models.py`. 테이블·열·제약조건을 SQLAlchemy에 알려 주는 객체.
- Pydantic `ProductCreate`, `ProductResponse`: `products/presentation/schemas.py`. 입력 형식과 공개할 필드를 정하는 객체.

**기능·코드:** 저장소의 `to_domain()`이 DB 행을 업무 객체로 바꿔요. 입력 검증 외에 도메인 검증도 있어서 HTTP 밖에서 호출해도 규칙을 지킬 수 있어요.

**직접 확인:** 음수 가격을 막는 코드를 스키마와 도메인에서 각각 찾아보세요. 상품 생성에는 관리자 권한도 필요하므로 입력 검사만 볼 때는 `tests/test_commerce.py`도 함께 읽어요.

## 3. 주문과 재고는 함께 저장돼야 해요

**개념:** 트랜잭션은 한 묶음으로 확정하거나 되돌리는 단위예요. 재고만 줄고 주문은 없는 상태를 막습니다.

**코드:** `database.py`의 `get_db()`가 세션을 공급해요. FastAPI 의존성 캐시 덕분에 같은 요청의 인증 조회와 주문 처리에서 같은 세션을 공유합니다. `wiring/commerce.py`도 상품·주문 저장소와 트랜잭션 관리자에 같은 세션을 넣어요.

`flush()`는 SQL을 DB에 반영하지만 최종 확정은 아니에요. 주문 서비스는 마지막에 `transaction.commit()`을 한 번 호출하고 중간 실패 시 `rollback()`으로 되돌립니다. `get_db()`의 예외 처리에도 rollback 안전망이 있어요. `get_db()`가 자동 commit하는 구조는 아닙니다.

인증 SELECT 때문에 SQLAlchemy의 autobegin으로 트랜잭션이 이미 시작될 수 있어요. 그래서 서비스에서 무조건 `session.begin()`을 또 열지 않습니다. `shared/domain/transaction.py`는 약속, `shared/infrastructure/transaction.py`는 구현이에요.

**직접 확인:** `tests/test_commerce.py`의 `test_order_insert_failure_rolls_back_stock`에서 주문 저장 실패 후 재고가 어떻게 검사되는지 찾아보세요.

## 4. 마지막 한 개와 두 번 누른 취소

**개념:** 두 요청이 동시에 재고 1을 읽으면 둘 다 주문하려 할 수 있어요. 행 잠금은 같은 상품을 변경할 차례를 세웁니다.

**기능·코드:** `products/infrastructure/repositories.py`의 `get_many_for_update()`가 `with_for_update()`로 잠급니다. 여러 상품은 ID 순으로 잠가 엇갈리는 잠금 위험을 줄여요. 취소는 주문 행을 먼저 잠그고 취소 가능 여부를 검사한 뒤 상품 재고를 복구합니다.

`orders/domain/entities.py`의 주문 항목은 상품명·단가를 주문 당시 값으로 보관해요. 내일 상품 가격을 바꿔도 오늘 주문 금액이 바뀌면 안 되니까요.

**직접 확인:** `tests/test_concurrency.py`에서 마지막 재고 동시 주문과 동시 취소를 보세요. 순차 클릭 두 번은 동시성 증거가 아닙니다. 가격 보관은 `test_order_snapshots_and_owner_access`에서 확인해요.

## 5. 로그인과 권한은 다른 질문이에요

**개념:** 인증은 “누구세요?”, 인가는 “이 일을 해도 되나요?”예요.

**기능·코드:** 회원가입은 `user/`, 토큰·로그아웃은 `auth/`, 실제 객체 연결은 `wiring/user.py`, `wiring/auth.py`에 있어요. 비밀번호는 bcrypt 해시로 확인해요. JWT는 서명으로 위조를 검사하는 토큰이지 내용을 숨기는 암호화가 아니므로 비밀정보를 넣으면 안 됩니다.

`/v1/auth/login`은 JSON, `/v1/auth/token`은 OAuth2 폼을 받아요. Swagger Authorize의 **username 칸에는 이메일**을 넣습니다. 로그아웃은 해당 토큰의 jti를 차단해요. 현재 비밀번호 변경만으로 기존 JWT가 자동 무효화되지는 않는다는 한계도 기억하세요.

**직접 확인:** A의 주문을 B로 조회하면 403, 토큰 없이 주문하면 401을 예상하세요. 토큰·비밀번호를 채팅, 스크린샷, 로그에 남기지 마세요.

## 6. CRUD와 HTTP 상태를 연결해요

CRUD는 생성(Create), 조회(Read), 수정(Update), 삭제(Delete)예요. 보통 POST, GET, PUT/PATCH, DELETE에 연결합니다. 모든 자원에 네 동작이 필요한 건 아니에요. 주문 취소는 이력을 지우지 않고 상태를 바꾸는 POST입니다.

- 200: 조회·수정·로그인·취소 성공. 201: 새 회원·상품·주문·글 생성 성공.
- 204: 삭제·로그아웃 성공. 응답 본문이 없어요.
- 400: 처리 조건에 맞지 않는 요청. 실제 확인 예: 비밀번호 변경 시 잘못된 현재 비밀번호. 공백 제목은 400이 아니라 422예요.
- 401: 인증 정보가 없거나 잘못됨. 403: 접근 권한이 없음.
- 404: 자원이 없음. 409: 재고 부족·중복 취소 등 현재 상태와 충돌. 발제문의 도메인 오류 400 예시와 구분한 API 설계예요.
- 422: 입력 검증 실패. 예: 수량 0, 중복 상품 ID.

**코드·직접 확인:** `shared/core/exception_handlers.py`가 오류를 응답으로 바꿉니다. `/docs`에서 본문뿐 아니라 상태 코드도 기록해 보세요.

## 7. 게시판과 화면도 이어 봐요

**게시판:** `board/presentation/router.py`에는 게시판 설정, 글·댓글 CRUD, 검색·페이지가 있어요. 게시판 역할 권한과 글 작성자 권한은 별개예요. 공개 작성자명은 실명 name 대신 username(3~30자)을 사용하며 name·phone·email은 게시글·댓글 작성자 응답에 공개하지 않아요. 비회원 글은 비밀번호도 확인합니다. `tests/test_api.py`에서 남의 글 수정·삭제 거부를 찾아보세요.

**화면:** `web/presentation/router.py`가 상품 서비스를 호출하고 `templates/catalog.html`에 데이터를 넣어 Jinja2 HTML을 만들어요. `static/styles.css`는 디자인입니다. `/`는 HTML, `/v1/products`는 JSON이에요. 현재 화면은 상품 목록·상세이며 회원·주문·게시판 조작은 `/docs`에서 실습해요.

**검색:** 상품 저장소가 DB에서 조건·정렬·페이지 범위를 적용해요. 허용 정렬은 `id`, `price`, `name`뿐입니다. 사용자 문자열을 SQL 문장에 그대로 붙이지 않아요. 다음 페이지에서도 검색 조건이 URL에 남는지 확인하세요.

**공통 처리:** `shared/core/middlewares.py`는 CORS와 요청 시간을 처리해요. CORS는 브라우저의 다른 출처 응답 접근 정책이지 인증이나 API 방화벽이 아닙니다. 로그에는 경로·상태·시간을 남기고 요청 헤더·본문·토큰은 남기지 않아요.

## 오늘의 작은 과제

1. 주문 후 줄어든 재고와 주문 항목 금액을 비교해 보세요.
2. 두 번째 취소가 실패해야 하는 이유를 설명해 보세요.
3. 화면이 고정 샘플인지 DB 결과인지 필터·상세·새로고침·API 값으로 구분해 보세요.
4. AI에게 “어느 계층을 바꾸고, 실패하면 무엇이 보존되며, 어떤 테스트가 증명하는가?”를 함께 물어보세요.

2026-11-10 경로 변경 후 전체 테스트 **95 passed in 18.20s**(기존 93개 + 구조 검사 2개), compileall·ruff가 통과했습니다. 백업과 새 앱의 OpenAPI 17 paths/28 operations 및 8개 테이블 메타데이터가 동일하고 함수·클래스 AST 보존도 읽기 검수로 확인했습니다. 이는 추가 Claude 검수가 아니며 Claude 2회 검수는 11/9 기록입니다.

실제 HTTP에서 /docs·/·CSS 200, 상품 20개, 가입 201 → OAuth2 로그인 200 → 주문 201/재고 2 차감 → 취소 200/재고 원복 → 중복 취소 409를 확인했습니다. 미존재 상품 404, 잘못된 현재 비밀번호 400, 게시글 생성·조회·수정·삭제·삭제 후 조회 201/200/200/204/404, 로그아웃 204 → 같은 토큰 401도 확인했습니다. 공백 제목은 422입니다.

브라우저 도구의 timeoutMs 오류로 시각 검증과 제출용 캡처는 미완료입니다. HTTP 성공을 화면 검수 완료로 대신하지 않습니다. PPT/PDF·공개 Notion·GitHub 게시·EC2 배포는 여전히 미완료입니다. 상세 증거는 [11/10 검증 기록](VERIFICATION_2026-11-10.md)을 보세요.
