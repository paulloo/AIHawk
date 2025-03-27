"""
This creates the cover letter (in html, utils will then convert in PDF) matching with job description and plain-text resume
"""
# app/libs/resume_and_cover_builder/llm/llm_generate_cover_letter_from_job.py
import os
import textwrap
from loguru import logger
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from src.libs.resume_and_cover_builder.config import global_config
from src.libs.resume_and_cover_builder.utils import LoggerChatModel
from src.libs.resume_and_cover_builder.llm.llm_generate_cover_letter import LLMCoverLetter
from dotenv import load_dotenv
from pathlib import Path
import re
import yaml
import html
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Configure log file
log_folder = 'log/cover_letter/gpt_cover_letter_job_descr'
if not os.path.exists(log_folder):
    os.makedirs(log_folder)
log_path = Path(log_folder).resolve()
logger.add(log_path / "gpt_cover_letter_job_descr.log", rotation="1 day", compression="zip", retention="7 days", level="DEBUG")

class LLMCoverLetterJobDescription(LLMCoverLetter):
    """求职信生成类 - 包含职位描述"""
    
    def __init__(self, openai_api_key=None, strings=None):
        """
        初始化LLMCoverLetterJobDescription
        
        Args:
            openai_api_key (str, optional): API密钥或Ollama本地模型标识符，默认None
            strings (module, optional): 包含模板字符串的模块，默认None
        """
        # 调用父类的初始化方法
        super().__init__(openai_api_key, strings)
        
        # 初始化必要的属性
        self.company_name = "未知公司"
        self.job_title = "未知职位"
        self.recruiter_name = "招聘经理"  # 添加招聘人员属性
        self.job_description = ""  # 添加职位描述属性
        self.resume = ""  # 添加简历属性
        
        # 确保llm_cheap已初始化（从父类继承）
        if not hasattr(self, 'llm_cheap') and hasattr(self, 'llm'):
            self.llm_cheap = LoggerChatModel(llm=self.llm)
            
        logger.debug("LLMCoverLetterJobDescription初始化完成")
    
    def extract_company_name(self, job_description_text):
        """
        从职位描述中提取公司名称
        
        Args:
            job_description_text (str): 职位描述文本
            
        Returns:
            str: 提取的公司名称
        """
        logger.debug("开始从职位描述中提取公司名称")
        
        # 确保job_description_text是字符串
        if hasattr(job_description_text, 'text'):
            # 如果是ChatPromptValue对象
            logger.debug("检测到ChatPromptValue对象，提取文本内容")
            try:
                job_description_text = job_description_text.text
            except Exception as e:
                logger.error(f"从ChatPromptValue提取文本失败: {str(e)}")
                # 尝试直接转换为字符串
                try:
                    job_description_text = str(job_description_text)
                except:
                    logger.error("ChatPromptValue无法转换为字符串")
                    self.company_name = "未知公司"
                    return "未知公司"
        elif not isinstance(job_description_text, str):
            # 如果不是字符串，尝试转换
            try:
                job_description_text = str(job_description_text)
            except Exception as e:
                logger.error(f"转换职位描述为字符串失败: {str(e)}")
                self.company_name = "未知公司"
                return "未知公司"
        
        # 确保job_description_text可用于len()调用
        if job_description_text is None:
            logger.error("职位描述为None")
            self.company_name = "未知公司"
            return "未知公司"
            
        # 处理可能为空的情况  
        if not job_description_text or len(job_description_text.strip()) == 0:
            logger.warning("职位描述为空")
            self.company_name = "未知公司"
            return "未知公司"
        
        # 清理思考过程标记
        cleaned_text = re.sub(r'<think>.*?</think>', '', job_description_text, flags=re.DOTALL)
        cleaned_text = re.sub(r'<think>.*', '', cleaned_text, flags=re.DOTALL)
        
        # 创建提示模板，专门用于提取公司名称
        prompt = ChatPromptTemplate.from_template("""
        请从以下职位描述中提取公司名称。如果有多个可能的公司名称，请选择最可能是招聘方的公司。
        职位描述：
        {text}
        
        只需返回公司名称，不要添加任何其他文字或解释。如果无法确定公司名称，请返回"未知公司"。
        """)
        
        # 创建链并执行
        try:
            chain = prompt | self.llm_cheap | StrOutputParser()
            company_name = chain.invoke({"text": cleaned_text})
            
            # 清理结果
            company_name = company_name.strip()
            company_name = re.sub(r'<think>.*?</think>', '', company_name, flags=re.DOTALL)
            company_name = re.sub(r'<think>.*', '', company_name, flags=re.DOTALL)
            
            # 如果结果为空，返回默认值
            if not company_name or company_name.strip() == "":
                logger.warning("提取的公司名称为空")
                company_name = "未知公司"
        except Exception as e:
            logger.error(f"提取公司名称失败: {str(e)}")
            company_name = "未知公司"
        
        # 更新对象属性并返回
        self.company_name = company_name
        logger.info(f"提取的公司名称: {company_name}")
        return company_name
    
    def extract_job_title(self, job_description_text):
        """
        从职位描述中提取职位名称
        
        Args:
            job_description_text (str): 职位描述文本
            
        Returns:
            str: 提取的职位名称
        """
        logger.debug("开始从职位描述中提取职位名称")
        
        # 确保job_description_text是字符串
        if hasattr(job_description_text, 'text'):
            # 如果是ChatPromptValue对象
            logger.debug("检测到ChatPromptValue对象，提取文本内容")
            try:
                job_description_text = job_description_text.text
            except Exception as e:
                logger.error(f"从ChatPromptValue提取文本失败: {str(e)}")
                # 尝试直接转换为字符串
                try:
                    job_description_text = str(job_description_text)
                except:
                    logger.error("ChatPromptValue无法转换为字符串")
                    self.job_title = "未知职位"
                    return "未知职位"
        elif not isinstance(job_description_text, str):
            # 如果不是字符串，尝试转换
            try:
                job_description_text = str(job_description_text)
            except Exception as e:
                logger.error(f"转换职位描述为字符串失败: {str(e)}")
                self.job_title = "未知职位"
                return "未知职位"
        
        # 确保job_description_text可用于len()调用
        if job_description_text is None:
            logger.error("职位描述为None")
            self.job_title = "未知职位"
            return "未知职位"
            
        # 处理可能为空的情况  
        if not job_description_text or len(job_description_text.strip()) == 0:
            logger.warning("职位描述为空")
            self.job_title = "未知职位"
            return "未知职位"
        
        # 清理思考过程标记
        cleaned_text = re.sub(r'<think>.*?</think>', '', job_description_text, flags=re.DOTALL)
        cleaned_text = re.sub(r'<think>.*', '', cleaned_text, flags=re.DOTALL)
        
        # 创建提示模板，专门用于提取职位名称
        prompt = ChatPromptTemplate.from_template("""
        请从以下职位描述中提取职位名称/职位标题。
        职位描述：
        {text}
        
        只需返回职位名称，不要添加任何其他文字或解释。如果无法确定职位名称，请返回"未知职位"。
        """)
        
        # 创建链并执行
        try:
            chain = prompt | self.llm_cheap | StrOutputParser()
            job_title = chain.invoke({"text": cleaned_text})
            
            # 清理结果
            job_title = job_title.strip()
            job_title = re.sub(r'<think>.*?</think>', '', job_title, flags=re.DOTALL)
            job_title = re.sub(r'<think>.*', '', job_title, flags=re.DOTALL)
            
            # 如果结果为空，返回默认值
            if not job_title or job_title.strip() == "":
                logger.warning("提取的职位名称为空")
                job_title = "未知职位"
        except Exception as e:
            logger.error(f"提取职位名称失败: {str(e)}")
            job_title = "未知职位"
        
        # 更新对象属性并返回
        self.job_title = job_title
        logger.info(f"提取的职位名称: {job_title}")
        return job_title

    def set_job_description_from_text(self, job_description_text) -> None:
        """
        设置用于生成求职信的职位描述文本
        
        Args:
            job_description_text (str): 要使用的纯文本职位描述
        """
        logger.debug("开始处理职位描述文本")
        
        # 确保job_description_text是字符串
        if hasattr(job_description_text, 'text'):
            # 如果是ChatPromptValue对象
            job_description_text = job_description_text.text
        elif not isinstance(job_description_text, str):
            # 如果不是字符串，尝试转换
            try:
                job_description_text = str(job_description_text)
            except Exception as e:
                logger.error(f"转换职位描述为字符串失败: {str(e)}")
                self.job_description = "未提供职位描述"
                return
        
        # 清理思考过程标记
        cleaned_text = re.sub(r'<think>.*?</think>', '', job_description_text, flags=re.DOTALL)
        cleaned_text = re.sub(r'<think>.*', '', cleaned_text, flags=re.DOTALL)
        
        # 提取公司名称和职位名称
        self.extract_company_name(cleaned_text)
        self.extract_job_title(cleaned_text)
        
        try:
            # 创建摘要提示模板
            prompt = ChatPromptTemplate.from_template(self.strings.summarize_prompt_template)
            logger.debug("已创建摘要提示模板")
            
            # 构建处理链
            chain = prompt | self.llm_cheap | StrOutputParser()
            logger.debug("已创建处理链")
            
            # 生成摘要
            output = chain.invoke({"text": cleaned_text})
            self.job_description = output
            logger.info(f"职位描述摘要生成成功，长度: {len(output)} 字符")
        except Exception as e:
            logger.error(f"生成职位描述摘要失败: {str(e)}")
            # 如果摘要生成失败，使用原始文本的前500个字符作为备选
            self.job_description = cleaned_text[:500] + "..."
            logger.info(f"使用截断的原始文本作为职位描述，长度: {len(self.job_description)} 字符")

    def generate_cover_letter(self) -> str:
        """
        基于简历和职位描述生成完整的求职信
        
        Returns:
            str: 生成的求职信HTML
        """
        try:
            # 检查必要的属性是否已初始化
            if not hasattr(self, 'job_description') or not self.job_description:
                logger.error("职位描述未设置")
                raise ValueError("职位描述未设置")
            
            if not hasattr(self, 'company_name') or not self.company_name:
                logger.error("公司名称未设置")
                raise ValueError("公司名称未设置")
            
            if not hasattr(self, 'job_title') or not self.job_title:
                logger.error("职位名称未设置")
                raise ValueError("职位名称未设置")
            
            if not hasattr(self, 'recruiter_name'):
                self.recruiter_name = "招聘经理"
                logger.warning("招聘人员信息未设置，使用默认值")
            
            if not hasattr(self, 'resume'):
                self.resume = ""
                logger.warning("简历信息未设置，使用空字符串")
            
            # 清理职位描述中的思考标记
            job_description = re.sub(r'<think>.*?</think>', '', self.job_description, flags=re.DOTALL)
            job_description = re.sub(r'<think>.*', '', job_description, flags=re.DOTALL)
            
            # 使用 strings_feder-cr.py 中定义的提示模板
            if hasattr(self.strings, 'cover_letter_template'):
                prompt_template = self.strings.cover_letter_template
                logger.debug("使用自定义求职信提示模板")
            else:
                # 创建默认提示模板
                prompt_template = """
                你是一位专业的求职信写作专家。请根据提供的职位描述和简历信息，生成一封专业、有说服力的求职信。
                求职信应该：
                1. 突出候选人的相关技能和经验
                2. 展示对公司和职位的了解
                3. 表达对职位的热情
                4. 使用专业、正式的语气
                5. 保持简洁明了
                6. 避免使用过于花哨或夸张的语言
                7. 确保内容真实可信
                8. 突出与职位要求的相关性
                9. 使用具体的例子和数据支持论点
                10. 结尾要表达对面试机会的期待
                
                ## 详细信息:
                - **职位描述:**
                ```
                {job_description}
                ```
                - **我的简历:**
                ```
                {resume}
                ```
                
                请生成一封专业的求职信，使用<p>标签包装段落。不要添加问候语和签名部分，这些将会单独添加。
                """
                logger.debug("使用默认求职信提示模板")
            
            # 创建提示
            prompt = ChatPromptTemplate.from_template(prompt_template)
            
            # 生成求职信
            chain = prompt | self.llm_cheap | StrOutputParser()
            cover_letter_content = chain.invoke({
                "job_title": self.job_title,
                "company_name": self.company_name,
                "recruiter_name": self.recruiter_name,
                "job_description": job_description,
                "resume": self.resume
            })
            
            # 清理生成的求职信
            cover_letter_content = re.sub(r'<think>.*?</think>', '', cover_letter_content, flags=re.DOTALL)
            cover_letter_content = re.sub(r'<think>.*', '', cover_letter_content, flags=re.DOTALL)
            
            # 检查是否为HTML格式，如果不是，则包装为<p>标签
            if not re.search(r'<\s*[p|div]', cover_letter_content):
                paragraphs = cover_letter_content.split('\n\n')
                formatted_paragraphs = [f"<p>{p.strip()}</p>" for p in paragraphs if p.strip()]
                cover_letter_content = '\n'.join(formatted_paragraphs)
            
            # 移除可能存在的嵌套html标签或markdown代码块
            cover_letter_content = re.sub(r'```html\s*', '', cover_letter_content)
            cover_letter_content = re.sub(r'```\s*', '', cover_letter_content)
            
            # 根据template_base.py中的模板格式生成最终HTML
            today_date = datetime.now().strftime('%Y-%m-%d')
            
            html_content = f"""
<section id="cover-letter">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
        <div>
            <p>丁东坡 (Paul)</p>
            <p>江苏省苏州市吴江区开平路</p>
            <p>215200</p>
            <p>dongpoding@gmail.com</p>
            <p>+86 15151508537</p>
        </div>
        <div style="text-align: right;">
            <p>{self.company_name}</p>
            <p>{self.company_name}公司地址</p>
            <p>澳大利亚</p>
        </div>
    </div>
    <div>
        <p>Dear {self.recruiter_name},</p>
        {cover_letter_content}
        <p>Sincerely,</p>
        <p>丁东坡 (Paul)</p>
        <p>{today_date}</p>
        <div style="margin-top: 20px;">
            <p>LinkedIn: <a href="https://www.linkedin.com/in/apaulloo/">https://www.linkedin.com/in/apaulloo/</a></p>
            <p>GitHub: <a href="https://github.com/paulloo">https://github.com/paulloo</a></p>
        </div>
    </div>
</section>"""
            
            logger.info("求职信生成成功")
            return html_content
            
        except Exception as e:
            logger.error(f"生成求职信时出错: {str(e)}")
            return f"""
<section id="cover-letter">
    <div class="error-message">
        <h2>生成求职信时出现错误</h2>
        <p>请稍后重试或联系技术支持。</p>
        <div class="error-details">
            <p>错误信息：{str(e)}</p>
            <p>请确保：</p>
            <ul>
                <li>职位描述已正确设置</li>
                <li>公司名称已正确设置</li>
                <li>职位名称已正确设置</li>
                <li>API密钥配置正确</li>
            </ul>
        </div>
    </div>
</section>""" 