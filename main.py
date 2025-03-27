import os
import sys
import base64
import platform
import re
from pathlib import Path
from datetime import datetime

import inquirer
from loguru import logger

from src.resume_generator import ResumeGenerator
from src.resume_facade import ResumeFacade
from src.resume_schemas.resume import Resume
from src.style_manager import StyleManager
import config as cfg
from src.utils.chrome_utils import browser_manager


def clean_filename(name: str) -> str:
    """
    清理文件名，确保其不包含非法字符
    
    Args:
        name: 原始文件名
        
    Returns:
        清理后的文件名
    """
    if not name:
        return "未提供"
        
    # 将None转为字符串
    if name is None:
        return "未提供"
    
    # 移除思考标记
    cleaned = re.sub(r'<think>.*?</think>', '', name, flags=re.DOTALL)
    cleaned = re.sub(r'<think>.*', '', cleaned, flags=re.DOTALL)
    
    # 移除换行符
    cleaned = cleaned.replace('\n', '_').strip()
    
    # 替换非法字符
    illegal_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    for char in illegal_chars:
        cleaned = cleaned.replace(char, '_')
    
    # 处理常见的标点符号，将它们替换为下划线
    cleaned = re.sub(r'[,.;，。；！？!?()（）\[\]【】{}]', '_', cleaned)
    
    # 替换空格
    cleaned = cleaned.replace(' ', '_')
    
    # 移除多余的下划线
    cleaned = re.sub(r'_+', '_', cleaned)
    
    # 移除开头和结尾的下划线
    cleaned = cleaned.strip('_')
    
    # 如果内容为空或只包含空白字符，返回"unknown"
    if not cleaned or cleaned.isspace():
        return "未提供"
    
    # 限制长度
    if len(cleaned) > 50:
        cleaned = cleaned[:47] + "..."
    
    # 如果第一个字符是点号，添加前缀
    if cleaned.startswith('.'):
        cleaned = 'file_' + cleaned
    
    return cleaned


# 确保日志目录存在
def ensure_directories_exist():
    """
    确保所有必要的目录都存在
    """
    # 日志目录
    os.makedirs(os.path.dirname(cfg.LOG_FILE_PATH), exist_ok=True)
    
    # 简历输出目录
    os.makedirs(cfg.RESUME_OUTPUT_DIR, exist_ok=True)
    
    # 求职信输出目录
    os.makedirs(cfg.COVER_LETTER_OUTPUT_DIR, exist_ok=True)
    
    # Selenium 日志目录
    os.makedirs(os.path.dirname(cfg.GECKODRIVER_LOG_PATH), exist_ok=True)
    
    logger.info("所有必要的目录已创建或存在")


