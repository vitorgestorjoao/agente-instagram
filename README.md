# Agente de publicação no Instagram

Ele roda sozinho no GitHub a cada 30 minutos, olha a sua planilha e publica os posts que já chegaram no horário: foto, carrossel, Reels ou story. Ele anota tudo o que publicou em `publicados.json`, por isso nunca posta duas vezes.

Custo: zero. O GitHub Actions é gratuito para repositórios públicos.

---

## Passo 1: Token da Meta (feito uma vez só)

Antes de começar, confira dois requisitos:
- O Instagram precisa ser uma conta **profissional** (comercial ou criador de conteúdo).
- O Instagram precisa estar **ligado a uma Página do Facebook**.

### 1.1 Criar o app
1. Entre em **developers.facebook.com**, clique em **Meus apps → Criar app** e escolha o tipo **Empresa** (Business).
2. Ligue o app ao seu **portfólio empresarial** (Gerenciador de Negócios).
3. No painel do app, adicione o produto **API do Instagram** (a configuração com login do Facebook).

### 1.2 Criar o token que não expira
1. Entre em **business.facebook.com → Configurações do negócio → Usuários → Usuários do sistema → Adicionar** e crie um usuário com função **Admin**.
2. Clique em **Atribuir ativos** e marque duas coisas com **controle total**:
   - a sua **Página** do Facebook;
   - a sua **conta do Instagram**.
3. Ainda em Configurações do negócio, abra **Contas → Apps**, selecione o app e **adicione esse usuário do sistema** ao app.
4. Volte ao usuário do sistema e clique em **Gerar novo token**:
   - Escolha o app.
   - Em validade, escolha **Nunca**.
   - Marque estas permissões: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`.
5. **Copie o token** e guarde, porque ele não aparece de novo.

> Você é dono do app e da conta, então não precisa enviar o app para análise da Meta.

---

## Passo 2: Repositório no GitHub

1. Crie uma conta grátis em **github.com**.
2. Clique em **New repository**. Nome: `agente-instagram`. Visibilidade: **Public**, para que o Instagram consiga baixar as imagens e para que o GitHub Actions seja grátis.
3. Clique em **Add file → Upload files** e envie: `publicar.py`, `descobrir_id.py`, `publicados.json`, `calendario.csv` e `LEIA-ME.md`.
4. Os arquivos que ficam em `.github/workflows/` não sobem bem pelo celular. Para eles:
   - Clique em **Add file → Create new file**.
   - No nome, digite `.github/workflows/publicar.yml`, cole o conteúdo e clique em **Commit**.
   - Repita com `.github/workflows/descobrir-id.yml`.

---

## Passo 3: Segredos (as senhas do agente)

No repositório, abra **Settings → Secrets and variables → Actions → New repository secret** e cadastre:

| Nome | O que colocar |
|---|---|
| `IG_TOKEN` | o token do passo 1 |
| `IG_USER_ID` | o ID do Instagram (veja logo abaixo) |
| `SHEET_CSV_URL` | o link da planilha (passo 4) |

**Para descobrir o `IG_USER_ID`:**
1. Na aba **Actions**, abra **Descobrir ID do Instagram** e clique em **Run workflow**.
2. Abra a execução e procure a linha `IG_USER_ID = ...`.
3. Copie esse número para o segredo.

---

## Passo 4: Planilha de posts

1. Crie uma planilha no Google Sheets com estas colunas, nesta ordem, na primeira linha:

   `data | hora | tipo | midia | legenda | ativo`

   Se preferir, importe o `calendario.csv` como modelo.

2. Publique a planilha:
   - Abra **Arquivo → Compartilhar → Publicar na Web**.
   - Escolha a aba e o formato **Valores separados por vírgula (.csv)** e clique em **Publicar**.
   - Copie o link gerado e coloque no segredo `SHEET_CSV_URL`.

   O Google pode levar uns 5 minutos para atualizar o CSV depois que você edita a planilha.

### Como preencher cada coluna

| Coluna | Exemplo | Observação |
|---|---|---|
| data | `28/11/2026` | |
| hora | `18:00` | horário de Brasília |
| tipo | `FOTO`, `CARROSSEL`, `REELS` ou `STORY` | se ficar vazio, o agente decide sozinho |
| midia | `post-01.jpg` | veja como usar mídias logo abaixo |
| legenda | texto do post | até 2.200 caracteres e 30 hashtags |
| ativo | `SIM` ou `NAO` | com `NAO`, o post fica pausado |

**Mídias:**
- **Melhor opção:** envie o arquivo para a pasta `midia/` do repositório (**Add file → Upload files**, dentro da pasta) e escreva só o nome do arquivo na planilha, por exemplo `post-01.jpg`.
- **Google Drive:** cole o link com o compartilhamento em "Qualquer pessoa com o link". Funciona bem para **imagens**. Para vídeos do Drive, escreva `video:` antes do link, mas prefira a pasta `midia/`, porque o Drive costuma bloquear vídeos grandes.
- **Carrossel:** separe as mídias com `|`, assim: `slide-1.jpg | slide-2.jpg | slide-3.jpg` (de 2 a 10 itens).
- **Imagens:** use JPG. **Vídeos (Reels):** use MP4, na vertical 9:16, entre 3 segundos e 15 minutos.
- **Stories:** coloque **um story por linha**, para que um erro não repita os stories anteriores.

---

## Passo 5: Testar

1. Na aba **Actions**, abra **Publicar no Instagram**, clique em **Run workflow** e marque **Só simular**.
2. O registro mostra o que seria publicado e aponta qualquer erro na planilha.
3. Quando estiver tudo certo, crie uma linha com o horário de agora e rode o workflow sem marcar "Só simular": o post sai na hora.

---

## Como funciona no dia a dia

- O agente confere a planilha a cada 30 minutos. Um post marcado para 18:00 sai entre 18:00 e mais ou menos 18:40, porque o GitHub às vezes atrasa um pouco.
- Se o horário passar há **mais de 6 horas** sem publicar (por exemplo, porque a planilha estava com erro), o agente **não posta**, para não soltar um post fora de hora. Nesse caso, é só mudar a data ou a hora na planilha.
- Se der erro, **o GitHub manda um e-mail** para você. Abra a execução para ver em qual linha está o problema.
- Para **repostar** algo, mude a data, a hora ou a legenda. Isso conta como um post novo.

## Problemas comuns

| Mensagem | Solução |
|---|---|
| `Faltam os segredos` | Cadastre `IG_TOKEN` e `IG_USER_ID` (passo 3). |
| `token... (código 190)` | O token foi revogado ou expirou. Gere outro (passo 1.2). |
| `(código 10)` ou `(código 200)` | Falta permissão. Gere o token marcando todas as permissões da lista. |
| `não aceitou a mídia` | Formato ou tamanho inválido, ou o link não é público. |
| `O link da planilha não devolveu um CSV` | Use o link de "Publicar na Web" em CSV, não o link normal da planilha. |
| O workflow parou de rodar sozinho | O GitHub pausa agendamentos depois de 60 dias sem atividade no repositório. Na aba Actions, clique em **Enable workflow**. |

O Instagram também limita a quantidade de posts por dia via API, mas o limite é alto: dá para postar várias vezes por dia sem problema.
