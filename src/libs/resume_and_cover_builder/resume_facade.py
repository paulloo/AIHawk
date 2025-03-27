"""
This module contains the FacadeManager class, which is responsible for managing the interaction between the user and other components of the application.
"""
# app/libs/resume_and_cover_builder/manager_facade.py
import hashlib
import inquirer
from pathlib import Path
from typing import Optional, Dict, Any
import re

from loguru import logger

from src.libs.resume_and_cover_builder.llm.llm_job_parser import LLMParser
from src.job import Job
from src.utils.chrome_utils import HTML_to_PDF
from .config import global_config
from src.style_manager import StyleManager
from src.utils.chrome_utils import browser_manager
from src.logging import logger
from src.resume_schemas.resume import Resume
from src.libs.resume_and_cover_builder.resume_generator import ResumeGenerator
import config as cfg
import os
import time
import random

class ResumeFacade:
    def __init__(
        self,
        api_key: str,
        style_manager: StyleManager,
        resume_generator: ResumeGenerator,
        resume_object: Optional[Resume] = None,
        output_path: Optional[Path] = None,
        debug: bool = False,
    ):
        """
        初始化ResumeFacade
        """
        lib_directory = Path(__file__).resolve().parent
        global_config.STRINGS_MODULE_RESUME_PATH = lib_directory / "resume_prompt/strings_feder-cr.py"
        global_config.STRINGS_MODULE_RESUME_JOB_DESCRIPTION_PATH = lib_directory / "resume_job_description_prompt/strings_feder-cr.py"
        global_config.STRINGS_MODULE_COVER_LETTER_PATH = lib_directory / "cover_letter_prompt/strings_feder-cr.py"
        global_config.STRINGS_MODULE_NAME = "strings_feder_cr"
        global_config.STYLES_DIRECTORY = lib_directory / "resume_style"
        global_config.LOG_OUTPUT_FILE_PATH = output_path
        global_config.API_KEY = api_key

        self.api_key = api_key
        self.style_manager = style_manager
        self.resume_generator = resume_generator
        
        if resume_object:
            self.resume_generator.set_resume_object(resume_object)
            
        self.resume_object = resume_object
        self.output_path = output_path
        self.debug = debug
        self.driver = None
        self.job_info = {}
        self.job_description_full = None
        self.selected_style = None  # Property to store the selected style
        
        # 从配置文件获取LLM配置
        try:
            import config as cfg
            self.llm_model_type = getattr(cfg, 'LLM_MODEL_TYPE', 'openai').lower()
            self.llm_model = getattr(cfg, 'LLM_MODEL', 'gpt-3.5-turbo')
            self.llm_api_url = getattr(cfg, 'LLM_API_URL', None)
            
            logger.info(f"使用语言模型: {self.llm_model_type.upper()} - {self.llm_model}")
        except ImportError:
            logger.warning("无法导入配置文件，使用默认OpenAI配置")
            self.llm_model_type = 'openai'
            self.llm_model = 'gpt-3.5-turbo'
            self.llm_api_url = None
    
    def set_driver(self, driver):
         self.driver = driver

    def prompt_user(self, choices: list[str], message: str) -> str:
        """
        Prompt the user with the given message and choices.
        Args:
            choices (list[str]): The list of choices to present to the user.
            message (str): The message to display to the user.
        Returns:
            str: The choice selected by the user.
        """
        questions = [
            inquirer.List('selection', message=message, choices=choices),
        ]
        return inquirer.prompt(questions)['selection']

    def prompt_for_text(self, message: str) -> str:
        """
        Prompt the user to enter text with the given message.
        Args:
            message (str): The message to display to the user.
        Returns:
            str: The text entered by the user.
        """
        questions = [
            inquirer.Text('text', message=message),
        ]
        return inquirer.prompt(questions)['text']

        
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
            logger.info(f"成功获取职位信息: {job_info.get('title', '未知职位')}")
            
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

    def create_resume_pdf_job_tailored(self) -> tuple[bytes, str]:
        """
        Create a resume PDF using the selected style and the given job description text.
        Args:
            job_url (str): The job URL to generate the hash for.
            job_description_text (str): The job description text to include in the resume.
        Returns:
            tuple: A tuple containing the PDF content as bytes and the unique filename.
        """
        style_path = self.style_manager.get_style_path()
        if style_path is None:
            raise ValueError("You must choose a style before generating the PDF.")

        html_resume = self.resume_generator.create_resume_job_description_text(style_path, self.job.description)

        # Generate a unique name using the job URL hash
        suggested_name = hashlib.md5(self.job.link.encode()).hexdigest()[:10]
        
        # 确保浏览器已初始化
        from src.utils.chrome_utils import HTML_to_PDF, browser_manager
        
        # 如果浏览器未初始化，则初始化它
        if not hasattr(self, 'driver') or self.driver is None:
            if not browser_manager.is_initialized:
                logger.info("浏览器未初始化，正在初始化...")
                browser_manager.initialize_browser()
            self.driver = browser_manager.driver
            
        try:
            result = HTML_to_PDF(html_resume, self.driver)
            return result, suggested_name
        except Exception as e:
            logger.error(f"PDF生成失败: {str(e)}")
            try:
                logger.info("尝试使用默认浏览器生成PDF...")
                result = HTML_to_PDF(html_resume)
                return result, suggested_name
            except Exception as inner_e:
                logger.error(f"使用默认浏览器生成PDF失败: {str(inner_e)}")
                raise
    
    
    def create_resume_pdf(self) -> tuple[bytes, str]:
        """
        创建简历PDF。

        Returns:
            tuple: 包含PDF内容（bytes）和建议的文件名（str）的元组。

        Raises:
            ValueError: 如果未选择样式。
        """
        style_path = self.style_manager.get_style_path()
        if style_path is None:
            raise ValueError("必须先选择样式才能生成PDF。")
        
        html_resume = self.resume_generator.create_resume(style_path)
        
        # 确保浏览器已初始化
        from src.utils.chrome_utils import HTML_to_PDF, browser_manager
        
        # 如果浏览器未初始化，则初始化它
        if not hasattr(self, 'driver') or self.driver is None:
            if not browser_manager.is_initialized:
                logger.info("浏览器未初始化，正在初始化...")
                browser_manager.initialize_browser()
            self.driver = browser_manager.driver
        
        try:
            result = HTML_to_PDF(html_resume, self.driver)
            # 生成唯一文件名
            suggested_name = "resume_base"
            return result, suggested_name
        except Exception as e:
            logger.error(f"PDF生成失败: {str(e)}")
            try:
                logger.info("尝试使用默认浏览器生成PDF...")
                result = HTML_to_PDF(html_resume)
                # 生成唯一文件名
                suggested_name = "resume_base"
                return result, suggested_name
            except Exception as inner_e:
                logger.error(f"使用默认浏览器生成PDF失败: {str(inner_e)}")
                raise

    def create_cover_letter(self) -> tuple[bytes, str]:
        """
        Create a cover letter based on the given job description text and job URL.
        Args:
            job_url (str): The job URL to generate the hash for.
            job_description_text (str): The job description text to include in the cover letter.
        Returns:
            tuple: A tuple containing the PDF content as bytes and the unique filename.
        """
        style_path = self.style_manager.get_style_path()
        if style_path is None:
            logger.error("未选择样式或样式路径不可用")
            raise ValueError("You must choose a style before generating the PDF.")
            
        logger.info(f"使用样式路径: {style_path}")
        
        # 确保样式文件存在
        if not os.path.exists(style_path):
            logger.error(f"样式文件不存在: {style_path}")
            # 尝试查找默认样式
            default_styles = list(self.style_manager.get_styles().items())
            if default_styles:
                logger.warning("使用第一个可用样式作为默认样式")
                default_style_name, (file_name, _) = default_styles[0]
                self.style_manager.set_selected_style(default_style_name)
                style_path = self.style_manager.get_style_path()
                logger.info(f"已选择默认样式: {default_style_name}, 路径: {style_path}")
            else:
                raise FileNotFoundError(f"样式文件不可用")
        
        cover_letter_html = self.resume_generator.create_cover_letter_job_description(style_path, self.job.description)

        # Generate a unique name using the job URL hash
        suggested_name = hashlib.md5(self.job.link.encode()).hexdigest()[:10]

        # 确保浏览器已初始化
        from src.utils.chrome_utils import HTML_to_PDF, browser_manager
        
        # 如果浏览器未初始化，则初始化它
        if not hasattr(self, 'driver') or self.driver is None:
            if not browser_manager.is_initialized:
                logger.info("浏览器未初始化，正在初始化...")
                browser_manager.initialize_browser()
            self.driver = browser_manager.driver
        
        try:
            logger.info("开始将HTML转换为PDF...")
            result = HTML_to_PDF(cover_letter_html, self.driver)
            logger.info(f"PDF生成成功，大小: {len(result)/1024:.2f} KB")
            return result, suggested_name
        except Exception as e:
            logger.error(f"PDF生成失败: {str(e)}")
            try:
                logger.info("尝试使用默认浏览器生成PDF...")
                result = HTML_to_PDF(cover_letter_html)
                return result, suggested_name
            except Exception as inner_e:
                logger.error(f"使用默认浏览器生成PDF失败: {str(inner_e)}")
                raise