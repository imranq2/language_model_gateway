import base64
import io
import logging
import os
from typing import Type, Literal, Tuple, Optional, Dict

import boto3
import httpx
import pypdf
from httpx import Response
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PDFExtractionToolInput(BaseModel):
    """Input model for PDF extraction tool."""

    url: Optional[str] = Field(
        default=None, description="Optional url of the pdf to extract text from"
    )
    base64_pdf: Optional[str] = Field(
        default=None,
        description="Optional Base64 encoded PDF content to extract text from",
    )
    start_page: Optional[int] = Field(
        default=None, description="Optional starting page for extraction (0-indexed)"
    )
    end_page: Optional[int] = Field(
        default=None, description="Optional ending page for extraction (0-indexed)"
    )
    use_ocr: Optional[bool] = Field(
        default=False, description="Use AWS Textract for OCR if text extraction fails"
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

    def _run(
        self,
        url: Optional[str] = None,
        base64_pdf: Optional[str] = None,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
        use_ocr: bool = False,
    ) -> Tuple[str, str]:
        """
        Synchronous version of the tool (falls back to async implementation).

        :param base64_pdf: Base64 encoded PDF content
        :param start_page: Optional starting page for extraction
        :param end_page: Optional ending page for extraction
        :return: Tuple of extracted text and artifact description
        """
        raise NotImplementedError("Use async version of this tool")

    async def _arun(
        self,
        url: Optional[str] = None,
        base64_pdf: Optional[str] = None,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
        use_ocr: bool = False,
    ) -> Tuple[str, str]:
        """
        Asynchronous version of the tool with OCR support.

        Args:
            url (Optional[str]): URL of the PDF
            base64_pdf (Optional[str]): Base64 encoded PDF content
            start_page (Optional[int]): Starting page for extraction
            end_page (Optional[int]): Ending page for extraction
            use_ocr (bool): Use AWS Textract for OCR if text extraction fails

        Returns:
            Tuple of extracted text and artifact description
        """
        if url:
            logger.info(f"Extracting text from PDF at URL: {url}")
        else:
            logger.info(f"Extracting text from base64 encoded PDF")

        assert base64_pdf or url, "Either base64_pdf or url must be provided"

        pdf_bytes: bytes
        if not base64_pdf and url:
            # Read PDF from URL
            try:
                async with httpx.AsyncClient() as client:
                    response: Response = await client.get(url)
                    response.raise_for_status()
                    pdf_bytes = response.content
            except Exception as e:
                return (
                    f"Failed to fetch or process the URL {url}: {str(e)}",
                    f"PDFExtractionTool: Failed to fetch or process the URL: <{url}> ",
                )
        else:
            assert base64_pdf is not None, "base64_pdf must be provided"
            pdf_bytes = base64.b64decode(base64_pdf)

        try:
            # Create a bytes buffer to simulate file-like object
            pdf_buffer: io.BytesIO = io.BytesIO(pdf_bytes)

            # First, try PyPDF text extraction
            full_text = self._extract_text_with_pypdf(pdf_buffer, start_page, end_page)

            # If text extraction fails and OCR is enabled, use Textract
            if not full_text.strip() and use_ocr:
                full_text = self._extract_text_with_textract(pdf_bytes)

            # Prepare artifact description
            total_pages = len(pypdf.PdfReader(pdf_buffer).pages)
            start = start_page if start_page is not None else 0
            end = end_page if end_page is not None else total_pages - 1

            artifact = (
                f"PDFExtractionTool: Extracted text from pages {start} to {end} "
                f"(Total pages: {total_pages}, OCR: {'Yes' if use_ocr else 'No'})"
            )

            return full_text.strip(), artifact

        except Exception as e:
            error_msg = f"Failed to extract PDF contents: {str(e)}"
            error_artifact = f"PDFExtractionTool: Failed to process PDF: {str(e)}"

            return error_msg, error_artifact

    @staticmethod
    def _extract_text_with_pypdf(
        pdf_buffer: io.BytesIO,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
    ) -> str:
        """
        Extract text using PyPDF with multiple extraction methods

        Args:
            pdf_buffer (io.BytesIO): PDF file buffer
            start_page (Optional[int]): Starting page
            end_page (Optional[int]): Ending page

        Returns:
            str: Extracted text
        """
        pdf_reader = pypdf.PdfReader(pdf_buffer)
        total_pages = len(pdf_reader.pages)

        # Determine page range
        start = start_page if start_page is not None else 0
        end = end_page if end_page is not None else total_pages - 1

        # Validate page range
        if start < 0 or end >= total_pages or start > end:
            raise ValueError(f"Invalid page range. Total pages: {total_pages}")

        full_text = ""
        for page_num in range(start, end + 1):
            page = pdf_reader.pages[page_num]
            try:
                # Primary method: extract_text()
                page_text = page.extract_text()

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
    def _extract_text_with_textract(pdf_bytes: bytes) -> str:
        """
        Extract text using AWS Textract

        Args:
            pdf_bytes (bytes): PDF content as bytes

        Returns:
            str: Extracted text from PDF
        """
        try:
            # Call Textract API
            region_name: str = os.environ.get("AWS_REGION", "us-east-1")
            textract_client = boto3.client("textract", region_name=region_name)

            response = textract_client.detect_document_text(
                Document={"Bytes": pdf_bytes}
            )

            # Process and extract text
            current_page_text = []

            for item in response.get("Blocks", []):
                if item["BlockType"] == "LINE":
                    current_page_text.append(item["Text"])

            # Join extracted text
            full_text = " ".join(current_page_text)

            return full_text

        except Exception as e:
            logger.error(f"Textract OCR failed: {str(e)}")
            return ""

    @staticmethod
    def extract_metadata(base64_pdf: str) -> Dict[str, str]:
        """
        Extract metadata from the PDF.

        Args:
            base64_pdf (str): Base64 encoded PDF content

        Returns:
            Dict[str, str]: PDF metadata
        """
        try:
            # Decode the base64 string to bytes
            pdf_bytes = base64.b64decode(base64_pdf)

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
