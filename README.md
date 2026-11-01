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
- `.github/workflows/update.yml`: busca novos resultados duas vezes ao dia e, quando há mudança, commita o JSON e publica o Pages atualizado. Também aceita execução manual.
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

## Publicação gratuita no GitHub Pages

O workflow de atualização usa cron UTC. `10:00 UTC` corresponde a `07:00` em Brasília e `20:00` em Brisbane; `22:00 UTC` corresponde a `19:00` em Brasília e `08:00` em Brisbane. GitHub Actions pode atrasar a execução em períodos de alta demanda. O workflow manual (`workflow_dispatch`) permite atualizar sob demanda.

Para habilitar a hospedagem no repositório, selecione GitHub Pages como fonte **GitHub Actions** nas configurações de Pages. Os workflows montam apenas `index.html`, JSON e escudos no artefato publicado. O job agendado tem permissão para commitar o novo JSON e fazer a publicação na mesma execução, sem backend permanente ou chave secreta.

## Marcas e escudos

Os escudos identificam os clubes e são marcas de seus respectivos titulares. Foram preservados da visualização anexada para esta publicação inicial. Revise direitos e licenças antes de monetizar o projeto.
