"""File upload routes with auto-save, multi-file, PDF/Word, and preview support."""

import os
import glob
import subprocess
import tempfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from config import settings
from middleware.auth_middleware import get_current_user, require_teacher

router = APIRouter()

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.pdf', '.doc', '.docx'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

# PDF/Word → image conversion helper (requires poppler-utils and libreoffice on server)
def _try_convert_to_images(filepath: str, ext: str) -> list[str]:
    """Try to convert PDF/Word to page images. Returns list of image paths or empty."""
    image_paths = []
    if ext == '.pdf':
        # Use pdftoppm (poppler-utils) to convert PDF pages to images
        try:
            base = os.path.splitext(filepath)[0]
            subprocess.run(
                ['pdftoppm', '-jpeg', '-r', '150', filepath, base + '_page'],
                capture_output=True, timeout=30, check=True
            )
            image_paths = sorted(glob.glob(base + '_page-*.jpg'))
        except Exception:
            pass
    elif ext in ('.doc', '.docx'):
        # Use libreoffice to convert to PDF first, then to images
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                subprocess.run(
                    ['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', tmpdir, filepath],
                    capture_output=True, timeout=60, check=True
                )
                pdfs = glob.glob(os.path.join(tmpdir, '*.pdf'))
                if pdfs:
                    base = os.path.splitext(filepath)[0]
                    subprocess.run(
                        ['pdftoppm', '-jpeg', '-r', '150', pdfs[0], base + '_page'],
                        capture_output=True, timeout=30, check=True
                    )
                    image_paths = sorted(glob.glob(base + '_page-*.jpg'))
        except Exception:
            pass
    return image_paths


@router.post("/upload/{task_id}")
async def upload_file(
    task_id: int,
    file: UploadFile = File(...),
    student_id: int = Form(None),
    page_number: int = Form(None),
    is_answer_key: bool = Form(False),
    _current_user=Depends(require_teacher),
):
    """Upload a single file for a task. Supports images, PDF, Word. Auto-saves immediately."""
    # Validate extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}，支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    # Build directory
    prefix = "answer" if is_answer_key else f"student_{student_id or 0}"
    dest_dir = os.path.join(settings.UPLOAD_DIR, f"task_{task_id}", prefix)
    os.makedirs(dest_dir, exist_ok=True)

    # Sanitize filename
    safe_name = os.path.basename(file.filename or "uploaded_file")
    if page_number:
        name_part, ext_part = os.path.splitext(safe_name)
        safe_name = f"page_{page_number}_{name_part}{ext_part}"
    dest_path = os.path.join(dest_dir, safe_name)

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"文件超过50MB限制")

    with open(dest_path, "wb") as f:
        f.write(content)

    # Try to convert PDF/Word to preview images (best-effort, don't fail on conversion error)
    converted_images = []
    if ext not in IMAGE_EXTENSIONS:
        converted_images = _try_convert_to_images(dest_path, ext)

    return {
        "filename": safe_name,
        "filepath": dest_path,
        "size": len(content),
        "task_id": task_id,
        "student_id": student_id,
        "page_number": page_number,
        "is_answer_key": is_answer_key,
        "file_type": ext,
        "converted_pages": len(converted_images),
        "message": "上传成功",
    }


@router.post("/upload/{task_id}/batch")
async def upload_files_batch(
    task_id: int,
    files: list[UploadFile] = File(...),
    student_id: int = Form(None),
    is_answer_key: bool = Form(False),
    _current_user=Depends(require_teacher),
):
    """Upload multiple files at once for a task."""
    results = []
    errors = []
    for file in files:
        try:
            # Reuse single upload logic via internal call
            ext = os.path.splitext(file.filename or "")[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                errors.append({"filename": file.filename, "error": f"不支持的文件类型: {ext}"})
                continue

            prefix = "answer" if is_answer_key else f"student_{student_id or 0}"
            dest_dir = os.path.join(settings.UPLOAD_DIR, f"task_{task_id}", prefix)
            os.makedirs(dest_dir, exist_ok=True)

            safe_name = os.path.basename(file.filename or "uploaded_file")
            dest_path = os.path.join(dest_dir, safe_name)

            content = await file.read()
            if len(content) > MAX_UPLOAD_SIZE:
                errors.append({"filename": file.filename, "error": "超过50MB限制"})
                continue

            with open(dest_path, "wb") as f:
                f.write(content)

            converted_images = []
            if ext not in IMAGE_EXTENSIONS:
                converted_images = _try_convert_to_images(dest_path, ext)

            results.append({
                "filename": safe_name,
                "size": len(content),
                "task_id": task_id,
                "student_id": student_id,
                "file_type": ext,
                "converted_pages": len(converted_images),
            })
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})

    return {
        "uploaded": len(results),
        "errors": len(errors),
        "files": results,
        "error_details": errors,
        "message": f"成功上传 {len(results)} 个文件" + (f"，{len(errors)} 个失败" if errors else ""),
    }


@router.get("/upload/{task_id}/files")
async def list_uploaded_files(
    task_id: int,
    _current_user=Depends(get_current_user),
):
    """List all uploaded files for a task, grouped by answer/student."""
    task_dir = os.path.join(settings.UPLOAD_DIR, f"task_{task_id}")
    if not os.path.exists(task_dir):
        return {"task_id": task_id, "answer_files": [], "student_files": {}}

    result = {"task_id": task_id, "answer_files": [], "student_files": {}}

    for root, dirs, files in os.walk(task_dir):
        rel_dir = os.path.relpath(root, task_dir)
        for fname in files:
            fpath = os.path.join(root, fname)
            fsize = os.path.getsize(fpath)
            entry = {"filename": fname, "size": fsize, "preview_url": f"/api/upload/{task_id}/preview/{rel_dir.replace(os.sep, '/')}/{fname}"}

            if rel_dir.startswith("answer"):
                result["answer_files"].append(entry)
            elif rel_dir.startswith("student_"):
                sid = rel_dir.split("_", 1)[1] if "_" in rel_dir else rel_dir
                if sid not in result["student_files"]:
                    result["student_files"][sid] = []
                result["student_files"][sid].append(entry)

    return result


@router.get("/upload/{task_id}/preview/{file_path:path}")
async def preview_file(
    task_id: int,
    file_path: str,
):
    """Serve an uploaded file as image for preview. No auth required (img tags can't send headers)."""
    # Security: prevent path traversal
    safe_path = os.path.normpath(file_path)
    if safe_path.startswith("..") or os.path.isabs(safe_path):
        raise HTTPException(status_code=400, detail="无效的文件路径")

    full_path = os.path.join(settings.UPLOAD_DIR, f"task_{task_id}", safe_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(full_path, media_type="image/jpeg")
