# Estudo de Viabilidade — Web Scraping (Provas e Gabaritos) + Proposta de Análise com IA

## 1. Contexto e objetivo
Este projeto tem como objetivo avaliar e implementar a viabilidade de um processo automatizado para **coleta de provas e gabaritos em PDF** (Web Scraping) a partir de uma plataforma web de concursos, organizando os documentos por **ano** e por **categoria de nível**.

Além da coleta, o projeto também descreve **como seria feita uma análise com IA (proposta)** para extrair informações e gerar insights a partir dos PDFs.

---

## 2. Escopo
### 2.1 O que foi implementado
- Web scraping para coletar **pares de documentos**:
  - **Prova (PDF)**
  - **Gabarito (PDF)**
- Organização dos arquivos em estrutura de pastas por:
  - Ano
  - Nível (`medio`, `superior`, `sem_classificacao`)
- Geração de um **manifesto (manifest.json)** com metadados dos downloads.

### 2.2 O que NÃO faz parte
- Redistribuição pública dos PDFs
- Publicação de conteúdo protegido
- Automatização de resolução de CAPTCHA ou bypass de bloqueios (o login é feito manualmente)

---

## 3. Viabilidade técnica

### 3.1 Alternativas avaliadas
1) **Scraping somente na listagem**
- Vantagem: mais simples
- Desvantagem: baixa taxa de acerto, pois muitos itens não expõem links de download no card

2) **Scraping “detail-first” (adotado)**
- O script coleta links de detalhe dos concursos e entra em cada detalhe para localizar PDFs
- Vantagem: aumenta muito a taxa de captura (links frequentemente aparecem apenas no detalhe)
- Desvantagem: mais navegação (maior tempo de execução)

3) **PDF Scraping**
- Aplicável após o download, para extração de texto e metadados

4) **Image Scraping**
- Possível caso PDFs estejam como imagens, exigindo OCR (não foi necessário como etapa principal)

### 3.2 Tecnologias
- **Playwright**: navegação automatizada e leitura do DOM
- **Chrome CDP (remote debugging)**: controle do Chrome real já logado (evita problemas de CAPTCHA em browser automatizado)
- **requests**: download robusto de arquivos usando cookies da sessão
- **python-slugify**: padronização de nomes de arquivos/pastas

---

## 4. Arquitetura da solução

### 4.1 Fluxo resumido
1. Usuário abre Chrome com `--remote-debugging-port`
2. Usuário faz login manualmente
3. Script conecta no Chrome via CDP
4. Para cada ano:
   - Busca pelo ano
   - (Opcional) busca por palavras‑chave (“prova”, “gabarito”, etc.)
5. Em cada página de resultados:
   - Coleta links de detalhe (`/concursos/...`)
6. Para cada detalhe:
   - Localiza links PDF/CDN e baixa arquivos
   - Classifica como `provas` ou `gabaritos`
   - Inferência de nível por texto (`medio/superior/sem_classificacao`)
7. Atualiza `manifest.json`

### 4.2 Estrutura de saída
```
saida/<ANO>/
  medio/
    provas/<concurso_id>/
    gabaritos/<concurso_id>/
  superior/
    provas/<concurso_id>/
    gabaritos/<concurso_id>/
  sem_classificacao/
    provas/<concurso_id>/
    gabaritos/<concurso_id>/
```

---

## 5. Indicadores e resultados (execução de teste)
- Meta: 300 pares (prova + gabarito)
- Resultado atingido:
  - **Pares (prova+gabarito): 300**
  - **Arquivos totais: 600**
  - **Páginas visitadas: 113**
  - **Detalhes visitados: 674**
  - **Skips por login: 0**

Esses números demonstram viabilidade operacional do processo de coleta no escopo do projeto.

---

## 6. Riscos e mitigação

### 6.1 Riscos técnicos
- Mudança de layout/seletores do site  
  **Mitigação:** seletores mais gerais, logs e possibilidade de modo debug.
- Bloqueios por automação/CAPTCHA  
  **Mitigação:** uso de **Chrome real via CDP** e login manual.
- Instabilidade de rede / downloads interrompidos  
  **Mitigação:** download via `requests` com timeout e manifesto de execução.

### 6.2 Riscos de performance
- Alto número de páginas/detalhes aumenta o tempo
  **Mitigação:** parâmetros de limite (`--max-pages-per-query`, keywords, delays)

---

## 7. Proposta de análise usando IA (apenas proposta)
Após coletar provas e gabaritos (PDF), a IA pode ser aplicada para:

### 7.1 Extração e estruturação
- Extração de texto por parser PDF (quando o PDF tem texto) ou OCR (quando o PDF é imagem)
- Identificação automática de banca, cargo, órgão, ano, disciplinas
- Mapeamento prova ↔ gabarito (questão → alternativa)

### 7.2 Classificação e insights
- Classificação de questões por disciplina/assunto
- Detecção de recorrência de tópicos por ano/banca
- Estimativa de dificuldade (heurísticas + modelos supervisionados)

### 7.3 Criação de dataset
- Transformar questões em JSON/CSV:
  - enunciado, alternativas, resposta correta, tema
- Usar em:
  - recomendação de estudo
  - simulados adaptativos
  - RAG/Chat com busca semântica sobre questões

---

## 8. Conclusão
O estudo demonstrou viabilidade de coleta automatizada em escala (300 pares) usando:
- Playwright + CDP para navegação em sessão autenticada
- requests para download com cookies sincronizados
- organização e manifesto para rastreabilidade

A análise com IA é viável como etapa posterior para estruturar e extrair valor do conteúdo coletado.

---

## 9. Como reproduzir
Ver instruções em `README.md`.
