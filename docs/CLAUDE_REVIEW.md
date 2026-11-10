# premium-food-api 코드 리뷰 (붙여 넣은 소스 기준, 읽기 전용)

요청하신 대로 도구는 사용하지 않았고 파일도 수정하지 않았습니다. 붙여 넣지 않은 `src/main.py`, `check_db.py`, `create_tables.py`, `seed_product.py`, `main.py`(루트)는 검토 범위에서 빠졌습니다.

## 총평

핵심 요구사항은 대체로 정확하게 구현되어 있습니다.

- **재고:** 정렬된 `FOR UPDATE` 락, 검증 후 일괄 차감, 단일 커밋/롤백으로 처리합니다.
- **주문 취소:** 주문 행을 먼저 잠근 뒤 `Order.cancel()`로 상태를 확인하므로 재고는 한 번만 복원됩니다.
- **인증:** 더미 해시로 타이밍을 맞추고, `jti` 블랙리스트를 쓰고, 잘못된 `Authorization` 헤더는 비회원이 아니라 401로 처리합니다.
- **소유권 검사:** 주문·게시글·댓글 모두 들어가 있습니다.

테스트(동시 주문, 동시 취소, 롤백)도 핵심 경로를 잘 덮고 있습니다. 아래는 실제로 고쳐야 할 항목과 선택 정리 항목을 나눈 것입니다.

---

## A. 구체적 버그 / 요구사항 위반

### 1. [중간] `web/templates/catalog.html`: "재고 있음" 옵션 태그가 깨져 있음
```html
<option value="">전체 상품</option value="in_stock" {% if ... %}selected{% endif %}>재고 있음</option>
```
- `<option value="in_stock" ...>`의 여는 태그가 빠지고 닫는 태그에 속성이 붙어 있습니다.
- 그 결과 브라우저에는 "재고 있음" 선택지가 없고, UI에서 `in_stock` 필터를 고를 수 없습니다.
- `test_catalog_filters_and_preserves_pagination`은 쿼리스트링을 직접 넣기 때문에 이 버그를 잡지 못합니다.
- 수정 방법: `<option value="">전체 상품</option><option value="in_stock" ...>재고 있음</option>`
- 테스트 보강: 응답 HTML에 `value="in_stock"`이 들어 있는지 확인하는 assert를 추가하세요.

### 2. [중간·아키텍처] `products/presentation/dependencies.py`, `orders/presentation/dependencies.py`: Presentation이 Infrastructure를 직접 import
- `get_product_service`와 `get_order_service`가 `SQLAlchemyProductRepository`, `SQLAlchemyOrderRepository`, `SQLAlchemyTransactionManager`를 직접 생성합니다.
- user/auth/board는 "presentation에는 placeholder, `wiring/`에서 `dependency_overrides`로 연결"하는 패턴인데, commerce 모듈만 엄격한 4계층 규칙을 어깁니다.
- `web/presentation/router.py`도 같은 함수를 쓰므로 함께 영향을 받습니다.
- 학습자 입장에서는 "왜 두 방식이 있지?"라는 혼란이 생깁니다.
- 수정 방법: presentation에는 `provide_product_service()` / `provide_order_service()` placeholder만 둡니다. 구현은 `wiring/commerce.py`로 옮기고 `wire_dependencies`에 등록합니다.

### 3. [중간·개인정보] `wiring/board.py::_get_current_author`: 실명(`name`)을 작성자명으로 사용
```python
return Author.member(user_id=user.id, username=user.name)
```
- 파라미터 이름은 `username`인데 넘기는 값은 `user.name`(실명)입니다.
- 회원 게시글과 댓글에 실명이 공개됩니다.
- `AUTHOR_NAME` 검색(`post_repository._build_search_filter`)으로 실명 검색까지 가능해집니다.
- 수정 방법: `username=user.username`으로 바꿉니다. `Author`의 20자 제한도 username 규칙(3~30자)에 맞게 조정이 필요합니다. 30자 username이면 `ValidationException`이 납니다.

### 4. [낮음] `auth/application/service.py::AuthService.logout`: 동시 로그아웃 시 409 응답
- `is_blacklisted` 확인 후 `add`를 하므로 확인과 삽입 사이에 경쟁이 생깁니다.
- 같은 토큰으로 동시에 두 번 로그아웃하면 PK `IntegrityError`가 나고, 사용자는 204 대신 409("중복되었거나…")를 받습니다.
- 수정 방법: repository `add`에서 PostgreSQL `insert(...).on_conflict_do_nothing()`을 사용합니다. 추가 프레임워크 없이 SQLAlchemy 기본 기능으로 됩니다.

