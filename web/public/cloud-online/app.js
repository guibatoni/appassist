"use strict";

/* DUELTRACE Cloud hosted browser, independent of React/Next hydration.
 * All game data is fetched directly from the user's localhost.
 * The pairing key exists only in this tab's JS memory.
 * Never use innerHTML for mod/card/opponent strings from the connector.
 */
(() => {
  const BASE = "http://127.0.0.1:8765";
  const MAX_IMAGES = 16;
  const $ = (id) => document.getElementById(id);
  let token = "";
  let state = null;
  let currentTab = "inicio";
  let selectedCard = null;
  let timer = null;
  let activeImages = [];
  let busy = false;
  let search = "";
  let opponentId = 0;
  let page = 0;

  const el = (tag, className = "", value = null) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== null) node.textContent = String(value);
    return node;
  };
  const append = (parent, ...children) => {
    for (const child of children) if (child != null) parent.append(child);
    return parent;
  };
  const clear = (node) => node.replaceChildren();
  const stat = (x) => typeof x === "number" ? x.toLocaleString("pt-BR") : "—";
  const notice = (message, error = false) => {
    const node = $("status");
    node.textContent = message;
    node.className = message ? "notice visible" + (error ? " error" : "") : "notice";
  };
  const section = (title) => {
    const p = el("section", "panel");
    append(p, el("h2", "", title));
    return p;
  };
  const button = (label, click, className = "") => {
    const b = el("button", className, label);
    b.type = "button";
    b.addEventListener("click", click);
    return b;
  };
  const linkTo = (text, cardId) => {
    if (!Number.isInteger(cardId) || cardId < 1 || cardId > 722) return el("span", "", text);
    return button(text, () => showCard(cardId), "rowlink");
  };

  async function request(path, method = "GET", data = null) {
    if (!token || token.length < 24) throw Error("Chave temporária ausente ou incompleta.");
    if (!path.startsWith("/v1/")) throw Error("Rota de Connector inválida.");
    const ctl = new AbortController();
    const time = method === "POST" && path === "/v1/import" ? 240000 : method === "POST" ? 45000 : 15000;
    const id = setTimeout(() => ctl.abort(), time);
    try {
      const response = await fetch(BASE + path, {
        method, cache: "no-store", mode: "cors", credentials: "omit",
        referrerPolicy: "no-referrer", signal: ctl.signal,
        headers: Object.assign({Authorization: "Bearer " + token},
          method === "POST" ? {"Content-Type": "application/json"} : {}),
        ...(method === "POST" ? {body: JSON.stringify(data || {})} : {})
      });
      if (!response.ok) {
        const json = await response.json().catch(() => ({}));
        throw Error(typeof json.error === "string" ? json.error : "Connector retornou HTTP " + response.status);
      }
      return await response.json();
    } catch (e) {
      if (e && e.name === "AbortError") throw Error("Tempo esgotado. Confira se o Connector Windows está aberto.");
      if (e instanceof TypeError) throw Error("Não foi possível acessar o Connector no PC. Abra DUELTRACE-Connector.exe, permita acesso à rede local no Chrome e confira a versão.");
      throw e;
    } finally { clearTimeout(id); }
  }

  async function getArt(sha, id) {
    if (!/^[0-9a-f]{64}$/.test(sha || "") || !Number.isInteger(id) || id < 1 || id > 722) return null;
    const response = await fetch(BASE + "/v1/art?sha=" + sha + "&id=" + id, {
      mode: "cors", cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer",
      headers: {Authorization: "Bearer " + token}
    });
    if (!response.ok) return null;
    const blob = await response.blob();
    if (blob.type !== "image/png" || blob.size > 8_000_000) return null;
    return URL.createObjectURL(blob);
  }

  function resetImages() {
    activeImages.forEach(url => URL.revokeObjectURL(url));
    activeImages = [];
  }
  function mountArt(node, sha, cardId) {
    if (!sha || activeImages.length >= MAX_IMAGES) return;
    getArt(sha, cardId).then(url => {
      if (url) {
        if (!node.isConnected) { URL.revokeObjectURL(url); return; }
        activeImages.push(url); node.src = url;
      }
    }).catch(() => {});
  }

  function resetUI() {
    clear($("panel"));
    resetImages();
    $("workspace").classList.toggle("hidden", !token);
    $("pair").classList.toggle("hidden", !!token);
    $("connection").textContent = token ? "Connector local autenticado" : "Conector desconectado";
    $("active-mod").textContent = state?.activeName || "Nenhuma ISO ativada";
    $("counts").textContent = state ? (state.mods?.length || 0) + " mods · " + (state.cards?.length || 0) + " cartas" : "";
    document.querySelectorAll("[data-tab]").forEach(b => b.classList.toggle("active", b.dataset.tab === currentTab));
  }
  function stopTimer() {
    if (timer) clearInterval(timer);
    timer = null;
  }
  async function connect() {
    if (busy) return;
    const key = $("key").value.trim();
    if (key.length < 24) { notice("Copie a chave temporária inteira do Connector (mínimo de 24 caracteres).", true); return; }
    busy = true; $("connect").disabled = true;
    notice("Consultando o Connector local no seu Windows...");
    try {
      token = key;
      const result = await request("/v1/state");
      if (result.storage !== "local-only" || result.cloudUpload !== false) throw Error("Connector não confirma isolamento local.");
      state = result;
      $("key").value = "";
      currentTab = "mods";
      notice("Conectado ao seu PC. Nenhum arquivo do jogo foi enviado à hospedagem.");
      await render();
    } catch (error) {
      token = ""; state = null;
      notice(error instanceof Error ? error.message : "Não foi possível conectar.", true);
      resetUI();
    } finally { busy = false; $("connect").disabled = false; }
  }

  function disconnect() {
    token = ""; state = null; selectedCard = null; search = ""; opponentId = 0;
    stopTimer(); notice("Desconectado. A chave da sessão foi descartada.");
    resetUI();
  }

  async function updateState() {
    const updated = await request("/v1/state");
    if (updated.storage !== "local-only" || updated.cloudUpload !== false) throw Error("Resposta local inválida.");
    state = updated;
    return updated;
  }

  async function act(path, body, success) {
    if (busy) return;
    busy = true; notice("Processando no computador. Um seletor de arquivos poderá abrir no Windows...");
    try {
      const response = await request(path, "POST", body);
      await updateState();
      notice(response?.cancelled ? "Seleção cancelada." : success);
      await render();
    } catch (e) { notice(e instanceof Error ? e.message : "Operação local indisponível.", true); }
    finally { busy = false; }
  }

  function tabs(tab) {
    selectedCard = null;
    currentTab = tab;
    page = 0; search = "";
    stopTimer();
    void render();
  }

  function textField(container, label, current, change) {
    const field = el("div");
    const l = el("label", "", label);
    const inp = el("input");
    inp.value = current;
    inp.setAttribute("aria-label", label);
    inp.addEventListener("change", () => change(inp.value.trim()));
    append(field, l, inp);
    container.append(field);
  }

  function drawTable(node, headers, rows) {
    const scroll = el("div", "table-scroll");
    const table = el("table");
    const thead = el("thead"); const header = el("tr");
    headers.forEach(h => append(header, el("th", "", h)));
    thead.append(header); table.append(thead);
    const tbody = el("tbody");
    rows.forEach(row => {
      const tr = el("tr");
      row.forEach(val => {
        const cell = el("td");
        if (val instanceof Node) cell.append(val);
        else cell.textContent = String(val ?? "—");
        tr.append(cell);
      });
      tbody.append(tr);
    });
    if (!rows.length) {
      const tr = el("tr"); const cell = el("td", "", "Sem registros disponíveis nesta ISO.");
      cell.colSpan = headers.length; tr.append(cell); tbody.append(tr);
    }
    table.append(tbody); scroll.append(table); node.append(scroll);
  }

  async function showCard(cardId) {
    const card = state?.cards?.find(c => c.id === cardId);
    if (!card) { notice("Carta não encontrada no mod ativo.", true); return; }
    selectedCard = card; stopTimer();
    resetUI();
    const target = $("panel");
    const detail = section("#" + card.id + " · " + card.name);
    detail.append(button("← Voltar à biblioteca", () => {
      selectedCard = null; currentTab = "biblioteca"; void render();
    }));
    const layout = el("div", "detail"); const img = el("img");
    img.alt = "Arte da carta: " + card.name; img.loading = "lazy";
    mountArt(img, state.activeSha, card.id);
    const text = el("div");
    append(text, el("p", "stats", "ATK " + stat(card.atk) + " · DEF " + stat(card.def)),
      el("p", "", "Tipo: " + (card.type || card.category || "Não identificado")),
      el("p", "", "Atributo: " + (card.attribute || "—")),
      el("p", "", card.effect || card.description || "Descrição não identificada na ISO."));
    append(layout, img, text); detail.append(layout); target.append(detail);
    const hint = section("Caminhos de fusão");
    hint.append(el("p", "muted", "Até cinco dicas da ISO ativa. Algumas receitas podem ser provisórias."));
    try {
      const data = await request("/v1/fusions?limit=100&query=" + encodeURIComponent(card.name || ""));
      const rows = Array.isArray(data.rows) ? data.rows : [];
      let shown = 0;
      for (const f of rows) {
        if (shown >= 5) break;
        if (f.a !== cardId && f.b !== cardId && f.result !== cardId) continue;
        const line = el("p");
        append(line, linkTo(f.nameA || "#" + f.a, f.a), document.createTextNode(" + "),
          linkTo(f.nameB || "#" + f.b, f.b), document.createTextNode(" → "),
          linkTo(f.nameResult || "#" + f.result, f.result));
        hint.append(line); shown++;
      }
      if (!shown) hint.append(el("p", "muted", "Nenhuma receita correspondente disponível neste filtro."));
      if (data.provisional) hint.append(el("p", "muted", "Receitas provisórias: ainda não confirmadas individualmente no jogo."));
    } catch (e) { hint.append(el("p", "muted", "Consulte a aba Fusões para procurar receitas.")); }
    if (selectedCard?.id === cardId) target.append(hint);
  }

  async function render() {
    resetUI();
    if (!token || !state) return;
    if (selectedCard) { void showCard(selectedCard.id); return; }
    const target = $("panel");
    const active = !!state.activeSha;
    try {
      if (currentTab === "mods") {
        const top = section("Biblioteca de Mods");
        top.append(el("p", "muted", "Seleção e análise feitas exclusivamente no seu Windows."));
        top.append(button("Selecionar ISO/BIN", () => void act("/v1/import", {chooseLocalFile: true}, "ISO importada. Ative o mod."), "gold"));
        top.append(document.createTextNode("  "));
        top.append(button("Memory Card", () => void act("/v1/memory-card", {chooseLocalFile: true}, "Memory Card selecionado.")));
        target.append(top);
        const grid = el("div", "grid");
        (state.mods || []).forEach(mod => {
          const card = el("article", "card");
          card.append(el("h3", "", mod.name), el("p", "muted small", [mod.cards, " cartas · ", mod.fusions, " fusões · ", mod.opponents, " oponentes"].join("")));
          card.append(button(mod.sha256 === state.activeSha ? "Mod ativo" : "Ativar mod",
            () => void act("/v1/activate", {sha: mod.sha256}, "Mod ativado."), mod.sha256 === state.activeSha ? "" : "gold"));
          grid.append(card);
        });
        target.append(grid);
      } else if (!active && currentTab !== "configuracoes") {
        target.append(section("Ative uma ISO/BIN na Biblioteca de Mods para consultar os dados."));
      } else if (currentTab === "biblioteca") {
        const panel = section("Biblioteca de Cartas");
        const filter = el("div", "filterbar");
        textField(filter, "Pesquisar carta", search, s => {search = s; page = 0; void render();});
        panel.append(filter);
        const cards = (state.cards || []).filter(c => (String(c.id) + " " + c.name).toLowerCase().includes(search.toLowerCase()));
        panel.append(el("p", "muted", cards.length + " cartas encontradas"));
        const grid = el("div", "grid");
        cards.slice(page * 24, page * 24 + 24).forEach(c => {
          const item = el("article", "card");
          const img = el("img"); img.alt = ""; img.loading = "lazy"; mountArt(img, state.activeSha, c.id);
          append(item, img, el("h3", "", "#" + c.id + " · " + c.name),
            el("p", "stats", "ATK " + stat(c.atk) + " · DEF " + stat(c.def)),
            button("Abrir informações", () => void showCard(c.id)));
          grid.append(item);
        });
        panel.append(grid);
        if (page) panel.append(button("Anterior", () => {page--; void render();}));
        if ((page + 1) * 24 < cards.length) panel.append(button("Próxima", () => {page++; void render();}));
        target.append(panel);
      } else if (currentTab === "fusoes") {
        const panel = section("Fusões"); const bar = el("div", "filterbar");
        textField(bar, "Nome, carta ou ID", search, s => {search = s; void render();});
        panel.append(bar);
        const data = await request("/v1/fusions?limit=100&query=" + encodeURIComponent(search));
        panel.append(el("p", "muted", "Total informado: " + stat(data.total)));
        drawTable(panel, ["Material A", "Material B", "Resultado"], (data.rows || []).map(f => [
          linkTo(f.nameA, f.a), linkTo(f.nameB, f.b), linkTo(f.nameResult, f.result)]));
        if (data.provisional) panel.append(el("p", "muted", "Receitas provisórias: confirmação no jogo pendente."));
        target.append(panel);
      } else if (currentTab === "oponentes" || currentTab === "drops") {
        const names = await request("/v1/opponents?opponent=" + opponentId);
        const panel = section(currentTab === "drops" ? "Drops" : "Oponentes");
        const filter = el("div", "filterbar"); const wrap = el("div");
        wrap.append(el("label", "", "Oponente"));
        const sel = el("select");
        const empty = el("option", "", "Escolha um oponente"); empty.value = "0"; sel.append(empty);
        (names.opponents || []).forEach(o => {
          const option = el("option", "", o.name); option.value = String(o.id); sel.append(option);
        });
        sel.value = String(opponentId);
        sel.addEventListener("change", () => {opponentId = Number(sel.value); void render();});
        wrap.append(sel); filter.append(wrap); panel.append(filter);
        if (currentTab === "drops") {
          const data = await request("/v1/drops?opponent=" + opponentId);
          panel.append(el("p", "muted", data.status || "Dados do mod ativo."));
          drawTable(panel, ["ID", "Carta", "Grupo", "Chance"], (data.rows || []).map(x => [
            x.cardId, linkTo(x.cardName, x.cardId), x.groupLabel, stat(x.chancePercent)]));
        } else {
          panel.append(el("p", "muted", names.status || "Dados do mod ativo."));
          drawTable(panel, ["ID", "Carta", "Peso"], (names.cards || []).map(x => [
            x.id, linkTo(x.name, x.id), stat(x.weight)]));
        }
        target.append(panel);
      } else if (currentTab === "decks") {
        const data = await request("/v1/decks");
        const panel = section("Decks / Memory Card");
        panel.append(el("p", "muted", data.status || "Deck da ISO ativa."));
        panel.append(button("Selecionar Memory Card", () => void act("/v1/memory-card", {chooseLocalFile: true}, "Memory Card selecionado.")));
        drawTable(panel, ["ID", "Carta", "Quantidade", "ATK", "DEF"], (data.cards || []).map(x =>
          [x.id, linkTo(x.name, x.id), stat(x.count), stat(x.atk), stat(x.def)]));
        target.append(panel);
      } else if (currentTab === "configuracoes") {
        const panel = section("Configurações");
        panel.append(el("p", "", "Cloud Web v0.6.0 · dados do jogo processados localmente."));
        panel.append(el("p", "muted", "A chave temporária não é persistida nem enviada à hospedagem. Feche a guia para descartá-la."));
        panel.append(el("p", "muted", "O Connector atende somente 127.0.0.1 no computador do jogador."));
        target.append(panel);
      } else {
        const data = await request("/v1/live");
        const panel = section("Duelo e RANK ao vivo");
        panel.append(el("p", "muted", data.hand?.status || "Sem leitura de mão ativa."));
        drawTable(panel, ["Slot", "Carta", "ATK", "DEF"], (data.hand?.cards || []).map(c =>
          [c.slot, linkTo(c.name, c.id), stat(c.atk), stat(c.def)]));
        panel.append(el("p", "stats", "RANK: " + (data.rank?.category || "—") +
          " · Pontuação: " + stat(data.rank?.score)));
        panel.append(el("p", "muted small", data.rank?.status || ""));
        target.append(panel);
        stopTimer();
        timer = setInterval(() => { if (currentTab === "inicio" && token && !selectedCard) void render(); }, 2400);
      }
    } catch (e) {
      notice(e instanceof Error ? e.message : "Falha ao consultar dados locais.", true);
    }
  }

  $("connect").addEventListener("click", () => void connect());
  $("key").addEventListener("keydown", event => { if (event.key === "Enter") void connect(); });
  $("disconnect").addEventListener("click", disconnect);
  $("reload").addEventListener("click", async () => {
    try { await updateState(); notice("Dados locais atualizados."); await render(); }
    catch (e) { notice(e instanceof Error ? e.message : "Falha ao recarregar.", true); }
  });
  document.querySelectorAll("[data-tab]").forEach(b => b.addEventListener("click", () => tabs(b.dataset.tab)));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopTimer(); else if (token && currentTab === "inicio") void render();
  });
  $("client-status").textContent = "Interface independente iniciada. JavaScript carregado.";
  resetUI();
})();
