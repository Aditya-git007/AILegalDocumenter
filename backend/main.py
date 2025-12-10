import os
import uuid
import shutil
from typing import Dict, Any

# PyMuPDF is imported as fitz
import fitz
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse

# --- Configuration ---
STORAGE_DIR = "backend/storage"   # Directory to store uploaded files
_upload_store: Dict[str, Dict[str, Any]] = {}  # In-memory store
ALLOWED_EXTENSIONS = {"pdf", "txt"}            # Allowed file types

# Create the storage directory if it doesn't exist
os.makedirs(STORAGE_DIR, exist_ok=True)

app = FastAPI(title="File Upload and Text Extraction Service")

# --- Helper: Text Extraction ---
def extract_text_from_file(file_path: str, file_ext: str) -> str:
    """Extracts text from a file (PDF or TXT)."""
    try:
        if file_ext == "pdf":
            doc = fitz.open(file_path)
            text_content = ""
            for page in doc:
                text_content += page.get_text()
            doc.close()
            return text_content

        elif file_ext == "txt":
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

        else:
            raise ValueError(f"Unsupported file type: .{file_ext}")

    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extract text from file."
        )

# --- Upload Endpoint ---
@app.post("/uploads/", status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(..., description="PDF or TXT file to upload.")):
    """Upload a file, validate, store, and extract text."""
    doc_id = str(uuid.uuid4())

    # 1. Validate file extension
    file_extension = file.filename.split(".")[-1].lower() if file.filename else ""
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Only {', '.join(ALLOWED_EXTENSIONS).upper()} files are allowed."
        )

    # 2. Store uploaded file
    file_path = os.path.join(STORAGE_DIR, f"{doc_id}.{file_extension}")
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save file: {e}"
        )
    finally:
        await file.close()

    # 3. Extract text
    try:
        extracted_text = extract_text_from_file(file_path, file_extension)
        _upload_store[doc_id] = {
            "filename": file.filename,
            "filepath": file_path,
            "extension": file_extension,
            "text": extracted_text,
        }
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    return {"doc_id": doc_id, "message": "File uploaded and text extracted successfully."}

# --- Text Retrieval Endpoint ---
@app.get("/uploads/{doc_id}/text")
def get_extracted_text(doc_id: str):
    """Return extracted text for a given doc_id."""
    if doc_id not in _upload_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document ID not found."
        )
    return JSONResponse(
        content={
            "doc_id": doc_id,
            "filename": _upload_store[doc_id]["filename"],
            "extracted_text": _upload_store[doc_id]["text"]
        }
    )