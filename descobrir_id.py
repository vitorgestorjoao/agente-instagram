#!/usr/bin/env python3
"""Mostra o ID da conta do Instagram ligada ao token (para o segredo IG_USER_ID)."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

GRAPH = f"https://graph.facebook.com/{os.environ.get('GRAPH_VERSION', 'v23.0')}"
TOKEN = os.environ.get("IG_TOKEN", "").strip()

if not TOKEN:
    raise SystemExit("Cadastre primeiro o segredo IG_TOKEN no GitHub.")

params = urllib.parse.urlencode({
    "fields": "name,instagram_business_account{id,username}",
    "access_token": TOKEN,
})
try:
    with urllib.request.urlopen(f"{GRAPH}/me/accounts?{params}", timeout=60) as r:
        dados = json.load(r)
except urllib.error.HTTPError as e:
    raise SystemExit(f"A Meta recusou o token: {e.read().decode(errors='replace')}")

achou = False
for pagina in dados.get("data", []):
    ig = pagina.get("instagram_business_account")
    if ig:
        achou = True
        print(f"Página: {pagina.get('name')}")
        print(f"Instagram: @{ig.get('username')}")
        print(f"IG_USER_ID = {ig.get('id')}\n")

if not achou:
    print("Nenhum Instagram encontrado. Confira se o usuário do sistema recebeu a Página E a "
          "conta do Instagram como ativos, e se o Instagram está ligado à Página.")
