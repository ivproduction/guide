"""
ingest/smart.py — конвертация PDF через Gemini Vision.

Медленно (загрузка в Gemini Files API), но понимает:
- двухколоночный layout
- диалоговый формат
- таблицы и схемы
"""

import logging
from pathlib import Path

from google import genai as google_genai
from langchain_text_splitters import MarkdownHeaderTextSplitter

from app.config import GEMINI_API_KEY, PDF_PROCESSING_MODEL
from app.ingest._common import skip_intro

log = logging.getLogger(__name__)

_genai = google_genai.Client(api_key=GEMINI_API_KEY)

PROMPT = """You are a document processing assistant preparing content for a RAG knowledge base.
Analyze this PDF and rewrite its content in your own words as structured Markdown.

Rules:
- Use proper heading hierarchy (# ## ###) based on document structure
- Rewrite and paraphrase all content — do not quote verbatim
- Summarize key ideas, concepts, and practical guidance
- Convert tables to Markdown tables
- Describe diagrams and figures: [Figure: brief description]
- Skip page numbers, running headers, footers, copyright notices
- Output ONLY the Markdown content, no explanations or meta-commentary"""


def convert(pdf_path: Path) -> str:
    log.info("  [smart] Загружаю в Gemini Files API: %s", pdf_path.name)
    uploaded = _genai.files.upload(file=str(pdf_path))
    log.info("  [smart] Файл загружен: %s", uploaded.name)

    try:
        log.info("  [smart] Генерирую Semantic Markdown...")
        response = _genai.models.generate_content(
            model=PDF_PROCESSING_MODEL,
            contents=[uploaded, PROMPT],
        )
        md_text = response.text
        if not md_text:
            raise ValueError(f"Gemini вернул пустой ответ. finish_reason={response.candidates[0].finish_reason if response.candidates else 'unknown'}")
        log.info("  [smart] Получено %d символов", len(md_text))
    finally:
        _genai.files.delete(name=uploaded.name)
        log.info("  [smart] Файл удалён из Gemini")

    md_text = skip_intro(md_text)

    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "chapter"), ("##", "section"), ("###", "subsection")],
        strip_headers=False,
    )
    chunks = splitter.split_text(md_text)
    log.info("  [smart] Смысловых чанков: %d", len(chunks))

    parts = []
    for chunk in chunks:
        header = " / ".join(
            v for v in [
                chunk.metadata.get("chapter"),
                chunk.metadata.get("section"),
                chunk.metadata.get("subsection"),
            ] if v
        )
        parts.append(f"[{header}]\n{chunk.page_content}" if header else chunk.page_content)

    return "\n\n---\n\n".join(parts)