def create_cover_letter(parameters: dict, llm_api_key: str):
    """
    生成求职信
    """
    driver = None
    start_time = datetime.now()
    try:
        logger.info("开始生成求职信...")

        # 检查必要的参数
        if not parameters.get("uploads") or not parameters.get("outputFileDirectory"):
            raise ValueError("缺少必要参数: uploads 或 outputFileDirectory")

        # 加载简历文本
        try:
            logger.info("正在加载简历文本...")
            with open(parameters["uploads"]["plainTextResume"], "r", encoding="utf-8") as file:
                plain_text_resume = file.read()
            logger.info("简历文本加载成功")
        except FileNotFoundError:
            logger.error("找不到简历文件")
            raise
        except Exception as e:
            logger.error(f"读取简历文件时出错: {e}")
            raise

        # 初始化样式管理器
        logger.info("初始化样式管理器...")
        style_manager = StyleManager()
        available_styles = style_manager.get_styles()

        if not available_styles:
            logger.warning("没有可用的样式，使用默认样式")
        else:
            choices = style_manager.format_choices(available_styles)
            questions = [
                inquirer.List(
                    "style",
                    message="选择求职信样式:",
                    choices=choices,
                )
            ]
            style_answer = inquirer.prompt(questions)
            if style_answer and "style" in style_answer:
                selected_choice = style_answer["style"]
                for style_name, (file_name, author_link) in available_styles.items():
                    if selected_choice.startswith(style_name):
                        style_manager.set_selected_style(style_name)
                        logger.info(f"已选择样式: {style_name}")
                        break
            else:
                logger.warning("未选择样式，使用默认样式")

        # 获取工作URL
        logger.info("请输入职位链接...")
        questions = [
            inquirer.Text('job_url', message="请输入职位描述链接:")
        ]
        answers = inquirer.prompt(questions)
        job_url = answers.get('job_url')
        
        if not job_url:
            raise ValueError("职位链接不能为空")
        
        # 验证 URL 格式
        if not job_url.startswith("https://"):
            logger.warning(f"URL 不以 https:// 开头: {job_url}")
            job_url = "https://" + job_url
            logger.info(f"已修正 URL: {job_url}")
            
        logger.info(f"获取到职位链接: {job_url}")

        # 初始化浏览器
        logger.info("初始化浏览器...")
        try:
            # 确保日志目录存在
            ensure_directories_exist()
                    
            # 设置浏览器代理（如果启用）
            if cfg.PROXY_ENABLED and (cfg.PROXY_HTTP or cfg.PROXY_HTTPS):
                logger.info(f"使用代理: HTTP={cfg.PROXY_HTTP}, HTTPS={cfg.PROXY_HTTPS}")
                
            browser_manager.initialize_browser()
            driver = browser_manager.get_driver()
            if not driver:
                raise RuntimeError("浏览器初始化失败")
            logger.info(f"浏览器初始化成功 (类型: {cfg.BROWSER_TYPE})")
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            raise

        # 初始化简历生成器
        logger.info("初始化简历生成器...")
        resume_generator = ResumeGenerator()
        resume_object = Resume(plain_text_resume)
        resume_generator.set_resume_object(resume_object)
        logger.info("简历生成器初始化成功")

        # 创建ResumeFacade实例
        logger.info("创建ResumeFacade实例...")
        # 优先使用output目录，确保路径存在
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"设置输出目录为: {output_dir.absolute()}")
        
        resume_facade = ResumeFacade(
            api_key=llm_api_key,
            style_manager=style_manager,
            resume_generator=resume_generator,
            resume_object=resume_object,
            output_path=output_dir,
        )
        resume_facade.set_driver(driver)
        logger.info("ResumeFacade实例创建成功")

        # 获取职位信息
        logger.info(f"正在获取职位信息: {job_url}")
        try:
            job_info = resume_facade.link_to_job(job_url)
            if not job_info:
                raise ValueError("无法获取职位信息")
            logger.info(f"职位信息获取成功: {job_info.get('role', '未知')} at {job_info.get('company', '未知')}")
        except Exception as e:
            logger.error(f"获取职位信息时出错: {e}")
            raise

        # 生成求职信PDF
        logger.info("开始生成求职信PDF...")
        try:
            # 检查样式路径
            style_path = style_manager.get_style_path()
            if style_path:
                logger.info(f"使用样式: {style_manager.selected_style}，路径: {style_path}")
            else:
                logger.warning("没有选择样式或样式路径不可用，将使用默认样式")
                
            result_base64, suggested_name = resume_facade.create_cover_letter()
            if not result_base64:
                raise ValueError("生成求职信失败")
            logger.info("求职信PDF生成成功")
        except Exception as e:
            logger.error(f"生成求职信时出错: {e}")
            raise

        # 解码Base64数据
        logger.info("正在解码PDF数据...")
        try:
            pdf_data = base64.b64decode(result_base64)
            logger.info(f"PDF数据解码成功，大小: {len(pdf_data)/1024:.2f} KB")
        except base64.binascii.Error as e:
            logger.error(f"解码Base64数据时出错: {e}")
            raise

        # 创建输出目录
        company_name = job_info.get('company', 'unknown')
        role_name = job_info.get('title', 'unknown')
        
        # 清理公司名称、职位名称和建议名称，确保可以安全用作文件名
        company_name = clean_filename(company_name)
        role_name = clean_filename(role_name)
        suggested_name = clean_filename(suggested_name)
        
        # 检查是否有空值
        if company_name.lower() == 'unknown' or company_name == '':
            company_name = 'unknown_company'
        if role_name.lower() == 'unknown' or role_name == '':
            role_name = 'unknown_position'
        
        logger.info(f"使用以下信息创建文件名: 公司={company_name}, 职位={role_name}")
        
        # 创建公司和职位特定的子目录
        company_job_dir = f"{company_name}_{role_name}_{suggested_name}"
        final_output_dir = output_dir / company_job_dir
        try:
            final_output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"输出目录创建成功: {final_output_dir}")
        except Exception as e:
            logger.error(f"创建输出目录时出错: {e}")
            raise

        # 保存PDF文件
        output_file = final_output_dir / f"{company_name}_{role_name}_cover_letter.pdf"
        logger.info(f"正在保存求职信到: {output_file}")
        try:
            with open(output_file, "wb") as file:
                file.write(pdf_data)
            logger.info(f"求职信已保存到: {output_file}")
            print(f"✅ 求职信已生成并保存到: {output_file}")
        except IOError as e:
            logger.error(f"保存文件时出错: {e}")
            raise

        # 计算总耗时
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"求职信生成完成，总耗时: {elapsed_time:.2f} 秒")
        return True

    except Exception as e:
        logger.exception(f"生成求职信时发生错误: {e}")
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"操作失败，总耗时: {elapsed_time:.2f} 秒")
        return False
    finally:
        # 确保资源被正确释放
        try:
            if driver:
                logger.info("正在关闭浏览器...")
                browser_manager.close()
                logger.info("浏览器已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器时出错: {e}")


