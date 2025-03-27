"""
This module is used to store the global configuration of the application.
"""
# app/libs/resume_and_cover_builder/config.py
from pathlib import Path
import os
from dotenv import load_dotenv

# 先加载环境变量，以便配置类可以使用
load_dotenv()

# 获取当前模块的路径
current_dir = Path(__file__).parent.resolve()

class GlobalConfig:
    """全局配置类"""
    def __init__(self):
        # API配置
        self.API_KEY = os.environ.get("OPENAI_API_KEY", "sk-ollama-local-model-no-api-key-required")
        self.MODEL_TYPE = os.environ.get("MODEL_TYPE", "ollama").lower()  # 从环境变量加载模型类型
        self.MODEL = os.environ.get("MODEL", "deepseek-r1")  # 从环境变量加载模型名称
        
        # 验证MODEL_TYPE
        valid_model_types = ["ollama", "openai", "gemini"]
        if self.MODEL_TYPE not in valid_model_types:
            print(f"警告: 未知模型类型 {self.MODEL_TYPE}，将使用默认的ollama")
            self.MODEL_TYPE = "ollama"
            
        # 根据MODEL_TYPE设置默认模型
        if self.MODEL_TYPE == "ollama" and self.MODEL == "deepseek-r1":
            pass  # 使用默认设置
        elif self.MODEL_TYPE == "openai" and self.MODEL == "deepseek-r1":
            self.MODEL = "gpt-3.5-turbo"  # OpenAI默认模型
        elif self.MODEL_TYPE == "gemini" and self.MODEL == "deepseek-r1":
            self.MODEL = "gemini-pro"  # Gemini默认模型
        
        # 温度参数
        self.TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.7"))
        
        # Ollama API URL
        self.LLM_API_URL = os.environ.get("LLM_API_URL", "http://localhost:11434")
        
        # 代理配置
        self.PROXY_ENABLED = os.environ.get("PROXY_ENABLED", "False").lower() == "true"
        self.PROXY_HTTP = os.environ.get("PROXY_HTTP", None)
        self.PROXY_HTTPS = os.environ.get("PROXY_HTTPS", None)
        
        # Gemini配置
        self.GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
        
        # OpenAI配置
        self.OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
        
        # 模拟数据配置
        self.USE_MOCK_DATA = True  # 默认启用模拟数据，避免LinkedIn访问失败
        self.MOCK_DATA_CHANCE = 0.8  # 当LinkedIn访问失败时使用模拟数据的概率
        
        # 浏览器配置
        self.BROWSER_TYPE = "chrome"
        self.HEADLESS_MODE = True
        self.BROWSER_WIDTH = 1920
        self.BROWSER_HEIGHT = 1080
        self.BROWSER_USER_AGENT = os.environ.get("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # 超时设置
        self.PAGE_LOAD_TIMEOUT = 30
        self.SCRIPT_TIMEOUT = 30
        self.IMPLICIT_WAIT = 10
        self.MAX_RETRIES = 3
        
        # Ollama设置
        self.OLLAMA_BASE_URL = self.LLM_API_URL  # 使用同一个URL
        self.OLLAMA_TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.7"))
        self.OLLAMA_TOP_P = 0.8
        self.OLLAMA_TOP_K = 40
        
        # 支持的本地模型列表
        self.SUPPORTED_LOCAL_MODELS = [
            "deepseek-r1",
            "phi4",
            "llama3",
            "mistral",
            "mixtral"
        ]
        
        # PDF导出设置
        self.PDF_PAPER_WIDTH = 8.5
        self.PDF_PAPER_HEIGHT = 11
        self.PDF_MARGIN_TOP = 0.5
        self.PDF_MARGIN_BOTTOM = 0.5
        self.PDF_MARGIN_LEFT = 0.5
        self.PDF_MARGIN_RIGHT = 0.5
        
        # 设置模块路径，确保它们不为None
        self.STRINGS_MODULE_NAME = "strings_feder_cr"
        
        # 如果不存在strings_feder_cr.py文件，创建一个
        base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
        strings_file = base_path / f"{self.STRINGS_MODULE_NAME}.py"
        if not strings_file.exists():
            from shutil import copyfile
            # 尝试从示例文件复制
            sample_file = current_dir / "templates" / "strings_sample.py"
            if sample_file.exists():
                copyfile(sample_file, strings_file)
            else:
                # 创建一个默认的空文件
                with open(strings_file, "w", encoding="utf-8") as f:
                    f.write('"""字符串配置文件"""\n\n# 简历模板\nprompt_header = """\n你需要按照标准HTML格式输出一个简历的Header部分。\n基于下面的个人信息：\n{personal_information}\n"""\n\n# 求职信模板\nprompt_cover_letter = """\n生成一封针对以下信息的专业求职信。使用清晰的段落和适当的格式。\n\n简历信息：\n{resume}\n\n职位描述：\n{job_description}\n\n公司信息：\n{company}\n\n请确保包含一个正式的问候语、一个介绍段落、2-3个描述为什么应聘者是该职位理想人选的段落、一个总结段落和恰当的结束语。\n"""')
        
        # 设置路径变量        
        self.STRINGS_MODULE_RESUME_PATH = strings_file
        self.STRINGS_MODULE_RESUME_JOB_DESCRIPTION_PATH = strings_file
        self.STRINGS_MODULE_COVER_LETTER_JOB_DESCRIPTION_PATH = strings_file
        self.STYLES_DIRECTORY = current_dir / "resume_style"
        self.LOG_OUTPUT_FILE_PATH = Path("log") / "resume" / "gpt_resume"
        
        # 创建日志目录（如果不存在）
        if not self.LOG_OUTPUT_FILE_PATH.exists():
            self.LOG_OUTPUT_FILE_PATH.mkdir(parents=True, exist_ok=True)
            
        self.html_template = """
                            <!DOCTYPE html>
                            <html lang="en">
                            <head>
                                <meta charset="UTF-8">
                                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                <title>Resume</title>
                                <link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;600&display=swap" rel="stylesheet" />
                                <link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;600&display=swap" rel="stylesheet" /> 
                                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css" /> 
                                    <style>
                                        $style_css
                                    </style>
                            </head>
                            <body>
                            $body
                            </body>
                            </html>
                            """

global_config = GlobalConfig()
