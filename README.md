# Web Scraping - ContestsAI

Script em Python para **coletar provas e gabaritos** (PDF) a partir da área de **Concursos** do TecConcursos, organizando os arquivos por **ano** e por **nível** (`medio`, `superior`, `sem_classificacao`).

> Resultado obtido no projeto: **300 pares (prova+gabarito)**, **600 arquivos** (PDF), com navegação por páginas de listagem + páginas de detalhe.

---

## ✅ Funcionalidades

- Busca por **ano** (ex.: `2022`) e também por **palavras‑chave** (ex.: `2022 prova`, `2022 gabarito`, etc.)
- Estratégia **detail-first**: entra na página de detalhes do concurso e captura links de PDF/CDN por lá  
  (isso aumenta muito a taxa de acerto vs. buscar apenas botões no card da listagem).
- Download com `requests` usando os **cookies** da sessão do navegador (Playwright).
- Organização automática de pastas:
  ```
  saida/<ANO>/
    medio/provas/<concurso_id>/
    medio/gabaritos/<concurso_id>/
    superior/provas/<concurso_id>/
    superior/gabaritos/<concurso_id>/
    sem_classificacao/provas/<concurso_id>/
    sem_classificacao/gabaritos/<concurso_id>/
  ```
- Gera `manifest.json` com metadados dos arquivos baixados (url, caminho, concurso_id, etc.)

---

## ⚙️ Pré-requisitos

- Python 3.10+ (recomendado)
- Google Chrome instalado
- Conta logada no site (login manual)

---

## 📦 Instalação

### 1) Criar ambiente virtual (opcional, mas recomendado)

**Windows**
```bat
python -m venv .venv
.venv\Scripts\activate
```

### 2) Instalar dependências
```bat
pip install -r requirements.txt
python -m playwright install chromium
```

---

## 🔐 Como rodar (modo recomendado: CDP / Chrome “real”)

O site pode bloquear login em browser automatizado/headless. Por isso, o modo mais estável é controlar **um Chrome real já logado** via CDP (remote debugging).

### 1) Abra um Chrome com porta CDP

**Windows (CMD)**
```bat
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\chrome_tec_profile"
```

> Isso abre um Chrome separado, com um perfil dedicado.

### 2) Faça login manualmente no site usando esse Chrome
- Acesse a área de concursos
- Confirme que está logado
- **Não feche** esse Chrome

### 3) Rode o script apontando para o CDP

Exemplo para baixar **300 pares** entre 2010 e 2026:

```bat
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
```

---

## 🧩 Argumentos principais

- `--cdp`: endpoint do Chrome via CDP (ex.: `http://127.0.0.1:9222`)
- `--out`: pasta de saída (default: `saida`)
- `--target-pairs`: meta de concursos com prova+gabarito (default: 300)
- `--year-start / --year-end`: intervalo de anos
- `--max-pages-per-query`: quantas páginas percorrer por consulta
- `--use-keywords`: ativa consultas extras por ano usando keywords (melhora muito o resultado)
- `--keywords`: lista de termos usados quando `--use-keywords` está ligado
- `--delay-min / --delay-max`: atraso aleatório entre ações (ajuda estabilidade)

---

## 📄 `manifest.json`

O script gera um `saida/manifest.json` com entradas no formato:

```json
{
  "year": "2022",
  "nivel": "superior",
  "concurso_id": "nome-do-concurso-1a2b3c4d",
  "concurso_title": "Nome do Concurso",
  "tipo": "provas",
  "label": "Prova objetiva - PDF",
  "source": "detail_pdf",
  "url": "https://...pdf",
  "path": "saida/2022/superior/provas/<concurso_id>/prova.pdf"
}
```

---

## 🧯 Troubleshooting rápido

### “Login/CAPTCHA não aparece no Playwright”
Use o modo CDP (Chrome real) como descrito acima.

### “Poucos pares”
- Ative `--use-keywords`
- Aumente `--max-pages-per-query`
- Ajuste o range de anos
- Use delays levemente maiores (ex.: 1.0–2.5)

---

## ⚠️ Observações
- Este projeto é de código aberto para fins educacionais. Use com responsabilidade e respeite os termos de uso dos sites de origem.
