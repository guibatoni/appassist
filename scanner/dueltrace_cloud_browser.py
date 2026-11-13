"""Server-rendered, JavaScript-free DUELTRACE Cloud browser UI.

This is intentionally independent of Next.js/React hydration. The local
connector renders only derived game data and never sends a file to a host.
"""
from __future__ import annotations

from html import escape
from urllib.parse import urlencode

TABS = (
    ("inicio", "⌂", "Início"),
    ("mods", "▣", "Biblioteca de Mods"),
    ("biblioteca", "▤", "Biblioteca de Cartas"),
    ("fusoes", "∞", "Fusões"),
    ("drops", "♢", "Drops"),
    ("oponentes", "♟", "Oponentes"),
    ("decks", "▧", "Decks"),
    ("configuracoes", "⚙", "Configurações"),
)

STYLE = """
:root{color-scheme:dark;--bg:#040a1a;--panel:#081530;--line:#1b3f78;
--blue:#38c8ff;--gold:#f5b83d;--text:#e6f0ff;--muted:#9cafc9}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:var(--bg);
color:var(--text);font:14px/1.5 system-ui,'Segoe UI',sans-serif}
body{background:radial-gradient(ellipse at 58% 35%,#122650 0%,#060e27 55%,#030713 100%)}
header{display:flex;justify-content:space-between;align-items:center;gap:12px;
min-height:76px;padding:13px 23px;border-bottom:1px solid #26375a;background:#05091c}
.brand{display:flex;gap:15px;align-items:center}.brand svg{width:45px;height:45px}
.brand strong{font-size:25px;font-style:italic;letter-spacing:1px}
.brand em{display:block;color:var(--gold);font-size:12px}
.pill{border:1px solid var(--line);background:#0a1b35;color:var(--blue);
padding:8px 12px;border-radius:8px;font-size:12px}
.layout{display:grid;grid-template-columns:225px minmax(0,1fr);max-width:2200px;margin:auto}
nav{display:flex;flex-direction:column;gap:5px;padding:12px}
nav a{display:flex;align-items:center;gap:12px;text-decoration:none;color:#b4c0d3;
padding:12px 13px;border:1px solid transparent;border-radius:8px}
nav a:hover,nav a.active{color:#fff;background:#112544;border-color:#36c8ff;
box-shadow:0 0 12px #38c8ff45}nav .sym{width:19px;text-align:center;font-size:20px}
main{min-width:0;padding:18px 22px 40px}h1,h2,h3{line-height:1.25;margin:0 0 12px}
h1{font-size:25px;color:var(--gold)}h2{font-size:19px;color:var(--gold)}h3{font-size:16px}
p{margin:7px 0 14px}.muted{color:var(--muted)}.small{font-size:12px}
.hero{padding:17px 20px;border:1px solid #8c6a27;border-radius:13px;
background:linear-gradient(110deg,#1a2b50,#071126);margin-bottom:17px}
.panel{padding:18px;border:1px solid #233e71;border-radius:12px;background:#0a1430e8;margin-bottom:15px}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
.cards{grid-template-columns:repeat(auto-fill,minmax(160px,1fr))}
.card{border:1px solid #285085;border-radius:9px;padding:14px;background:#091a35;min-width:0}
.card h3,.card p{overflow-wrap:anywhere}
.card img{display:block;width:100%;height:160px;object-fit:contain;background:#050b1a;border-radius:6px;margin-bottom:9px}
.card .stats{color:#7fe3ff;font-size:12px}
.card-link{color:inherit;text-decoration:none;display:block}.card-link:hover{color:#fff}
.card:has(.card-link):hover{border-color:#38c8ff;box-shadow:0 0 16px #38c8ff33}
.card:has(.card-link):focus-within{outline:2px solid var(--blue)}
.detail-layout{display:grid;grid-template-columns:minmax(190px,300px) minmax(0,1fr);gap:20px}
.detail-image{width:100%;max-height:435px;object-fit:contain;background:#050b1a;border:1px solid var(--line);border-radius:9px}
.detail-pair{padding:12px;background:#091a35;border:1px solid #294d7d;border-radius:8px;margin:9px 0}
.detail-pair a{font-weight:600;text-decoration:underline}
@media(max-width:700px){.detail-layout{grid-template-columns:1fr}.detail-image{max-height:370px}}
label{display:block;color:#bed0eb;font-weight:600;margin:0 0 6px}
button,.button{display:inline-block;border:1px solid #c39233;border-radius:7px;
padding:10px 14px;background:#4a3618;color:#ffce63;font-weight:700;cursor:pointer;
text-decoration:none;font:inherit}button:hover,.button:hover{background:#785521}
button.blue,.button.blue{border-color:#3474a8;background:#123456;color:#8ddfff}
form.inline{display:inline}input,select{max-width:100%;border:1px solid #31598b;
border-radius:7px;padding:10px;color:white;background:#07122c;font:inherit}
form.filters{display:flex;flex-wrap:wrap;align-items:end;gap:10px;margin:0 0 16px}
.form-field{min-width:140px;flex:1}
.form-field input,.form-field select{width:100%}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{border-bottom:1px solid #24416a;padding:9px;text-align:left;vertical-align:top}
th{color:#ffcc62}td{overflow-wrap:anywhere}
.table-wrap{overflow-x:auto}a{color:#80d9ff}
.notice{padding:11px 14px;border:1px solid #286da3;border-radius:8px;
background:#0d2b4a;color:#9de4ff;margin-bottom:14px}
footer{border-top:1px solid #26395d;margin-top:22px;padding:14px 0;color:#92aac6;font-size:12px}
@media(max-width:750px){.layout{grid-template-columns:1fr}nav{display:grid;
grid-template-columns:repeat(2,1fr)}main{padding:8px 12px}
header{padding:10px}.brand strong{font-size:19px}.brand svg{width:31px}
.pill{font-size:10px}.grid{grid-template-columns:repeat(auto-fill,minmax(180px,1fr))}}
"""


