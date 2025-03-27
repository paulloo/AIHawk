"""
This module is responsible for generating resumes and cover letters using the LLM model.
"""
# app/libs/resume_and_cover_builder/resume_generator.py
import json
import yaml
from string import Template
from typing import Any, Dict, Optional
from pathlib import Path
import os
from src.libs.resume_and_cover_builder.llm.llm_generate_resume import LLMResumer
from src.libs.resume_and_cover_builder.llm.llm_generate_resume_from_job import LLMResumeJobDescription
from src.libs.resume_and_cover_builder.llm.llm_generate_cover_letter_from_job import LLMCoverLetterJobDescription
from .module_loader import load_module
from .config import global_config
from loguru import logger

class ResumeGenerator:
    def __init__(self):
        self.resume_object = None
        self.load_resume_data()
    
    def load_resume_data(self):
        """从yaml文件加载简历数据"""
        # 尝试寻找简历文件
        resume_path = Path("data/plain_text_resume.yaml")
        
        if not resume_path.exists():
            logger.warning(f"找不到简历文件: {resume_path}，将使用空简历")
            self.resume_object = {}
            return
        
        try:
            # 读取并解析YAML文件
            with open(resume_path, 'r', encoding='utf-8') as f:
                resume_data = yaml.safe_load(f)
            
            logger.info(f"成功加载简历数据: {resume_path}")
            self.resume_object = resume_data
        except Exception as e:
            logger.error(f"加载简历数据失败: {str(e)}")
            self.resume_object = {}
    
    def set_resume_object(self, resume_object):
        """设置要使用的简历对象"""
        if resume_object:
            self.resume_object = resume_object
            logger.debug(f"简历对象已设置: {type(resume_object)}")
        else:
            logger.warning("尝试设置空简历对象，保持使用已加载的简历数据")
         
    def _convert_resume_to_text(self):
        """将简历对象转换为文本格式"""
        if not self.resume_object:
            logger.warning("简历对象为空，加载默认简历数据")
            self.load_resume_data()
            
        if not self.resume_object:
            logger.warning("仍然无法加载简历数据，返回空字符串")
            return "未提供简历信息"
            
        try:
            # 将字典转换为YAML格式的字符串
            resume_text = yaml.dump(self.resume_object, default_flow_style=False, allow_unicode=True)
            logger.debug(f"简历对象已转换为文本，长度: {len(resume_text)} 字符")
            return resume_text
        except Exception as e:
            logger.error(f"将简历对象转换为文本时出错: {str(e)}")
            # 尝试使用字符串转换
            try:
                resume_text = str(self.resume_object)
                logger.debug(f"使用str()转换简历对象，长度: {len(resume_text)} 字符")
                return resume_text
            except:
                logger.error("无法将简历对象转换为文本")
                return "简历数据无法处理"

    def _format_resume_for_prompt(self):
        """格式化简历数据，使其更适合LLM提示"""
        if not self.resume_object:
            logger.warning("简历对象为空，加载默认简历数据")
            self.load_resume_data()
        
        if not self.resume_object:
            logger.warning("仍然无法加载简历数据，返回空字符串")
            return "未提供简历信息"
        
        try:
            # 检查resume_object是否为Resume类的实例
            if hasattr(self.resume_object, 'to_dict'):
                # 如果是Resume对象，使用to_dict方法转换为字典
                resume_dict = self.resume_object.to_dict()
                logger.debug("已将Resume对象转换为字典格式")
            elif isinstance(self.resume_object, dict):
                # 如果已经是字典，直接使用
                resume_dict = self.resume_object
                logger.debug("使用现有的字典格式简历数据")
            elif hasattr(self.resume_object, '__str__'):
                # 如果是其他可转换为字符串的对象
                resume_text = str(self.resume_object)
                logger.debug(f"使用__str__方法转换简历对象，长度: {len(resume_text)} 字符")
                return resume_text
            else:
                # 无法处理的类型
                logger.warning(f"无法处理的简历对象类型: {type(self.resume_object)}")
                return "无法处理的简历格式"
            
            # 构建格式化的简历文本
            formatted_text = []
            
            # 个人信息
            personal = resume_dict.get('personal_information', {})
            if personal:
                formatted_text.append("## 个人信息")
                for key, value in personal.items():
                    formatted_text.append(f"{key}: {value}")
            
            # 教育经历
            education = resume_dict.get('education_details', [])
            if education:
                formatted_text.append("\n## 教育经历")
                for edu in education:
                    edu_text = []
                    for key, value in edu.items():
                        edu_text.append(f"{key}: {value}")
                    formatted_text.append(" | ".join(edu_text))
            
            # 工作经历
            experience = resume_dict.get('experience_details', [])
            if experience:
                formatted_text.append("\n## 工作经历")
                for exp in experience:
                    formatted_text.append(f"职位: {exp.get('position', '未知职位')}")
                    formatted_text.append(f"公司: {exp.get('company', '未知公司')}")
                    formatted_text.append(f"时间: {exp.get('employment_period', '未知时间')}")
                    
                    # 主要职责
                    if 'key_responsibilities' in exp:
                        formatted_text.append("主要职责:")
                        for resp in exp['key_responsibilities']:
                            for _, desc in resp.items():
                                formatted_text.append(f"- {desc}")
                    
                    # 获得的技能
                    if 'skills_acquired' in exp:
                        formatted_text.append("技能:")
                        formatted_text.append(", ".join(exp['skills_acquired']))
                    
                    formatted_text.append("")
            
            # 项目经历
            projects = resume_dict.get('projects', [])
            if projects:
                formatted_text.append("\n## 项目经历")
                for proj in projects:
                    formatted_text.append(f"项目名称: {proj.get('name', '未知项目')}")
                    formatted_text.append(f"描述: {proj.get('description', '无描述')}")
                    if 'link' in proj and proj['link'] != 'N/A':
                        formatted_text.append(f"链接: {proj['link']}")
                    formatted_text.append("")
            
            # 技能
            skills = resume_dict.get('skills', [])
            if skills:
                formatted_text.append("\n## 技能")
                formatted_text.append(", ".join(skills))
            
            # 语言
            languages = resume_dict.get('languages', [])
            if languages:
                formatted_text.append("\n## 语言")
                for lang in languages:
                    formatted_text.append(f"{lang.get('language', '未知语言')}: {lang.get('proficiency', '未知水平')}")
            
            # 兴趣爱好
            interests = resume_dict.get('interests', [])
            if interests:
                formatted_text.append("\n## 兴趣爱好")
                formatted_text.append(", ".join(interests))
            
            result = "\n".join(formatted_text)
            logger.debug(f"简历已格式化，长度: {len(result)} 字符")
            return result
            
        except Exception as e:
            logger.error(f"格式化简历数据失败: {str(e)}")
            # 尝试直接使用字符串表示
            try:
                resume_text = str(self.resume_object)
                logger.debug(f"使用字符串表示作为备选，长度: {len(resume_text)} 字符")
                return resume_text
            except:
                logger.error("无法将简历对象转换为文本")
                return "简历数据无法处理"

    def _create_resume(self, gpt_answerer: Any, style_path):
        """创建简历HTML"""
        # 设置简历对象
        resume_text = self._format_resume_for_prompt()
        gpt_answerer.set_resume(resume_text)
        
        # 读取模板HTML
        template = Template(global_config.html_template)
        
        try:
            # 读取CSS样式
            with open(style_path, "r") as f:
                style_css = f.read()
        except FileNotFoundError:
            logger.error(f"样式文件未找到: {style_path}")
            raise ValueError(f"样式文件未找到: {style_path}")
        except Exception as e:
            logger.error(f"读取CSS文件时出错: {str(e)}")
            raise RuntimeError(f"读取CSS文件时出错: {str(e)}")
        
        # 生成简历HTML
        body_html = gpt_answerer.generate_html_resume()
        
        # 应用模板
        return template.substitute(body=body_html, style_css=style_css)

    def create_resume(self, style_path):
        """创建标准简历"""
        strings = load_module(global_config.STRINGS_MODULE_RESUME_PATH, global_config.STRINGS_MODULE_NAME)
        gpt_answerer = LLMResumer(global_config.API_KEY, strings)
        return self._create_resume(gpt_answerer, style_path)

    def create_resume_job_description_text(self, style_path: str, job_description_text: str):
        """创建针对特定职位的简历"""
        strings = load_module(global_config.STRINGS_MODULE_RESUME_JOB_DESCRIPTION_PATH, global_config.STRINGS_MODULE_NAME)
        gpt_answerer = LLMResumeJobDescription(global_config.API_KEY, strings)
        gpt_answerer.set_job_description_from_text(job_description_text)
        return self._create_resume(gpt_answerer, style_path)

    def create_cover_letter_job_description(self, style_path: str, job_description_text: str):
        """创建针对特定职位的求职信"""
        logger.debug("开始创建针对特定职位的求职信")
        logger.debug(f"使用样式路径: {style_path}")
        
        # 确保样式路径存在
        if not os.path.exists(style_path):
            logger.error(f"样式文件不存在: {style_path}")
            raise FileNotFoundError(f"样式文件不存在: {style_path}")
            
        strings = load_module(global_config.STRINGS_MODULE_COVER_LETTER_JOB_DESCRIPTION_PATH, global_config.STRINGS_MODULE_NAME)
        logger.debug(f"已加载求职信字符串模块: {global_config.STRINGS_MODULE_COVER_LETTER_JOB_DESCRIPTION_PATH}")
        
        # 初始化求职信生成器
        gpt_answerer = LLMCoverLetterJobDescription(global_config.API_KEY, strings)
        
        # 将简历对象格式化为对LLM更友好的文本
        resume_text = self._format_resume_for_prompt()
        logger.debug(f"简历文本准备完成: {len(resume_text)} 字符")
        
        # 设置简历和职位描述
        gpt_answerer.set_resume(resume_text)
        gpt_answerer.set_job_description_from_text(job_description_text)
        
        # 生成求职信HTML
        cover_letter_html = gpt_answerer.generate_cover_letter()
        logger.debug(f"求职信HTML生成成功: {len(cover_letter_html)} 字符")
        
        # 应用HTML模板
        template = Template(global_config.html_template)
        
        try:
            # 读取样式文件内容
            with open(style_path, "r", encoding="utf-8") as f:
                original_style_css = f.read()
                logger.debug(f"成功读取样式CSS，长度: {len(original_style_css)} 字符")
            
            # 添加额外的求职信特定样式
            style_css = original_style_css + """
                /* 求职信特定样式 */
                .cover-letter {
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    font-family: inherit;
                }
                .cover-letter .header {
                    margin-bottom: 30px;
                    text-align: center;
                }
                .cover-letter .header h1 {
                    margin-bottom: 10px;
                    color: inherit;
                }
                .cover-letter .content {
                    line-height: 1.6;
                    text-align: justify;
                }
                .cover-letter p {
                    margin-bottom: 15px;
                }
                .cover-letter h3, .cover-letter h4 {
                    margin-top: 20px;
                    margin-bottom: 10px;
                }
                .cover-letter ul {
                    padding-left: 20px;
                    margin-bottom: 15px;
                }
                .cover-letter li {
                    margin-bottom: 5px;
                }
            """
            logger.debug("已添加求职信特定样式")
                
            # 替换模板中的变量
            logger.debug("正在应用样式到HTML模板...")
            # 在替换前检查模板是否包含$style_css占位符
            if "$style_css" not in template.template:
                logger.error("HTML模板中没有找到$style_css占位符")
                
            # 包装HTML以确保样式应用正确
            if not cover_letter_html.strip().startswith('<div class="cover-letter">'):
                # 移除思考部分
                import re
                cover_letter_html = re.sub(r'<think>.*?</think>', '', cover_letter_html, flags=re.DOTALL)
                cover_letter_html = re.sub(r'<think>.*', '', cover_letter_html, flags=re.DOTALL)
                
                # 如果是纯文本格式，转换为正确的HTML格式
                if not ('<div' in cover_letter_html or '<p>' in cover_letter_html):
                    paragraphs = cover_letter_html.strip().split('\n\n')
                    formatted_paragraphs = [f"<p>{p.replace('\n', '<br>')}</p>" for p in paragraphs if p.strip()]
                    cover_letter_html = '\n'.join(formatted_paragraphs)
                
                # 包装在适当的HTML结构中
                cover_letter_html = f"""
                <div class="cover-letter">
                    <div class="header">
                        <h1>求职信</h1>
                    </div>
                    <div class="content">
                        {cover_letter_html}
                    </div>
                </div>
                """
                logger.debug("已将内容包装在适当的HTML结构中")
            
            complete_html = template.substitute(body=cover_letter_html, style_css=style_css)
            logger.debug(f"完整HTML生成成功，长度: {len(complete_html)} 字符")
            
            # 写入调试输出
            try:
                debug_file = Path("output") / "debug_html.html"
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(complete_html)
                logger.debug(f"已将调试HTML保存到: {debug_file}")
            except Exception as debug_e:
                logger.warning(f"保存调试HTML失败: {str(debug_e)}")
            
            # 返回完整HTML
            return complete_html
        except Exception as e:
            logger.error(f"应用样式时出错: {str(e)}")
            # 出错时尝试使用空样式
            logger.warning("使用空样式作为备选")
            return template.substitute(body=cover_letter_html, style_css="")
    
    
    