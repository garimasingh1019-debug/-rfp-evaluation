"""Document Tool: extract clean text from an uploaded PDF."""
import io
import re
import subprocess
import tempfile

MIN_USEFUL_CHARS = 200


def _clean(text):
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(pdf_bytes):
    """Return (text, warnings). Never raises for a bad file; reports it as a warning."""
    warnings = []
    text = ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = [(p.extract_text() or "") for p in reader.pages]
        text = "\n\n".join(pages)
    except ImportError:
        # Fallback for machines that have poppler but not pypdf.
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(pdf_bytes)
                f.flush()
                text = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True,
                                      text=True, timeout=60, check=True).stdout
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"PDF could not be read: {exc}")
    except Exception as exc:  # noqa: BLE001 - corrupt/encrypted PDFs
        warnings.append(f"PDF could not be read: {exc}")

    text = _clean(text)
    if not warnings and len(text) < MIN_USEFUL_CHARS:
        warnings.append("Very little text was extracted (scanned image PDF?). "
                        "Scores for this supplier will be unreliable.")
    return text, warnings