def esc(value):
    return escape(str(value if value is not None else ""), quote=True)


def number(value):
    return "—" if value is None else esc(value)


def link(tab, **params):
    args = {"tab": tab}
    args.update({key: value for key, value in params.items() if value is not None})
    return "/local/?" + urlencode(args)


def post_button(action, token, text, *, sha=None):
    extra = f'<input type="hidden" name="sha" value="{esc(sha)}">' if sha else ""
    return (f'<form class="inline" method="post" action="/local/action">'
            f'<input type="hidden" name="csrf" value="{esc(token)}">'
            f'<input type="hidden" name="action" value="{esc(action)}">'
            f'{extra}<button type="submit">{esc(text)}</button></form>')


def card_anchor(card_id, label):
    """Link to a same-origin card detail page; HTML escapes label text."""
    if type(card_id) is not int or not 1 <= card_id <= 722:
        return esc(label)
    return f'<a href="{link("carta",id=card_id)}">{esc(label)}</a>'


def _table(headers, rows):
    heading = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) +
                   "</tr>" for row in rows)
    return '<div class="table-wrap"><table><thead><tr>' + heading +         "</tr></thead><tbody>" + (body or
        f'<tr><td colspan="{len(headers)}">Nenhum registro disponível.</td></tr>') +         "</tbody></table></div>"


def _filters(tab, *, query="", opponent=None, page=None, opponents=None):
    fields = [f'<input type="hidden" name="tab" value="{esc(tab)}">']
    if query is not None:
        fields.append('<div class="form-field"><label for="q">Buscar</label>'
                      f'<input id="q" name="q" maxlength="80" value="{esc(query)}" '
                      'placeholder="Nome ou ID"></div>')
    if opponents is not None:
        options = ['<option value="0">Selecione um oponente</option>']
        for row in opponents[:39]:
            try:
                oid = int(row.get("id", 0))
            except (TypeError, ValueError):
                continue
            if not 1 <= oid <= 39:
                continue
            selected = " selected" if oid == opponent else ""
            options.append(f'<option value="{oid}"{selected}>{esc(row.get("name", oid))}</option>')
        fields.append('<div class="form-field"><label for="opp">Oponente</label>'
                      '<select name="opponent" id="opp">' + "".join(options) + '</select></div>')
    fields.append('<button class="blue" type="submit">Consultar</button>')
    return '<form class="filters" method="get" action="/local/">' + "".join(fields) + "</form>"


