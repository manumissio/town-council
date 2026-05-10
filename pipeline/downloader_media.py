import logging
import os

import requests

from pipeline.config import DOWNLOAD_TIMEOUT_SECONDS, FILE_WRITE_CHUNK_SIZE, MAX_FILE_SIZE_BYTES

logger = logging.getLogger(__name__)

DEFAULT_CONTENT_TYPE = "application/pdf"
PDF_CONTENT_MARKER = "pdf"
HTML_CONTENT_MARKER = "html"
DEFAULT_DOCUMENT_EXTENSION = ".pdf"
FALLBACK_OCD_DIRECTORY = "misc"


class Media:
    """
    Handles the downloading of documents (PDFs, HTML) from the web.
    """

    def __init__(self, doc):
        # Use DATA_DIR from environment or default to local data folder.
        self.working_dir = os.getenv("DATA_DIR", "./data")
        self.doc = doc
        # Security: disable trust_env so requests does not use local .netrc credentials.
        self.session = requests.Session()
        self.session.trust_env = False

    def gather(self):
        """
        Download and store one document. Return local path or None.
        """
        self.response = self._get_document(self.doc.url)

        if self.response and not isinstance(self.response, int):
            content_type = self._parse_content_type(self.response.headers)
            return self._store_document(self.response, content_type, self.doc.url_hash)
        return None

    def _parse_content_type(self, headers):
        """
        Normalize response content type for extension detection.
        """
        content_type = headers.get("Content-Type", DEFAULT_CONTENT_TYPE)
        return content_type.split(";")[0]

    def _get_document(self, document_url):
        """
        Download a document with streaming and timeout protection.
        """
        try:
            # Stream response so large files do not load fully into memory.
            response = self.session.get(document_url, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS)

            if response.ok:
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > MAX_FILE_SIZE_BYTES:
                    logger.warning(
                        "download_skip_oversized url=%s content_length=%s max_bytes=%s",
                        document_url,
                        content_length,
                        MAX_FILE_SIZE_BYTES,
                    )
                    return None
                return response
            return response.status_code
        except requests.RequestException as e:
            # Any network failure returns None so caller can skip safely.
            logger.error("download_request_failed url=%s error=%s", document_url, e)
            return None

    def _store_document(self, response, content_type, url_hash):
        """
        Save downloaded bytes to local disk.
        """
        file_path = self._create_fp_from_ocd_id(self.doc.ocd_division_id)

        if PDF_CONTENT_MARKER in content_type:
            ext = DEFAULT_DOCUMENT_EXTENSION
        elif HTML_CONTENT_MARKER in content_type:
            ext = ".html"
        else:
            ext = DEFAULT_DOCUMENT_EXTENSION

        full_path = os.path.join(file_path, f"{url_hash}{ext}")
        abs_path = os.path.abspath(full_path)

        # Write in chunks to keep memory usage low.
        try:
            with open(abs_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=FILE_WRITE_CHUNK_SIZE):
                    f.write(chunk)
            return abs_path
        except OSError as e:
            logger.error("Failed to write file %s: %s", abs_path, e)
            return None

    def _create_fp_from_ocd_id(self, ocd_id_str):
        """
        Build a city-specific data directory from OCD division ID.
        """
        try:
            if not ocd_id_str or "/" not in ocd_id_str:
                raise ValueError("Missing '/' separator")

            parts = ocd_id_str.split("/")
            location_segments = parts[1:]

            segments = []
            for token in location_segments:
                if ":" in token:
                    segments.append(token.split(":")[1])

            if not segments:
                raise ValueError("No valid location segments found")

            safe_path = os.path.join(self.working_dir, *segments)
            os.makedirs(safe_path, exist_ok=True)
            return safe_path

        except (ValueError, OSError) as e:
            # Keep ingestion moving even when location metadata is malformed.
            logger.warning(
                "downloader_ocd_fallback ocd_division_id=%r error=%s fallback_dir=%s",
                ocd_id_str,
                e,
                FALLBACK_OCD_DIRECTORY,
            )
            fallback_path = os.path.join(self.working_dir, FALLBACK_OCD_DIRECTORY)
            os.makedirs(fallback_path, exist_ok=True)
            return fallback_path
