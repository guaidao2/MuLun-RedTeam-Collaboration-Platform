# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 提权分析 API
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from api.auth import get_current_user
from modules.privilege_analyzer import analyze_text

router = APIRouter(prefix="/api/privilege-escalation", tags=["privesc"])


class AnalyzeRequest(BaseModel):
    text: str


@router.post("/analyze")
def analyze_privesc(req: AnalyzeRequest, user: str = Depends(get_current_user)):
    """从枚举文本分析提权向量（只读，输入用户粘贴的枚举输出）"""
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="文本内容不能为空")
    findings = analyze_text(req.text)
    return {"success": True, "data": findings}
