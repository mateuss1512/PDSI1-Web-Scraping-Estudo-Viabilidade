# Proposta de Análise com IA (pós-coleta) — Provas e Gabaritos

Este documento descreve **apenas a proposta** de como aplicar IA após a etapa de Web Scraping (já implementada) para transformar PDFs de **provas** e **gabaritos** em dados estruturados e gerar análises úteis.

---

## 1) Objetivo

A partir dos PDFs coletados, usar IA para:

- **Estruturar** as provas em um dataset de questões (enunciado, alternativas, metadados).
- **Vincular** cada questão à resposta correta (gabarito).
- **Classificar** questões por disciplina/assunto.
- Estimar **dificuldade** e **tipo** (múltipla escolha, certo/errado, discursiva).
- Gerar **insights** para estudo: tópicos mais recorrentes por ano, banca, órgão, etc.
- (Opcional) oferecer **busca inteligente (RAG)**: buscar questões por linguagem natural.

---

## 2) Entradas e saídas

### Entradas
- PDFs baixados pelo scraper, organizados em:
  - `saida/<ANO>/<nivel>/provas/<concurso_id>/*.pdf`
  - `saida/<ANO>/<nivel>/gabaritos/<concurso_id>/*.pdf`
- `manifest.json` com metadados (ano, nível, concurso_id, caminho do arquivo, url, etc.)

### Saídas (propostas)
1) **Dataset estruturado** (JSONL/CSV/Parquet), por exemplo `questoes.jsonl`:
```json
{
  "concurso_id": "xxx-1a2b3c4d",
  "ano": 2022,
  "nivel": "superior",
  "orgao": "TCU",
  "banca": "CESPE",
  "cargo": "Auditor",
  "questao_num": 12,
  "enunciado": "…",
  "alternativas": {"A": "…", "B": "…", "C": "…", "D": "…", "E": "…"},
  "resposta": "C",
  "disciplina": "Direito Constitucional",
  "assunto": "Controle de constitucionalidade",
  "tipo": "multipla_escolha",
  "dificuldade": "media",
  "fonte_prova": "…/provas/…pdf",
  "fonte_gabarito": "…/gabaritos/…pdf"
}
```

2) **Relatórios** (HTML/PDF) com gráficos/tabelas:
- Frequência de disciplinas e assuntos por ano
- Tendências por banca (tópicos que mais caem)
- Distribuição de dificuldade estimada

3) (Opcional) **Busca semântica / RAG**:
- Recupera questões relevantes para uma pergunta (“questões de crase nível médio 2018–2022”).

---

## 3) Pipeline proposto (etapas)

### Etapa A — Extração de texto dos PDFs
**Desafio:** alguns PDFs têm texto nativo; outros são imagens escaneadas.

**Estratégia:**
1. Tentar extração direta (rápida):
   - `pymupdf` (fitz), `pdfminer.six`, `pypdf`
2. Se texto vier vazio/ruim → OCR:
   - Converter páginas em imagem (`pymupdf`/`pdf2image`)
   - OCR com `tesseract` (`pytesseract`) ou serviço cloud

**Saída:** texto por página + metadados (nº páginas, confiança OCR, etc.)

---

### Etapa B — Segmentação de questões
**Objetivo:** separar cada questão com enunciado e alternativas.

**Técnicas combinadas:**
- Heurísticas e regex (padrões como `Questão 1`, `Q. 01`, `01.`).
- Quando a formatação for confusa: usar LLM para reestruturar o texto em formato JSON.

**Exemplo de prompt (LLM):**
> “Separe o texto abaixo em uma lista de questões numeradas. Para cada questão, extraia enunciado e alternativas (A–E ou certo/errado). Devolva JSON válido.”

**Saída:** lista de questões “cruas” (sem gabarito ainda).

---

### Etapa C — Extração do gabarito e pareamento prova ↔ gabarito
**Objetivo:** mapear `questão → alternativa correta`.

**Como fazer:**
- Detectar padrões comuns no gabarito (`01 - C`, `1) C`, tabelas).
- Normalizar o gabarito para `{questao_num: resposta}`.
- Validar consistência:
  - nº de respostas no gabarito ≈ nº de questões detectadas na prova.

**Saída:** questões com campo `resposta` preenchido.

---

### Etapa D — Classificação por disciplina e assunto
**Objetivo:** rotular as questões para análise e busca.

**Opções:**
1) **LLM zero-shot/few-shot** com uma taxonomia fixa (ex.: Português, RLM, Constitucional…)
- Vantagem: não exige dataset rotulado
- Desvantagem: custo e variação → precisa validação por amostragem

2) **Embeddings + clustering**
- Embeddings do enunciado
- Agrupar por similaridade
- Rotular clusters com LLM (“qual o tema comum deste grupo?”)

3) **Modelo supervisionado** (se houver rótulos)
- Rotular uma amostra e treinar classificador

**Saída:** `disciplina` e `assunto` por questão.

---

### Etapa E — Estimativa de dificuldade e tipo de questão
**Tipo** (múltipla escolha, certo/errado, discursiva) pode ser inferido por padrões das alternativas.

**Dificuldade** (fácil/média/difícil) pode usar:
- Heurísticas (tamanho do enunciado, presença de cálculos, densidade técnica)
- LLM com critérios definidos
- (Futuro) modelo treinado com dados de acerto/erro se houver histórico

**Exemplo de prompt (LLM):**
> “Classifique a dificuldade em fácil/média/difícil com base em: complexidade do enunciado, quantidade de passos lógicos e conhecimento prévio exigido. Retorne também uma justificativa curta.”

---

### Etapa F (Opcional) — Busca inteligente (RAG)
- Indexar questões com embeddings em um vetor store (FAISS/Chroma/Elastic)
- Pergunta do usuário → recuperar top-k questões → gerar resposta com base no conjunto recuperado

**Exemplo de uso:**
- “Mostre 10 questões de Direito Administrativo sobre licitações (2015–2022) com gabarito.”

---

## 4) Métricas de validação (propostas)

### Métricas de extração
- % de PDFs com extração direta bem-sucedida (sem OCR)
- % que exigiram OCR
- taxa de páginas com texto “aproveitável”

### Métricas de consistência prova ↔ gabarito
- diferença média: `|n_questoes - n_respostas|`
- % de concursos com pareamento completo (todas as questões com resposta)

### Métricas de classificação (amostragem manual)
- Acurácia de disciplina em amostra (ex.: 200 questões)
- Acurácia de assunto em amostra (ex.: 200 questões)
- Concordância entre avaliadores (se houver 2 pessoas revisando)

---

## 5) Ferramentas sugeridas (stack)

- **PDF/Text**: `pymupdf`, `pdfminer.six`, `pypdf`
- **OCR**: `pytesseract` + `tesseract-ocr` (ou serviço cloud)
- **IA**:
  - LLM para normalização/rotulagem
  - Embeddings para clustering e busca semântica
- **Dados/Armazenamento**:
  - JSONL/Parquet + SQLite
  - (Opcional) FAISS/Chroma para RAG

---

## 6) Entregáveis do módulo de IA (propostos)
1) `questoes.jsonl` (questões estruturadas + gabarito)
2) `relatorio_temas.html` (incidência de temas por ano/banca)
3) (Opcional) protótipo de consulta (RAG) com exemplos de perguntas

---

## 7) Observações e limitações
- PDFs variam muito de formatação; OCR pode introduzir erros.
- Classificação por IA deve ser validada por amostragem (não assumir 100% correto).
- O modelo não “resolve” questões; apenas estrutura, classifica e analisa padrões.
