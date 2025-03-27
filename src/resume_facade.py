"""
简历生成外观模块
从libs/resume_and_cover_builder导入ResumeFacade类并重新导出
"""

from src.libs.resume_and_cover_builder.resume_facade import ResumeFacade

# 重新导出ResumeFacade类
__all__ = ['ResumeFacade'] 