from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings


@dataclass
class Block:
    text: str
    page: int | None
    section: str | None
    kind: str = "paragraph"
    locator: dict = field(default_factory=dict)


@dataclass
class ParsedPaper:
    title: str
    abstract: str
    blocks: list[Block]
    metadata: dict


def chunk_section(text: str, size: int = 1800, overlap: int = 180) -> list[str]:
    if size < 100 or overlap >= size or overlap < 0:
        raise ValueError("Invalid chunk bounds")
    chunks, cursor = [], 0
    while cursor < len(text):
        end = min(cursor + size, len(text))
        if end < len(text):
            split = text.rfind(" ", cursor + size // 2, end)
            if split > cursor:
                end = split
        chunks.append(text[cursor:end].strip())
        if end == len(text):
            break
        cursor = max(cursor + 1, end - overlap)
    return [c for c in chunks if c]


def parse_pdf(path: Path) -> ParsedPaper:
    if settings().parser == "pypdf":
        # Explicit fallback: real text extraction, without layout/table recovery.
        from pypdf import PdfReader

        reader = PdfReader(path)
        blocks = [Block(p.extract_text() or "", i, None) for i, p in enumerate(reader.pages, 1)]
        return ParsedPaper(
            str((reader.metadata or {}).get("/Title", path.stem)),
            "",
            blocks,
            {
                "parser": "pypdf",
                "limitations": ["No layout, table or equation structure; evidence is page text only."],
            },
        )
    if settings().parser != "docling":
        raise ValueError("Unknown PDF parser")
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    options.table_structure_options.do_cell_matching = settings().docling_cell_matching
    if settings().docling_pipeline == "simple":
        from docling.pipeline.simple_pipeline import SimplePipeline

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(backend=PyPdfiumDocumentBackend, pipeline_cls=SimplePipeline)
            }
        )
    else:
        # PDFium avoids docling-parse resource-path failures in non-ASCII Windows workspaces.
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(backend=PyPdfiumDocumentBackend, pipeline_options=options)
            }
        )
    result = converter.convert(
        path, max_num_pages=settings().max_pages, max_file_size=settings().max_upload_mb * 1024 * 1024
    )
    document = result.document
    blocks, title, abstract = [], "", []
    section = None
    table_count = 0
    for item, _level in document.iterate_items():
        label = str(item.label.value)
        page = item.prov[0].page_no if item.prov else None
        locator = {"self_ref": item.self_ref}
        if item.prov:
            locator["bbox"] = item.prov[0].bbox.model_dump(mode="json")
        text = getattr(item, "text", "")
        if label in ("title", "section_header"):
            section = text
            if not title:
                title = text
        if label == "table":
            table_count += 1
            cells = []
            for cell in item.data.table_cells:
                cells.append(
                    {
                        "row": cell.start_row_offset_idx,
                        "col": cell.start_col_offset_idx,
                        "end_row": cell.end_row_offset_idx,
                        "end_col": cell.end_col_offset_idx,
                        "text": cell.text,
                        "column_header": cell.column_header,
                        "row_header": cell.row_header,
                    }
                )
            text = item.export_to_markdown(doc=document)
            locator.update(
                {
                    "table_id": f"table-{table_count}",
                    "table_id_source": "parser order, not printed table number",
                    "cells": cells,
                    "captions": [ref.resolve(document).text for ref in item.captions],
                }
            )
            # Preserve complete tables. Oversized ones are left for review, never row-truncated.
            blocks.append(Block(text, page, section, "table", locator))
        elif text.strip():
            blocks.append(Block(text, page, section, label, locator))
            if section and "abstract" in section.casefold():
                abstract.append(text)
    limitations = [
        "Figure pixels and complex equations are not interpreted; their source locations are retained.",
        "Cross-page and ambiguous table headers require review.",
    ]
    if settings().docling_pipeline == "simple":
        limitations.append("Simple Docling pipeline: layout and table recovery disabled.")
    return ParsedPaper(
        title or path.stem,
        "\n".join(abstract)[:12000],
        blocks,
        {
            "parser": "docling",
            "pipeline": settings().docling_pipeline,
            "limitations": limitations,
            "status": str(result.status),
            "document": document.export_to_dict(),
        },
    )
