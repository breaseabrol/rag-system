import re
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from urllib.parse import urljoin


@dataclass
class LoadedDocument:
    url: str
    title: str
    text: str
    doc_metadata: dict


def fetch_page(url: str) -> str:
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.text, resp.url


def clean_text(text: str) -> str:
    """Collapse all whitespace (including newlines) into single spaces. Use for prose."""
    return re.sub(r"\s+", " ", text).strip()


def clean_cell_text(text: str) -> str:
    """Collapse repeated whitespace WITHIN each line, but keep line breaks between them.
    Used for table cells, where <br> tags separate distinct sub-values (operator variants,
    description, examples) that need to stay visually distinct."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    lines = [l for l in lines if l]
    return "\n".join(lines)


def parse_page(url: str, html: str) -> LoadedDocument:
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.find("title")
    title = clean_text(title_el.text) if title_el else "Untitled Document"

    body_content = soup.find("div", id="docContent") or soup.find("body") or soup

    for nav in body_content.select(".navheader, .navfooter, .navsummary"):
        nav.decompose()

    content_segments = []

    for el in body_content.find_all(["p", "pre", "h1", "h2", "h3", "table"]):
        # skip anything that lives inside a <table> we've already processed —
        # otherwise recursive find_all() picks up nested <p> tags a second time
        if el.find_parent("table") is not None:
            continue

        if el.name == "pre":
            code_text = el.get_text(" ", strip=True).strip()
            if code_text:
                content_segments.append(f"[CODE]\n{code_text}\n[/CODE]")

        elif el.name == "table":
            rows = []
            for row in el.find_all("tr"):
                cells = []
                for cell in row.find_all(["td", "th"]):
                    # Postgres reference tables often pack multiple logical lines
                    # (operator variant / description / example) into ONE cell via <br>.
                    # Convert those to real newlines before extracting text, or they're lost.
                    for br in cell.find_all("br"):
                        br.replace_with("\n")
                    cell_text = clean_cell_text(cell.get_text(""))
                    if cell_text:
                        cells.append(cell_text)
                if cells:
                    rows.append(" | ".join(cells))
            table_text = "\n\n".join(rows)
            if table_text:
                content_segments.append(f"[TABLE]\n{table_text}\n[/TABLE]")

        else:
            text = clean_text(el.get_text(" ", strip=True))
            if text:
                content_segments.append(text)

    full_text = "\n\n".join(content_segments)

    return LoadedDocument(
        url=url,
        title=title,
        text=full_text,
        doc_metadata={"section": url.rstrip("/").split("/")[-1].replace(".html", "")}
    )


def load_doc(url: str) -> LoadedDocument:
    html, resolved_url = fetch_page(url)
    return parse_page(resolved_url, html)

def get_all_doc_urls(sections=("sql-", "functions-", "queries-", "performance-", "indexes-")) -> list[str]:
    toc_url = "https://www.postgresql.org/docs/16/index.html"

    html = fetch_page(toc_url)
    soup = BeautifulSoup(html, "html.parser")

    # Step 1: find the chapter "hub" pages by their link text, not their href —
    # index.html names them descriptively (e.g. "Functions and Operators"),
    # not with the sql-/functions- prefix used by their child leaf pages.
    hub_keywords = ["functions and operators", "queries", "indexes", "performance tips", "reference", "sql commands"]
    hub_urls = set()
    for a in soup.find_all("a", href=True):
        link_text = a.get_text(strip=True).lower()
        href = a["href"].split("#")[0]
        if href.endswith(".html") and any(k in link_text for k in hub_keywords):
            full_url = urljoin(toc_url, href)
            if "/docs/16/" in full_url:
                hub_urls.add(full_url)

    # Step 2: crawl each hub page for the real leaf URLs
    urls = set()
    for hub_url in hub_urls:
        sub_html, resolved_hub_url = fetch_page(hub_url)
        sub_soup = BeautifulSoup(sub_html, "html.parser")
        for a in sub_soup.find_all("a", href=True):
            href = a["href"].split("#")[0]
            if not href.endswith(".html"):
                continue
            full_url = urljoin(resolved_hub_url, href)
            if "/docs/16/" not in full_url:
                continue
            if any(s in full_url for s in sections):
                urls.add(full_url)

    urls |= {u for u in hub_urls if any(s in u for s in sections)}

    return sorted(urls)