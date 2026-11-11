// Premium Food API 테스트 화면: 프레임워크 없이 fetch만 사용합니다.
// - JWT는 아래 accessToken 변수(메모리)에만 둡니다. localStorage·sessionStorage·쿠키에 저장하지 않습니다.
// - 화면에 넣는 모든 값은 textContent 또는 new Option(text)로 넣습니다. (HTML로 해석하지 않음)
(function () {
  "use strict";

  const MAX_LOG_ENTRIES = 20;
  // 이 이름이 들어간 키의 값은 응답 기록에 보여주지 않습니다.
  const SECRET_KEY = /token|password|authorization|secret|jti/i;

  let accessToken = null;
  let loginEmail = "";
  let busy = false;

  const byId = (id) => document.getElementById(id);
  const log = byId("response-log");
  const productSelect = byId("product-select");
  const orderSelect = byId("order-select");
  const boardSelect = byId("board-select");
  const postList = byId("post-list");

  // 비밀 값은 "[숨김]"으로 바꾼 복사본을 돌려줍니다. 오류 메시지 목록(배열)은 그대로 보여줍니다.
  function redact(value, key = "") {
    if (Array.isArray(value)) return value.map((item) => redact(item));
    if (value !== null && typeof value === "object") {
      const copy = {};
      for (const [childKey, child] of Object.entries(value)) copy[childKey] = redact(child, childKey);
      return copy;
    }
    return SECRET_KEY.test(key) ? "[숨김]" : value;
  }

  function addLog(title, ok, body) {
    const entry = document.createElement("article");
    entry.className = "tu-entry";
    const heading = document.createElement("p");
    heading.className = ok ? "tu-ok" : "tu-fail";
    heading.textContent = title;
    const pre = document.createElement("pre");
    pre.textContent = body;
    entry.append(heading, pre);
    log.prepend(entry);
    while (log.children.length > MAX_LOG_ENTRIES) log.lastElementChild.remove();
  }

  // 서버에 보내지 않고 화면에서 막은 경우를 기록합니다.
  function addNote(message) {
    addLog("요청하지 않음", false, message);
  }

  async function callApi(method, path, body) {
    const headers = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const sendToken = Boolean(accessToken) && path !== "/v1/auth/login" && path !== "/v1/users";
    if (sendToken) headers.Authorization = `Bearer ${accessToken}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(path, {
        signal: controller.signal,
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        cache: "no-store",
      });
      const text = await response.text();
      if (response.status === 401 && sendToken) clearToken();
      let data = null;
      let shown = "(본문 없음)";
      if (text) {
        try {
          data = JSON.parse(text);
          shown = JSON.stringify(redact(data), null, 2);
        } catch {
          shown = "(JSON이 아닌 응답이라 표시하지 않습니다)";
        }
      }
      addLog(`${method} ${path} → HTTP ${response.status}`, response.ok, shown);
      return { ok: response.ok, status: response.status, data };
    } catch {
      addLog(`${method} ${path} → 네트워크 오류`, false, "응답을 확인하지 못했습니다. 주문·취소·글 작성은 처리됐을 수 있으니 목록을 조회한 뒤 재시도하세요.");
      return { ok: false, status: 0, data: null };
    } finally {
      clearTimeout(timer);
    }
  }

  // 요청 중에는 모든 버튼을 비활성화해 중복 클릭(중복 주문·중복 취소)을 막습니다.
  function setBusy(value) {
    busy = value;
    for (const button of document.querySelectorAll("main button")) button.disabled = value;
  }

  function action(handler) {
    return async (event) => {
      event.preventDefault();
      const target = event.currentTarget; // await 뒤에는 currentTarget이 비므로 미리 저장합니다.
      if (busy) return;
      setBusy(true);
      try {
        await handler(target);
      } finally {
        setBusy(false);
      }
    };
  }

  function fillSelect(select, items, toOption, emptyText) {
    const previous = select.value;
    select.replaceChildren();
    if (items.length === 0) {
      select.append(new Option(emptyText, ""));
      return;
    }
    for (const item of items) {
      const [value, label] = toOption(item);
      select.append(new Option(label, value));
    }
    if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  }

  function resetSelect(select, text) {
    select.replaceChildren(new Option(text, ""));
  }

  const won = (amount) => `${Number(amount).toLocaleString("ko-KR")}원`;

  function clearToken() {
    accessToken = null;
    loginEmail = "";
    resetSelect(orderSelect, "먼저 내 주문을 불러오세요");
    updateAuthStatus();
  }

  function updateAuthStatus() {
    byId("auth-status").textContent = accessToken ? `로그인됨 (${loginEmail})` : "로그아웃";
  }

  // 1. 회원
  async function signUp(form) {
    const fields = form.elements;
    const body = {
      username: fields.username.value.trim(),
      phone: fields.phone.value.trim(),
      email: fields.email.value.trim(),
      name: fields.name.value.trim(),
      password: fields.password.value,
    };
    fields.password.value = "";
    await callApi("POST", "/v1/users", body);
  }

  async function logIn(form) {
    const email = form.elements.email.value.trim();
    const password = form.elements.password.value;
    form.elements.password.value = "";
    const result = await callApi("POST", "/v1/auth/login", { email, password });
    if (result.ok && result.data && typeof result.data.access_token === "string") {
      accessToken = result.data.access_token;
      loginEmail = email;
      resetSelect(orderSelect, "먼저 내 주문을 불러오세요");
      updateAuthStatus();
    }
  }

  async function logOut() {
    // 토큰이 없으면 서버가 401을 돌려줍니다. 결과와 관계없이 화면의 토큰은 지웁니다.
    await callApi("POST", "/v1/auth/logout");
    clearToken();
  }

  // 2. 상품·주문
  async function loadProducts() {
    const result = await callApi("GET", "/v1/products?size=100");
    if (!result.ok) return;
    fillSelect(productSelect, result.data.items,
      (p) => [String(p.id), `#${p.id} ${p.name} · ${won(p.price)} · 재고 ${p.stock_quantity}개`],
      "상품이 없습니다");
  }

  async function createOrder(form) {
    // 빈 값·0·소수는 그대로 보내 서버 검증(422)을 확인할 수 있게 합니다.
    const item = {
      product_id: Number(form.elements.product_id.value),
      quantity: Number(form.elements.quantity.value),
    };
    const result = await callApi("POST", "/v1/orders", { items: [item] });
    if (result.ok) {
      await loadProducts();
      await loadOrders();
    }
  }

  // 3. 내 주문
  async function loadOrders() {
    const result = await callApi("GET", "/v1/orders?limit=100");
    if (!result.ok) {
      resetSelect(orderSelect, "주문을 불러오지 못했습니다");
      return;
    }
    fillSelect(orderSelect, result.data,
      (o) => [o.id, `${o.order_number} · ${o.status} · ${won(o.total_price)}`],
      "주문이 없습니다");
  }

  async function cancelOrder() {
    const orderId = orderSelect.value;
    if (!orderId) {
      addNote("취소할 주문을 먼저 선택하세요.");
      return;
    }
    await callApi("POST", `/v1/orders/${encodeURIComponent(orderId)}/cancel`);
    // 성공(200)이든 중복 취소(409)든 재고와 주문 상태를 다시 확인합니다.
    await loadProducts();
    await loadOrders();
  }

  // 4. 게시판
  async function loadBoards() {
    const result = await callApi("GET", "/v1/boards");
    if (!result.ok) return;
    fillSelect(boardSelect, result.data, (b) => [b.board_id, `${b.board_name} (${b.board_id})`], "게시판이 없습니다");
  }

  async function loadPosts() {
    const boardId = boardSelect.value;
    if (!boardId) {
      addNote("게시판을 먼저 선택하세요.");
      return;
    }
    const result = await callApi("GET", `/v1/boards/${encodeURIComponent(boardId)}/posts`);
    postList.replaceChildren();
    if (!result.ok) return;
    const items = result.data.items;
    if (items.length === 0) {
      const empty = document.createElement("li");
      empty.textContent = "글이 없습니다";
      postList.append(empty);
    }
    for (const post of items) {
      const li = document.createElement("li");
      li.textContent = `#${post.post_id} ${post.title} · ${post.author.author_name}`;
      postList.append(li);
    }
  }

  async function createPost(form) {
    const boardId = boardSelect.value;
    if (!boardId) {
      addNote("게시판을 먼저 선택하세요.");
      return;
    }
    const body = { title: form.elements.title.value, content: form.elements.content.value };
    const result = await callApi("POST", `/v1/boards/${encodeURIComponent(boardId)}/posts`, body);
    if (result.ok) {
      form.reset();
      await loadPosts();
    }
  }

  byId("signup-form").addEventListener("submit", action(signUp));
  byId("login-form").addEventListener("submit", action(logIn));
  byId("logout-button").addEventListener("click", action(logOut));
  byId("load-products").addEventListener("click", action(loadProducts));
  byId("order-form").addEventListener("submit", action(createOrder));
  byId("load-orders").addEventListener("click", action(loadOrders));
  byId("cancel-order").addEventListener("click", action(cancelOrder));
  byId("load-boards").addEventListener("click", action(loadBoards));
  byId("load-posts").addEventListener("click", action(loadPosts));
  byId("post-form").addEventListener("submit", action(createPost));

  // 뒤로/앞으로 가기 캐시에서 페이지가 복원되어도 이전 토큰을 다시 쓰지 않습니다.
  window.addEventListener("pagehide", clearToken);
  window.addEventListener("pageshow", updateAuthStatus);
  updateAuthStatus();
})();