### 5. [낮음·인증] `user/application/service.py::change_password`: 비밀번호를 바꿔도 기존 토큰이 유효함
- 비밀번호를 변경해도 이미 발급된 JWT는 만료(60분) 전까지 계속 쓸 수 있습니다.
- 교육용이라면 "알려진 한계"로 README에 명시하는 것으로 충분합니다.
- 막으려면 사용자에 `password_changed_at`을 두고 `iat`와 비교하는 방법이 가장 단순합니다.

### 6. [낮음] `shared/core/exception_handlers.py::unhandled_exception_handler`: 500 응답 경로의 한계
- Starlette는 `Exception` 핸들러를 가장 바깥의 `ServerErrorMiddleware`에서 실행합니다. 그래서 500 응답에는 CORS 헤더가 없고, `log_request` 미들웨어 로그도 남지 않습니다.
- 핸들러는 예외 타입 이름만 기록합니다. 학습자가 원인을 추적하기 어렵습니다.
- 수정 방법: 서버 로그에만 `logger.exception(...)`으로 traceback을 남깁니다. 응답 본문은 지금처럼 일반 메시지를 유지합니다.

---

## B. 동시성 / 트랜잭션 점검 결과 (문제 없음 확인)

- **`OrderService.create_order`:** 상품 락 → 전체 검증 → `save` → 주문 `add` → 단일 commit 순서입니다. 하나라도 실패하면 rollback되므로 부분 차감이 없습니다.
- **`OrderService.cancel_order`:** 주문 `FOR UPDATE` → 상태 전이 → 상품 락(같은 ID 정렬 순서) 순서입니다. 주문 생성은 주문 락을 잡지 않으므로 락 순서가 역전될 일이 없어 데드락 위험이 낮습니다.
- **`populate_existing=True`:** identity map에 남은 이전 재고 값을 덮어쓰므로 올바른 처리입니다.
- **`get_db`:** FastAPI 의존성 캐시 덕분에 한 요청 안에서 auth/repo/transaction이 같은 세션을 공유합니다.

---

## C. 선택적 정리 (교육용 단순화)

1. **역할 표현이 두 가지입니다.** user/orders는 문자열 `"ADMIN"`, board는 `Role` enum을 씁니다. `OrderService._check_access`의 `role != "ADMIN"` 같은 문자열 비교를 줄이려면 shared domain에 enum 하나로 통일하는 편이 설명하기 쉽습니다.
2. **`PasswordHasher` 인터페이스와 `BcryptPasswordHasher` 구현이 중복입니다.** `board/`와 `user/`에 동일하게 있으니 `shared/`로 하나만 두면 됩니다.
3. **`products/models.py`의 호환 alias 이름이 혼동을 줍니다.** `ProductModel as Product`가 도메인 `Product`와 이름이 겹칩니다. 기존 import가 없다면 삭제하세요. `database.py` 재노출 파일도 같은 판단이 필요합니다.
4. **`resolve_optional_user`(`wiring/user.py`)의 함수 내부 import와 수동 생성:** 순환 import를 피하려고 `create_auth_service`를 직접 호출하고 있습니다. `Depends(create_auth_service)`로 받도록 구조를 정리하면 더 읽기 쉽습니다.
5. **`list_boards(include_deleted=True)` 응답에 `deleted_at`이 없습니다.** 관리자가 어떤 게시판이 삭제됐는지 구분할 수 없습니다.
6. **`Board.__post_init__`은 `board_name`을 strip하지 않습니다.** `update_config`는 strip하므로 일관성이 없습니다.
7. **`CreatePostRequest.guest_password`의 `min_length=6`이 회원에게도 적용됩니다.** 회원이 무시될 짧은 값을 보내도 422가 납니다.
8. **영문/한글 에러 메시지가 섞여 있습니다.** orders/products는 영문, 나머지는 한글이므로 교안 일관성 측면에서 통일을 권합니다.
9. **DELETE 요청 본문:** 비회원 삭제 비밀번호를 DELETE 본문으로 받는데, 일부 클라이언트나 프록시는 DELETE 본문을 버립니다. 교안에 주의사항으로 한 줄 남겨두면 좋습니다.

---

## 우선순위 요약
1. `catalog.html` option 태그 수정과 테스트 보강
2. commerce 의존성을 `wiring/`으로 이동해 4계층 일관성 확보
3. 게시판 작성자명을 `username`으로 변경
4. 블랙리스트 `ON CONFLICT DO NOTHING` 적용, 500 로그에 traceback 추가
