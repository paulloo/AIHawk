import os
import tempfile
import textwrap
import time
import re  # For email validation
from src.libs.resume_and_cover_builder.utils import LoggerChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger
from pathlib import Path
from langchain_core.prompt_values import StringPromptValue
from langchain_core.runnables import RunnablePassthrough
from langchain_text_splitters import TokenTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings, OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from src.libs.resume_and_cover_builder.config import global_config
from langchain_community.document_loaders import TextLoader
from requests.exceptions import HTTPError as HTTPStatusError  # HTTP error handling
import openai
from typing import Dict, Any, List, Optional, Union
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_models import ChatOpenAI
from langchain_openai import OpenAI
from langchain_community.llms import Ollama
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain_community.document_loaders import SeleniumURLLoader, WebBaseLoader
from src.libs.resume_and_cover_builder.llm.prompts import (
    LINKEDIN_SYSTEM_PROMPT,
    JOB_INFORMATION_EXTRACTION_PROMPT,
    SKILL_MATCHING_PROMPT
)
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.utils.chrome_utils import browser_manager

# Load environment variables from the .env file
load_dotenv()

# Configure the log file
log_folder = 'log/resume/gpt_resume'
if not os.path.exists(log_folder):
    os.makedirs(log_folder)
log_path = Path(log_folder).resolve()
logger.add(log_path / "gpt_resume.log", rotation="1 day", compression="zip", retention="7 days", level="DEBUG")


