import os
import subprocess
import logging
from typing import Dict, List, Any
from config import LIBREOFFICE_PATH, DOCUMENTS_DIR

logger = logging.getLogger(__name__)


def convert_to_pdf(file_path: str) -> str:
    """Convert a document to PDF using LibreOffice. Returns path to the PDF."""
    if file_path.lower().endswith('.pdf'):
        return file_path

    output_dir = os.path.dirname(file_path)
    try:
        result = subprocess.run(
            [LIBREOFFICE_PATH, "--headless", "--convert-to", "pdf", "--outdir", output_dir, file_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            logger.error(f"LibreOffice conversion failed: {result.stderr}")
            raise Exception(f"Document conversion failed: {result.stderr}")

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        pdf_path = os.path.join(output_dir, f"{base_name}.pdf")

        if not os.path.exists(pdf_path):
            raise Exception("PDF file was not created after conversion")

        return pdf_path
    except subprocess.TimeoutExpired:
        raise Exception("Document conversion timed out")


def extract_content(pdf_path: str) -> Dict[str, Any]:
    """Extract text and tables from a PDF using Docling with OCR support."""
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True

        converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        result = converter.convert(pdf_path)
        doc = result.document

        # Extract full text preserving layout
        text_content = doc.export_to_markdown()

        # Extract tables as DataFrames
        tables = []
        if hasattr(doc, 'tables'):
            for item in doc.tables:
                try:
                    df = item.export_to_dataframe(doc)
                    if df is not None and not df.empty:
                        tables.append(df)
                except Exception as e:
                    logger.warning(f"Failed to extract table: {e}")
                    continue

        return {
            "text_content": text_content,
            "tables": tables
        }

    except ImportError:
        logger.warning("Docling not available, falling back to basic text extraction")
        return _fallback_extract(pdf_path)


def _fallback_extract(pdf_path: str) -> Dict[str, Any]:
    """Fallback text extraction when Docling is not available."""
    try:
        import subprocess
        result = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            capture_output=True, text=True, timeout=60
        )
        return {
            "text_content": result.stdout if result.returncode == 0 else "",
            "tables": []
        }
    except Exception:
        return {"text_content": "", "tables": []}