def create_resume_pdf_job_tailored(parameters: dict, llm_api_key: str):
    """
    生成针对工作描述定制的简历。
    """
    driver = None
    start_time = datetime.now()
    try:
        logger.info("开始生成定制简历...")

        # 检查必要的参数
        if not parameters.get("uploads") or not parameters.get("outputFileDirectory"):
            raise ValueError("缺少必要参数: uploads 或 outputFileDirectory")

        # 加载简历文本
        try:
            logger.info("正在加载简历文本...")
            with open(parameters["uploads"]["plainTextResume"], "r", encoding="utf-8") as file:
                plain_text_resume = file.read()
            logger.info("简历文本加载成功")
        except FileNotFoundError:
            logger.error("找不到简历文件")
            raise
        except Exception as e:
            logger.error(f"读取简历文件时出错: {e}")
            raise

        # 初始化样式管理器
        logger.info("初始化样式管理器...")
        style_manager = StyleManager()
        available_styles = style_manager.get_styles()

        if not available_styles:
            logger.warning("没有可用的样式，使用默认样式")
        else:
            choices = style_manager.format_choices(available_styles)
            questions = [
                inquirer.List(
                    "style",
                    message="选择简历样式:",
                    choices=choices,
                )
            ]
            style_answer = inquirer.prompt(questions)
            if style_answer and "style" in style_answer:
                selected_choice = style_answer["style"]
                for style_name, (file_name, author_link) in available_styles.items():
                    if selected_choice.startswith(style_name):
                        style_manager.set_selected_style(style_name)
                        logger.info(f"已选择样式: {style_name}")
                        break
            else:
                logger.warning("未选择样式，使用默认样式")

        # 获取工作URL
        logger.info("请输入职位链接...")
        questions = [
            inquirer.Text('job_url', message="请输入职位描述链接:")
        ]
        answers = inquirer.prompt(questions)
        job_url = answers.get('job_url')
        
        if not job_url:
            raise ValueError("职位链接不能为空")
        
        # 验证 URL 格式
        if not job_url.startswith("https://"):
            logger.warning(f"URL 不以 https:// 开头: {job_url}")
            job_url = "https://" + job_url
            logger.info(f"已修正 URL: {job_url}")
            
        logger.info(f"获取到职位链接: {job_url}")

        # 初始化浏览器
        logger.info("初始化浏览器...")
        try:
            # 确保日志目录存在
            ensure_directories_exist()
                    
            # 设置浏览器代理（如果启用）
            if cfg.PROXY_ENABLED and (cfg.PROXY_HTTP or cfg.PROXY_HTTPS):
                logger.info(f"使用代理: HTTP={cfg.PROXY_HTTP}, HTTPS={cfg.PROXY_HTTPS}")
                
            browser_manager.initialize_browser()
            driver = browser_manager.get_driver()
            if not driver:
                raise RuntimeError("浏览器初始化失败")
            logger.info(f"浏览器初始化成功 (类型: {cfg.BROWSER_TYPE})")
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            raise

        # 初始化简历生成器
        logger.info("初始化简历生成器...")
        resume_generator = ResumeGenerator()
        resume_object = Resume(plain_text_resume)
        resume_generator.set_resume_object(resume_object)
        logger.info("简历生成器初始化成功")

        # 创建ResumeFacade实例
        logger.info("创建ResumeFacade实例...")
        # 优先使用output目录，确保路径存在
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"设置输出目录为: {output_dir.absolute()}")
        
        resume_facade = ResumeFacade(
            api_key=llm_api_key,
            style_manager=style_manager,
            resume_generator=resume_generator,
            resume_object=resume_object,
            output_path=output_dir,
        )
        resume_facade.set_driver(driver)
        logger.info("ResumeFacade实例创建成功")

        # 获取职位信息
        logger.info(f"正在获取职位信息: {job_url}")
        try:
            job_info = resume_facade.link_to_job(job_url)
            if not job_info:
                raise ValueError("无法获取职位信息")
            logger.info(f"职位信息获取成功: {job_info.get('role', '未知')} at {job_info.get('company', '未知')}")
        except Exception as e:
            logger.error(f"获取职位信息时出错: {e}")
            raise

        # 生成简历PDF
        logger.info("开始生成定制简历PDF...")
        try:
            result_base64, suggested_name = resume_facade.create_resume_pdf_job_tailored()
            if not result_base64:
                raise ValueError("生成简历失败")
            logger.info("定制简历PDF生成成功")
        except Exception as e:
            logger.error(f"生成定制简历时出错: {e}")
            raise

        # 解码Base64数据
        logger.info("正在解码PDF数据...")
        try:
            pdf_data = base64.b64decode(result_base64)
            logger.info(f"PDF数据解码成功，大小: {len(pdf_data)/1024:.2f} KB")
        except base64.binascii.Error as e:
            logger.error(f"解码Base64数据时出错: {e}")
            raise

        # 创建输出目录
        company_name = job_info.get('company', 'unknown')
        role_name = job_info.get('title', 'unknown')
        
        # 清理公司名称、职位名称和建议名称，确保可以安全用作文件名
        company_name = clean_filename(company_name)
        role_name = clean_filename(role_name)
        suggested_name = clean_filename(suggested_name)
        
        # 检查是否有空值
        if company_name.lower() == 'unknown' or company_name == '':
            company_name = 'unknown_company'
        if role_name.lower() == 'unknown' or role_name == '':
            role_name = 'unknown_position'
        
        logger.info(f"使用以下信息创建文件名: 公司={company_name}, 职位={role_name}")
        
        # 创建公司和职位特定的子目录
        company_job_dir = f"{company_name}_{role_name}_{suggested_name}"
        final_output_dir = output_dir / company_job_dir
        try:
            final_output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"输出目录创建成功: {final_output_dir}")
        except Exception as e:
            logger.error(f"创建输出目录时出错: {e}")
            raise

        # 保存PDF文件
        output_file = final_output_dir / f"{company_name}_{role_name}_resume.pdf"
        logger.info(f"正在保存简历到: {output_file}")
        try:
            with open(output_file, "wb") as file:
                file.write(pdf_data)
            logger.info(f"简历已保存到: {output_file}")
            print(f"✅ 定制简历已生成并保存到: {output_file}")
        except IOError as e:
            logger.error(f"保存文件时出错: {e}")
            raise

        # 计算总耗时
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"定制简历生成完成，总耗时: {elapsed_time:.2f} 秒")
        return True

    except Exception as e:
        logger.exception(f"生成定制简历时发生错误: {e}")
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"操作失败，总耗时: {elapsed_time:.2f} 秒")
        return False
    finally:
        # 确保资源被正确释放
        try:
            if driver:
                logger.info("正在关闭浏览器...")
                browser_manager.close()
                logger.info("浏览器已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器时出错: {e}")