def render_local_page(state, *, token, tab="inicio", query="", opponent=0,
                      page=0, panel=None, notice="", card_id=0):
    """Render only sanitized, derived data. No JS/hydration and no remote assets."""
    tabs = {row[0] for row in TABS}
    tab = tab if tab in tabs or tab == "carta" else "inicio"
    panel = panel if isinstance(panel, dict) else {}
    query = str(query)[:80]
    page = max(0, min(int(page), 10000))
    active = state.get("activeSha")
    mods = state.get("mods") or []
    cards = state.get("cards") or []
    active_name = state.get("activeName") or "Nenhum mod ativado"
    navigation = "".join(
        f'<a class="{"active" if ident == tab or (tab == "carta" and ident == "biblioteca") else ""}" href="{link(ident)}">'
        f'<span class="sym">{sym}</span>{esc(title)}</a>'
        for ident, sym, title in TABS
    )
    sections = []
    if notice:
        sections.append(f'<div class="notice" role="status">{esc(notice[:180])}</div>')

    if tab == "inicio":
        sections.append('<section class="panel"><h2>Conexão local estabelecida</h2>'
                        '<p>O Chrome abriu o DUELTRACE diretamente pelo Connector. '
                        'Não é necessário copiar chaves, iniciar o Next.js ou habilitar JavaScript.</p>'
                        '<p class="muted">ISOs, Memory Cards e RAM permanecem no computador.</p>'
                        f'<p><strong>ISO ativa:</strong> {esc(active_name)}</p>'
                        f'<p><strong>Mods:</strong> {len(mods)} · '
                        f'<strong>Cartas:</strong> {len(cards)}</p>'
                        f'<a class="button blue" href="{link("inicio")}">Atualizar duelo</a></section>')
        if active:
            hand = panel.get("hand") or {}
            rank = panel.get("rank") or {}
            rows = [
                (number(c.get("slot")), number(c.get("id")), esc(c.get("name")),
                 number(c.get("atk")), number(c.get("def")))
                for c in (hand.get("cards") or [])[:5] if isinstance(c, dict)
            ]
            sections.append('<section class="panel"><h2>Mão e RANK ao vivo</h2>'
                            f'<p class="muted">{esc(hand.get("status", ""))}</p>' +
                            _table(("Slot", "ID", "Carta", "ATK", "DEF"), rows) +
                            f'<p><strong>RANK:</strong> {esc(rank.get("category", "—"))} · '
                            f'{esc(rank.get("score", "—"))} pontos</p></section>')
        else:
            sections.append('<section class="panel"><p>Importe ou ative uma ISO '
                            'na Biblioteca de Mods para consultar as cartas e o duelo.</p></section>')
    elif tab == "mods":
        sections.append('<section class="panel"><h2>Biblioteca de Mods</h2>'
                        '<p class="muted">Os arquivos são selecionados no próprio Windows; '
                        'nenhum BIN ou ISO é enviado ao navegador.</p>'
                        f'{post_button("import",token,"Selecionar ISO/BIN")} '
                        f'{post_button("memory-card",token,"Selecionar Memory Card")}</section>')
        blocks = []
        for mod in mods:
            sha = mod.get("sha256")
            is_active = sha == active
            blocks.append('<article class="card">'
                          f'<h3>{esc(mod.get("name", "Mod"))}</h3>'
                          f'<p class="small muted">{number(mod.get("cards"))} cartas · '
                          f'{number(mod.get("fusions"))} fusões · '
                          f'{number(mod.get("opponents"))} oponentes</p>'
                          + ('<span class="pill">Mod ativo</span>' if is_active
                             else post_button("activate",token,"Ativar mod",sha=sha)) +
                          "</article>")
        sections.append('<section class="grid">' + "".join(blocks) + "</section>")
    elif not active:
        sections.append('<section class="panel">Ative uma ISO na Biblioteca de Mods '
                        'antes de consultar esta seção.</section>')
    elif tab == "biblioteca":
        selection = [c for c in cards if
                     query.casefold() in (str(c.get("id", "")) + " " +
                                          str(c.get("name", ""))).casefold()]
        start = page * 30
        blocks = []
        for c in selection[start:start + 30]:
            cid = c.get("id")
            art = ('<img loading="lazy" alt="" src="/local/art?' +
                   urlencode({"sha": active, "id": cid}) + '">' if active else "")
            blocks.append('<article class="card"><a class="card-link" href="' +
                          link("carta", id=cid) + '">' + art +
                          f'<h3>#{number(cid)} · {esc(c.get("name"))}</h3>'
                          f'<p class="stats">ATK {number(c.get("atk"))} · '
                          f'DEF {number(c.get("def"))}</p>'
                          f'<p class="muted small">{esc(c.get("type") or c.get("category"))}</p>'
                          '<span class="small">Clique para ver informações e fusões</span>'
                          '</a></article>')
        sections.append('<section class="panel"><h2>Biblioteca de Cartas</h2>' +
                        _filters(tab, query=query) +
                        f'<p class="muted">{len(selection)} cartas encontradas</p>'
                        '<div class="grid cards">' + "".join(blocks) + "</div>"
                        '<p>' + (f'<a class="button blue" href="{link(tab,q=query,page=page-1)}">Anterior</a> '
                               if page > 0 else "") +
                        (f'<a class="button blue" href="{link(tab,q=query,page=page+1)}">Próxima</a>'
                         if start + 30 < len(selection) else "") + '</p></section>')
    elif tab == "carta":
        card = next((c for c in cards if c.get("id") == card_id), None)
        if card is None:
            sections.append('<section class="panel">Carta não encontrada na ISO ativa.'
                            f' <a href="{link("biblioteca")}">Voltar à biblioteca</a></section>')
        else:
            art = '<img class="detail-image" alt="" src="/local/art?' + urlencode(
                {"sha": active, "id": card_id}) + '">'
            sections.append('<section class="panel">'
                            f'<p><a href="{link("biblioteca")}">← Biblioteca de Cartas</a></p>'
                            '<div class="detail-layout"><div>' + art +
                            '</div><div>'
                            f'<h2>#{number(card_id)} · {esc(card.get("name"))}</h2>'
                            f'<p class="stats">ATK {number(card.get("atk"))} · '
                            f'DEF {number(card.get("def"))}</p>'
                            f'<p><strong>Tipo:</strong> {esc(card.get("type") or card.get("category"))}</p>'
                            f'<p><strong>Atributo:</strong> {esc(card.get("attribute") or "—")}</p>'
                            f'<p><strong>Nível:</strong> {number(card.get("level"))}</p>'
                            f'<p>{esc(card.get("effect") or card.get("description") or
                                      "Sem descrição validada para este mod.")}</p>'
                            '</div></div></section>')
            materials_all = (panel.get("materialRows") or []) if isinstance(panel, dict) else []
            results_all = (panel.get("resultRows") or []) if isinstance(panel, dict) else []
            # Five suggestions total across both directions; no crowded UI.
            materials = materials_all[:3]
            results = results_all[:max(0, 5 - len(materials))]
            if len(materials) + len(results) < 5:
                materials = materials_all[:5 - len(results)]
            provisional = panel.get("provisional") is True
            if provisional:
                sections.append('<div class="notice">Fusões provisórias: o jogo ainda '
                                'não confirmou individualmente estas receitas.</div>')
            fusion_parts = ['<section class="panel"><h2>Fusões desta carta</h2>'
                            f'<p class="muted">{number(panel.get("materialTotal", 0))} '
                            'receitas usando a carta · '
                            f'{number(panel.get("resultTotal", 0))} '
                            'receitas que produzem a carta · '
                            'até 5 dicas exibidas</p>']
            fusion_parts.append('<h3>Esta carta como material</h3>')
            for row in materials:
                if not isinstance(row, dict):
                    continue
                fusion_parts.append('<div class="detail-pair">Esta carta + ' +
                                    card_anchor(row.get("partnerId"), row.get("partnerName")) +
                                    ' → ' + card_anchor(row.get("resultId"),
                                                        row.get("resultName")) +
                                    f' · ATK {number(row.get("atk"))} / '
                                    f'DEF {number(row.get("def"))}</div>')
            if not materials:
                fusion_parts.append('<p class="muted">Nenhuma receita de material disponível.</p>')
            fusion_parts.append('<h3>Como criar esta carta</h3>')
            for row in results:
                if not isinstance(row, dict):
                    continue
                fusion_parts.append('<div class="detail-pair">' +
                                    card_anchor(row.get("materialAId"),
                                                row.get("materialAName")) + ' + ' +
                                    card_anchor(row.get("materialBId"),
                                                row.get("materialBName")) +
                                    ' → esta carta</div>')
            if not results:
                fusion_parts.append('<p class="muted">Nenhuma receita de resultado disponível.</p>')
            fusion_parts.append('</section>')
            sections.append(''.join(fusion_parts))
    elif tab == "fusoes":
        rows = []
        for f in (panel.get("rows") or []):
            if isinstance(f, dict):
                rows.append((number(f.get("a")), card_anchor(f.get("a"), f.get("nameA")),
                             number(f.get("b")), card_anchor(f.get("b"), f.get("nameB")),
                             number(f.get("result")), card_anchor(f.get("result"), f.get("nameResult"))))
        sections.append('<section class="panel"><h2>Fusões</h2>' +
                        _filters(tab, query=query) +
                        f'<p class="muted">Total: {number(panel.get("total", 0))}</p>' +
                        _table(("ID", "Material 1", "ID", "Material 2", "ID", "Resultado"), rows) +
                        "</section>")
    elif tab in ("oponentes", "drops"):
        others = panel.get("opponents") or []
        sections.append(f'<section class="panel"><h2>{esc("Oponentes" if tab == "oponentes" else "Drops")}</h2>' +
                        _filters(tab, query=None, opponent=opponent, opponents=others) +
                        f'<p class="muted">{esc(panel.get("status", ""))}</p>')
        if tab == "oponentes":
            rows = [(number(c.get("id")), card_anchor(c.get("id"), c.get("name")),
                     number(c.get("weight")), number(c.get("chancePercent")))
                    for c in (panel.get("cards") or []) if isinstance(c, dict)]
            sections.append(_table(("ID", "Carta", "Peso", "%"), rows) + "</section>")
        else:
            rows = [(number(c.get("cardId")), card_anchor(c.get("cardId"), c.get("cardName")),
                     esc(c.get("groupLabel")), number(c.get("chancePercent")))
                    for c in (panel.get("rows") or []) if isinstance(c, dict)]
            sections.append(_table(("ID", "Carta", "Grupo RANK", "%"), rows) + "</section>")
    elif tab == "decks":
        rows = [(number(c.get("id")), card_anchor(c.get("id"), c.get("name")),
                 number(c.get("count")), number(c.get("atk")), number(c.get("def")))
                for c in (panel.get("cards") or []) if isinstance(c, dict)]
        sections.append('<section class="panel"><h2>Decks / Memory Card</h2>'
                        f'<p class="muted">{esc(panel.get("status", ""))}</p>' +
                        post_button("memory-card",token,"Selecionar Memory Card") +
                        _table(("ID", "Carta", "Qtd.", "ATK", "DEF"), rows) + "</section>")
    else:
        sections.append('<section class="panel"><h2>Configurações</h2>'
                        '<p>Modo local: dados processados apenas neste computador.</p>'
                        '<p>Este navegador se comunica com 127.0.0.1; '
                        'não é necessário Node.js, PowerShell ou chave digitada.</p>'
                        '<p class="muted">DUELTRACE Cloud v0.6.0 · diagnóstico '
                        'independente de JavaScript</p></section>')

    return ('''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DUELTRACE Cloud — Local</title><style>''' + STYLE +
            '''</style></head><body><header><div class="brand">
<svg viewBox="0 0 48 44" aria-hidden="true"><path d="M2 2h44L24 42z"
fill="none" stroke="#7fe3ff" stroke-width="4"/><path d="M13 9h22L24 30z"
fill="none" stroke="#38c8ff" stroke-width="3"/></svg><div>
<strong>DUELTRACE</strong><em>— MultiMod Companion —</em></div></div>
<span class="pill">● Connector local ativo · Sem login</span></header>
<div class="layout"><nav aria-label="Navegação">''' + navigation +
            '''</nav><main><div class="hero"><h1>DUELTRACE Cloud</h1>
<span class="muted">MultiMod Companion · modo local no Chrome · v0.6.0</span>
</div>''' + "".join(sections) +
            '''<footer>🔒 ISO, Memory Card e RAM permanecem no PC ·
Acesso local 127.0.0.1 · Batoni Dev</footer></main></div></body></html>''')
