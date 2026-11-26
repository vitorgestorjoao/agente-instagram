#!/usr/bin/env python3
"""Mostra o ID da conta do Instagram ligada ao token (para o segredo IG_USER_ID)."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

V = os.environ.get("GRAPH_VERSION", "v23.0")
TOKEN = os.environ.get("IG_TOKEN", "").strip()

if not TOKEN:
    raise SystemExit("Cadastre primeiro o segredo IG_TOKEN no GitHub.")


def get(url, **params):
    params["access_token"] = TOKEN
    try:
        with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=60) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        return None, e.read().decode(errors="replace")[:300]


achados = {}
erros = []

# 1) Token do login com Facebook: Instagram ligado às Páginas
dados, erro = get(f"https://graph.facebook.com/{V}/me/accounts",
                  fields="name,instagram_business_account{id,username}")
if dados:
    print("Páginas que o token enxerga:")
    for pg in dados.get("data", []):
        ig = pg.get("instagram_business_account")
        print(f" - {pg.get('name')}: " + (f"Instagram @{ig.get('username')}" if ig else "SEM Instagram ligado"))
        if ig:
            achados[ig["id"]] = ig.get("username")
    if not dados.get("data"):
        print(" (nenhuma)")
    print()
else:
    erros.append(f"graph.facebook.com/me/accounts: {erro}")

# 1b) Contas do Instagram atribuídas diretamente ao usuário do sistema
dados, erro = get(f"https://graph.facebook.com/{V}/me",
                  fields="name,businesses{name,instagram_business_accounts{id,username},client_instagram_business_accounts{id,username}}")
if dados:
    for b in (dados.get("businesses") or {}).get("data", []):
        for chave in ("instagram_business_accounts", "client_instagram_business_accounts"):
            for ig in (b.get(chave) or {}).get("data", []):
                achados[ig["id"]] = ig.get("username")
elif erro:
    erros.append(f"graph.facebook.com/me businesses: {erro}")

# 2) Token do login unificado / Instagram: o próprio /me
for host, campos in (("https://graph.facebook.com", "id,username"),
                     ("https://graph.instagram.com", "user_id,username")):
    dados, erro = get(f"{host}/{V}/me", fields=campos)
    if dados and dados.get("username"):
        achados[str(dados.get("user_id") or dados.get("id"))] = dados["username"]
    elif erro:
        erros.append(f"{host}/me: {erro}")

if achados:
    for i, u in achados.items():
        print(f"Instagram: @{u}")
        print(f"IG_USER_ID = {i}\n")
else:
    print("Nenhum Instagram encontrado com esse token. Detalhes:")
    for e in erros:
        print(" -", e)
