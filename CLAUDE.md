# Ecossistema de conteúdo do @joaovitor_gestor

Este repositório é o "motor" de publicação. Fluxo:

1. O João pede um conteúdo no chat (carrossel, post, Reels ou story).
2. O Claude cria as artes ou edita o vídeo e mostra para aprovação.
3. **Só depois da aprovação explícita**, o Claude:
   - salva as mídias em `midia/`;
   - adiciona a linha em `calendario.csv`;
   - faz commit e push.
4. O GitHub Actions (`publicar.yml`) roda a cada 30 minutos e publica no horário.

## Regras

- Nunca agendar nem publicar nada sem o "aprovado" do João.
- Nunca colocar token ou senha em arquivo. Eles ficam só nos Secrets do GitHub.
- O João também pode agendar pela planilha do Google (secret `SHEET_CSV_URL`). O agente lê a planilha e o `calendario.csv` juntos.

## Formato do calendario.csv

`data,hora,tipo,midia,legenda,ativo`

- **data:** `DD/MM/AAAA`.
- **hora:** `HH:MM`, horário de Brasília.
- **tipo:** FOTO, CARROSSEL, REELS ou STORY.
- **midia:** nome do arquivo em `midia/`. No carrossel, separe os arquivos com ` | ` (de 2 a 10).
- **legenda:** entre aspas se tiver vírgula ou quebra de linha. Máximo de 2.200 caracteres e 30 hashtags.
- **ativo:** SIM ou NAO.

## Padrões de mídia

- **Feed e carrossel:** JPG de 1080x1350 (4:5), sRGB, menor que 8 MB.
- **Reels:** MP4 H.264 + AAC, 1080x1920 (9:16), 30 fps, de 3 s a 15 min, menor que 100 MB.
- **Story:** JPG ou MP4 de 1080x1920.
- **Nomes dos arquivos:** sem espaço nem acento, no padrão `AAAA-MM-DD_tema_01.jpg`.
- Os posts já publicados ficam registrados em `publicados.json`. Não edite esse arquivo à mão.
