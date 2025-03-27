import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import inquirer
import re

from loguru import logger
from src.logging import logger

from src.libs.resume_and_cover_builder.job import Job
from src.libs.resume_and_cover_builder.llm.llm_job_parser import LLMParser
from src.libs.resume_and_cover_builder.config import global_config
from src.libs.resume_and_cover_builder.llm.prompts import COVER_LETTER_GENERATION_PROMPT
from src.style_manager import StyleManager

class CoverLetterFacade:
    """求职信生成门面类"""
    
    def __init__(self, model_type: str = None, model: str = None, api_key: str = None):
        """
        初始化求职信生成门面类
        
        Args:
            model_type: 模型类型，如果不指定则使用全局配置
            model: 模型名称，如果不指定则使用全局配置
            api_key: API密钥，如果不指定则使用全局配置
        """
        self.model_type = model_type or global_config.MODEL_TYPE
        self.model = model or global_config.MODEL
        self.api_key = api_key or global_config.API_KEY
        self.job = None
        self.llm_job_parser = None
        
        logger.info(f"使用语言模型: {self.model_type.upper()} - {self.model}")
    
    def link_to_job(self, job_url: str) -> Dict[str, Any]:
        """从职位链接获取职位信息"""
        try:
            # 初始化LLM解析器
            self.llm_job_parser = LLMParser(
                api_key=global_config.API_KEY,
                model_type=global_config.MODEL_TYPE,
                model=global_config.MODEL
            )
            
            # 获取职位信息
            job_info = self.llm_job_parser.parse_job(job_url)
            logger.info(f"成功获取职位信息: {job_info.get('title', 'Unknown Title')}")
            
            # 更新职位对象
            self.job = Job()
            self.job.role = job_info.get('title', '')
            self.job.company = job_info.get('company', '')
            self.job.description = job_info.get('description', '')
            self.job.location = job_info.get('location', '')
            self.job.link = job_url
            
            return job_info
        except Exception as e:
            logger.error(f"获取职位信息时出错: {str(e)}")
            logger.info("尝试使用模拟数据...")
            
            # 使用模拟数据
            mock_data = self._create_mock_job_data(job_url)
            
            # 更新职位对象
            self.job = Job()
            self.job.role = mock_data.get('title', '')
            self.job.company = mock_data.get('company', '')
            self.job.description = mock_data.get('description', '')
            self.job.location = mock_data.get('location', '')
            self.job.link = job_url
            
            return mock_data
    
    def _create_mock_job_data(self, job_url: str) -> Dict[str, Any]:
        """创建模拟职位数据"""
        # 从URL中提取一些信息
        job_id = re.search(r'view/(\d+)', job_url)
        job_id = job_id.group(1) if job_id else "未知ID"
        
        logger.warning(f"创建模拟数据，职位ID: {job_id}")
        
        # 根据ID生成一些随机数据
        return {
            "title": f"模拟职位 #{job_id[:4] if job_id != '未知ID' else '0000'}",
            "company": "模拟公司",
            "description": """这是一个模拟的职位描述，由于无法访问实际的职位页面而生成。
            
            职位要求:
            - 熟练掌握编程语言（如Python、Java或C++）
            - 具有良好的沟通能力和团队协作精神
            - 有解决复杂问题的能力
            - 熟悉软件开发流程
            
            我们提供:
            - 有竞争力的薪资
            - 灵活的工作时间
            - 职业发展机会
            - 友好的工作环境
            """,
            "location": "远程",
            "recruiter": "模拟招聘人员",
            "url": job_url
        }
    
    def create_cover_letter_pdf_job_tailored(
        self, 
        name: str, 
        email: str, 
        phone: str, 
        company_address: str = "",
        manager_name: str = ""
    ) -> Tuple[bytes, str]:
        """生成针对职位的求职信PDF"""
        try:
            if not self.job:
                raise ValueError("请先使用 link_to_job 方法获取职位信息")
            
            logger.info(f"正在为 {self.job.company} 的 {self.job.role} 职位生成求职信")
            
            # 使用LLM生成求职信内容
            cover_letter_content = self._generate_cover_letter_content(
                name, 
                email, 
                phone, 
                self.job.company, 
                self.job.role, 
                company_address,
                manager_name
            )
            
            # 生成HTML
            html_content = self._generate_html(
                cover_letter_content,
                name,
                email,
                phone,
                self.job.company,
                self.job.role,
                company_address,
                manager_name
            )
            
            # 生成PDF
            pdf_content = self._generate_pdf(html_content)
            
            # 生成文件名
            file_name = f"Cover_Letter_{name.replace(' ', '_')}_{self.job.company.replace(' ', '_')}.pdf"
            
            return pdf_content, file_name
            
        except Exception as e:
            logger.error(f"生成求职信PDF时出错: {str(e)}")
            raise
    
    def _generate_cover_letter_content(
        self,
        name: str,
        email: str,
        phone: str,
        company: str,
        role: str,
        company_address: str = "",
        manager_name: str = ""
    ) -> str:
        """使用LLM生成求职信内容"""
        try:
            logger.info(f"正在为 {company} 的 {role} 职位生成求职信内容")
            
            # 构建附加信息
            additional_info = ""
            if manager_name:
                additional_info += f"招聘经理: {manager_name}\n"
            if company_address:
                additional_info += f"公司地址: {company_address}\n"
            
            # 使用提示词模板
            prompt = COVER_LETTER_GENERATION_PROMPT.format(
                name=name,
                email=email,
                phone=phone,
                company=company,
                role=role,
                job_description=self.job.description,
                additional_info=additional_info
            )
            
            # 使用LLM生成内容
            logger.debug(f"使用提示词: {prompt[:200]}...")  # 仅记录前200个字符
            response = self.llm_job_parser.llm.predict(prompt)
            
            logger.info("求职信内容生成成功")
            return response
            
        except Exception as e:
            logger.error(f"生成求职信内容时出错: {str(e)}")
            raise
    
    def _generate_html(
        self,
        content: str,
        name: str,
        email: str,
        phone: str,
        company: str,
        role: str,
        company_address: str = "",
        manager_name: str = ""
    ) -> str:
        """生成求职信HTML"""
        try:
            # 创建样式管理器
            style_manager = StyleManager()
            
            # 选择样式
            style_choices = style_manager.get_available_styles()
            style_options = [
                f"{style_name} (style author -> {style_author})" 
                for style_name, style_author in style_choices
            ]
            
            questions = [
                inquirer.List(
                    "style", 
                    message="选择求职信样式:",
                    choices=style_options
                )
            ]
            
            answers = inquirer.prompt(questions)
            selected_style = answers["style"].split(" (")[0]
            style_manager.set_style(selected_style)
            
            logger.info(f"已选择样式: {selected_style}")
            
            # 获取日期
            from datetime import datetime
            current_date = datetime.now().strftime("%Y年%m月%d日")
            
            # 替换内容中的换行符为HTML换行
            formatted_content = content.replace("\n", "<br>")
            
            # 构建HTML
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>求职信 - {name} - {role} at {company}</title>
                <style>
                {style_manager.get_css()}
                </style>
            </head>
            <body>
                <div class="cover-letter">
                    <div class="header">
                        <div class="personal-info">
                            <h1>{name}</h1>
                            <p>{email} | {phone}</p>
                        </div>
                        <div class="date">
                            {current_date}
                        </div>
                    </div>
                    
                    <div class="recipient">
            """
            
            if manager_name:
                html += f"<p>{manager_name}</p>\n"
            
            html += f"""
                        <p>{company}</p>
            """
            
            if company_address:
                html += f"<p>{company_address}</p>\n"
            
            html += f"""
                    </div>
                    
                    <div class="content">
                        {formatted_content}
                    </div>
                    
                    <div class="signature">
                        <p>此致</p>
                        <p>{name}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return html
            
        except Exception as e:
            logger.error(f"生成求职信HTML时出错: {str(e)}")
            raise
    
    def _generate_pdf(self, html_content: str) -> bytes:
        """生成PDF"""
        try:
            from src.utils.chrome_utils import HTML_to_PDF, browser_manager
            
            # 如果浏览器未初始化，则初始化它
            if not browser_manager.is_initialized:
                logger.info("浏览器未初始化，正在初始化...")
                browser_manager.initialize_browser()
            
            # 获取浏览器驱动
            driver = browser_manager.driver
            
            # 生成PDF
            pdf_data = HTML_to_PDF(html_content, driver)
            
            return pdf_data
            
        except Exception as e:
            logger.error(f"生成PDF时出错: {str(e)}")
            # 尝试不提供driver参数
            try:
                logger.info("尝试使用默认浏览器生成PDF...")
                from src.utils.chrome_utils import HTML_to_PDF
                return HTML_to_PDF(html_content)
            except Exception as inner_e:
                logger.error(f"使用默认浏览器生成PDF失败: {str(inner_e)}")
                raise 