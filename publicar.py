#!/usr/bin/env python3
"""
Agente de publicação no Instagram.

Lê o calendário de posts (planilha do Google publicada como CSV, ou o arquivo
calendario.csv do repositório), publica os posts cujo horário já chegou e
registra o que foi publicado em publicados.json, para nunca postar duas vezes.

Usa só a biblioteca padrão do Python (nada para instalar).

Variáveis de ambiente:
  IG_TOKEN        token de acesso da Meta (usuário do sistema)
  IG_USER_ID      ID da conta profissional do Instagram
  SHEET_CSV_URL   link CSV da planilha publicada (se vazio, usa calendario.csv)
  REPO_RAW_BASE   endereço público dos arquivos do repositório (preenchido pelo GitHub)
  DRY_RUN         "true" para só simular, sem publicar
  JANELA_HORAS    até quantas horas de atraso um post ainda é publicado (padrão 6)
  FUSO            fuso horário da planilha (padrão America/Sao_Paulo)
"""

import csv
import hashlib
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
TOKEN = os.environ.get("IG_TOKEN", "").strip()
IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()
SHEET_CSV_URL = os.environ.get("SHEET_CSV_URL", "").strip()
ARQUIVO_LOCAL = os.environ.get("CALENDARIO_CSV", "calendario.csv")
ARQUIVO_ESTADO = os.environ.get("ARQUIVO_ESTADO", "publicados.json")
REPO_RAW_BASE = os.environ.get("REPO_RAW_BASE", "").strip()
FUSO = ZoneInfo(os.environ.get("FUSO", "America/Sao_Paulo"))
JANELA_HORAS = float(os.environ.get("JANELA_HORAS", "6") or 6)
DRY_RUN = os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "sim", "yes")

EXT_VIDEO = (".mp4", ".mov", ".m4v")
NAO = ("nao", "n", "0", "false", "pausado", "pausar", "off")


class ErroPost(Exception):
    pass


# ---------------------------------------------------------------- utilidades

def sem_acento(txt):
    txt = unicodedata.normalize("NFKD", str(txt or ""))
    return "".join(c for c in txt if not unicodedata.combining(c)).strip().lower()


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- calendário

def baixar_texto(url):
    req = urllib.request.Request(url, headers={"User-Agent": "agente-instagram"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8-sig")


def carregar_calendario():
    if SHEET_CSV_URL:
        log("Lendo a planilha do Google...")
        texto = baixar_texto(SHEET_CSV_URL)
        if texto.lstrip().lower().startswith("<!doctype html") or "<html" in texto[:500].lower():
            raise SystemExit(
                "O link da planilha não devolveu um CSV. Use Arquivo > Compartilhar > "
                "Publicar na Web, escolha a aba e o formato CSV, e copie esse link."
            )
    else:
        log(f"Lendo {ARQUIVO_LOCAL}...")
        with open(ARQUIVO_LOCAL, encoding="utf-8-sig") as f:
            texto = f.read()

    linhas = list(csv.reader(io.StringIO(texto)))
    if not linhas:
        return []
    cabecalho = [sem_acento(c) for c in linhas[0]]
    posts = []
    for n, valores in enumerate(linhas[1:], start=2):
        if not any(v.strip() for v in valores):
            continue
        linha = {cabecalho[i]: (valores[i].strip() if i < len(valores) else "")
                 for i in range(len(cabecalho))}
        linha["_linha"] = n
        posts.append(linha)
    return posts


def ler_data_hora(post):
    data = post.get("data", "")
    hora = post.get("hora", "") or post.get("horario", "")
    if not data or not hora:
        raise ErroPost("preencha as colunas data e hora")
    hora = hora.replace("h", ":").rstrip(":")
    if re.fullmatch(r"\d{1,2}", hora):
        hora += ":00"
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%Y-%m-%d %H:%M",
                "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(f"{data} {hora}", fmt).replace(tzinfo=FUSO)
        except ValueError:
            pass
    raise ErroPost(f"data/hora inválida: '{data} {hora}' (use 25/12/2026 e 18:30)")


def lista_midias(post):
    bruto = post.get("midia", "") or post.get("midias", "")
    return [m.strip() for m in re.split(r"[|\n]", bruto) if m.strip()]


def eh_video(item):
    if item.lower().startswith("video:"):
        return True
    caminho = urllib.parse.urlparse(item).path if "://" in item else item
    return caminho.lower().endswith(EXT_VIDEO)


def url_publica(item):
    """Converte o que está na planilha num link que o Instagram consegue baixar."""
    video = eh_video(item)
    if item.lower().startswith("video:"):
        item = item[6:].strip()

    # Arquivo na pasta midia/ do repositório
    if "://" not in item:
        if not REPO_RAW_BASE:
            raise ErroPost(f"'{item}' não é um link e o endereço do repositório não está configurado")
        caminho = item if "/" in item else f"midia/{item}"
        return REPO_RAW_BASE.rstrip("/") + "/" + urllib.parse.quote(caminho), video

    # Link de compartilhamento do Google Drive
    m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:.*&)?id=)([\w-]+)", item)
    if m:
        fid = m.group(1)
        if video:
            return f"https://drive.google.com/uc?export=download&id={fid}", True
        return f"https://lh3.googleusercontent.com/d/{fid}", False

    return item, video


