@echo off
REM Exemplo de execução (ajuste os parâmetros conforme necessário)

python tec_download_concursos.py ^
  --cdp http://127.0.0.1:9222 ^
  --out saida ^
  --target-pairs 300 ^
  --year-start 2010 ^
  --year-end 2026 ^
  --max-pages-per-query 120 ^
  --use-keywords ^
  --delay-min 0.8 ^
  --delay-max 2.0