class LLMParser:
    """LLM解析器类，用于从职位描述中提取信息"""
    
    def __init__(self, api_key: Optional[str] = None, model_type: str = "openai", model: str = "gpt-3.5-turbo"):
        """
        初始化LLMParser
        
        Args:
            api_key: API密钥
            model_type: 模型类型，"openai"、"ollama"或"gemini"
            model: 模型名称
        """
        self.api_key = api_key
        self.model_type = model_type.lower()
        self.model_name = model
        self.body_html = None
        self.vectorstore = None  # 初始化 vectorstore
        self.fragments = []  # 初始化 fragments 列表
        self.embeddings = None  # 初始化 embeddings
        self.llm = None  # 初始化 llm
        
        logger.info(f"初始化LLMParser，模型类型: {self.model_type}，模型: {self.model_name}")
        
        # 根据模型类型初始化不同的模型
        if self.model_type == "ollama":
            logger.info("使用Ollama模型")
            # 使用完整的模型名称
            logger.info(f"Ollama模型名称: {self.model_name}")
            
            self.embeddings = OllamaEmbeddings(
                base_url="http://localhost:11434",
                model=self.model_name
            )
            self.llm = Ollama(
                base_url="http://localhost:11434",
                model=self.model_name,
                temperature=0.7,
                top_p=0.8,
                top_k=40,
                num_ctx=4096,
                num_thread=4,
                repeat_penalty=1.1,
                stop=["<|im_end|>", "</answer>"]
            )
        elif self.model_type == "openai":
            logger.info("使用OpenAI模型")
            if not api_key:
                raise ValueError("使用OpenAI模型需要提供API密钥")
            self.embeddings = OpenAIEmbeddings(openai_api_key=self.api_key)
            self.llm = ChatOpenAI(
                openai_api_key=self.api_key,
                model=self.model_name,
                temperature=0.5
            )
        elif self.model_type == "gemini":
            logger.info("使用Gemini模型")
            try:
                # 尝试导入Gemini相关库
                from langchain_google_genai import ChatGoogleGenerativeAI
                
                if not api_key:
                    raise ValueError("使用Gemini模型需要提供Google API密钥")
                
                # 配置HTTP选项（代理设置）
                http_options = {}
                if global_config.PROXY_ENABLED and (global_config.PROXY_HTTP or global_config.PROXY_HTTPS):
                    http_options["proxy"] = {
                        "http": global_config.PROXY_HTTP,
                        "https": global_config.PROXY_HTTPS,
                    }
                    logger.info("已为Gemini API配置代理设置")
                
                # 使用Gemini模型
                self.llm = ChatGoogleGenerativeAI(
                    model=self.model_name,
                    google_api_key=self.api_key,
                    temperature=0.7,
                    convert_system_message_to_human=True,
                    http_options=http_options
                )
                
                # 暂时使用OpenAI的嵌入模型（可以后续改为使用Gemini的嵌入模型）
                try:
                    from langchain_google_genai import GoogleGenerativeAIEmbeddings
                    self.embeddings = GoogleGenerativeAIEmbeddings(
                        model="models/embedding-001",
                        google_api_key=self.api_key,
                        http_options=http_options
                    )
                    logger.info("使用Google嵌入模型")
                except ImportError:
                    logger.warning("无法导入GoogleGenerativeAIEmbeddings，使用OpenAI嵌入模型")
                    if api_key:
                        self.embeddings = OpenAIEmbeddings(openai_api_key=global_config.OPENAI_API_KEY)
                    else:
                        logger.warning("没有可用的嵌入模型")
                        self.embeddings = None
                
            except ImportError:
                logger.error("未安装Gemini库，请运行: pip install langchain-google-genai google-generativeai")
                raise ValueError("未安装Gemini库，请运行: pip install langchain-google-genai google-generativeai")
        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")
    
    def parse_job(self, job_url: str) -> Dict[str, Any]:
        """
        解析工作详情页面，提取结构化信息
        
        Args:
            job_url: 工作详情页URL
            
        Returns:
            Dict[str, Any]: 包含职位结构化信息的字典
        """
        try:
            logger.info(f"开始解析职位页面: {job_url}")
            
            # 如果启用了测试模式，返回模拟数据
            if hasattr(global_config, 'TEST_MODE') and global_config.TEST_MODE:
                logger.warning("测试模式已启用，返回模拟职位数据")
                return self._create_mock_job_data(job_url)
            
            # 获取页面HTML内容
            html_content = self._get_job_page_content(job_url)
            
            if not html_content:
                logger.warning(f"无法获取职位页面内容: {job_url}，返回模拟数据")
                return self._create_mock_job_data(job_url)
            
            # 解析HTML内容
            job_info = self.parse_job_html(html_content, job_url)
            
            # 确保返回数据包含必要的字段
            if not job_info.get('company'):
                logger.warning("提取的公司名称为空，尝试从URL提取")
                job_info['company'] = self._extract_company_from_url(job_url)
            
            if not job_info.get('title'):
                job_info['title'] = job_info.get('role', '未知职位')
            
            if not job_info.get('title'):
                logger.warning("提取的职位名称为空，使用默认值")
                job_info['title'] = '未知职位'
            
            if not job_info.get('company'):
                logger.warning("提取的公司名称为空，使用默认值")
                job_info['company'] = '未知公司'
            
            # 确保返回数据格式一致，并记录关键信息
            result = {
                'title': job_info.get('title', '未知职位'),
                'company': job_info.get('company', '未知公司'),
                'location': job_info.get('location', '未知地点'),
                'description': job_info.get('description', ''),
                'recruiter': job_info.get('recruiter', ''),
                'url': job_url
            }
            
            logger.info(f"职位解析完成: {result['title']} @ {result['company']}")
            return result
            
        except Exception as e:
            logger.error(f"解析职位页面失败: {str(e)}")
            logger.exception("详细错误信息")
            return self._create_mock_job_data(job_url)
    
    def _get_job_page_content(self, url: str) -> Optional[str]:
        """获取职位页面内容"""
        try:
            logger.info(f"开始获取页面内容: {url}")
            
            # 根据URL判断是否为LinkedIn职位页面
            if "linkedin.com" in url.lower() and ("/jobs/" in url.lower() or "/job/" in url.lower()):
                logger.info("检测到LinkedIn职位页面，使用专用爬取方法")
                content = self._get_linkedin_page_content(url)
            else:
                # 使用标准方法获取页面内容
                content = browser_manager.get_page_content(url)
            
            # 记录获取的内容大小
            if content:
                logger.info(f"成功获取页面内容，大小: {len(content)} 字符")
            else:
                logger.warning("获取到的页面内容为空")
                
            return content
        except Exception as e:
            logger.error(f"获取页面内容失败: {str(e)}")
            return None
            
    def _get_linkedin_page_content(self, url: str) -> Optional[str]:
        """
        获取LinkedIn职位页面的内容
        
        Args:
            url: LinkedIn职位页面URL
            
        Returns:
            Optional[str]: 页面HTML内容
        """
        try:
            logger.info(f"正在获取LinkedIn页面内容: {url}")
            
            # 高级浏览器配置
            browser_options = {
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
                },
                "stealth_mode": True,  # 启用隐身模式避免被检测为自动化工具
                "random_delay": True,  # 使用随机延迟模拟人类行为
                "page_load_strategy": "eager",  # 只等待DOM加载完成，提高速度
                "disable_images": True  # 禁用图片加载以提高速度
            }
            
            # 等待加载的选择器，LinkedIn职位详情页的主要内容区域
            job_selectors = [
                ".jobs-description__content",
                ".job-view-layout",
                ".jobs-unified-top-card",
                "#job-details",
                ".jobs-box--fadein"
            ]
            
            # 尝试多个选择器
            html_content = None
            for selector in job_selectors:
                try:
                    html_content = browser_manager.get_page_content(
                        url=url,
                        wait_for_selector=selector,
                        wait_time=8,  # 增加等待时间
                        scroll=True,  # 滚动加载更多内容
                        scroll_wait=1.5,
                        max_scrolls=3,
                        check_content_size=True,
                        browser_options=browser_options
                    )
                    
                    if html_content and len(html_content) > 5000:
                        logger.info(f"使用选择器 {selector} 成功获取LinkedIn页面内容")
                        break
                    else:
                        logger.warning(f"选择器 {selector} 获取的内容不完整，尝试下一个")
                except Exception as e:
                    logger.warning(f"使用选择器 {selector} 获取LinkedIn内容失败: {str(e)}")
            
            # 如果所有选择器都失败，则尝试不使用选择器直接获取页面
            if not html_content:
                logger.warning("所有选择器都失败，尝试不使用选择器直接获取页面")
                html_content = browser_manager.get_page_content(
                    url=url,
                    wait_time=10,
                    scroll=True,
                    max_scrolls=5,
                    browser_options=browser_options
                )
            
            # 验证内容是否包含职位信息
            if html_content:
                # 检查是否包含关键词
                key_indicators = ["job-details", "职位详情", "工作职责", "要求", "岗位职责", 
                                 "job description", "responsibilities", "requirements"]
                
                html_lower = html_content.lower()
                found_indicators = [ind for ind in key_indicators if ind.lower() in html_lower]
                
                if not found_indicators:
                    logger.warning("获取的页面内容可能不是职位详情页，未找到关键词指标")
                    # 尝试更激进的获取方式
                    browser_options["page_load_strategy"] = "normal"  # 等待完整加载
                    browser_options["stealth_mode"] = True
                    html_content = browser_manager.get_page_content(
                        url=url,
                        wait_time=15,  # 等待更长时间
                        scroll=True,
                        max_scrolls=5,
                        browser_options=browser_options
                    )
            
            return html_content
            
        except Exception as e:
            logger.error(f"获取LinkedIn页面内容失败: {str(e)}")
            return None
            
    def _create_mock_job_data(self, job_url: str) -> Dict[str, Any]:
        """创建模拟职位数据"""
        # 从URL中提取一些信息
        job_id = re.search(r'view/(\d+)', job_url)
        job_id = job_id.group(1) if job_id else "未知ID"
        
        logger.warning(f"创建模拟数据，职位ID: {job_id}")
        
        # 根据ID生成一些随机数据
        return {
            "title": f"软件工程师{job_id[:4]}",
            "company": "模拟公司",
            "description": "这是一个模拟的职位描述，由于无法访问实际的职位页面而生成。",
            "location": "远程",
            "recruiter": "模拟招聘人员",
            "url": job_url
        }

    @staticmethod
    def _preprocess_template_string(template: str) -> str:
        """
        Preprocess the template string by removing leading whitespaces and indentation.
        Args:
            template (str): The template string to preprocess.
        Returns:
            str: The preprocessed template string.
        """
        return textwrap.dedent(template)
    
    def set_body_html(self, html_content):
        """设置HTML内容并提取正文文本"""
        try:
            self.body_html = html_content
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取正文文本
            text_content = soup.get_text(separator='\n', strip=True)
            
            # 使用文本分割器将内容分割成片段
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )
            
            # 分割文本
            self.fragments = text_splitter.split_text(text_content)
            logger.debug(f"文本已分割成 {len(self.fragments)} 个片段")
            
            # 创建向量存储
            try:
                if not hasattr(self, 'embeddings') or self.embeddings is None:
                    logger.warning("没有可用的嵌入模型，跳过向量存储创建")
                    return True
                
                # 确保为Ollama embeddings指定模型名称
                if self.model_type.lower() == "ollama":
                    # 使用完整的模型名称
                    logger.debug(f"使用Ollama embeddings，模型: {self.model_name}")
                    embeddings = OllamaEmbeddings(
                        model=self.model_name,
                        base_url="http://localhost:11434"
                    )
                else:
                    embeddings = self.embeddings
                
                if not self.fragments:
                    logger.warning("没有文本片段可用于创建向量存储")
                    return True
                
                # 创建向量存储
                self.vectorstore = FAISS.from_texts(
                    self.fragments,
                    embedding=embeddings,
                    metadatas=[{"source": f"chunk_{i}"} for i in range(len(self.fragments))]
                )
                logger.debug("Vectorstore created successfully.")
            except Exception as e:
                logger.error(f"Error during vectorstore creation: {str(e)}")
                # 不抛出异常，而是继续处理
                self.vectorstore = None
            
            logger.debug("HTML body processing completed.")
            return True
        except Exception as e:
            logger.error(f"Error processing HTML body: {str(e)}")
            return False

    def _retrieve_context(self, query: str, top_k: int = 3) -> str:
        """
        Retrieves the most relevant text fragments using the retriever.
        Args:
            query (str): The search query.
            top_k (int): Number of fragments to retrieve.
        Returns:
            str: Concatenated text fragments.
        """
        try:
            if not hasattr(self, 'vectorstore') or self.vectorstore is None:
                logger.warning("Vectorstore not available, using all fragments")
                # 如果没有向量存储，返回所有文本片段
                if not hasattr(self, 'fragments') or not self.fragments:
                    logger.warning("No fragments available")
                    return ""
                return "\n\n".join(self.fragments[:top_k])
            
            retriever = self.vectorstore.as_retriever()
            retrieved_docs = retriever.get_relevant_documents(query)[:top_k]
            context = "\n\n".join(doc.page_content for doc in retrieved_docs)
            logger.debug(f"Context retrieved for query '{query}': {context[:200]}...")  # Log the first 200 characters
            return context
        except Exception as e:
            logger.error(f"Error retrieving context: {str(e)}")
            # 发生错误时返回空字符串
            return ""
    
    def _extract_information(self, question: str, retrieval_query: str) -> str:
        """
        Generic method to extract specific information using the retriever and LLM.
        Args:
            question (str): The question to ask the LLM for extraction.
            retrieval_query (str): The query to use for retrieving relevant context.
        Returns:
            str: The extracted information.
        """
        # 尝试从HTML元数据中直接提取信息
        metadata_info = self._extract_from_metadata(retrieval_query)
        if metadata_info:
            logger.info(f"从元数据中直接提取到信息: {metadata_info}")
            return self._clean_extraction_result(metadata_info)
            
        # 如果元数据提取失败，使用向量检索和LLM提取
        context = self._retrieve_context(retrieval_query)
        
        # 创建带有系统提示的聊天模板
        chat_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(LINKEDIN_SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template(
                """
                从以下职位描述中提取信息，回答问题：
                
                职位描述内容:
                {context}
                
                问题: {question}
                
                请只回答问题，不要添加解释或多余的信息。
                如果信息不在上下文中，请回答"未提供"。
                """
            )
        ])
        
        formatted_prompt = chat_prompt.format_messages(
            context=context,
            question=question
        )
        
        try:
            if self.model_type == "ollama":
                # Ollama模型使用不同的提示处理方法
                formatted_text = chat_prompt.format(
                    context=context,
                    question=question
                )
                result = self.llm.predict(formatted_text)
            else:
                # OpenAI模型使用标准的格式化消息
                chain = chat_prompt | self.llm | StrOutputParser()
                result = chain.invoke({"context": context, "question": question})
            
            extracted_info = result.strip()
            logger.debug(f"LLM提取的信息: {extracted_info}")
            return self._clean_extraction_result(extracted_info)
        except Exception as e:  
            logger.error(f"提取信息时出错: {str(e)}")
            return ""
    
    def _extract_from_metadata(self, info_type: str) -> Optional[str]:
        """
        从HTML元数据中提取特定信息
        
        Args:
            info_type: 要提取的信息类型
            
        Returns:
            提取的信息，如果未找到则返回None
        """
        if not hasattr(self, 'body_html') or not self.body_html:
            return None
        
        try:
            soup = BeautifulSoup(self.body_html, 'html.parser')
            
            if info_type.lower() == "company name":
                # 尝试从多个可能的元素中提取公司名称
                selectors = [
                    ".job-details-jobs-unified-top-card__company-name",  # 职位卡片中的公司名称
                    ".jobs-unified-top-card__company-name",              # 旧版职位卡片
                    ".jobs-company__name",                               # 公司名称组件
                    ".company-name",                                     # 通用公司名类
                    ".topcard__org-name-link",                           # 顶部卡片中的公司名链接
                    "a[data-tracking-control-name='public_jobs_topcard-org-name']",  # 公司链接
                    "meta[property='og:site_name']"                      # Open Graph 站点名称
                ]
                
                for selector in selectors:
                    elements = soup.select(selector)
                    if elements and len(elements) > 0:
                        if selector.startswith("meta"):
                            # 元数据标签，获取content属性
                            return elements[0].get("content")
                        else:
                            # 普通HTML元素，获取文本内容
                            text = elements[0].get_text(strip=True)
                            if text:
                                return text
                            
            elif info_type.lower() == "job title":
                # 尝试从多个可能的元素中提取职位名称
                selectors = [
                    ".job-details-jobs-unified-top-card__job-title",     # 职位顶部卡片标题
                    ".t-24.job-details-jobs-unified-top-card__job-title", # 带样式的职位标题
                    ".jobs-unified-top-card__job-title",                 # 旧版职位标题
                    ".topcard__title",                                   # 经典页面顶部卡片标题
                    "h1.job-title",                                      # H1标题的职位
                    "title",                                             # 页面标题
                    "meta[property='og:title']"                          # Open Graph 标题
                ]
                
                # 首先检查页面标题，因为通常它会包含职位名称和公司名称
                page_title = soup.title.string if soup.title else None
                if page_title:
                    # 常见格式: "职位名称 at 公司名称"
                    title_parts = page_title.split(' at ')
                    if len(title_parts) > 1:
                        return title_parts[0].strip()
                    
                    # 常见格式: "职位名称 | 公司名称"
                    title_parts = page_title.split(' | ')
                    if len(title_parts) > 1:
                        return title_parts[0].strip()
                
                # 如果从标题中未能提取，尝试从元素中提取
                for selector in selectors:
                    elements = soup.select(selector)
                    if elements and len(elements) > 0:
                        if selector.startswith("meta"):
                            content = elements[0].get("content")
                            if content:
                                # 如果是OG标题，通常格式是"职位名称 | 公司名称 | LinkedIn"
                                parts = content.split(' | ')
                                if len(parts) > 1:
                                    return parts[0].strip()
                                return content
                        else:
                            # 普通HTML元素，获取文本内容
                            text = elements[0].get_text(strip=True)
                            if text and len(text) < 100:
                                return text
                
                # 尝试从description或其他部分提取
                job_details = soup.select_one("#job-details") or soup.select_one(".jobs-description-content__text")
                if job_details:
                    # 尝试找出职位相关陈述，例如"We are looking for a Software Engineer..."
                    patterns = [
                        r"(?:looking for|hiring|seeking) (?:an?|the) ([A-Za-z\s]+?)(?: to | who |[,\.])",
                        r"(?:开放|招聘|寻找|诚聘)(?:一名|一位|)[（(]?([^，,：:()（）]{2,30})[)）]?(?:岗位|职位)?"
                    ]
                    
                    text = job_details.get_text()
                    for pattern in patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            return match.group(1).strip()
                        
            elif info_type.lower() == "job description":
                # 尝试提取职位描述
                selectors = [
                    "#job-details",                              # 主职位详情ID
                    ".jobs-description-content__text",           # 新版职位描述内容
                    ".jobs-description__content",                # 职位描述内容
                    ".jobs-box__html-content",                   # LinkedIn描述HTML内容
                    ".description-section",                      # 描述部分
                    ".description"                               # 通用描述类
                ]
                
                for selector in selectors:
                    elements = soup.select(selector)
                    if elements and len(elements) > 0:
                        return elements[0].get_text(strip=True)
                        
            elif info_type.lower() == "location":
                # 尝试提取位置信息
                selectors = [
                    ".job-details-jobs-unified-top-card__job-insight span:not(.job-details-jobs-unified-top-card__job-insight-view-model-secondary)",
                    ".jobs-unified-top-card__bullet",            # 职位卡片中的项目符号（通常是位置）
                    ".jobs-unified-top-card__workplace-type",    # 工作地点类型
                    ".topcard__flavor--bullet",                  # 经典页面的项目符号（位置）
                    ".location",                                 # 通用位置类
                    "meta[property='og:location']"               # 位置元数据
                ]
                
                # 首先尝试特定元素
                for selector in selectors:
                    elements = soup.select(selector)
                    if elements and len(elements) > 0:
                        if selector.startswith("meta"):
                            # 元数据标签，获取content属性
                            return elements[0].get("content")
                        else:
                            # 普通HTML元素，获取文本内容
                            text = elements[0].get_text(strip=True)
                            if text:
                                return text
                
                # 尝试查找包含位置关键词的元素
                location_keywords = ['remote', '远程', 'hybrid', '混合', 'onsite', '现场', 'in-office', '办公室']
                for keyword in location_keywords:
                    elements = soup.find_all(string=re.compile(keyword, re.IGNORECASE))
                    if elements:
                        # 查找最短且最可能是位置的文本
                        locations = [el.strip() for el in elements if len(el.strip()) < 50]
                        if locations:
                            return min(locations, key=len)
            
            # 特别处理招聘人员信息
            elif info_type.lower() == "recruiter or hiring manager":
                # 尝试提取招聘人员信息
                recruiter_elements = None
                
                # 查找可能包含招聘人员信息的区域
                about_sections = soup.select(".jobs-company__box, .company-panel, .jobs-details-top-card__company-info")
                if about_sections:
                    for section in about_sections:
                        # 查找招聘人员名称
                        person_elements = section.select(".name, .jobs-poster__name")
                        if person_elements:
                            recruiter_elements = person_elements[0].get_text(strip=True)
                            break
                
                # 如果招聘人员找不到，尝试在整个页面查找关键词
                if not recruiter_elements:
                    patterns = [
                        r"(?:recruiter|hiring manager|contact)(?:\s*:|\s+is|\s+at)\s+([A-Za-z\s\.]+)",
                        r"(?:招聘人员|招聘经理|联系人)(?:\s*:|\s+是|\s+为)?\s+([^\n,，.。]{2,30})"
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, soup.get_text(), re.IGNORECASE)
                        if matches:
                            return matches[0].strip()
                
                return recruiter_elements
            
            # 尝试提取职位要求
            elif info_type.lower() == "job requirements" or info_type.lower() == "requirements":
                # 先查找明确的要求部分
                requirement_headers = soup.find_all(['h2', 'h3', 'h4', 'strong', 'b'], 
                                                   string=re.compile(r'(requirements|qualifications|skills|要求|资格|技能)', 
                                                                    re.IGNORECASE))
                for header in requirement_headers:
                    # 查找头部后面的列表或段落
                    next_element = header.find_next_sibling()
                    if next_element and next_element.name == 'ul':
                        # 如果是列表，提取所有列表项
                        items = [li.get_text(strip=True) for li in next_element.find_all('li')]
                        if items:
                            return "\n".join(f"• {item}" for item in items)
                    elif next_element and next_element.name == 'p':
                        # 如果是段落，直接提取文本
                        return next_element.get_text(strip=True)
                
                # 如果没有找到明确的部分，尝试通过模式识别
                job_details = soup.select_one("#job-details") or soup.select_one(".jobs-description-content__text")
                if job_details:
                    # 查找包含要求或资格关键词的段落
                    text = job_details.get_text()
                    requirement_patterns = [
                        r"(?:Requirements|Qualifications|Skills Required|What You Need|Required Skills|Experience)(?:\s*:|\s*-|\s*–)?\s*((?:.+\n?)+?)(?:\n\n|\Z|Responsibilities|About Us|Benefits|How to Apply)",
                        r"(?:要求|资格要求|技能要求|所需技能|资质要求|经验要求|岗位要求)(?:\s*:|\s*：|\s*-|\s*–)?\s*((?:.+\n?)+?)(?:\n\n|\Z|职责|岗位职责|工作职责|关于我们|公司介绍|福利待遇|如何申请)",
                        # 更通用的模式，尝试捕获位于段落中的要求
                        r"(?:required skills|requirements|qualifications)[\s\S]{0,20}?(?:include|are|:)[\s\S]{0,10}((?:(?:\s*[-•*]\s*|\s*\d+\.\s*|(?:\s*[A-Za-z0-9]+\)\s*))(?:[\w\s,.]+)(?:\n|$))+)",
                        r"(?:技能要求|岗位要求|资格要求)[\s\S]{0,20}?(?:包括|是|：|:)[\s\S]{0,10}((?:(?:\s*[-•*]\s*|\s*\d+\.\s*|(?:\s*[A-Za-z0-9]+\)\s*))(?:[\w\s,.]+)(?:\n|$))+)"
                    ]
                    
                    for pattern in requirement_patterns:
                        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                        if match:
                            requirements = match.group(1).strip()
                            logger.debug(f"提取到职位要求: {requirements[:100]}...")
                            return requirements
            
            # 未找到任何匹配元素
            return None
            
        except Exception as e:
            logger.warning(f"从HTML元数据提取信息时出错: {str(e)}")
            return None
            
    def _clean_extraction_result(self, result: str) -> str:
        """
        清理提取结果，移除不必要的内容
        
        Args:
            result: 待清理的文本
            
        Returns:
            清理后的文本
        """
        if not result:
            return "未提供"
            
        # 移除思考标记
        import re
        cleaned = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL)
        cleaned = re.sub(r'<think>.*', '', cleaned, flags=re.DOTALL)
        
        # 移除换行符和多余空格
        cleaned = cleaned.replace('\n', ' ').strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # 移除常见的回答格式
        common_prefixes = [
            r"^The company(?:'s)? name is ",
            r"^The company is ",
            r"^The job title is ",
            r"^The role is ",
            r"^The position is ",
            r"^The location is ",
            r"^The job description is ",
            r"^公司名称[是为：:]\s*",
            r"^公司[是为：:]\s*",
            r"^职位名称[是为：:]\s*",
            r"^职位[是为：:]\s*",
            r"^地点[是为：:]\s*",
            r"^职位描述[是为：:]\s*"
        ]
        
        for prefix in common_prefixes:
            cleaned = re.sub(prefix, '', cleaned, flags=re.IGNORECASE)
        
        # 如果清理后为空，返回"未提供"
        if not cleaned or cleaned.isspace() or cleaned.lower() in ["none", "unknown", "not found", "not provided", "未找到", "未知", "无"]:
            return "未提供"
            
        return cleaned
    
    def extract_job_description(self) -> str:
        """
        Extracts the company name from the job description.
        Returns:
            str: The extracted job description.
        """
        question = "What is the job description of the company?"
        retrieval_query = "Job description"
        logger.debug("Starting job description extraction.")
        return self._extract_information(question, retrieval_query)
    
    def extract_company_name(self) -> str:
        """
        Extracts the company name from the job description.
        Returns:
            str: The extracted company name.
        """
        question = "What is the company's name?"
        retrieval_query = "Company name"
        logger.debug("Starting company name extraction.")
        
        # 使用加强版的信息提取方法
        result = self._extract_information(question, retrieval_query)
        logger.info(f"提取的公司名称: {result}")
        
        return result
    
    def extract_role(self) -> str:
        """
        Extracts the sought role/title from the job description.
        Returns:
            str: The extracted role/title.
        """
        question = "What is the role or title sought in this job description?"
        retrieval_query = "Job title"
        logger.debug("Starting role/title extraction.")
        
        # 使用加强版的信息提取方法
        result = self._extract_information(question, retrieval_query)
        logger.info(f"提取的职位名称: {result}")
        
        return result
    
    def extract_location(self) -> str:
        """
        Extracts the location from the job description.
        Returns:
            str: The extracted location.
        """
        question = "What is the location mentioned in this job description?"
        retrieval_query = "Location"
        logger.debug("Starting location extraction.")
        return self._extract_information(question, retrieval_query)
    
    def extract_recruiter_email(self) -> str:
        """
        Extracts the recruiter's email from the job description.
        Returns:
            str: The extracted recruiter's email.
        """
        question = "What is the recruiter's email address in this job description?"
        retrieval_query = "Recruiter email"
        logger.debug("Starting recruiter email extraction.")
        email = self._extract_information(question, retrieval_query)
        
        # Validate the extracted email using regex
        email_regex = r'[\w\.-]+@[\w\.-]+\.\w+'
        if re.match(email_regex, email):
            logger.debug("Valid recruiter's email.")
            return email
        else:
            logger.warning("Invalid or not found recruiter's email.")
            return ""
    
    def extract_recruiter_info(self) -> str:
        """
        Extracts the recruiter's information from the job description.
        Returns:
            str: The extracted recruiter information.
        """
        question = "Who is the recruiter or hiring manager for this position? Extract any contact information."
        retrieval_query = "Recruiter or hiring manager"
        logger.debug("Starting recruiter information extraction.")
        return self._extract_information(question, retrieval_query)
    
    def analyze_skill_match(self, candidate_skills: List[str]) -> Dict[str, Any]:
        """
        分析候选人技能与职位要求的匹配度
        
        Args:
            candidate_skills: 候选人的技能列表
            
        Returns:
            包含匹配分析的字典
        """
        try:
            logger.info("开始分析技能匹配度")
            
            # 获取职位描述
            job_description = self.extract_job_description()
            if not job_description:
                logger.warning("无法获取职位描述，无法进行技能匹配分析")
                return {
                    "match_score": 0,
                    "matching_skills": [],
                    "missing_skills": [],
                    "recommendations": "无法分析，职位描述不可用"
                }
            
            # 构建提示词
            prompt = SKILL_MATCHING_PROMPT.format(
                job_description=job_description,
                candidate_skills=", ".join(candidate_skills)
            )
            
            # 使用LLM分析匹配度
            logger.debug(f"使用提示词进行技能匹配分析: {prompt[:200]}...")  # 仅记录前200个字符
            response = self.llm.predict(prompt)
            
            # 解析响应
            result = self._parse_skill_match_response(response)
            
            logger.info(f"技能匹配分析完成，匹配度: {result.get('match_score', '未知')}%")
            return result
            
        except Exception as e:
            logger.error(f"技能匹配分析出错: {str(e)}")
            return {
                "match_score": 0,
                "matching_skills": [],
                "missing_skills": [],
                "recommendations": f"分析出错: {str(e)}"
            }
    
    def _parse_skill_match_response(self, response: str) -> Dict[str, Any]:
        """
        解析技能匹配分析响应
        
        Args:
            response: LLM的响应文本
            
        Returns:
            解析后的结果字典
        """
        try:
            # 提取匹配度分数
            match_score = 0
            match_score_pattern = r'(\d+)%'
            match = re.search(match_score_pattern, response)
            if match:
                match_score = int(match.group(1))
            
            # 简单解析匹配技能和缺失技能
            lines = response.split('\n')
            matching_skills = []
            missing_skills = []
            recommendations = ""
            
            # 解析各部分
            current_section = ""
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 识别部分标题
                if line.startswith('1.') or '关键技能' in line:
                    current_section = "required_skills"
                elif line.startswith('2.') or '匹配技能' in line:
                    current_section = "matching_skills"
                elif line.startswith('3.') or '缺少的技能' in line:
                    current_section = "missing_skills"
                elif line.startswith('4.') or '匹配度评分' in line:
                    current_section = "match_score"
                elif line.startswith('5.') or line.startswith('6.') or '建议' in line:
                    current_section = "recommendations"
                    recommendations += line + "\n"
                elif current_section == "matching_skills" and line.startswith('-'):
                    skill = line.strip('- ').split('（')[0].split('(')[0].strip()
                    matching_skills.append(skill)
                elif current_section == "missing_skills" and line.startswith('-'):
                    skill = line.strip('- ').split('（')[0].split('(')[0].strip()
                    missing_skills.append(skill)
                elif current_section == "recommendations":
                    recommendations += line + "\n"
            
            return {
                "match_score": match_score,
                "matching_skills": matching_skills,
                "missing_skills": missing_skills,
                "recommendations": recommendations.strip()
            }
        except Exception as e:
            logger.error(f"解析技能匹配响应出错: {str(e)}")
            return {
                "match_score": 0,
                "matching_skills": [],
                "missing_skills": [],
                "recommendations": "无法解析匹配结果"
            }
    
    def _extract_linkedin_job_sections(self) -> Dict[str, str]:
        """
        从LinkedIn职位详情HTML中提取结构化的职位部分信息
        
        Returns:
            Dict[str, str]: 包含职位不同部分的字典，如职责、要求等
        """
        if not hasattr(self, 'body_html') or not self.body_html:
            return {}
            
        try:
            sections = {}
            soup = BeautifulSoup(self.body_html, 'html.parser')
            
            # 提取顶部卡片信息
            # 1. 提取职位标题
            job_title_elements = soup.select(".job-details-jobs-unified-top-card__job-title, .t-24.job-details-jobs-unified-top-card__job-title")
            if job_title_elements:
                sections["job_title"] = job_title_elements[0].get_text(strip=True)
                logger.info(f"提取到职位标题: {sections['job_title']}")
            
            # 2. 提取公司名称
            company_elements = soup.select(".job-details-jobs-unified-top-card__company-name")
            if company_elements:
                sections["company_name"] = company_elements[0].get_text(strip=True)
                logger.info(f"提取到公司名称: {sections['company_name']}")
            
            # 3. 提取位置信息
            location_elements = soup.select(".job-details-jobs-unified-top-card__job-insight:first-child")
            if location_elements:
                # 排除带有secondary类的元素(通常是额外信息)
                location_text = ""
                for el in location_elements[0].select("span:not(.job-details-jobs-unified-top-card__job-insight-view-model-secondary)"):
                    location_text += el.get_text(strip=True) + " "
                if location_text:
                    sections["location"] = location_text.strip()
                    logger.info(f"提取到位置信息: {sections['location']}")
            
            # 查找职位详情主区域
            job_details = soup.select_one("#job-details") or soup.select_one(".jobs-description-content__text--stretch") or soup.select_one(".jobs-description__content")
            if not job_details:
                logger.warning("无法找到职位详情主区域")
                return sections
            
            # 尝试提取职位详情结构化内容
            # 1. 首先尝试通过结构识别各部分（寻找小标题）
            sections_mapping = {
                # 职责部分可能的标题关键词
                "responsibilities": [
                    "responsibilities", "role responsibilities", "job responsibilities", 
                    "duties", "what you'll do", "职责", "工作职责", "岗位职责", "你将要做什么"
                ],
                # 要求部分可能的标题关键词
                "requirements": [
                    "requirements", "qualifications", "skills", "experience", "what you need", 
                    "what we're looking for", "required skills", "要求", "资格", "技能", 
                    "经验", "我们在寻找", "必备技能"
                ],
                # 福利部分可能的标题关键词
                "benefits": [
                    "benefits", "perks", "what we offer", "compensation", "salary", 
                    "package", "福利", "薪资", "待遇", "我们提供"
                ],
                # 公司介绍部分可能的标题关键词
                "company_info": [
                    "about us", "company", "who we are", "our team", "团队介绍", 
                    "公司介绍", "关于我们", "我们是谁"
                ]
            }
            
            # 查找所有可能的部分标题元素
            heading_elements = job_details.select("h1, h2, h3, h4, h5, strong, b")
            current_section = None
            section_content = ""
            
            for i, heading in enumerate(heading_elements):
                heading_text = heading.get_text(strip=True).lower()
                
                # 识别这个标题属于哪个部分
                matched_section = None
                for section_key, keywords in sections_mapping.items():
                    if any(keyword in heading_text for keyword in keywords):
                        matched_section = section_key
                        break
                
                # 如果找到了匹配的部分
                if matched_section:
                    # 如果之前正在收集其他部分的内容，保存它
                    if current_section and section_content:
                        sections[current_section] = section_content.strip()
                        section_content = ""
                    
                    # 开始收集新部分
                    current_section = matched_section
                    
                    # 尝试不同方法获取此部分内容
                    # 方法1：找到下一个heading元素前的所有内容
                    if i < len(heading_elements) - 1:
                        next_sibling = heading.find_next_sibling()
                        while next_sibling and next_sibling != heading_elements[i+1]:
                            if hasattr(next_sibling, "get_text"):
                                section_content += next_sibling.get_text(strip=True) + " "
                            next_sibling = next_sibling.next_sibling
                    # 方法2：如果是最后一个标题，获取它之后的所有内容
                    else:
                        next_sibling = heading.find_next_sibling()
                        while next_sibling:
                            if hasattr(next_sibling, "get_text"):
                                section_content += next_sibling.get_text(strip=True) + " "
                            next_sibling = next_sibling.next_sibling
                    
                    # 方法3：查找列表内容
                    ul_element = heading.find_next("ul")
                    if ul_element:
                        list_items = []
                        for li in ul_element.find_all("li"):
                            list_items.append("• " + li.get_text(strip=True))
                        if list_items:
                            section_content = "\n".join(list_items)
            
            # 保存最后一个部分的内容
            if current_section and section_content:
                sections[current_section] = section_content.strip()
            
            # 如果没有成功提取到结构化内容，尝试全文提取
            if not any(k in sections for k in sections_mapping.keys()):
                logger.warning("无法识别结构化内容，尝试全文提取")
                
                # 提取整个职位描述
                job_description = job_details.get_text(strip=True)
                sections["description"] = job_description
                
                # 使用启发式方法尝试识别部分
                patterns = {
                    "responsibilities": [
                        r"(?:职责|工作职责|岗位职责|责任|Responsibilities|Duties|What You['']ll Do)[：:]\s*([\s\S]+?)(?=(?:要求|资格|技能|经验|福利|薪资|待遇|公司介绍|关于我们|Requirements|Qualifications|Skills|Experience|Benefits|About Us)[：:]|\Z)",
                    ],
                    "requirements": [
                        r"(?:要求|资格|技能|经验|Requirements|Qualifications|Skills|Experience)[：:]\s*([\s\S]+?)(?=(?:职责|工作职责|岗位职责|责任|福利|薪资|待遇|公司介绍|关于我们|Responsibilities|Duties|Benefits|About Us)[：:]|\Z)",
                    ],
                    "benefits": [
                        r"(?:福利|薪资|待遇|Benefits|Perks|What We Offer|Compensation)[：:]\s*([\s\S]+?)(?=(?:职责|工作职责|岗位职责|责任|要求|资格|技能|经验|公司介绍|关于我们|Responsibilities|Duties|Requirements|Qualifications|About Us)[：:]|\Z)",
                    ],
                    "company_info": [
                        r"(?:公司介绍|关于我们|About Us|Company|Who We Are)[：:]\s*([\s\S]+?)(?=(?:职责|工作职责|岗位职责|责任|要求|资格|技能|经验|福利|薪资|待遇|Responsibilities|Duties|Requirements|Qualifications|Benefits)[：:]|\Z)",
                    ]
                }
                
                for section_key, regex_patterns in patterns.items():
                    for pattern in regex_patterns:
                        match = re.search(pattern, job_description, re.IGNORECASE)
                        if match and match.group(1).strip():
                            sections[section_key] = match.group(1).strip()
                            break
            
            # 增强提取: 查找职位卡片中的额外信息
            job_cards = soup.select(".job-card-job-posting-card-wrapper")
            if job_cards and "similar_jobs" not in sections:
                similar_jobs = []
                for card in job_cards[:5]:  # 限制为最多5个相似职位
                    job_title_element = card.select_one(".job-card-job-posting-card-wrapper__title")
                    company_element = card.select_one(".job-card-job-posting-card-wrapper__entity-lockup")
                    location_element = card.select_one(".job-card-job-posting-card-wrapper__footer-item")
                    
                    if job_title_element:
                        job_info = {
                            "title": job_title_element.get_text(strip=True),
                            "company": company_element.get_text(strip=True) if company_element else "",
                            "location": location_element.get_text(strip=True) if location_element else ""
                        }
                        similar_jobs.append(job_info)
                
                if similar_jobs:
                    sections["similar_jobs"] = similar_jobs
                    logger.info(f"提取到{len(similar_jobs)}个相似职位")
            
            logger.info(f"从LinkedIn职位详情中提取了{len(sections)}个部分: {list(sections.keys())}")
            return sections
            
        except Exception as e:
            logger.error(f"提取LinkedIn职位部分时出错: {str(e)}")
            return {}
    
    def parse_job_html(self, html_content: str, job_url: str = "") -> Dict[str, Any]:
        """
        解析职位HTML内容
        
        Args:
            html_content: 职位页面HTML内容
            job_url: 职位URL
            
        Returns:
            Dict[str, Any]: 包含职位信息的字典
        """
        logger.info(f"开始解析职位HTML，URL: {job_url}")
        
        # 初始化返回结果
        result = {
            'title': "",
            'company': "",
            'location': "",
            'description': "",
            'requirements': "",
            'responsibilities': "",
            'recruiter': "",
            'date_posted': ""
        }
        
        try:
            # 预处理HTML
            self.set_body_html(html_content)
            
            # 检测页面类型
            if "linkedin.com/jobs" in job_url:
                logger.info("检测到LinkedIn页面")
                
                # 提取LinkedIn职位各部分内容
                sections = self._extract_linkedin_job_sections()
                
                if sections:
                    # 如果成功提取到各部分，则填充结果
                    result['description'] = sections.get('job_description', '')
                    result['requirements'] = sections.get('qualifications', '')
                    result['responsibilities'] = sections.get('responsibilities', '')
                
                # 提取公司名称
                company_name = self.extract_company_name()
                if company_name:
                    result['company'] = company_name
                    logger.info(f"提取的公司名称: {company_name}")
                
                # 提取职位名称
                job_title = self.extract_role()
                if job_title:
                    result['title'] = job_title
                    logger.info(f"提取的职位名称: {job_title}")
                
                # 提取地点
                location = self.extract_location()
                if location:
                    result['location'] = location
                    logger.info(f"提取的地点: {location}")
                
                # 提取职位描述（如果之前未成功提取）
                if not result['description']:
                    job_description = self.extract_job_description()
                    if job_description:
                        result['description'] = job_description
                        # 只记录截断的描述用于日志
                        desc_preview = job_description[:100] + "..." if len(job_description) > 100 else job_description
                        logger.info(f"提取的职位描述(截断): {desc_preview}")
                
                # 提取招聘者信息
                recruiter = self.extract_recruiter_info()
                if recruiter:
                    result['recruiter'] = recruiter
                    logger.info(f"提取的招聘者信息: {recruiter}")
            
            # 添加其他特定网站的解析逻辑...
            elif "caterpillar.com" in job_url:
                # Caterpillar特定解析逻辑
                job_description = self._extract_caterpillar_job_description(html_content)
                if job_description:
                    result['description'] = job_description
                    
                # 提取其他信息...
                company_name = self.extract_company_name() or "Caterpillar"
                result['company'] = company_name
                
                job_title = self.extract_role()
                if job_title:
                    result['title'] = job_title
                
                location = self.extract_location()
                if location:
                    result['location'] = location
            
            # 通用解析逻辑
            else:
                logger.info("使用通用解析逻辑")
                
                # 提取基本信息
                company_name = self.extract_company_name()
                if company_name:
                    result['company'] = company_name
                    
                job_title = self.extract_role()
                if job_title:
                    result['title'] = job_title
                    
                location = self.extract_location()
                if location:
                    result['location'] = location
                    
                job_description = self.extract_job_description()
                if job_description:
                    result['description'] = job_description
                    
                job_requirements = self.extract_job_requirements()
                if job_requirements:
                    result['requirements'] = job_requirements
            
            # 清理结果
            for key in result:
                if isinstance(result[key], str):
                    result[key] = self._clean_extraction_result(result[key])
            
            return result
            
        except Exception as e:
            logger.error(f"解析职位HTML失败: {str(e)}")
            logger.exception("详细错误信息")
            
            # 尝试简单提取关键信息
            try:
                # 基本提取逻辑
                result['company'] = self.extract_company_name() or ""
                result['title'] = self.extract_role() or ""
                result['location'] = self.extract_location() or ""
                result['description'] = self.extract_job_description() or ""
                
                # 清理结果
                for key in result:
                    if isinstance(result[key], str):
                        result[key] = self._clean_extraction_result(result[key])
                        
                return result
            except:
                # 如果完全失败，返回空结果
                logger.error("无法提取任何职位信息")
                return result

    def _extract_company_from_url(self, url: str) -> str:
        """
        从URL中提取公司名称
        
        Args:
            url: 职位页面URL
            
        Returns:
            str: 提取的公司名称
        """
        try:
            # 常见的公司域名模式
            if not url:
                return ""
            
            # 移除http://和https://
            clean_url = url.lower()
            if clean_url.startswith('http'):
                parts = clean_url.split('://', 1)
                if len(parts) > 1:
                    clean_url = parts[1]
            
            # 提取域名部分
            domain_parts = clean_url.split('/', 1)
            domain = domain_parts[0] if domain_parts else ""
            
            # 移除www.前缀
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # 提取公司名称
            company = ""
            
            # 处理不同的域名模式
            if "linkedin.com" in domain:
                # 如果是LinkedIn，尝试从URL路径提取公司
                if 'company/' in clean_url:
                    company_path = clean_url.split('company/', 1)[1]
                    company = company_path.split('/', 1)[0] if '/' in company_path else company_path
                    # 将连字符替换为空格
                    company = company.replace('-', ' ').title()
            elif "indeed.com" in domain:
                # Indeed通常在URL中没有公司名称
                company = "Unknown (Indeed)"
            else:
                # 一般公司网站，取顶级域名
                parts = domain.split('.')
                if len(parts) >= 2:
                    company = parts[-2]  # 取倒数第二个部分，例如example.com中的example
                    
                    # 常见的不代表公司名称的域名
                    common_domains = ['careers', 'jobs', 'career', 'job', 'work', 'apply']
                    if company.lower() in common_domains and len(parts) >= 3:
                        company = parts[-3]  # 取倒数第三个部分
                
                # 格式化公司名称
                company = company.replace('-', ' ').title()
            
            return company or "未知公司"
        except Exception as e:
            logger.error(f"从URL提取公司名称失败: {str(e)}")
            return "未知公司"

    def _extract_caterpillar_job_description(self, html_content: str) -> str:
        """
        专门提取Caterpillar网站的职位描述
        
        Args:
            html_content: 页面HTML内容
            
        Returns:
            str: 提取的职位描述
        """
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Caterpillar特定的职位描述容器
            description = ""
            
            # 尝试多种选择器
            selectors = [
                '.job-description',
                '#job-details',
                '.job-details',
                '.description',
                '[data-automation="job-description"]',
                '.job-content',
                '.jobDetail',
                '.cat-job-description'
            ]
            
            # 尝试所有选择器
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    for element in elements:
                        content = element.get_text(separator='\n').strip()
                        if len(content) > len(description):
                            description = content
                
                        if description:
                            break
            
            # 如果上面的方法失败，尝试查找包含特定关键词的段落
            if not description:
                keywords = ["职位描述", "工作职责", "岗位要求", "job description", "responsibilities", "requirements", "qualifications"]
                
                paragraphs = soup.find_all(['p', 'div', 'li', 'span'])
                relevant_paragraphs = []
                
                for p in paragraphs:
                    text = p.get_text().strip().lower()
                    if text and any(keyword.lower() in text for keyword in keywords):
                        # 找到匹配的段落后，尝试获取其父元素或后续元素
                        parent = p.parent
                        if parent:
                            parent_text = parent.get_text(separator='\n').strip()
                            if len(parent_text) > 100:  # 确保内容够长
                                relevant_paragraphs.append(parent_text)
                        
                        # 或者获取之后的同级元素
                        next_siblings = list(p.next_siblings)
                        if next_siblings:
                            siblings_text = '\n'.join([sib.get_text().strip() for sib in next_siblings if hasattr(sib, 'get_text') and sib.get_text().strip()])
                            if len(siblings_text) > 100:
                                relevant_paragraphs.append(siblings_text)
            
            # 选择最长的相关段落
            if relevant_paragraphs:
                description = max(relevant_paragraphs, key=len)
            
            return description
        except Exception as e:
            logger.error(f"提取Caterpillar职位描述失败: {str(e)}")
            return ""

    def extract_job_requirements(self) -> str:
        """从职位描述中提取岗位要求"""
        logger.info("提取岗位要求")
        
        if not self.body_html:
            logger.warning("HTML内容为空，无法提取岗位要求")
            return ""
            
        # 使用BeautifulSoup清理HTML
        try:
            soup = BeautifulSoup(self.body_html, 'html.parser')
            text = soup.get_text()
            clean_text = ' '.join(text.split())
        except Exception as e:
            logger.error(f"解析HTML时出错: {str(e)}")
            clean_text = self.body_html
            
        # 处理过长的文本
        if len(clean_text) > 4000:
            logger.warning(f"文本过长 ({len(clean_text)} 字符)，将被截断")
            clean_text = clean_text[:4000]
        
        # 构造提示
        prompt = f"""
        请从以下职位描述中提取关键的岗位要求，包括：
        1. 必备技能和经验
        2. 教育背景要求
        3. 软技能要求
        
        以清晰的分点形式列出这些要求，不要添加额外解释。只输出要求列表。
        
        职位描述:
        {clean_text}
        """
        
        max_tokens = 500
        temperature = 0.5
        
        # 根据模型类型进行不同的调用
        try:
            if self.model_type == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": "你是一位专业的职位分析专家，擅长提取和总结职位信息。请提供简洁、准确和有用的回答。"},
                              {"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return response.choices[0].message.content.strip()
            
            elif self.model_type == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system="你是一位专业的职位分析专家，擅长提取和总结职位信息。请提供简洁、准确和有用的回答。",
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()
            
            elif self.model_type == "gemini":
                # 使用langchain接口调用Gemini
                system_prompt = "你是一位专业的职位分析专家，擅长提取和总结职位信息。请提供简洁、准确和有用的回答。"
                user_prompt = prompt
                
                from langchain_core.messages import SystemMessage, HumanMessage
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt)
                ]
                
                try:
                    response = self.llm.invoke(messages)
                    if hasattr(response, "content"):
                        return response.content.strip()
                    else:
                        return str(response).strip()
                except Exception as e:
                    logger.error(f"调用Gemini API时出错: {str(e)}")
                    return "无法提取岗位要求：API调用失败"
            
            elif self.model_type == "ollama":
                # 使用langchain接口调用Ollama
                from langchain_core.messages import SystemMessage, HumanMessage
                messages = [
                    SystemMessage(content="你是一位专业的职位分析专家，擅长提取和总结职位信息。请提供简洁、准确和有用的回答。"),
                    HumanMessage(content=prompt)
                ]
                
                try:
                    response = self.llm.invoke(messages)
                    if hasattr(response, "content"):
                        return response.content.strip()
                    else:
                        return str(response).strip()
                except Exception as e:
                    logger.error(f"调用Ollama API时出错: {str(e)}")
                    return "无法提取岗位要求：API调用失败"
            
            else:
                logger.error(f"不支持的模型类型: {self.model_type}")
                return "不支持的模型类型"
            
        except Exception as e:
            logger.error(f"生成文本时出错: {str(e)}")
            return ""

    def _generate_text(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
        """
        使用LLM生成文本
        
        Args:
            prompt: 提示词
            max_tokens: 最大生成令牌数
            temperature: 温度参数，控制随机性
            
        Returns:
            str: 生成的文本
        """
        try:
            if self.model_type == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": "你是一位专业的职位分析专家，擅长提取和总结职位信息。请提供简洁、准确和有用的回答。"},
                              {"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return response.choices[0].message.content.strip()
            
            elif self.model_type == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system="你是一位专业的职位分析专家，擅长提取和总结职位信息。请提供简洁、准确和有用的回答。",
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()
            
            else:
                logger.error(f"不支持的模型类型: {self.model_type}")
                return ""
            
        except Exception as e:
            logger.error(f"生成文本时出错: {str(e)}")
            return ""

    def _generate_job_summary(self, job_data: Dict[str, str]) -> str:
        """
        生成职位摘要
        
        Args:
            job_data: 包含职位信息的字典
            
        Returns:
            str: 生成的职位摘要
        """
        try:
            # 提取关键信息
            job_title = job_data.get("job_title", "未知职位")
            company_name = job_data.get("company_name", "未知公司")
            location = job_data.get("location", "未知地点")
            job_description = job_data.get("job_description", "")
            
            # 截取职位描述（不要太长）
            description_preview = job_description[:2000] if job_description else ""
            
            # 构建提示词
            prompt = f"""
请根据以下职位信息，生成一份专业、简洁的职位摘要。摘要应不超过150字，并确保包含以下关键信息：
1. 公司名称和职位标题
2. 核心职责（2-3项最重要的）
3. 关键要求或资格（2-3项最重要的）
4. 工作地点

请使用清晰的结构和专业的语言，避免过于冗长的描述。使用第三人称，客观描述职位情况。

职位信息:
职位标题: {job_title}
公司名称: {company_name}
工作地点: {location}
职位描述:
{description_preview}

请直接开始你的摘要，无需添加标题或引言。确保摘要清晰、准确、简洁，并突出职位的关键点。
"""
            
            # 生成摘要
            summary = self._generate_text(prompt, max_tokens=200, temperature=0.2)
            
            # 清理生成的摘要
            summary = summary.strip()
            summary = re.sub(r'\n+', '\n', summary)  # 删除多余换行
            
            # 如果摘要以职位标题开头，可能是重复信息，尝试删除
            if summary.lower().startswith(job_title.lower()) or summary.lower().startswith(company_name.lower()):
                # 尝试提取更精炼的部分
                lines = summary.split('\n')
                if len(lines) > 1:
                    summary = '\n'.join(lines[1:])
            
            # 如果摘要太长，尝试截断并保持完整句子
            if len(summary) > 200:
                sentences = re.split(r'(?<=[.!?])\s+', summary)
                truncated_summary = ""
                for sentence in sentences:
                    if len(truncated_summary) + len(sentence) <= 200:
                        truncated_summary += sentence + " "
                    else:
                        break
                summary = truncated_summary.strip()
            
            return summary
            
        except Exception as e:
            logger.error(f"生成职位摘要时出错: {str(e)}")
            return f"{company_name}招聘{job_title}职位，工作地点在{location}。"
 