def tipo_do_post(post, midias):
    t = sem_acento(post.get("tipo", ""))
    if t in ("foto", "imagem", "image", "post", "feed"):
        return "FOTO"
    if t in ("carrossel", "carousel", "carrosel"):
        return "CARROSSEL"
    if t in ("reels", "reel", "video"):
        return "REELS"
    if t in ("story", "stories", "storys", "storie"):
        return "STORY"
    if t:
        raise ErroPost(f"tipo desconhecido: '{post.get('tipo')}' (use FOTO, CARROSSEL, REELS ou STORY)")
    if len(midias) > 1:
        return "CARROSSEL"
    return "REELS" if midias and eh_video(midias[0]) else "FOTO"


def chave_do_post(post):
    if post.get("id"):
        return f"id:{post['id']}"
    base = "|".join([post.get("data", ""), post.get("hora", ""), post.get("midia", ""),
                     post.get("legenda", "")[:80]])
    return "h:" + hashlib.sha1(base.encode()).hexdigest()[:12]


def ativo(post):
    return sem_acento(post.get("ativo", "sim")) not in NAO


# ---------------------------------------------------------------- API da Meta

def api(metodo, caminho, params=None):
    params = dict(params or {})
    params["access_token"] = TOKEN
    corpo = urllib.parse.urlencode(params)
    url = f"{GRAPH}/{caminho}"
    if metodo == "GET":
        req = urllib.request.Request(f"{url}?{corpo}")
    else:
        req = urllib.request.Request(url, data=corpo.encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        texto = e.read().decode(errors="replace")
        try:
            err = json.loads(texto).get("error", {})
            msg = err.get("error_user_msg") or err.get("message") or texto
            msg = f"{msg} (código {err.get('code')}"
            if err.get("error_subcode"):
                msg += f"/{err.get('error_subcode')}"
            msg += ")"
        except ValueError:
            msg = texto[:300]
        raise ErroPost(f"Instagram recusou: {msg}") from None


def aguardar(container_id, limite=900):
    inicio = time.time()
    while True:
        r = api("GET", container_id, {"fields": "status_code,status"})
        s = r.get("status_code")
        if s in ("FINISHED", "PUBLISHED"):
            return
        if s in ("ERROR", "EXPIRED"):
            raise ErroPost(f"o Instagram não aceitou a mídia: {r.get('status') or s}")
        if time.time() - inicio > limite:
            raise ErroPost("o Instagram demorou demais para processar o vídeo")
        time.sleep(8)


def criar_container(url, video, **extra):
    params = {k: v for k, v in extra.items() if v not in (None, "")}
    if video:
        params["video_url"] = url
    else:
        params["image_url"] = url
    return api("POST", f"{IG_USER_ID}/media", params)["id"]


def publicar_container(container_id):
    aguardar(container_id)
    return api("POST", f"{IG_USER_ID}/media_publish", {"creation_id": container_id})["id"]


def link_do_post(media_id):
    try:
        return api("GET", media_id, {"fields": "permalink"}).get("permalink", "")
    except ErroPost:
        return ""


def publicar(post, tipo, midias):
    """Publica o post e devolve a lista de IDs criados."""
    legenda = post.get("legenda", "")
    urls = [url_publica(m) for m in midias]

    if tipo == "FOTO":
        url, video = urls[0]
        if video:
            raise ErroPost("tipo FOTO com arquivo de vídeo; use REELS")
        return [publicar_container(criar_container(url, False, caption=legenda))]

    if tipo == "REELS":
        url, _ = urls[0]
        capa = post.get("capa", "")
        cid = criar_container(url, True, media_type="REELS", caption=legenda,
                              share_to_feed="true",
                              cover_url=url_publica(capa)[0] if capa else None)
        return [publicar_container(cid)]

    if tipo == "CARROSSEL":
        filhos = []
        for url, video in urls:
            extra = {"is_carousel_item": "true"}
            if video:
                extra["media_type"] = "VIDEO"
            filhos.append(criar_container(url, video, **extra))
        for f in filhos:
            aguardar(f)
        cid = api("POST", f"{IG_USER_ID}/media",
                  {"media_type": "CAROUSEL", "children": ",".join(filhos), "caption": legenda})["id"]
        return [publicar_container(cid)]

    if tipo == "STORY":
        ids = []
        for url, video in urls:
            ids.append(publicar_container(criar_container(url, video, media_type="STORIES")))
        return ids

    raise ErroPost(f"tipo não suportado: {tipo}")


def validar(post, tipo, midias):
    if not midias:
        raise ErroPost("coluna midia vazia")
    if tipo in ("FOTO", "REELS") and len(midias) != 1:
        raise ErroPost(f"{tipo} aceita só 1 mídia (achei {len(midias)}); para várias use CARROSSEL")
    if tipo == "CARROSSEL" and not 2 <= len(midias) <= 10:
        raise ErroPost(f"carrossel precisa de 2 a 10 mídias (achei {len(midias)})")
    if tipo == "REELS" and not eh_video(midias[0]):
        raise ErroPost("REELS precisa de um vídeo .mp4/.mov (ou escreva video: antes do link do Drive)")
    if len(post.get("legenda", "")) > 2200:
        raise ErroPost("legenda passa de 2.200 caracteres")
    if post.get("legenda", "").count("#") > 30:
        raise ErroPost("mais de 30 hashtags na legenda")
    for m in midias:
        url_publica(m)


# ---------------------------------------------------------------- estado

def carregar_estado():
    try:
        with open(ARQUIVO_ESTADO, encoding="utf-8") as f:
            dados = json.load(f)
            return dados if isinstance(dados, dict) else {}
    except (FileNotFoundError, ValueError):
        return {}


def salvar_estado(estado):
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


# ---------------------------------------------------------------- principal

def main():
    simular = DRY_RUN or "--testar" in sys.argv
    if not simular and (not TOKEN or not IG_USER_ID):
        log("Agente ainda não configurado: faltam os segredos IG_TOKEN e/ou IG_USER_ID. Nada a fazer.")
        return

    agora = datetime.now(FUSO)
    log(f"Agora: {agora:%d/%m/%Y %H:%M} ({FUSO.key})" + ("  [MODO TESTE: nada será publicado]" if simular else ""))

    estado = carregar_estado()
    posts = carregar_calendario()
    log(f"{len(posts)} linha(s) no calendário.\n")

    falhas, publicados, proximos = 0, 0, []

    for post in posts:
        rotulo = f"Linha {post['_linha']}"
        try:
            chave = chave_do_post(post)
            if chave in estado or not ativo(post):
                continue
            quando = ler_data_hora(post)
            midias = lista_midias(post)
            tipo = tipo_do_post(post, midias)
            validar(post, tipo, midias)
        except ErroPost as e:
            falhas += 1
            log(f"❌ {rotulo}: {e}")
            continue

        rotulo += f" ({tipo} de {quando:%d/%m %H:%M})"
        if quando > agora:
            proximos.append((quando, rotulo))
            continue
        if agora - quando > timedelta(hours=JANELA_HORAS):
            if agora - quando < timedelta(days=2):  # só avisa sobre atrasos recentes
                log(f"⏭️  {rotulo}: horário passou há mais de {JANELA_HORAS:g}h, não publiquei. "
                    f"Mude a data/hora na planilha se ainda quiser postar.")
            continue

        if simular:
            log(f"🧪 {rotulo}: seria publicado agora.")
            continue

        try:
            log(f"⏳ {rotulo}: publicando...")
            ids = publicar(post, tipo, midias)
            estado[chave] = {"ids": ids, "tipo": tipo, "agendado": quando.isoformat(),
                             "publicado_em": datetime.now(FUSO).isoformat(timespec="seconds")}
            salvar_estado(estado)  # salva na hora, para nunca repetir
            link = link_do_post(ids[-1])
            if link:
                estado[chave]["link"] = link
                salvar_estado(estado)
            publicados += 1
            log(f"✅ {rotulo}: publicado! {link}")
        except ErroPost as e:
            falhas += 1
            log(f"❌ {rotulo}: {e}")

    proximos.sort()
    if proximos:
        log(f"\nPróximo(s) agendado(s): {len(proximos)}")
        for _, r in proximos[:5]:
            log(f"   • {r}")

    log(f"\nResumo: {publicados} publicado(s), {falhas} com problema.")
    if falhas:
        sys.exit(1)  # o GitHub avisa por e-mail quando dá erro


if __name__ == "__main__":
    main()