def create_resume_pdf(parameters: dict, llm_api_key: str):
    """
    生成简历PDF。
    """
    driver = None
    try:
        logger.info("开始生成简历...")

        # 检查必要的参数
        if not parameters.get("uploads") or not parameters.get("outputFileDirectory"):
            raise ValueError("缺少必要参数: uploads 或 outputFileDirectory")

        # 加载简历文本
        try:
            logger.info("正在加载简历文本...")
            with open(parameters["uploads"]["plainTextResume"], "r", encoding="utf-8") as file:
                plain_text_resume = file.read()
            logger.info("简历文本加载成功")
        except FileNotFoundError:
            logger.error("找不到简历文件")
            raise
        except Exception as e:
            logger.error(f"读取简历文件时出错: {e}")
            raise

        # 初始化样式管理器
        logger.info("初始化样式管理器...")
        style_manager = StyleManager()
        available_styles = style_manager.get_styles()

        if not available_styles:
            logger.warning("没有可用的样式，使用默认样式")
        else:
            choices = style_manager.format_choices(available_styles)
            questions = [
                inquirer.List(
                    "style",
                    message="请选择简历样式:",
                    choices=choices,
                )
            ]
            style_answer = inquirer.prompt(questions)
            if style_answer and "style" in style_answer:
                selected_choice = style_answer["style"]
                for style_name, (file_name, author_link) in available_styles.items():
                    if selected_choice.startswith(style_name):
                        style_manager.set_selected_style(style_name)
                        logger.info(f"已选择样式: {style_name}")
                        break

        # 初始化浏览器
        logger.info("初始化浏览器...")
        try:
            driver = init_browser()
            if not driver:
                raise RuntimeError("浏览器初始化失败")
            logger.info("浏览器初始化成功")
        except WebDriverException as e:
            logger.error(f"浏览器初始化失败: {e}")
            raise
        except Exception as e:
            logger.error(f"初始化浏览器时发生未知错误: {e}")
            raise

        # 初始化简历生成器
        logger.info("初始化简历生成器...")
        resume_generator = ResumeGenerator()
        resume_object = Resume(plain_text_resume)
        resume_generator.set_resume_object(resume_object)
        logger.info("简历生成器初始化成功")

        # 创建ResumeFacade实例
        logger.info("创建ResumeFacade实例...")
        output_path = Path(parameters["outputFileDirectory"])
        resume_facade = ResumeFacade(
            api_key=llm_api_key,
            style_manager=style_manager,
            resume_generator=resume_generator,
            resume_object=resume_object,
            output_path=output_path,
        )
        resume_facade.set_driver(driver)
        logger.info("ResumeFacade实例创建成功")

        # 生成简历PDF
        logger.info("开始生成简历PDF...")
        try:
            result_base64, suggested_name = resume_facade.create_resume_pdf()
            if not result_base64:
                raise ValueError("生成简历失败")
            logger.info("简历PDF生成成功")
        except Exception as e:
            logger.error(f"生成简历时出错: {e}")
            raise

        # 解码Base64数据
        logger.info("正在解码PDF数据...")
        try:
            pdf_data = base64.b64decode(result_base64)
            logger.info("PDF数据解码成功")
        except base64.binascii.Error as e:
            logger.error(f"解码Base64数据时出错: {e}")
            raise

        # 创建输出目录
        company_name = job_info.get('company', 'unknown')
        role_name = job_info.get('title', 'unknown')
        
        # 清理公司名称、职位名称和建议名称，确保可以安全用作文件名
        company_name = clean_filename(company_name)
        role_name = clean_filename(role_name)
        suggested_name = clean_filename(suggested_name)
        
        output_dir = output_path / f"{company_name}_{role_name}_{suggested_name}"
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"输出目录创建成功: {output_dir}")
        except Exception as e:
            logger.error(f"创建输出目录时出错: {e}")
            raise

        # 保存PDF文件
        output_file = output_dir / "resume.pdf"
        logger.info(f"正在保存简历到: {output_file}")
        try:
            with open(output_file, "wb") as file:
                file.write(pdf_data)
            logger.info(f"简历已保存到: {output_file}")
        except IOError as e:
            logger.error(f"保存文件时出错: {e}")
            raise

        return True

    except Exception as e:
        logger.exception(f"生成简历时发生错误: {e}")
        raise
    finally:
        if driver:
            logger.info("正在关闭浏览器...")
            try:
                driver.quit()
                logger.info("浏览器已关闭")
            except Exception as e:
                logger.error(f"关闭浏览器时出错: {e}")


