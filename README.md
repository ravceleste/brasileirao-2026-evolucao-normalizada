# Brasileirão 2026 — evolução normalizada

Site estático para acompanhar a trajetória dos 20 clubes da Série A. O gráfico reaproveita o HTML anterior: mantém o visual, as cores e tracejados, os escudos, o Santos destacado por padrão, seleção de clube, marcadores sob demanda, tooltips e conectores calculados a partir do último ponto real.

## Métrica e eixo

`Índice normalizado = pontos oficiais acumulados − jogos disputados`.

Todos começam no jogo 0 com índice e pontos iguais a zero. Vitória soma +2 ao índice, empate 0 e derrota −1. Os pontos oficiais seguem a regra da competição (3/1/0) e são exibidos separadamente. O eixo X conta o número de jogos de cada clube em ordem cronológica da data real; a rodada oficial da CBF é apenas informação no tooltip. Linhas param no último jogo concluído de cada time.

## Arquivos

- `index.html`: aplicação HTML/CSS/SVG e JavaScript, sem framework.
- `data/brasileirao_2026.json`: pontos, partidas, trajetórias e metadados exibidos no site.
- `data/fixtures_2026.json`: confronto e rodada oficial, extraídos da tabela básica publicada pela CBF.
- `assets/`: escudos que já estavam embutidos na visualização original.
- `scripts/update.py`: busca o placar, recalcula as séries e interrompe o update se uma auditoria falhar.
- `scripts/schedule_matches.py`: lê os horários futuros do feed ESPN e gera agendamentos de checagem após cada partida.
- `scripts/check_after_matches.py`: espera até a checagem pós-jogo programada e tenta novamente se a fonte ainda não marcou a partida como encerrada.
- `.github/workflows/update.yml`: faz uma conferência diária de recuperação, atualiza o calendário de partidas e aceita execução manual.
- `.github/workflows/match-checks.yml`: é atualizado automaticamente para disparar uma verificação 2h15 após o início previsto de cada jogo.
- `.github/workflows/pages.yml`: publica o site em alterações normais na branch `main` e permite publicação manual.

## Fonte dos resultados

O atualizador consulta o endpoint JSON público usado pelo site da ESPN: [`site.api.espn.com/.../scoreboard?dates=2026`](https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/scoreboard?dates=2026&limit=1000). Não exige conta, chave de API ou serviço pago. Ele fornece clubes, placares, datas/horários e situação da partida. O script considera apenas partidas finalizadas.

A rodada oficial vem da tabela básica do Brasileirão 2026 publicada pela [CBF](https://www.cbf.com.br/futebol-brasileiro/noticias/detalhes/competicoes-campeonato-brasileiro-serie-b/cbf-divulga-tabela-detalhada-das-primeiras-rodadas-do-brasileirao-2026), guardada localmente em `data/fixtures_2026.json`. Assim, a ordenação usa o horário real do feed; a rodada não desloca a série no eixo X.

**Limitações:** o feed JSON da ESPN é público, mas não é uma API com contrato de estabilidade. Pode mudar o formato, os nomes de clubes ou a disponibilidade. Se isso acontecer, edite os aliases e a leitura em `scripts/update.py`; o job falha sem publicar uma atualização inválida. Se a CBF mudar um confronto da tabela básica, atualize `data/fixtures_2026.json` a partir da tabela oficial e rode o atualizador novamente. Não há scraping de páginas de resultados.

## Auditorias do atualizador

Antes de gravar o JSON, o script verifica IDs e confrontos duplicados, participação apenas dos 20 clubes, placares inteiros não negativos, associação dos jogos à tabela CBF, limite de 38 jogos por clube, ordenação cronológica, jogo 0, acumulação oficial 3/1/0, variações do índice em `{-1, 0, +2}` e a identidade `índice final = pontos − jogos`. Ele só recebe partidas finalizadas e nunca preenche jogos futuros. Se a fonte retornar menos partidas do que o JSON já publicado, o update é recusado para evitar apagar dados por uma resposta incompleta.

## Atualização local

Requer Python 3.10+; só usa a biblioteca padrão.

```bash
python scripts/update.py
python -m http.server 8000
```

Depois, abra `http://localhost:8000`. O JSON não é reconstruído no HTML; atualizações futuras só alteram o arquivo de dados.

## Atualização após os jogos

O workflow consulta os horários futuros do feed ESPN e gera agendamentos por partida. A primeira checagem ocorre 2h15 após o início previsto; se a partida ainda não estiver finalizada no feed, há novas tentativas 15 e 45 minutos depois. A checagem diária às 07h de Brasília recupera resultados caso um gatilho não rode ou a partida seja adiada. Não há consultas de resultado durante o jogo.

O GitHub Actions usa `America/Sao_Paulo` para os agendamentos. O horário é uma estimativa baseada no início previsto, e o próprio GitHub pode atrasar execuções agendadas. Partidas remarcadas são incorporadas quando o calendário é sincronizado no ciclo diário seguinte.

## Publicação gratuita no GitHub Pages

O workflow diário usa o fuso `America/Sao_Paulo`; os agendamentos pós-jogo usam a mesma zona. GitHub Actions pode atrasar execuções em períodos de alta demanda. Os workflows também podem ser executados manualmente (`workflow_dispatch`).

Para habilitar a hospedagem no repositório, selecione GitHub Pages como fonte **GitHub Actions** nas configurações de Pages. Os workflows montam apenas `index.html`, JSON e escudos no artefato publicado. O job agendado tem permissão para commitar o novo JSON e fazer a publicação na mesma execução, sem backend permanente ou chave secreta.

## Marcas e escudos

Os escudos identificam os clubes e são marcas de seus respectivos titulares. Foram preservados da visualização anexada para esta publicação inicial. Revise direitos e licenças antes de monetizar o projeto.
