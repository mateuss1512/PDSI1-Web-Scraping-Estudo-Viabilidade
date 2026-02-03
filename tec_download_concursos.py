import argparse
import hashlib
import json
import os
import random
import re
import time
from typing import Dict, List, Optional, Set, Tuple

import requests
from requests.cookies import create_cookie
from slugify import slugify
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

BASE_URL = "https://www.tecconcursos.com.br/concursos"
ORIGIN = "https://www.tecconcursos.com.br"


# -------------------------
# Utils
# -------------------------
def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def jitter_sleep(a: float, b: float):
    if b <= 0:
        return
    time.sleep(random.uniform(a, b))


def normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return ORIGIN + u
    return u


def safe_filename(name: str, ext_default: str = ".pdf") -> str:
    name = re.sub(r"\s+", " ", (name or "")).strip()
    base = slugify(name)[:120] or "arquivo"
    ext = os.path.splitext(name)[1].lower()
    if ext not in [".pdf", ".zip", ".doc", ".docx"]:
        ext = ext_default
    return base + ext


def make_concurso_id(detail_url: str, title: str) -> str:
    seed = (detail_url or "") + "||" + (title or "")
    h = hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]
    t = slugify(title)[:70] or "concurso"
    return f"{t}-{h}"


def classify_tipo(label: str) -> Optional[str]:
    l = (label or "").lower()
    if "gabar" in l or "respost" in l:
        return "gabaritos"
    if "prova" in l or "caderno" in l or "quest" in l or "discurs" in l or "objetiva" in l:
        return "provas"
    return None


def dismiss_overlays(page):
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass


# Login detection

def is_login_gate(page) -> bool:
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""

    if re.search(r"/(login|entrar)(/|$|\?)", url):
        return True

    try:
        if page.locator('input[type="password"]:visible').count() > 0:
            return True
    except Exception:
        pass

    try:
        if page.locator('text=/faça\\s+login|entre\\s+para\\s+continuar|acesso\\s+restrito/i').count() > 0:
            return True
    except Exception:
        pass

    return False

# Search helpers

def pick_search_input(page):
    selectors = [
        'input[ng-model="vm.busca"]',
        'input[ng-model*="busca"]',
        'input[name*="busca" i]',
        'input[placeholder*="busca" i]',
        'input[type="search"]',
    ]
    for sel in selectors:
        loc = page.locator(sel)
        for i in range(loc.count()):
            el = loc.nth(i)
            try:
                if el.is_visible():
                    return el
            except Exception:
                pass

    tbs = page.get_by_role("textbox")
    for i in range(tbs.count()):
        el = tbs.nth(i)
        try:
            if el.is_visible():
                return el
        except Exception:
            pass

    raise RuntimeError("Não achei campo de busca visível na página /concursos.")


def click_search(page, query: str, max_wait_ms: int = 30000):
    inp = pick_search_input(page)
    inp.click()
    inp.fill(query)
    try:
        inp.press("Tab")
    except Exception:
        pass

    dismiss_overlays(page)
    page.wait_for_timeout(250)

    buscar_btn = page.locator("#buscar")
    try:
        page.wait_for_function(
            """() => {
                const b = document.querySelector('#buscar');
                if (!b) return false;
                const clsDisabled = b.classList.contains('disabled');
                const ariaDisabled = (b.getAttribute('aria-disabled') || '').toLowerCase() === 'true';
                const propDisabled = !!b.disabled;
                return !(clsDisabled || ariaDisabled || propDisabled);
            }""",
            timeout=max_wait_ms,
        )
    except PWTimeoutError:
        pass

    try:
        buscar_btn.click(timeout=2500, force=True)
    except Exception:
        buscar_btn.evaluate("b => b.click()")

    try:
        page.wait_for_load_state("networkidle", timeout=7000)
    except Exception:
        pass
    page.wait_for_timeout(700)


def find_next_page_button(page):
    candidates = [
        'a[rel="next"]',
        'a:has-text("Próxima")',
        'button:has-text("Próxima")',
        'a:has-text("»")',
        'li:has(a:has-text("»")) a',
    ]
    for sel in candidates:
        loc = page.locator(sel)
        try:
            if loc.count() > 0 and loc.first.is_visible():
                return loc.first
        except Exception:
            pass
    return None