def main():
    """
    主函数，运行应用程序。
    """
    try:
        # 配置日志
        logger.info("正在初始化应用程序...")
        logger.info(f"操作系统: {platform.system()} {platform.release()}")
        
        # 确保所有目录存在
        ensure_directories_exist()
        
        # 设置LLM API密钥
        if cfg.LLM_MODEL_TYPE.lower() == 'openai':
            llm_api_key = cfg.LLM_API_KEY or os.environ.get("OPENAI_API_KEY")
            if not llm_api_key:
                logger.error("未设置OpenAI API密钥。请在config.py中设置LLM_API_KEY或设置OPENAI_API_KEY环境变量。")
                print("❌ 错误: 未设置OpenAI API密钥。请在config.py中设置LLM_API_KEY或设置OPENAI_API_KEY环境变量。")
                sys.exit(1)
            logger.info("使用OpenAI模型")
        else:
            # 对于Ollama等本地模型，使用虚拟API密钥
            llm_api_key = cfg.FAKE_API_KEY
            logger.info(f"使用本地模型: {cfg.LLM_MODEL_TYPE} - {cfg.LLM_MODEL}")
        
        # 同步配置到模块配置
        from src.libs.resume_and_cover_builder.config import global_config
        global_config.API_KEY = llm_api_key
        global_config.MODEL_TYPE = cfg.LLM_MODEL_TYPE.lower()
        global_config.MODEL = cfg.LLM_MODEL
        
        logger.info(f"配置信息: MODEL_TYPE={global_config.MODEL_TYPE}, MODEL={global_config.MODEL}")
        
        # 欢迎信息
        print("=" * 60)
        print("👔 欢迎使用 Jobs Applier AI Agent - AIHawk! 🦅")
        print("=" * 60)
        print("这个工具帮助您生成定制化的简历和求职信，提高求职成功率。")
        print("选择您要执行的操作:")
        print()
        
        # 定义功能选项
        questions = [
            inquirer.List(
                "action",
                message="请选择一个操作:",
                choices=[
                    "生成针对职位描述的简历",
                    "生成针对职位描述的求职信",
                    "退出"
                ],
            )
        ]
        
        answers = inquirer.prompt(questions)
        
        if not answers or answers.get("action") == "退出":
            print("👋 感谢使用，再见!")
            return
        
        # 准备参数
        parameters = {
            "uploads": {
                "plainTextResume": "data_folder/plain_text_resume.yaml"
            },
            "outputFileDirectory": "output"
        }
        
        # 根据选择执行相应功能
        if answers["action"] == "生成针对职位描述的简历":
            logger.info("用户选择: 生成针对职位描述的简历")
            success = create_resume_pdf_job_tailored(parameters, llm_api_key)
            if success:
                print("✨ 简历生成成功!")
                print("请查看 log/resume/ 目录查找生成的文件。")
            else:
                print("❌ 简历生成失败，请查看日志了解详情。")
                
        elif answers["action"] == "生成针对职位描述的求职信":
            logger.info("用户选择: 生成针对职位描述的求职信")
            success = create_cover_letter(parameters, llm_api_key)
            if success:
                print("✨ 求职信生成成功!")
                print("请查看 log/cover_letter/ 目录查找生成的文件。")
            else:
                print("❌ 求职信生成失败，请查看日志了解详情。")
    
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        print("\n👋 操作已中断，再见!")
    except Exception as e:
        logger.exception(f"程序执行时出错: {e}")
        print(f"❌ 发生错误: {e}")
        print("请查看日志了解详情。")
    finally:
        # 确保资源被正确释放
        try:
            browser_manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
