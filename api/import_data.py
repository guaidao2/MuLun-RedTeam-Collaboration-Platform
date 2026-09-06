# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 数据导入 API
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

from api.auth import get_current_user
from api.authz import require_project_member

router = APIRouter(prefix="/api/projects/{project_id}/import", tags=["import"])

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB


def _read_limited(file: UploadFile, max_size: int = MAX_UPLOAD_SIZE) -> bytes:
    """读取文件内容，超限则拒绝（防止内存 DoS）"""
    content = file.file.read(max_size + 1)
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail=f"文件超过大小限制 {max_size // (1024*1024)}MB")
    return content


def _run_import(importer_cls, content: bytes, project_id: int, author: str):
    """执行导入并统一处理解析错误"""
    try:
        importer = importer_cls()
        result = importer.import_from_bytes(content, project_id, author)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception:
        # 不向客户端泄漏内部解析细节
        import logging
        logging.getLogger('import').exception('import failed')
        raise HTTPException(status_code=400, detail="导入解析失败，请检查文件格式")


@router.post("/nmap")
async def import_nmap(project_id: int, file: UploadFile = File(...),
                      user: str = Depends(require_project_member)):
    """导入 Nmap XML"""
    if not file.filename or not file.filename.lower().endswith('.xml'):
        raise HTTPException(status_code=400, detail="需要 .xml 文件")
    content = _read_limited(file)
    from modules.data_importer import NmapImporter
    return _run_import(NmapImporter, content, project_id, user)


@router.post("/nessus")
async def import_nessus(project_id: int, file: UploadFile = File(...),
                        user: str = Depends(require_project_member)):
    """导入 Nessus 报告（.nessus XML 或 .json）"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")
    name = file.filename.lower()
    if not (name.endswith('.nessus') or name.endswith('.xml') or name.endswith('.json')):
        raise HTTPException(status_code=400, detail="需要 .nessus/.xml/.json 文件")
    content = _read_limited(file)
    from modules.data_importer import NessusImporter
    return _run_import(NessusImporter, content, project_id, user)


@router.post("/json")
async def import_json(project_id: int, file: UploadFile = File(...),
                      user: str = Depends(require_project_member)):
    """导入 JSON 数据"""
    if not file.filename or not file.filename.lower().endswith('.json'):
        raise HTTPException(status_code=400, detail="需要 .json 文件")
    content = _read_limited(file)
    from modules.data_importer import JsonImporter
    return _run_import(JsonImporter, content, project_id, user)
