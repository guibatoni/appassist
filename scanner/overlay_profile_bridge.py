"""Aplica um perfil MultiMod à memória do overlay legado, preservando referências.

O CompactPanel recebe os mesmos dicts/listas criados na inicialização de
assistente_x15.py; substituí-los por novos objetos não atualiza referências
capturadas por callbacks, estratégias e painéis secundários.

Este módulo atualiza essas estruturas *in-place* para permitir que as cartas
já detectadas na RAM sejam resolvidas pelo catálogo recém-confirmado.

NÃO confirma a ROM ativa no ePSXe nem inventa ranks/fusões/drops.
"""
from __future__ import annotations

from collections.abc import Mapping


def _replace_mapping(holder, attribute: str, values: dict) -> bool:
    if holder is None or not hasattr(holder, attribute):
        return False
    old=getattr(holder,attribute)
    if isinstance(old,dict):
        old.clear()
        old.update(values)
    else:
        setattr(holder,attribute,dict(values))
    return True


def _replace_sequence(holder, attribute: str, values: list) -> bool:
    if holder is None or not hasattr(holder,attribute):
        return False
    old=getattr(holder,attribute)
    if isinstance(old,list):
        old[:]=list(values)
    else:
        setattr(holder,attribute,list(values))
    return True


def _normalize_cards(cards) -> dict:
    result={}
    for raw_id,raw_card in (cards or {}).items():
        try:
            cid=int(raw_id)
            if not (1<=cid<=9999) or not isinstance(raw_card,Mapping):
                continue
            name=str(raw_card.get("name","")).strip()
            if not name:
                continue
            result[cid]={
                "name":name,
                "atk":int(raw_card.get("atk",0)),
                "def":int(raw_card.get("def",0)),
                "type_id":raw_card.get("type_id"),
            }
        except (ValueError,TypeError):
            continue
    return result


def apply_overlay_profile(snapshot:dict, *, app=None, compact=None) -> dict:
    """Atualiza app e CompactPanel, inclusive referências antigas.

    Return summary for diagnostics and unit tests; does not alter ISO/saves.
    """
    if not snapshot.get("ready"):
        return {"applied":False,"reason":snapshot.get("reason","Perfil não pronto")}
    features=snapshot.get("features",{})
    cards=_normalize_cards(snapshot.get("cards")) if features.get("nomes_cartas") else {}
    recipes=[]
    if features.get("fusoes"):
        for recipe in snapshot.get("recipes",[]):
            try:
                a,b,c=(int(x) for x in recipe)
                if 1<=a<=9999 and 1<=b<=9999 and 1<=c<=9999:
                    recipes.append((a,b,c))
            except (ValueError,TypeError):
                continue
    index={}
    for a,b,c in recipes:
        index[(a,b)]=c
        index[(b,a)]=c

    # Priorizar o hook explícito quando o app sabe como reconstruir tudo.
    # Fallback precisa usar os mesmos dicts/listas que callbacks já capturaram.
    if app is not None and callable(getattr(app,"apply_mod_profile",None)):
        app.apply_mod_profile(snapshot)
    else:
        _replace_mapping(app,"cards",cards)
        _replace_sequence(app,"recipes",recipes)
        _replace_mapping(app,"index",index)

    _replace_mapping(compact,"cards",cards)
    _replace_sequence(compact,"recipes",recipes)
    _replace_mapping(compact,"index",index)

    strategy=getattr(compact,"strategy",None)
    if strategy is not None:
        # Estratégias que mantêm o catálogo por referência (mesmo formato).
        _replace_mapping(strategy,"cards",cards)
        _replace_mapping(strategy,"card_db",cards)
        _replace_mapping(strategy,"index",index)
        _replace_sequence(strategy,"recipes",recipes)
        # As estruturas internas e caches variam entre versões, por isso
        # reconstruímos um Strategist quando possível.
        try:
            from estrategia_x15 import Strategist
            setattr(compact,"strategy",Strategist(getattr(compact,"cards",cards),
                                                  getattr(compact,"recipes",recipes)))
        except (ImportError,TypeError,ValueError,AttributeError):
            pass

    # Nunca exibir drops/ranks do X15 para mods sem ranks confirmados.
    if compact is not None and not features.get("rank"):
        atlas=getattr(compact,"atlas",None)
        empty={"opponents":[],"drops":[],"rankLabels":[]}
        if isinstance(atlas,dict):
            atlas.clear()
            atlas.update(empty)
        elif atlas is not None:
            setattr(compact,"atlas",empty)

    # PONTO DECISIVO DO PAINEL COMPACTO:
    # painel_compacto.CompactPanel.tick só atualiza os StringVar hand[n] quando
    # self.last != ids ou self.last_pid != rd.pid. Ao trocar o catálogo,
    # os IDs/PID NÃO mudam, então invalidar explicitamente o cache é necessário.
    if compact is not None:
        setattr(compact,"_active_profile",snapshot)
        if hasattr(compact,"profile_has_cards"):
            compact.profile_has_cards=bool(cards)
        if hasattr(compact,"profile_has_fusions"):
            compact.profile_has_fusions=bool(recipes)
        if hasattr(compact,"last"):
            compact.last=None
        if hasattr(compact,"last_pid"):
            compact.last_pid=None

        # Distinguir catálogo selecionado de ROM efetivamente detectada.
        game_line=getattr(compact,"game_line",None)
        if cards and callable(getattr(game_line,"set",None)):
            game_line.set("CATÁLOGO: "+str(snapshot.get("profile_name","Mod local"))+
                          " · seleção manual; ISO no ePSXe NÃO confirmada")
        if callable(getattr(compact,"refresh_collection",None)):
            try:
                compact.refresh_collection()
            except (AttributeError,ValueError,TypeError,KeyError):
                pass

    if app is not None:
        setattr(app,"_active_mod_profile",snapshot)

    # Não tentar inferir qual ISO o ePSXe carregou só porque o usuário
    # ativou uma entrada da Biblioteca.
    return {
        "applied":True,
        "profile_name":snapshot.get("profile_name","Mod local"),
        "card_count":len(cards),
        "recipe_count":len(recipes),
        "profile_sha256":snapshot.get("rom_sha256"),
        "iso_active_in_emulator_verified":False,
    }
