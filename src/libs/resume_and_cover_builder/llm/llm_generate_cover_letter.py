"""
Create a base class that generates a cover letter based on a resume and additional data.
"""
import os
from loguru import logger
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from src.libs.resume_and_cover_builder.utils import LoggerChatModel
from src.libs.resume_and_cover_builder.config import global_config
from pathlib import Path
from dotenv import load_dotenv
import openai

# Load environment variables from .env file
load_dotenv()

log_folder = 'log/cover_letter/gpt_cover_letter'
if not os.path.exists(log_folder):
    os.makedirs(log_folder)
log_path = Path(log_folder).resolve()
logger.add(log_path / "gpt_cover_letter.log", rotation="1 day", compression="zip", retention="7 days", level="DEBUG")

class LLMCoverLetter:
    """Base class for generating cover letters using LLMs"""
    
    def __init__(self, openai_api_key=None, strings=None):
        """
        Initialize the LLMCoverLetter class.
        Setup LLM, if Ollama server is down or not available, use OpenAI.
        
        Args:
            openai_api_key (str, optional): OpenAI API key. Defaults to None (use from config).
            strings (module, optional): Strings module with templates. Defaults to None.
        """
        self.strings = strings
        self.job_description = None
        self.resume = None
        
        # 获取API密钥（优先使用传入的，否则从配置中获取）
        if openai_api_key is None:
            if global_config.MODEL_TYPE == "openai":
                openai_api_key = global_config.OPENAI_API_KEY
            elif global_config.MODEL_TYPE == "gemini":
                openai_api_key = global_config.GOOGLE_API_KEY
            else:
                openai_api_key = global_config.API_KEY
        
        # 初始化LLM，确保正确选择模型类型
        model_type = global_config.MODEL_TYPE.lower()
        logger.info(f"初始化LLM，使用模型类型: {model_type}，模型: {global_config.MODEL}")
        
        # 获取代理设置
        proxy_enabled = global_config.PROXY_ENABLED
        proxy_http = global_config.PROXY_HTTP
        proxy_https = global_config.PROXY_HTTPS
        
        if proxy_enabled:
            logger.info(f"检测到代理设置: HTTP={proxy_http}, HTTPS={proxy_https}")
            # 设置环境变量，以便requests使用代理
            if proxy_http:
                os.environ['HTTP_PROXY'] = proxy_http
            if proxy_https:
                os.environ['HTTPS_PROXY'] = proxy_https

        if model_type == "ollama":
            try:
                logger.info(f"使用Ollama模型: {global_config.MODEL}")
                # 使用Ollama
                self.llm = ChatOllama(
                    model=global_config.MODEL,
                    base_url=global_config.OLLAMA_BASE_URL,
                    temperature=global_config.TEMPERATURE,
                    top_p=global_config.OLLAMA_TOP_P,
                    top_k=global_config.OLLAMA_TOP_K
                )
                return
            except Exception as e:
                logger.error(f"无法初始化Ollama模型: {str(e)}")
                logger.warning("将回退到OpenAI模型")
                model_type = "openai"
                
        elif model_type == "gemini":
            logger.info(f"使用Gemini模型: {global_config.MODEL}")
            # 使用Gemini
            try:
                # 导入并初始化Gemini
                from langchain_google_genai import ChatGoogleGenerativeAI
                
                # 获取Google API密钥
                api_key = global_config.GOOGLE_API_KEY
                if not api_key:
                    logger.error("Google API密钥未设置，将回退到OpenAI")
                    model_type = "openai"
                else:
                    # 配置HTTP选项，以便使用代理
                    http_options = {}
                    if proxy_enabled and (proxy_http or proxy_https):
                        http_options["proxy"] = {
                            "http": proxy_http,
                            "https": proxy_https,
                        }
                        logger.info("已为Gemini API配置代理设置")
                    
                    # 配置SSL选项，解决握手失败问题
                    # Google Gemini有时会出现SSL握手失败: [ERROR:ssl_client_socket_impl.cc]
                    import ssl
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    ssl_context.options |= ssl.OP_NO_SSLv2
                    ssl_context.options |= ssl.OP_NO_SSLv3
                    ssl_context.options |= ssl.OP_NO_TLSv1
                    ssl_context.options |= ssl.OP_NO_TLSv1_1
                    http_options["ssl_context"] = ssl_context
                    logger.info("已为Gemini API配置SSL安全选项，解决握手失败问题")
                    
                    # 创建Gemini模型
                    self.llm = ChatGoogleGenerativeAI(
                        model=global_config.MODEL,
                        google_api_key=api_key,
                        temperature=global_config.TEMPERATURE,
                        convert_system_message_to_human=True,
                        http_options=http_options
                    )
                    logger.info("Gemini模型初始化成功")
                    
                    # 测试连接
                    if proxy_enabled:
                        try:
                            import requests
                            test_url = "https://generativelanguage.googleapis.com/v1beta/models"
                            response = requests.get(
                                f"{test_url}?key={api_key}",
                                timeout=5,
                                proxies={
                                    "http": proxy_http,
                                    "https": proxy_https
                                } if proxy_enabled else None
                            )
                            if response.status_code == 200:
                                logger.info("Gemini API连接测试成功")
                            else:
                                logger.warning(f"Gemini API连接测试失败: 状态码 {response.status_code}")
                        except Exception as e:
                            logger.warning(f"Gemini API连接测试失败: {str(e)}")
                    
                    # 如果成功初始化了Gemini，直接返回
                    return
            except ImportError:
                logger.error("未找到Gemini库，请安装: pip install langchain-google-genai google-generativeai")
                # 回退到OpenAI
                logger.warning("回退到OpenAI模型")
                model_type = "openai"
            except Exception as e:
                logger.error(f"初始化Gemini模型时出错: {str(e)}")
                logger.warning("将回退到OpenAI模型")
                model_type = "openai"
        
        # 使用OpenAI（作为最后的回退选项）
        try:
            from langchain_openai import ChatOpenAI
            api_key = openai_api_key
            if not api_key or api_key == "sk-ollama-local-model-no-api-key-required":
                api_key = os.environ.get("OPENAI_API_KEY", "")
            
            if not api_key:
                logger.error("OpenAI API密钥未设置，无法初始化LLM")
                raise ValueError("未设置OpenAI API密钥")
                
            logger.info("初始化OpenAI模型")
            self.llm = ChatOpenAI(
                model=global_config.MODEL if model_type == "openai" else "gpt-3.5-turbo",
                openai_api_key=api_key,
                temperature=global_config.TEMPERATURE
            )
        except Exception as e:
            logger.error(f"无法初始化OpenAI模型: {str(e)}")
            raise
        
        # 使用自定义的LLM实例
        self.llm_cheap = LoggerChatModel(llm=self.llm)
    
    def set_resume(self, resume_obj) -> None:
        """
        设置用于生成求职信的简历
        
        Args:
            resume_obj: 可以是简历对象或简历文本
        """
        # 检查输入类型
        if hasattr(resume_obj, '__str__'):
            # 如果是Resume对象，转换为字符串
            try:
                resume_text = str(resume_obj)
                self.resume = resume_text
                logger.debug(f"简历对象已转换为文本并设置")
            except Exception as e:
                logger.error(f"简历对象转换为文本失败: {str(e)}")
                self.resume = "简历数据无法处理"
        elif isinstance(resume_obj, str):
            # 如果已经是字符串
            self.resume = resume_obj
            logger.debug(f"简历文本已设置，长度: {len(resume_obj)} 字符")
        else:
            # 其他情况
            logger.warning(f"未知的简历类型: {type(resume_obj)}，尝试转换为字符串")
            try:
                self.resume = str(resume_obj)
            except:
                self.resume = "未提供简历信息"
                logger.error("简历转换失败，使用默认文本")
    
    @staticmethod
    def _preprocess_template_string(template):
        """
        Preprocess the template string to ensure it works correctly with LLM
        
        Args:
            template (str): The template string to preprocess
            
        Returns:
            str: The preprocessed template string
        """
        return template
    
    def create_messages(self, resume: str, job_description: str) -> list:
        """创建发送给LLM的消息列表"""
        logger.debug("创建消息列表...")
        
        # 使用职位描述的模板
        if hasattr(self.strings, 'prompt_cover_letter_job_description'):
            prompt_template = self._preprocess_template_string(self.strings.prompt_cover_letter_job_description)
            logger.debug("使用带职位描述的求职信模板")
        else:
            # 使用默认模板
            default_template = """
            生成一封针对以下信息的专业求职信。使用清晰的段落和适当的格式。
            
            简历信息：
            {resume}
            
            职位描述：
            {job_description}
            
            请确保包含一个正式的问候语、一个介绍段落、2-3个描述为什么应聘者是该职位理想人选的段落、一个总结段落和恰当的结束语。
            """
            prompt_template = self._preprocess_template_string(default_template)
            logger.debug("使用默认求职信模板")
        
        system_prompt = """你是一位专业的求职信写作助手。你的任务是为用户创建一封专业、有吸引力且针对性强的求职信。
        求职信应该突出候选人的技能、经验如何与职位要求匹配，并表达出候选人对该职位的热情。
        使用正式但不生硬的语言，保持简洁、专业。
        如果你想分享思考过程，请使用<think>...</think>标签包裹，这部分不会显示给用户。
        """
        
        # 准备所有变量
        format_vars = {
            'resume': resume,
            'job_description': job_description,
            'company': "未提供公司信息",  # 默认值，防止模板中需要但未提供
            'job_title': "未提供职位信息"  # 默认值，防止模板中需要但未提供
        }
        
        # 使用字符串格式化替换变量
        try:
            user_prompt = prompt_template.format(**format_vars)
            logger.debug("成功格式化提示模板")
        except KeyError as e:
            logger.error(f"模板变量错误: {str(e)}")
            # 使用简单格式化尝试修复
            user_prompt = f"""
            生成一封专业求职信。
            
            简历: {resume}
            
            职位描述: {job_description}
            
            公司: {format_vars.get('company', '未提供')}
            职位: {format_vars.get('job_title', '未提供')}
            """
            logger.debug("使用备用简单模板")
        except Exception as e:
            logger.error(f"格式化模板时出错: {str(e)}")
            # 最后的备用方案
            user_prompt = f"根据简历和职位描述生成一封求职信。简历:\n{resume}\n\n职位描述:\n{job_description}"
            logger.debug("使用最简单的备用模板")
        
        # 创建消息列表 - 使用langchain消息对象而不是字典
        model_type = global_config.MODEL_TYPE.lower()
        
        if model_type == "gemini":
            # Gemini API需要特殊处理
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            logger.debug("创建Gemini兼容的消息格式")
        else:
            # 对于其他API，使用字典格式
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            logger.debug("创建标准字典消息格式")
        
        return messages

    def call_api(self, messages: list):
        """
        调用LLM API生成回复
        
        Args:
            messages (list): 消息列表
            
        Returns:
            str: API返回的文本
        """
        logger.debug(f"调用API生成回复...")
        model_type = global_config.MODEL_TYPE.lower()
        logger.debug(f"使用模型类型: {model_type}")
        
        try:
            # 根据不同的模型类型处理消息
            if model_type == "gemini":
                # Gemini需要直接调用llm
                logger.debug("直接调用Gemini模型")
                response = self.llm.invoke(messages)
                if hasattr(response, "content"):
                    text_response = response.content
                else:
                    text_response = str(response)
                logger.debug(f"Gemini响应: {len(text_response)} 字符")
                return text_response
            else:
                # 创建提示模板
                prompt = ChatPromptTemplate.from_messages(messages)
                
                # 创建输出解析器
                output_parser = StrOutputParser()
                
                # 构建链
                chain = prompt | self.llm_cheap | output_parser
                
                # 执行链
                logger.debug("执行LLM链...")
                response = chain.invoke({})
                
                logger.debug(f"API响应长度: {len(response) if response else 0}")
                return response
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"调用API时出错: {error_msg}")
            
            # 创建模拟响应
            error_response = self._create_error_response(error_msg, model_type)
            return error_response
    
    def _create_error_response(self, error_msg, model_type):
        """创建错误响应"""
        # 根据错误信息提供更友好的反馈
        friendly_error = "生成求职信时出错"
        
        if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            if model_type == "ollama":
                friendly_error = "无法连接到Ollama服务。请确保Ollama服务正在运行，或切换到其他API。"
            elif model_type == "gemini":
                friendly_error = "无法连接到Gemini API。请检查您的网络连接和代理设置，或切换到其他API。"
            else:
                friendly_error = "API连接超时。请检查您的网络连接和代理设置，或稍后再试。"
        elif "api key" in error_msg.lower() or "apikey" in error_msg.lower():
            if model_type == "gemini":
                friendly_error = "Google API密钥无效或未设置。请检查您的环境变量中是否正确设置了GOOGLE_API_KEY。"
            else:
                friendly_error = "API密钥无效或未设置。请检查您的环境变量。"
        elif "rate limit" in error_msg.lower() or "ratellimit" in error_msg.lower():
            friendly_error = "API请求频率超出限制。请稍后再试。"
        
        logger.debug(f"生成错误响应: {friendly_error}")
        
        return f"""
        <div class="error-message">
            <p><strong>生成求职信时遇到问题:</strong></p>
            <p>{friendly_error}</p>
            <p>技术细节: {error_msg}</p>
            <p>请检查您的配置或稍后再试。</p>
        </div>
        """

    def generate_cover_letter(self, resume: str = None, job_description: str = None, data: dict = None) -> str:
        """生成求职信
        
        Args:
            resume (str, optional): 简历文本，如果为None则使用已存储的简历
            job_description (str, optional): 职位描述文本，如果为None则使用已存储的职位描述
            data (dict, optional): 包含所有必要数据的字典，用于兼容旧的接口
            
        Returns:
            str: 生成的求职信内容
        """
        logger.debug("开始生成求职信")
        
        # 提取所有需要的数据
        company = None
        job_title = None
        
        # 处理data参数，用于向后兼容
        if data is not None:
            logger.debug("使用data参数中的数据")
            if resume is None and 'resume' in data:
                resume = data['resume']
            if job_description is None and 'job_description' in data:
                job_description = data['job_description']
                
            # 提取公司和职位信息
            if 'company' in data:
                company = data['company']
                logger.debug(f"从data提取公司名称: {company}")
            if 'job_title' in data:
                job_title = data['job_title']
                logger.debug(f"从data提取职位名称: {job_title}")
                
            # 额外的数据可以记录在日志中
            extra_keys = [k for k in data.keys() if k not in ('resume', 'job_description', 'company', 'job_title')]
            if extra_keys:
                logger.debug(f"data中的额外键: {', '.join(extra_keys)}")
        
        if resume is None:
            resume = self.resume
            logger.debug("使用已存储的简历内容")
            
        if job_description is None:
            job_description = self.job_description
            logger.debug("使用已存储的职位描述")
            
        if not resume or not job_description:
            logger.error("缺少生成求职信所需的简历或职位描述")
            raise ValueError("缺少生成求职信所需的简历或职位描述")
            
        try:
            # 准备输入到LLM的消息
            format_vars = {
                'resume': resume,
                'job_description': job_description
            }
            
            # 添加公司和职位信息（如果有）
            if company:
                format_vars['company'] = company
            else:
                format_vars['company'] = "未提供公司信息"
                
            if job_title:
                format_vars['job_title'] = job_title
            else:
                format_vars['job_title'] = "未提供职位信息"
                
            # 创建消息
            messages = self.create_messages(resume, job_description)
            logger.debug(f"已准备消息列表，共{len(messages)}条消息")
            
            # 调用LLM API
            response = self.call_api(messages)
            
            if not response:
                logger.error("调用API返回空结果")
                return None
                
            # 处理不同类型的响应
            if hasattr(response, 'content'):
                # 这是一个AIMessage对象
                logger.debug("处理AIMessage类型的响应")
                output = response.content
            elif hasattr(response, 'choices') and len(response.choices) > 0:
                # 这是一个OpenAI响应
                logger.debug("处理OpenAI类型的响应")
                output = response.choices[0].message.content
            elif isinstance(response, str):
                # 直接返回字符串
                logger.debug("处理字符串类型的响应")
                output = response
            else:
                # 尝试读取未知响应类型
                logger.warning(f"未知的响应类型: {type(response)}")
                try:
                    if hasattr(response, '__dict__'):
                        logger.debug(f"响应对象的属性: {response.__dict__}")
                    
                    # 尝试各种可能的属性
                    if hasattr(response, 'text'):
                        output = response.text
                    elif hasattr(response, 'message'):
                        output = response.message
                    elif hasattr(response, 'response'):
                        output = response.response
                    else:
                        # 最后的尝试：转换为字符串
                        output = str(response)
                        if output.startswith("<") and output.endswith(">"):
                            # 可能是对象的字符串表示，不是有用的内容
                            logger.error("无法从响应中提取文本内容")
                            return None
                except Exception as e:
                    logger.error(f"尝试读取响应时出错: {str(e)}")
                    return None
                
            logger.debug(f"成功获取API返回内容，长度: {len(output)} 字符")
            
            # 提取并记录思考过程
            import re
            
            # 查找并记录所有思考标签中的内容
            thought_pattern = r'<think>(.*?)</think>'
            thoughts = re.findall(thought_pattern, output, re.DOTALL)
            
            if thoughts:
                logger.info(f"发现{len(thoughts)}个思考过程:")
                for i, thought in enumerate(thoughts):
                    logger.info(f"思考 #{i+1}:\n{thought.strip()}")
                
                # 移除所有思考标签及其内容
                output = re.sub(thought_pattern, '', output, flags=re.DOTALL)
                # 处理可能没有正确关闭的思考标签
                output = re.sub(r'<think>.*', '', output, flags=re.DOTALL)
                logger.debug("已移除所有思考标签及其内容")
            
            # 格式化和清理输出
            output = output.strip()
            logger.debug(f"最终输出长度: {len(output)} 字符")
            
            return output
        except Exception as e:
            logger.error(f"生成求职信时出错: {str(e)}")
            raise 