def locator_is_disabled(loc) -> bool:
    try:
        return bool(
            loc.evaluate(
                """(el) => {
                    const li = el.closest('li');
                    const cls = (el.getAttribute('class') || '') + ' ' + (li ? (li.getAttribute('class')||'') : '');
                    const aria = (el.getAttribute('aria-disabled') || '').toLowerCase() === 'true';
                    return aria || cls.includes('disabled');
                }"""
            )
        )
    except Exception:
        return False

# Level inference

RE_SUP = re.compile(r"(nível|nivel)\s*[:\-]?\s*superior|\bensino\s+superior\b", re.I)
RE_MED = re.compile(r"(nível|nivel)\s*[:\-]?\s*m[eé]dio|\bensino\s+m[eé]dio\b", re.I)

def infer_nivel(texto: str) -> str:
    txt = (texto or "").lower()
    sup = bool(RE_SUP.search(txt))
    med = bool(RE_MED.search(txt))
    if sup and med:
        return "sem_classificacao"
    if sup:
        return "superior"
    if med:
        return "medio"
    return "sem_classificacao"

# Detail extraction (PDFs)

def collect_detail_links(page) -> List[Tuple[str, str, str]]:
    """
    Retorna lista de (detail_url, title_guess, card_text).
    Busca links internos /concursos/ (não o /concursos list).
    """
    items = page.evaluate(
        """() => {
            function clean(s){ return (s||'').replace(/\\s+/g,' ').trim(); }
            const links = Array.from(document.querySelectorAll('a[href*="/concursos/"]'))
              .map(a => a.getAttribute('href') || '')
              .filter(h => h && !h.includes('/concursos?') && !h.endsWith('/concursos') && !h.endsWith('/concursos/'));

            // pega apenas links que parecem ser "detalhe" (tem mais de 2 segmentos após /concursos/)
            const detail = [];
            for (const h of links){
              try{
                const u = new URL(h, location.origin);
                const p = u.pathname;
                // algo como /concursos/<slug...>
                if (!p.startsWith('/concursos/')) continue;
                const rest = p.replace('/concursos/','').split('/').filter(Boolean);
                if (rest.length < 1) continue;
                detail.push(u.toString());
              }catch(e){}
            }

            // tenta capturar cards: pega ancestor e extrai texto/título
            const unique = Array.from(new Set(detail)).slice(0, 120);
            return unique.map(url => {
              let title = '';
              let rawText = '';
              // tenta achar o <a> correspondente e o "card" pai
              const a = Array.from(document.querySelectorAll('a[href]')).find(x => {
                try { return new URL(x.getAttribute('href'), location.origin).toString() === url; } catch(e){ return false; }
              });
              if (a){
                let card = a;
                for (let i=0;i<10 && card; i++){
                  const hasHeading = card.querySelector && card.querySelector('h1,h2,h3,strong');
                  if (hasHeading) break;
                  card = card.parentElement;
                }
                if (card){
                  rawText = clean(card.innerText || '');
                  const h = card.querySelector && card.querySelector('h1,h2,h3,strong');
                  if (h) title = clean(h.innerText || '');
                  if (!title && rawText) title = rawText.split('\\n')[0].trim();
                }
              }
              return {url, title, rawText};
            });
        }"""
    )
    out = []
    seen = set()
    for it in items or []:
        u = (it.get("url") or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append((u, (it.get("title") or "").strip(), (it.get("rawText") or "").strip()))
    return out


def collect_pdf_links_in_detail(detail_page) -> List[Tuple[str, str]]:
    """
    Retorna lista de (pdf_url, label).
    Pega href/ng-href para CDN e .pdf.
    Também tenta inferir label pelo texto do link/botão.
    """
    pairs = detail_page.evaluate(
        """() => {
            function clean(s){ return (s||'').replace(/\\s+/g,' ').trim(); }
            const out = [];

            function push(u, label){
              if (!u) return;
              out.push({u, label: clean(label || '')});
            }

            const els = Array.from(document.querySelectorAll('a,button'));
            for (const el of els){
              const href = el.getAttribute('href') || '';
              const ngh  = el.getAttribute('ng-href') || '';
              const url  = href || ngh;
              const txt  = clean(el.innerText || el.getAttribute('title') || el.getAttribute('aria-label') || '');
              if (!url) continue;

              let abs = '';
              try{ abs = new URL(url, location.origin).toString(); }catch(e){ abs = ''; }

              const low = abs.toLowerCase();
              if (low.includes('cdn.tecconcursos.com.br') || low.endsWith('.pdf')){
                push(abs, txt || 'pdf');
              }
            }
            // dedup por url
            const seen = new Set();
            const uniq = [];
            for (const it of out){
              if (seen.has(it.u)) continue;
              seen.add(it.u);
              uniq.push(it);
            }
            return uniq;
        }"""
    )
    out = []
    for it in pairs or []:
        u = normalize_url(it.get("u") or "")
        if not u:
            continue
        out.append((u, (it.get("label") or "").strip() or "pdf"))
    return out


def sync_cookies_to_requests(context, session: requests.Session):
    try:
        cookies = context.cookies()
    except Exception:
        return
    for c in cookies:
        try:
            session.cookies.set_cookie(
                create_cookie(
                    name=c["name"],
                    value=c["value"],
                    domain=c.get("domain"),
                    path=c.get("path", "/"),
                )
            )
        except Exception:
            pass


def download_url(session: requests.Session, url: str, path: str):
    r = session.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 128):
            if chunk:
                f.write(chunk)

