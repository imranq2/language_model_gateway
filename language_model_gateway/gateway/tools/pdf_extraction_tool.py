import base64
import io
import logging
from typing import Type, Literal, Tuple, Optional, Dict

import httpx
import pypdf
from httpx import Response, Headers
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from pypdf import PageObject

from language_model_gateway.gateway.ocr.ocr_extractor import OCRExtractor
from language_model_gateway.gateway.ocr.ocr_extractor_factory import OCRExtractorFactory

logger = logging.getLogger(__name__)


class PDFExtractionToolInput(BaseModel):
    """Input model for PDF extraction tool."""

    url: Optional[str] = Field(
        default=None, description="Optional url of the pdf to extract text from"
    )
    base64Pdf: Optional[str] = Field(
        default=None,
        description="Optional Base64 encoded PDF content to extract text from",
    )
    startPage: Optional[int] = Field(
        default=None, description="Optional starting page for extraction (0-indexed)"
    )
    endPage: Optional[int] = Field(
        default=None, description="Optional ending page for extraction (0-indexed)"
    )
    useOCR: Optional[bool] = Field(
        default=False,
        description="Use OCR (Optical Character Recognition) if text extraction fails",
    )


class PDFExtractionTool(BaseTool):
    """
    LangChain-compatible tool for extracting text from PDFs using PyPDF and AWS Textract.
    """

    name: str = "pdf_text_extractor"
    description: str = (
        "Extracts text from a base64 encoded PDF. "
        "Provide the url to the PDF or the base64 encoded PDF content. "
        "Optionally use AWS Textract for OCR on scanned or image-based PDFs."
    )
    args_schema: Type[BaseModel] = PDFExtractionToolInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    ocr_extractor_factory: OCRExtractorFactory
    ocr_type: Literal["aws"] = "aws"

    def _run(
        self,
        url: Optional[str] = None,
        base64Pdf: Optional[str] = None,
        startPage: Optional[int] = None,
        endPage: Optional[int] = None,
        useOCR: bool = False,
    ) -> Tuple[str, str]:
        """
        Synchronous version of the tool (falls back to async implementation).

        :param base64Pdf: Base64 encoded PDF content
        :param startPage: Optional starting page for extraction
        :param endPage: Optional ending page for extraction
        :return: Tuple of extracted text and artifact description
        """
        raise NotImplementedError("Use async version of this tool")

    async def _arun(
        self,
        url: Optional[str] = None,
        base64Pdf: Optional[str] = None,
        startPage: Optional[int] = None,
        endPage: Optional[int] = None,
        useOCR: bool = False,
    ) -> Tuple[str, str]:
        """
        Asynchronous version of the tool with OCR support.

        Args:
            url (Optional[str]): URL of the PDF
            base64Pdf (Optional[str]): Base64 encoded PDF content
            startPage (Optional[int]): Starting page for extraction
            endPage (Optional[int]): Ending page for extraction
            useOCR (bool): Use AWS Textract for OCR if text extraction fails

        Returns:
            Tuple of extracted text and artifact description
        """
        if url:
            logger.info(f"Extracting text from PDF at URL: {url}")
        else:
            logger.info("Extracting text from base64 encoded PDF")

        assert base64Pdf or url, "Either base64Pdf or url must be provided"

        pdf_bytes: bytes
        if not base64Pdf and url:
            # Read PDF from URL
            headers = Headers(
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "application/pdf, text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    # "Referer": "/".join(url.split("/")[:3]),  # Add base URL as referer
                }
            )
            try:
                async with httpx.AsyncClient(
                    headers=headers, follow_redirects=True
                ) as client:
                    response: Response = await client.get(url)
                    response.raise_for_status()
                    pdf_bytes = response.content
            except Exception as e:
                return (
                    f"Failed to fetch or process the URL {url}: {str(e)}",
                    f"PDFExtractionAgent: Failed to fetch or process the URL: <{url}> ",
                )
        else:
            assert base64Pdf is not None, "base64Pdf must be provided"
            pdf_bytes = base64.b64decode(base64Pdf)

        try:
            # Create a bytes buffer to simulate file-like object
            pdf_buffer: io.BytesIO = io.BytesIO(pdf_bytes)

            # First, try PyPDF text extraction
            full_text = self._extract_text_with_pypdf(pdf_buffer, startPage, endPage)

            # If text extraction fails and OCR is enabled, use Textract
            if not full_text.strip() and useOCR:
                ocr_extractor: OCRExtractor = self.ocr_extractor_factory.get(
                    name=self.ocr_type
                )
                full_text = await ocr_extractor.extract_text_with_textract_async(
                    pdf_bytes
                )

            # Prepare artifact description
            total_pages = len(pypdf.PdfReader(pdf_buffer).pages)
            start = startPage if startPage is not None else 0
            end = endPage if endPage is not None else total_pages - 1

            artifact = (
                f"PDFExtractionAgent: Extracted text from pages {start} to {end} "
                f"(Total pages: {total_pages}, OCR: {'Yes' if useOCR else 'No'})"
            )

            return full_text.strip(), artifact

        except Exception as e:
            error_msg = f"Failed to extract PDF contents: {str(e)}"
            error_artifact = f"PDFExtractionAgent: Failed to process PDF: {str(e)}"

            return error_msg, error_artifact

    @staticmethod
    def extract_single_page_as_pdf(
        pdf_reader: pypdf.PdfReader, page_number: int
    ) -> Optional[bytes]:
        """
        Extract a single page from a PDF as a new PDF byte stream.

        Args:
        pdf_reader: Opened PyPDF PdfReader object
        page_number: Zero-indexed page number to extract

        Returns:
        Bytes of the single-page PDF or None if extraction fails
        """

        try:
            # Validate page number
            if page_number < 0 or page_number >= len(pdf_reader.pages):
                raise ValueError(f"Invalid page number: {page_number}")

            # Create a new PDF writer
            pdf_writer = pypdf.PdfWriter()

            # Add the specific page to the writer
            pdf_writer.add_page(pdf_reader.pages[page_number])

            # Create a bytes buffer to store the PDF
            output_buffer = io.BytesIO()

            # Write the single-page PDF to the buffer
            pdf_writer.write(output_buffer)

            # Reset buffer to beginning
            output_buffer.seek(0)

            # Return the bytes of the single-page PDF
            return output_buffer.getvalue()

        except Exception as e:
            print(f"Page extraction error: {e}")
            return None

    @staticmethod
    def _extract_text_with_pypdf(
        pdf_buffer: io.BytesIO,
        startPage: Optional[int] = None,
        endPage: Optional[int] = None,
    ) -> str:
        """
        Extract text using PyPDF with multiple extraction methods

        Args:
            pdf_buffer (io.BytesIO): PDF file buffer
            startPage (Optional[int]): Starting page
            endPage (Optional[int]): Ending page

        Returns:
            str: Extracted text
        """
        pdf_reader = pypdf.PdfReader(pdf_buffer)
        total_pages = len(pdf_reader.pages)

        # Determine page range
        start = startPage if startPage is not None else 0
        end = endPage if endPage is not None else total_pages - 1

        # Validate page range
        if start < 0 or end >= total_pages or start > end:
            raise ValueError(f"Invalid page range. Total pages: {total_pages}")

        full_text = ""
        for page_num in range(start, end + 1):
            page: PageObject = pdf_reader.pages[page_num]
            try:
                # Primary method: extract_text()
                page_text: str = page.extract_text()

                # Fallback: alternative extraction methods
                if not page_text:
                    page_text = page.extract_text(extraction_mode="layout")
            except Exception as extract_error:
                logger.warning(
                    f"Text extraction failed for page {page_num}: {extract_error}"
                )
                page_text = ""

            full_text += page_text + "\n"

        return full_text

    @staticmethod
    def extract_metadata(base64Pdf: str) -> Dict[str, str]:
        """
        Extract metadata from the PDF.

        Args:
            base64Pdf (str): Base64 encoded PDF content

        Returns:
            Dict[str, str]: PDF metadata
        """
        try:
            # Decode the base64 string to bytes
            pdf_bytes = base64.b64decode(base64Pdf)

            # Create a bytes buffer to simulate file-like object
            pdf_buffer = io.BytesIO(pdf_bytes)

            # Create a PDF reader object
            pdf_reader = pypdf.PdfReader(pdf_buffer)

            # Extract metadata
            metadata: Dict[str, str] = pdf_reader.metadata or {}

            # Convert metadata to dictionary
            return {
                k.replace("/", ""): v
                for k, v in metadata.items()
                if isinstance(k, str) and isinstance(v, str)
            }

        except Exception as e:
            logger.error(f"Failed to extract PDF metadata: {str(e)}")
            return {}
