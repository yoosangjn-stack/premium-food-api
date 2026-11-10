# Chapter 3를 내 프로젝트로 이해하는 이야기

[최신 발제문](https://app.notion.com/p/2-API-7443559b23138235848201fc2cd01522)은 강의 3장을 **고급 요청 처리 및 웹 인터페이스 구성**으로 설명해요. 경로·쿼리 매개변수, HTTP 예외 변환, Jinja2·정적 파일이 해당 내용입니다. 아래는 이를 주문 프로젝트 전체 흐름과 연결한 복습 이야기예요. ORM은 5장, 인증은 6장, 4계층은 7장 내용이므로 모두 3장 범위라고 외울 필요는 없어요. 원본과 확장 구분은 [학습 가이드](LEARNING_GUIDE.md)를 보세요.

## 오늘 열 가게: 한정 수량 식품점

“남은 상품을 보고 주문하고, 잘못 주문하면 취소할 수 있게 해 주세요.”

간단해 보이지만 질문이 생겨요. 마지막 한 개를 둘이 동시에 사면? 남의 주문을 취소하면? 주문 저장은 실패했는데 재고만 줄면? 이 질문에 답하는 게 백엔드의 역할이에요.

오늘은 **개념 → 기능 → 코드 → 직접 확인** 순서로 따라가요. 코드 경로는 `src/` 기준입니다. 실제 개인정보 대신 아래 가상 계정을 사용하세요.

## 0장면. 안전한 연습장을 열어요

**개념:** 실행 환경은 프로그램이 읽을 DB 주소와 설정을 정하는 곳이에요.

**기능·코드:** `main.py`의 lifespan은 시작·종료 작업을 맡아요. `CREATE_TABLES=true`는 없는 테이블을 만들고 `DEMO_SEED=true`는 예시 상품과 `free` 게시판을 넣습니다. 테이블 생성은 기존 DB 구조를 바꾸는 마이그레이션 도구가 아니에요.

**직접 확인:** 루트 README대로 **새 실습 전용 DB**를 준비한 뒤 시작하세요. 기존 `.env`나 실사용 DB를 재사용하지 마세요. 데모 플래그는 새 실습 DB에서만 켜고 평소에는 꺼 두세요. 데모는 회원·관리자 계정을 자동으로 만들지 않습니다.

서버가 실행되면 `http://127.0.0.1:8000/health`, `/`, `/docs`를 각각 열어요. health의 ok는 프로세스 응답이지 모든 DB 기능의 성공 증거는 아닙니다. 아래는 따라 할 절차이며 실제 화면을 검토했다는 보고서는 아니에요.

## 1장면. 상품을 보여 주세요

**개념:** GET은 정보를 읽는 요청이에요. API는 화면 대신 JSON을 돌려줄 수 있어요.

**기능·코드:** `/v1/products` → `products/presentation/router.py` → `products/application/service.py` → `products/infrastructure/repositories.py`를 따라가세요. ORM이 SQL을 만들어 DB에서 가져옵니다.

**직접 확인:** `/docs`의 GET `/v1/products`에서 Try it out을 눌러 `page=1`, `size=2`, `stock=in_stock`, `sort=price`로 실행해요. 응답의 `items`, `total`, `page`, `size`를 봅니다. 실제 반환된 상품 ID 하나와 재고를 적어 두세요. ID가 1이라고 가정하지 마세요.

이제 `/`에서 같은 조건으로 검색해요. 화면과 API는 같은 상품 서비스를 사용합니다. Jinja2는 서버에서 HTML을 만들고 CSS는 보기 좋게 꾸며 줘요. 필터를 바꾸거나 다음 페이지로 이동할 때 결과도 달라져야 합니다.

**스스로 답하기:** 화면에 보이는 상품명만 바꾸면 DB 상품명이 바뀔까요? HTML 템플릿과 저장소의 역할을 구분해 보세요.

## 2장면. 누가 주문하는지 알아야 해요

**개념:** 회원가입은 계정 생성, 로그인은 본인 확인, 토큰은 이후 요청에 붙이는 인증 수단이에요.

**기능·코드:** `user/presentation/schemas.py`가 회원가입 입력을 검사하고, `user/application/service.py`가 가입을 처리해요. 비밀번호 해시는 `user/infrastructure/security.py`, JWT 서명·검사는 `auth/infrastructure/security.py`에 있어요.

**직접 확인:** POST `/v1/users`에 아래 가상 데이터로 가입해요. 이미 썼다면 이메일과 username을 새 값으로 바꾸세요. 이 비밀번호는 실습 예시이며 다른 서비스에 사용하면 안 됩니다.

```json
{"username":"learner_a","phone":"01000000000","email":"learner_a@example.com","name":"학습자A","password":"StudyOnly1!"}
```

201을 확인한 뒤 Swagger 상단 Authorize를 열어요. username에는 `learner_a@example.com`, password에는 위 실습 비밀번호를 넣습니다. 이는 폼 방식 POST `/v1/auth/token`을 사용해요. 별도 JSON 로그인은 POST `/v1/auth/login`입니다.

현재 비밀번호 변경만으로 이미 발급된 JWT를 자동 무효화하지는 않습니다. 로그아웃으로 해당 토큰을 차단하는 동작과 구분해 두세요.

**스스로 답하기:** JWT 내용을 읽을 수 있다는 사실이 왜 비밀번호를 넣어도 된다는 뜻이 아닐까요?

## 3장면. 상품 한 개를 주문해요

**개념:** 요청 스키마는 주문서를 검사하고, 도메인은 업무 규칙을 검사해요. Application은 전체 순서를 정합니다.

**기능·코드:** `orders/presentation/schemas.py`는 수량 1 이상과 중복 상품 금지를 검사해요. `orders/application/service.py`의 `create_order()`는 상품을 잠그고 재고 규칙을 적용한 뒤 주문을 저장합니다.

**직접 확인:** POST `/v1/orders`에 아래 JSON을 넣되 `product_id`의 1을 앞에서 확인한 실제 ID로 바꾸세요.

```json
{"items":[{"product_id":1,"quantity":1}]}
```

201과 응답의 주문 `id`를 확인해요. GET `/v1/products/{product_id}`로 재고가 1 줄었는지 보고, GET `/v1/orders/{order_id}`에서 단가와 합계를 봅니다. 주문은 로그인 사용자에게 귀속되므로 본문에 임의의 user_id를 넣지 않아요.

**스스로 답하기:** 상품 이름과 단가를 주문 항목에도 저장하는 이유는 뭘까요? 내일 상품 가격을 바꾼 상황을 상상해 보세요.

## 4장면. 일부만 저장되면 곤란해요

**개념:** 재고 차감과 주문 생성은 하나의 트랜잭션이어야 해요.

**기능·코드:** 같은 요청의 인증 조회·저장소·트랜잭션 관리자는 `get_db()`가 공급한 세션을 공유합니다. 상품·주문 객체를 실제로 조립하는 코드는 `wiring/commerce.py`이고 presentation의 dependencies는 연결할 자리를 선언해요. `flush()`는 중간 SQL 반영, `commit()`은 최종 확정, `rollback()`은 되돌리기예요. 인증 조회로 이미 트랜잭션이 시작될 수 있어 서비스를 시작할 때 또 begin하지 않습니다.

**직접 확인:** 재고가 있는 상품과 부족한 상품을 함께 주문한 실패 사례를 `tests/test_commerce.py`의 `test_failed_multiline_order_changes_nothing`에서 읽어요. 저장 중 예외는 `test_order_insert_failure_rolls_back_stock`이 검사합니다. 실제 서버에 일부러 저장 오류를 심는 대신 격리된 테스트를 사용하세요.

**스스로 답하기:** 상품 저장소가 자기 작업 직후 commit하면 왜 전체 주문을 되돌리기 어려워질까요?

## 5장면. 취소 버튼을 두 번 눌렀어요

**개념:** 취소는 주문 이력을 지우는 게 아니라 상태를 바꾸고 재고를 복구하는 업무예요.

**기능·코드:** `cancel_order()`는 주문 행을 잠그고 `orders/domain/entities.py`의 `cancel()`을 호출합니다. 이후 상품 행도 잠가 재고를 돌려놓고 한 번에 확정해요.

**직접 확인:** POST `/v1/orders/{order_id}/cancel`을 실행해요. 200, 취소 상태, 원래로 돌아온 재고를 확인하세요. 같은 요청을 한 번 더 보내면 409여야 하고 재고가 또 늘면 안 됩니다.

동시에 눌린 상황은 `tests/test_concurrency.py`의 `test_competing_cancellations_restore_stock_once`가 다룹니다. 마지막 재고 경쟁은 `test_competing_orders_cannot_oversell`을 보세요. 두 테스트는 서로 다른 요청의 잠금 효과를 확인하는 연습입니다.

## 6장면. 로그인만 하면 남의 것도 바꿀 수 있나요?

**개념:** 인증과 인가는 달라요. 사용자 확인 뒤에도 소유자·관리자 여부를 판단해야 해요.

**기능·코드:** 주문의 `_check_access()`는 본인 또는 관리자만 상세 조회·취소하도록 합니다. 상품 생성·수정은 `require_admin`을 요구해요. 회원가입으로 만든 계정은 일반 사용자입니다.

**직접 확인:** Swagger Authorize를 해제하고 주문하면 401을 확인해요. 새 가상 회원 B로 가입·로그인한 뒤 A의 주문을 조회하면 403을 예상하세요. 일반 회원으로 POST `/v1/products`를 시도해도 403이에요. 관리자 권한을 받으려고 가입 JSON에 role을 넣거나 실제 DB를 임의 수정하지 마세요. 관리자 흐름은 격리된 테스트의 admin fixture로 확인할 수 있어요.

## 7장면. 게시판도 같은 방식이에요

**개념:** 게시판 설정 권한, 글 작성 권한, 남의 글 변경 권한은 각각 확인해야 해요.

**기능·코드:** `board/presentation/router.py`에서 `board/application/service.py`, 도메인, `board/infrastructure/`로 이어집니다. 글·댓글 CRUD와 검색·페이지가 있어요. 공개 작성자명에는 실명 name 대신 username(3~30자)을 사용하고, 작성자의 name·phone·email을 공개하지 않아요.

**직접 확인:** 데모 `free` 게시판에서 회원 A로 POST `/v1/boards/free/posts`를 실행해요.

```json
{"title":"첫 실습 글","content":"주문과 재고의 흐름을 이해했어요."}
```

반환된 `post_id`로 GET `/v1/posts/{post_id}`를 확인하고 POST `/v1/posts/{post_id}/comments`에 `{"content":"복습 완료"}`를 보내세요. 목록 검색은 GET `/v1/boards/free/posts`의 `search_type=TITLE`, `keyword=실습`을 사용합니다. 수정은 PUT, 삭제는 DELETE이며 삭제 성공은 204예요. B로 바꿔 남의 글을 수정할 때 거절되는지도 확인하세요.

데모 free는 회원 작성용입니다. 비회원 글·댓글은 비회원 권한을 허용한 게시판에서만 가능하며 이름과 비밀번호가 필요해요. 이를 확인하려고 공개 권한을 임의로 넓히지 말고 `tests/test_api.py`의 격리 사례를 보세요.

## 마무리. 내가 이해했다는 증거

- 어떤 요청이 어느 네 계층을 지나는지 실제 함수로 설명할 수 있나요?
- 200·201·204와 400·401·403·404·409·422를 이번 실습 사례로 구분할 수 있나요?
- 재고 부족, 남의 주문, 중복 취소가 실패하면서 데이터는 보존됨을 확인했나요?
- 화면이 고정 더미가 아니라 DB와 연결됐는지 API·필터·상세·주문 전후 재고로 대조했나요?
- CORS가 로그인 보안을 대신하지 않으며 로그에 토큰을 남기면 안 되는 이유를 설명할 수 있나요?

2026-11-10 경로 변경 후 전체 테스트 **95 passed in 18.20s**(기존 93개 + 구조 검사 2개), compileall·ruff가 통과했습니다. 백업과 새 앱의 OpenAPI 17 paths/28 operations 및 8개 테이블 메타데이터가 동일하고 함수·클래스 AST 보존도 읽기 검수로 확인했습니다. 이는 추가 Claude 검수가 아니며 Claude 2회 검수는 11/9 기록입니다.

실제 HTTP에서 /docs·/·CSS 200, 상품 20개, 가입 201 → OAuth2 로그인 200 → 주문 201/재고 2 차감 → 취소 200/재고 원복 → 중복 취소 409를 확인했습니다. 미존재 상품 404, 잘못된 현재 비밀번호 400, 게시글 생성·조회·수정·삭제·삭제 후 조회 201/200/200/204/404, 로그아웃 204 → 같은 토큰 401도 확인했습니다. 공백 제목은 422입니다.

브라우저 도구의 timeoutMs 오류로 시각 검증과 제출용 캡처는 미완료입니다. HTTP 성공을 화면 검수 완료로 대신하지 않습니다. PPT/PDF·공개 Notion·GitHub 게시·EC2 배포는 여전히 미완료입니다. 상세 증거는 [11/10 검증 기록](VERIFICATION_2026-11-10.md)을 보세요.