# Main

def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--out", default="saida")
    ap.add_argument("--debug", action="store_true")

    ap.add_argument("--cdp", default="", help="Ex.: http://127.0.0.1:9222 (recomendado)")

    ap.add_argument("--year-start", type=int, default=2010)
    ap.add_argument("--year-end", type=int, default=2026)
    ap.add_argument("--max-pages-per-query", type=int, default=120)

    # metas
    ap.add_argument("--target-pairs", type=int, default=300)
    ap.add_argument("--delay-min", type=float, default=0.8)
    ap.add_argument("--delay-max", type=float, default=2.0)

    # queries por ano
    ap.add_argument("--use-keywords", action="store_true")
    ap.add_argument(
        "--keywords",
        nargs="*",
        default=["prova", "gabarito", "caderno de prova", "prova objetiva", "gabarito oficial", "pdf"],
        help="Vira '{ano} <keyword>'",
    )

    args = ap.parse_args()

    if not args.cdp:
        raise RuntimeError("Use --cdp http://127.0.0.1:9222 (esse é o modo que funcionou no seu caso).")

    ensure_dir(args.out)
    debug_dir = os.path.join(args.out, "_debug")
    if args.debug:
        ensure_dir(debug_dir)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
            "Accept": "*/*",
            "Referer": BASE_URL,
        }
    )

    status: Dict[str, Dict[str, int]] = {}  # key=f"{year}|{nivel}|{cid}"
    manifest: List[Dict[str, str]] = []
    seen_file_urls: Set[str] = set()
    seen_detail_urls: Set[str] = set()

    def pairs_count() -> int:
        return sum(1 for st in status.values() if st.get("provas", 0) and st.get("gabaritos", 0))

    def out_path(year: int, nivel: str, tipo: str, cid: str, label: str) -> str:
        folder = os.path.join(args.out, str(year), nivel, tipo, cid)
        ensure_dir(folder)
        return os.path.join(folder, safe_filename(label or tipo, ".pdf"))

    visited_pages = 0
    visited_details = 0
    downloaded_files = 0
    skipped_login = 0
    pages_no_details = 0

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        detail_page = context.new_page()

        page.goto(BASE_URL, wait_until="domcontentloaded")
        sync_cookies_to_requests(context, session)

        for year in range(args.year_end, args.year_start - 1, -1):
            if pairs_count() >= args.target_pairs:
                break

            queries = [str(year)]
            if args.use_keywords:
                queries += [f"{year} {kw}".strip() for kw in args.keywords]

            # dedup preservando ordem
            seenq = set()
            queries = [q for q in queries if not (q in seenq or seenq.add(q))]

            for q in queries:
                if pairs_count() >= args.target_pairs:
                    break

                print(f"\n[INFO] Busca: '{q}'")
                page.goto(BASE_URL, wait_until="domcontentloaded")
                click_search(page, q)

                for pg in range(1, args.max_pages_per_query + 1):
                    if pairs_count() >= args.target_pairs:
                        break

                    visited_pages += 1

                    if is_login_gate(page):
                        skipped_login += 1
                        if args.debug:
                            try:
                                page.screenshot(path=os.path.join(debug_dir, f"login_list_{year}_{pg}.png"), full_page=True)
                            except Exception:
                                pass
                        break

                    details = collect_detail_links(page)
                    if not details:
                        pages_no_details += 1

                    # processa detalhes (limita por página para não explodir)
                    for (detail_url, title_guess, card_text) in details[:80]:
                        if pairs_count() >= args.target_pairs:
                            break
                        if detail_url in seen_detail_urls:
                            continue
                        seen_detail_urls.add(detail_url)

                        visited_details += 1
                        try:
                            detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
                        except Exception:
                            continue

                        if is_login_gate(detail_page):
                            skipped_login += 1
                            if args.debug:
                                try:
                                    detail_page.screenshot(path=os.path.join(debug_dir, f"login_detail_{year}_{visited_details}.png"), full_page=True)
                                except Exception:
                                    pass
                            continue

                        try:
                            # texto para inferir nível + título melhor
                            body_text = detail_page.locator("body").inner_text(timeout=3000)
                        except Exception:
                            body_text = card_text or ""

                        nivel = infer_nivel(body_text or card_text)
                        # título melhor
                        try:
                            h1 = detail_page.locator("h1").first
                            if h1.count() > 0 and h1.is_visible():
                                title = h1.inner_text(timeout=1000).strip()
                            else:
                                title = title_guess or "concurso"
                        except Exception:
                            title = title_guess or "concurso"

                        cid = make_concurso_id(detail_url, title)
                        sk = f"{year}|{nivel}|{cid}"
                        status.setdefault(sk, {"provas": 0, "gabaritos": 0})

                        pdfs = collect_pdf_links_in_detail(detail_page)

                        # baixa PDFs
                        for (pdf_url, label) in pdfs:
                            if pairs_count() >= args.target_pairs:
                                break
                            if pdf_url in seen_file_urls:
                                continue
                            seen_file_urls.add(pdf_url)

                            tipo = classify_tipo(label)
                            if not tipo:
                                # tenta inferir pela URL
                                low = (pdf_url or "").lower()
                                if "gabar" in low:
                                    tipo = "gabaritos"
                                elif "prova" in low or "caderno" in low:
                                    tipo = "provas"
                                else:
                                    continue

                            # se já temos esse tipo no concurso, pula (para maximizar pares)
                            if status[sk][tipo] > 0:
                                continue

                            outp = out_path(year, nivel, tipo, cid, label)
                            try:
                                sync_cookies_to_requests(context, session)
                                download_url(session, pdf_url, outp)

                                status[sk][tipo] = 1
                                downloaded_files += 1
                                manifest.append({
                                    "year": str(year),
                                    "nivel": nivel,
                                    "concurso_id": cid,
                                    "concurso_title": title,
                                    "tipo": tipo,
                                    "label": label,
                                    "source": "detail_pdf",
                                    "url": pdf_url,
                                    "path": outp
                                })
                            except Exception:
                                pass

                        # log leve
                        if (visited_details % 20) == 0:
                            print(f"[INFO] pages={visited_pages} details={visited_details} pairs={pairs_count()} files={downloaded_files}")

                        jitter_sleep(args.delay_min, args.delay_max)

                    if pairs_count() >= args.target_pairs:
                        break

                    nxt = find_next_page_button(page)
                    if not nxt or locator_is_disabled(nxt):
                        break
                    try:
                        nxt.click(timeout=2500, force=True)
                    except Exception:
                        try:
                            nxt.evaluate("b => b.click()")
                        except Exception:
                            break

                    try:
                        page.wait_for_load_state("networkidle", timeout=7000)
                    except Exception:
                        pass
                    page.wait_for_timeout(500)

        manifest_path = os.path.join(args.out, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        print("\n========== RESULTADO ==========")
        print("Pares (prova+gabarito):", pairs_count())
        print("Arquivos totais:", downloaded_files)
        print("Páginas visitadas:", visited_pages)
        print("Detalhes visitados:", visited_details)
        print("Skips por login:", skipped_login)
        print("Páginas sem detalhes:", pages_no_details)
        print("Manifest:", manifest_path)
        print("\nEstrutura:")
        print("saida/<ANO>/medio/{provas,gabaritos}/<concurso_id>/...")
        print("saida/<ANO>/superior/{provas,gabaritos}/<concurso_id>/...")
        print("saida/<ANO>/sem_classificacao/{provas,gabaritos}/<concurso_id>/...")

        try:
            detail_page.close()
        except Exception:
            pass
        try:
            page.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
