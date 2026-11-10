# 후속 리뷰 결과 (붙여넣은 코드 기준)

이전 지적 5건은 붙여주신 코드에서 모두 해소된 것으로 보입니다.

- **재고 옵션**: 파서 기반 테스트로 실제 `<option>` 3개를 검증합니다.
- **commerce DI**: `wiring/commerce.py`로 분리되어 presentation은 placeholder만 가집니다.
- **게시판 작성자**: 작성자가 `username`으로 바뀌었고 실명·연락처 비노출 테스트가 있습니다.
- **로그아웃 중복 insert**: `on_conflict_do_nothing`과 실제 동시성 테스트로 해결됐습니다.
- **500 CORS/로깅**: CORS가 바깥쪽에 있고, 안전한 JSON 응답과 타이밍 헤더를 테스트로 확인합니다.

남은 사항은 아래와 같습니다. 일부는 붙여주시지 않은 코드에 따라 성립 여부가 갈리므로 조건을 함께 적었습니다.

## 1. (확인 필요, 실제 버그 가능성 높음) 카탈로그 입력값에 `None`이 렌더링될 수 있음
- **위치**: `web/templates/catalog.html`의 `value="{{ filters.q }}"`, `{{ filters.min_price }}`, `{{ filters.max_price }}`
- **문제**: router가 빈 값을 `None`으로 넘기면 Jinja2는 이를 문자열 `"None"`으로 출력합니다.
  - 가격 필드: `type="number"`라서 브라우저가 무효값으로 비우는 경우가 많습니다.
  - 상품명 검색창: 실제로 `None`이 표시됩니다. 이 상태로 다시 제출하면 `q=None`으로 검색됩니다.
- **테스트 공백**: `test_catalog_empty_and_blank_price_fields`는 상태 코드와 빈 목록 문구만 확인하므로 이 문제를 잡지 못합니다.
- **수정**: router에서 `None`을 `""`로 정규화하는 편이 단순합니다. 템플릿에서 처리한다면 `{{ filters.min_price if filters.min_price is not none else '' }}`처럼 쓰세요. `or ''`는 `0`까지 지우므로 피해야 합니다.
- **테스트 추가**: 빈 파라미터로 요청했을 때 `value="None"`이 응답에 없는지 assert하세요.

## 2. (확인 필요) 요청 INFO 로그가 실제로 출력되지 않을 수 있음
- **위치**: `shared/core/middlewares.py`의 `logger.info(...)`
- **문제**: `logging.basicConfig` 같은 앱 로깅 설정이 어디에도 없다면 기본 uvicorn 실행에서 문제가 생깁니다.
  - uvicorn은 `uvicorn.*` 로거만 설정하고 root 로거는 건드리지 않습니다.
  - 그래서 `premium_food_api.*`의 INFO 로그는 버려지고, 500 `logger.error`만 lastResort 핸들러로 출력됩니다.
- **테스트 공백**: 테스트는 헤더만 검증하므로 이 문제를 잡지 못합니다.
- **수정**: 진입점에서 `logging.basicConfig(level=logging.INFO)`를 한 번 호출하세요. 이미 설정 코드가 있다면 이 항목은 해당 없습니다.

## 3. (조건부) 비회원 비밀번호 최대 길이
- **위치**: `GuestPassword.create`는 최소 6자만 검사합니다.
- **문제**: `BcryptPasswordHasher`가 `bcrypt` 5.x를 직접 쓰면 72바이트를 넘는 입력에서 `ValueError`가 발생해 500 응답이 납니다. 4.x에서는 72바이트 이후가 조용히 잘린 채 해시됩니다.
- **수정**: 요청 스키마에 이미 `max_length`가 있으면 문제없습니다. 없다면 도메인이나 스키마에 상한(예: 72바이트 이하)을 두고 422로 응답하세요.

## 경미 (선택)
- **`check_db.py`**: 모듈 최상단에서 `asyncio.run(check_db())`를 실행합니다. 다른 스크립트와 맞춰 `if __name__ == "__main__":` 가드를 두는 것을 권합니다.
- **`Post.create`, `Comment.create`**: 저장 시 title/content를 `strip()`하지 않아 `update_content`와 동작이 다릅니다. 같은 입력이 생성 때와 수정 때 다르게 저장됩니다.
- **`test_architecture.py`**: presentation 계층이 `wiring`을 import하는 경우는 막지 않습니다. 현재 위반은 없지만 guard 목록에 `"wiring"`을 추가하면 이번 DI 수정이 회귀 없이 유지됩니다.

## 문제 없음으로 확인한 부분
- **세션 공유**: 한 요청 안의 `Depends(get_db)`는 FastAPI가 캐시하므로, 여러 repository와 transaction manager가 같은 세션을 씁니다.
- **미로그인 권한 비교**: role이 `None`이어도 `== Role.ADMIN` 비교가 안전하게 False가 됩니다.
- **500 로그 보안**: `traceback.format_tb`는 예외 메시지와 locals를 포함하지 않아 SQL 파라미터가 노출되지 않습니다.
- **CORS 설정**: Bearer 헤더 방식이므로 `allow_credentials=False`가 적절합니다.
- **동시성 fixture**: 정리 범위가 UUID로 한정되어 있고, 요청 실패 시 rollback합니다. barrier로 두 요청이 서로 다른 커넥션을 쓰는 것도 검증합니다.

**결론**: 실질적으로 남은 결함 후보는 1번(카탈로그 `None` 렌더링)과 2번(INFO 로그 미출력)입니다. 둘 다 붙여주시지 않은 router와 로깅 설정에 따라 성립 여부가 정해지니, 해당 부분만 확인하시면 됩니다.

(요청하신 대로 도구나 파일에 접근하지 않고 붙여주신 코드만으로 검토했습니다.)
