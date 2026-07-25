import re
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass


@dataclass
class LoadedDocument:
    url: str
    title: str
    text: str
    doc_metadata: dict


def fetch_page(url: str) -> str:
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.text


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
    html = fetch_page(url)
    return parse_page(url, html)