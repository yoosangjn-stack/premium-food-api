# Premium Food API: 한정 수량 식품 주문·재고 + 게시판

재고 초과 주문, 중복 취소로 인한 재고 증가, 다른 회원의 주문 접근을 방지하는 학습용 API입니다. 회원·인증과 게시판을 함께 구현하며, AX Engineer 학습을 위해 코드와 실패 사례를 직접 설명할 수 있도록 구성했습니다.

## 저장소 상태 · 2026-11-10

- `work/premium-food-board`의 검증된 구현을 `main`에 fast-forward로 반영했습니다.
- 저장소는 **비공개**입니다. 공개 전환·별도 게시판 제출 저장소·EC2 배포는 이번 병합에 포함하지 않습니다.
- [최신 main](https://github.com/yoosangjn-stack/premium-food-api/tree/main) · [작업 브랜치](https://github.com/yoosangjn-stack/premium-food-api/tree/work/premium-food-board)
- `.env`, 실제 DB, 가상환경, 로그, 백업은 Git에서 제외했습니다. 검사한 소스·테스트·문서만 반영합니다.

## 기준과 구현 범위

- [최신 발제문: 프로젝트(2) 백엔드 서비스 API 구현하기](https://app.notion.com/p/2-API-7443559b23138235848201fc2cd01522)
- [단계별 교안](https://app.notion.com/p/3273559b2313821cbd53812797e518d0), [SQLAlchemy ORM 교안](https://app.notion.com/p/0713559b231383358f5281eaf2dbf757)
- [선생님 게시판 저장소](https://github.com/yonggyo1125/backend_project_ax1): 게시판 구조 참고. 상품 주문·가격 스냅샷·취소 규칙은 우리 프로젝트의 확장입니다.

필수 구현 범위는 4계층, 순수 도메인, PostgreSQL 비동기 ORM/저장소, Pydantic·라우터·예외 처리, OAuth2/JWT 블랙리스트, CORS/로깅, Jinja2 화면입니다. 동시성 방어는 도전 A에 해당합니다. BackgroundTasks·스트리밍(도전 B), 캐싱·배포(도전 C)는 필수 완료와 구분하며 구현 완료로 표시하지 않습니다.

- 회원: 가입, 중복 검사, bcrypt 비밀번호 해시, 본인 비밀번호 변경.
- 인증: JSON 로그인, OAuth2 폼 로그인, JWT, 블랙리스트 로그아웃.
- 상품: 목록·상세, 관리자 생성·수정, 검색·재고·가격 필터, 정렬·페이지.
- 주문: 본인 주문 생성·목록·상세, 주문 당시 상품명·단가 보관, 소유자/관리자 취소.
- 재고: 행 잠금, 주문·재고 일괄 commit/rollback, 중복 취소 방지.
- 게시판: 설정, 글·댓글 CRUD, 작성자/역할 권한, 검색·페이지. 공개 작성자명은 username이며 실명·전화·이메일은 공개하지 않습니다.
- 화면: DB 상품 목록·상세 Jinja2, CSS, Swagger `/docs`.

결제·배송·환불은 범위 밖입니다. 상품 삭제 API는 없으며 CRUD 실습은 게시글로 확인합니다.

## 현재 디렉터리

```text
premium-food-api/
├── pyproject.toml, uv.lock, .env.example, .gitignore
├── README.md
├── docs/                         # 학습·검수·제출 안내
├── scripts/                      # check_db.py, create_tables.py, seed_product.py
├── tests/                        # API·인증·주문·동시성·웹 테스트
└── src/
    ├── main.py                   # FastAPI 앱, lifespan, 라우터·미들웨어
    ├── database.py               # 엔진, 세션, get_db, Base, DateTimeBase, init_models
    ├── templates/                # Jinja2 HTML
    ├── static/                   # CSS
    ├── auth/                     # 인증
    ├── user/                     # 회원
    ├── products/                 # 상품
    ├── orders/                   # 주문
    ├── board/                    # 게시판
    │   ├── presentation/         # router.py, schemas.py, dependencies.py
    │   ├── application/          # service.py
    │   ├── domain/               # 엔티티·규칙·저장소 계약
    │   └── infrastructure/       # models.py, repositories.py, 변환·보안
    ├── shared/                   # 공통 예외·로그·트랜잭션 계약/구현
    ├── wiring/                   # 의존성 객체 조립
    └── web/presentation/router.py # 상품 화면 라우터
```

auth/user/products/orders도 board와 같이 네 계층을 가집니다. board의 저장소 계약과 구현은 각각 `domain/repositories.py`, `infrastructure/repositories.py`입니다. 기능·계층 패키지에는 `__init__.py`가 있습니다. `src/premium_food_api` 중첩과 루트 호환 진입점은 제거했고 앱 진입점은 `src/main.py`입니다. uv는 `[tool.uv] package = false`로 앱을 실행합니다.

### 컴포넌트와 요청 흐름

```text
HTTP JSON → presentation/router.py + schemas.py
          → application/service.py
            → domain 객체의 업무 규칙
            → repository 계약 → infrastructure/repositories.py
                              → models.py → PostgreSQL
          ← 순수 도메인 객체 ← ORM 행 변환
          → 응답 스키마 → JSON
브라우저 → web/presentation/router.py → 상품 서비스 → templates/ → HTML
wiring/ → 실제 저장소·서비스·트랜잭션 객체 조립
```

실행 호출 흐름과 import 의존성은 구분합니다. Domain은 FastAPI·SQLAlchemy를 import하지 않으며 Presentation은 Infrastructure를 직접 조립하지 않습니다. `wiring/commerce.py`가 같은 요청 세션을 주문·상품 저장소와 트랜잭션 관리자에 넣습니다. 서비스는 규칙을 호출하고 마지막에 한 번 commit, 실패 시 rollback합니다. 저장소의 flush는 최종 확정이 아닙니다.

## 최종 ERD: 실제 ORM 8개 테이블

현재 `src/*/infrastructure/models.py`와 `src/database.py`의 테이블 정의를 대조했습니다. 실제 회원·토큰·비밀번호·DB 접속값이 아닌 **구조만** 표시합니다. PK는 기본키, FK는 외래키, UK는 단일 컬럼 중복 금지입니다.

```mermaid
erDiagram
    users ||..o{ orders : user_id
    orders ||..o{ order_items : order_id
    products ||..o{ order_items : product_id
    boards ||..o{ posts : board_id
    users |o..o{ posts : author_id
    posts ||..o{ comments : post_id
    users |o..o{ comments : author_id
    users {
        uuid id PK "UUID; NOT NULL"
        varchar username UK "VARCHAR(30); NOT NULL"
        varchar phone "VARCHAR(15); NOT NULL"
        varchar email UK "VARCHAR(255); NOT NULL"
        varchar name "VARCHAR(50); NOT NULL"
        varchar password_hash "VARCHAR(255); NOT NULL"
        varchar role "VARCHAR(20); NOT NULL"
        boolean resign "BOOLEAN; NOT NULL"
        timestamptz created_at "TIMESTAMP WITH TIME ZONE; NOT NULL"
        timestamptz modified_at "TIMESTAMP WITH TIME ZONE; NULL allowed"
        timestamptz deleted_at "TIMESTAMP WITH TIME ZONE; NULL allowed"
    }
    products {
        integer id PK "INTEGER; NOT NULL"
        varchar name "VARCHAR(100); NOT NULL"
        integer price "INTEGER; NOT NULL"
        integer stock_quantity "INTEGER; NOT NULL"
    }
    orders {
        uuid id PK "UUID; NOT NULL"
        varchar order_number UK "VARCHAR(40); NOT NULL"
        uuid user_id FK "UUID; NOT NULL"
        timestamptz ordered_at "TIMESTAMP WITH TIME ZONE; NOT NULL"
        varchar status "VARCHAR(20); NOT NULL"
        bigint total_price "BIGINT; NOT NULL"
    }
    order_items {
        integer id PK "INTEGER; NOT NULL"
        uuid order_id FK "UUID; NOT NULL"
        integer product_id FK "INTEGER; NOT NULL"
        varchar product_name "VARCHAR(100); NOT NULL"
        integer quantity "INTEGER; NOT NULL"
        bigint unit_price "BIGINT; NOT NULL"
        bigint total_price "BIGINT; NOT NULL"
    }
    boards {
        varchar id PK "VARCHAR(30); NOT NULL"
        varchar board_name "VARCHAR(100); NOT NULL"
        integer page_size "INTEGER; NOT NULL"
        varchar edit_role "VARCHAR(20); NOT NULL"
        varchar view_role "VARCHAR(20); NOT NULL"
        varchar list_role "VARCHAR(20); NOT NULL"
        varchar comment_list_role "VARCHAR(20); NOT NULL"
        varchar comment_edit_role "VARCHAR(20); NOT NULL"
        timestamptz created_at "TIMESTAMP WITH TIME ZONE; NOT NULL"
        timestamptz modified_at "TIMESTAMP WITH TIME ZONE; NULL allowed"
        timestamptz deleted_at "TIMESTAMP WITH TIME ZONE; NULL allowed"
    }
    posts {
        bigint id PK "BIGINT; NOT NULL"
        varchar board_id FK "VARCHAR(30); NOT NULL"
        varchar title "VARCHAR(255); NOT NULL"
        text content "TEXT; NOT NULL"
        varchar author_name "VARCHAR(50); NOT NULL"
        uuid author_id FK "UUID; NULL allowed"
        varchar guest_password "VARCHAR(65); NULL allowed"
        timestamptz created_at "TIMESTAMP WITH TIME ZONE; NOT NULL"
        timestamptz modified_at "TIMESTAMP WITH TIME ZONE; NULL allowed"
        timestamptz deleted_at "TIMESTAMP WITH TIME ZONE; NULL allowed"
    }
    comments {
        bigint id PK "BIGINT; NOT NULL"
        bigint post_id FK "BIGINT; NOT NULL"
        text content "TEXT; NOT NULL"
        varchar author_name "VARCHAR(50); NOT NULL"
        uuid author_id FK "UUID; NULL allowed"
        varchar guest_password "VARCHAR(65); NULL allowed"
        timestamptz created_at "TIMESTAMP WITH TIME ZONE; NOT NULL"
        timestamptz modified_at "TIMESTAMP WITH TIME ZONE; NULL allowed"
        timestamptz deleted_at "TIMESTAMP WITH TIME ZONE; NULL allowed"
    }
    token_blacklist {
        varchar jti PK "VARCHAR(36); NOT NULL"
        timestamptz expired_at "TIMESTAMP WITH TIME ZONE; NOT NULL"
    }
```

### 관계를 읽는 법

- 회원 1명은 주문을 여러 번 할 수 있고, 주문항목마다 상품 1개를 참조합니다. 상품명·단가는 주문 당시 값으로 별도 보관합니다.
- 게시판 → 게시글 → 댓글 관계입니다. 회원이 쓴 글·댓글은 users를 참조하지만, 비회원 글·댓글의 author_id는 NULL일 수 있습니다.
- `token_blacklist`는 로그아웃한 JWT의 jti와 만료 시각만 저장합니다. **users와 FK가 없는 독립 테이블**이므로 연결선을 그리지 않습니다.
- 선은 실제 FK 기준이며, 주문당 최소 1개 항목 규칙은 도메인/API가 보장합니다. FK만으로 최소 항목 수를 강제하는 것은 아닙니다.
- `(order_id, product_id)`는 복합 UNIQUE입니다. 같은 주문 안에서 같은 상품을 중복 저장하지 않습니다. 각 컬럼이 단독 UNIQUE라는 의미는 아닙니다.

| 외래키 | 참조 | 물리 삭제 규칙 |
|---|---|---|
| orders.user_id | users.id | RESTRICT |
| order_items.order_id | orders.id | CASCADE |
| order_items.product_id | products.id | RESTRICT |
| posts.board_id | boards.id | NO ACTION (기본값) |
| posts.author_id | users.id | SET NULL |
| comments.post_id | posts.id | NO ACTION (기본값) |
| comments.author_id | users.id | SET NULL |

회원·게시글·댓글의 deleted_at 기반 소프트 삭제와 위 FK의 물리 삭제 규칙은 다릅니다. 주문 취소도 주문 삭제가 아니라 status를 CANCELLED로 바꾸고 재고를 한 번 복구하는 기능입니다.

모든 created_at/modified_at/deleted_at, ordered_at, expired_at은 시간대가 있는 TIMESTAMPTZ입니다. orders와 order_items의 CheckConstraint는 금액·수량·상태 정합성을 추가 방어합니다.

## 안전하게 실행하기

Python 3.13+, uv, PostgreSQL이 필요합니다. 저장소 clone은 공개 URL 확인 후 진행하고, 아래 명령은 프로젝트 루트에서 실행합니다. 아직 검증된 GitHub URL은 없습니다.

**새 실습 전용 DB만 사용하세요.** 기존 `.env`·실사용 DB를 덮어쓰지 마세요. create_all은 기존 테이블 구조를 바꾸는 마이그레이션 도구가 아닙니다.

```powershell
uv sync --group dev
# 새 실습 DB를 먼저 준비하고 아래 예시의 계정·주소를 직접 바꾸세요.
$env:DATABASE_URL = 'postgresql+asyncpg://USER:PASSWORD@127.0.0.1:5432/premium_food_learning'
$env:JWT_SECRET_KEY = uv run python -c "import secrets; print(secrets.token_urlsafe(64))"
$env:PYTHON_DOTENV_DISABLED = '1'
$env:CREATE_TABLES = 'true'
$env:DEMO_SEED = 'true'
$env:SQL_ECHO = 'False'
uv run uvicorn main:app --app-dir src --reload
```

이 PC에서는 표준 uvicorn 실행 파일이 Windows App Control 오류 4551로 차단되었습니다. 다음 Python 모듈 실행 방식은 실제 성공했습니다. 시스템 보안 설정은 변경하지 않았습니다.

```powershell
uv run python -m uvicorn main:app --app-dir src --host 127.0.0.1 --port 18084
```

- 표준 명령 기본 포트: 화면 http://127.0.0.1:8000/ , Swagger http://127.0.0.1:8000/docs
- 위 대안 명령의 포트: 화면 http://127.0.0.1:18084/ , Swagger http://127.0.0.1:18084/docs . 11/10 검증 후 이 로컬 서버를 열어 두었으며 컴퓨터/프로세스 종료 후에는 다시 실행해야 합니다.
- `CREATE_TABLES`, `DEMO_SEED`는 새 실습 DB에서만 켜며 기본값은 false입니다. 빈 상품 테이블에 데모 20개와 회원 작성용 free 게시판을 넣습니다. 재시작해도 기존 재고를 초기화하지 않습니다.
- 데모 회원·관리자는 자동 생성하지 않습니다. 일반 회원 가입 후 주문할 수 있고, 관리자 흐름은 격리 테스트의 admin fixture로 확인합니다.
- JWT 비밀키는 HS512용 64바이트 이상이며 Git·로그·공개 문서에 넣지 않습니다.
- CORS는 브라우저 출처 정책이지 인증을 대신하지 않습니다.

보조 스크립트는 `scripts/`로 이동했습니다. 실행 시 src를 import 경로로 지정해야 합니다. DB 생성·시드는 DB를 변경하므로 대상이 새 실습 DB인지 먼저 확인하세요.

```powershell
$env:PYTHONPATH = 'src'
uv run python scripts/check_db.py
# 필요할 때만: uv run python scripts/create_tables.py
# 필요할 때만: uv run python scripts/seed_product.py
```

## 개념 → 기능 → 코드 → 직접 확인

1. **도메인 규칙 → 재고 부족 방지 → `src/products/domain/entities.py`**: 주문 수량을 재고보다 크게 보냈을 때 실패하고 재고가 보존되는지 확인합니다.
2. **트랜잭션 → 주문·재고 함께 저장 → `src/orders/application/service.py`**: `tests/test_commerce.py`에서 주문 저장 실패 후 재고 rollback을 확인합니다.
3. **인증/인가 → 본인 주문 보호 → `src/auth/`, `src/wiring/user.py`**: 가입 후 Swagger Authorize의 username에 이메일을 넣습니다. 토큰 없음은 401, 다른 회원 주문 접근은 403을 확인합니다.
4. **ORM 변환 → DB와 규칙 분리 → `src/products/infrastructure/repositories.py`**: ProductModel이 Product로 바뀌는 `to_domain()`을 찾습니다.
5. **경로·쿼리/Jinja2 → 실제 상품 화면 → `src/web/presentation/router.py`, `src/templates/`**: `/`와 `/v1/products?page=1&size=2&sort=price`의 상품을 대조합니다. 주문 후 API 재고와 화면 새로고침 결과도 비교합니다.

주요 API는 `/v1/users`, `/v1/auth/token`, `/v1/auth/login`, `/v1/auth/logout`, `/v1/products`, `/v1/orders`, `/v1/orders/{order_id}/cancel`, `/v1/boards`, `/v1/boards/{board_id}/posts`, `/v1/posts/{post_id}/comments`입니다.

200은 조회·취소 성공, 201은 생성, 204는 삭제·로그아웃입니다. 400의 확인 사례는 잘못된 현재 비밀번호이며, 401/403은 인증/권한, 404는 미존재, 409는 상태 충돌, 422는 공백 제목 등을 포함한 입력 검증 실패입니다. 발제문은 도메인 차단 400을 예시로 들며 현재 구현은 재고 부족·중복 취소에 409를 사용합니다. 제출 시 이 차이를 설명하고 400·404·401 사례도 별도로 캡처해야 합니다.

## 테스트와 현재 증거

2026-11-10 경로 변경 후 전체 테스트 **95 passed in 18.48s**(기존 93개 + 구조 검사 2개), compileall·ruff가 통과했습니다. 백업과 새 앱의 OpenAPI 17 paths/28 operations 및 8개 테이블 메타데이터가 동일하고 함수·클래스 AST 보존도 읽기 검수로 확인했습니다. 이는 추가 Claude 검수가 아니며 Claude 2회 검수는 11/9 기록입니다.

실제 HTTP에서 /docs·/·CSS 200, 상품 20개, 가입 201 → OAuth2 로그인 200 → 주문 201/재고 2 차감 → 취소 200/재고 원복 → 중복 취소 409를 확인했습니다. 미존재 상품 404, 잘못된 현재 비밀번호 400, 게시글 생성·조회·수정·삭제·삭제 후 조회 201/200/200/204/404, 로그아웃 204 → 같은 토큰 401도 확인했습니다. 공백 제목은 422입니다.

브라우저 도구의 timeoutMs 오류로 시각 검증과 제출용 캡처는 미완료입니다. HTTP 성공을 화면 검수 완료로 대신하지 않습니다. 비공개 GitHub main에 구현 코드를 반영했습니다. 저장소 공개 전환·PPT/PDF·공개 Notion·EC2 배포는 미완료입니다. 상세 증거는 [11/10 검증 기록](docs/VERIFICATION_2026-11-10.md)을 보세요.

테스트는 **로컬 premium_food_test 전용 DB**만 허용합니다. 테이블 생성과 테스트 데이터 쓰기가 있으므로 실사용 DB를 연결하면 안 됩니다.

```powershell
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://USER:PASSWORD@127.0.0.1:5432/premium_food_test'
$env:PYTHON_DOTENV_DISABLED = '1'
uv run python -m pytest -q
uv run ruff check .
uv run python -m compileall -q src tests scripts
```

[11/9 검증 기록](docs/VERIFICATION.md), [Claude 검수 기록](docs/CLAUDE_REVIEW.md), [11/9 작업 기록](docs/WORKLOG_2026-11-09.md)은 당시 구조의 역사 자료입니다. 현재 경로 안내는 이 README를 기준으로 봅니다. 경로 변경 전 소스 148개는 프로젝트 밖 `_backups/premium-food-api-before-standard-layout-20261110-100207`에 보관했습니다.

## 학습·제출

- [학습 가이드](docs/LEARNING_GUIDE.md), [Chapter 3 연결 실습](docs/CHAPTER3_STORY.md)
- [제출 체크리스트](docs/SUBMISSION_CHECKLIST.md)

PPT/PDF, 공개 팀 Notion URL, Swagger·Jinja2·성공/오류·로그아웃 차단 캡처는 아직 미완료입니다. 코드는 [비공개 GitHub main](https://github.com/yoosangjn-stack/premium-food-api/tree/main)에 반영했습니다. 저장소 공개 전환과 EC2 배포는 하지 않았으며, 접근 권한이 없는 사람은 현재 링크를 열 수 없습니다. 실제 팀원 이름·역할·활동은 확인된 사실만 기록하며 가상의 팀 기록을 만들지 않습니다.

## 알려진 한계

- 비밀번호 변경만으로 기존 JWT가 모두 무효화되지는 않습니다. 해당 토큰의 로그아웃 또는 만료와 구분합니다.
- 회원 응답은 data envelope, 상품·주문·게시판은 직접 객체이며 오류 JSON은 공통입니다.
- 비회원 글 삭제는 DELETE 본문에 비밀번호를 받으므로 클라이언트·프록시의 본문 지원을 확인해야 합니다.
- 주문용 UI는 구현 범위가 아니며 회원·주문·게시판 조작은 Swagger로 실습합니다.
