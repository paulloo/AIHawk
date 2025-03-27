# In this file, you can set the configurations of the app.

from src.utils.constants import DEBUG, ERROR, LLM_MODEL, OPENAI
import os
import platform
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# 首先加载.env文件中的环境变量(如果存在)
load_dotenv()

# 日志相关配置（LOG_前缀）
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG')  # 可选值: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_SELENIUM_LEVEL = DEBUG
LOG_TO_FILE = True
LOG_TO_CONSOLE = True
LOG_FILE_PATH = "log/application.log"  # 修改为现有的日志目录
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# 等待时间相关配置（单位：秒）
MINIMUM_WAIT_TIME_IN_SECONDS = 60
PAGE_LOAD_TIMEOUT = 30
SCRIPT_TIMEOUT = 30
IMPLICIT_WAIT = 10

# 目录和文件相关配置
JOB_APPLICATIONS_DIR = "job_applications"
JOB_SUITABILITY_SCORE = 7
OUTPUT_DIR = "output"

# 工作申请相关配置
JOB_MAX_APPLICATIONS = 5
JOB_MIN_APPLICATIONS = 1

# 语言模型相关配置 - 从环境变量加载
LLM_MODEL_TYPE = os.environ.get('MODEL_TYPE', 'ollama')  # 可选值: 'ollama', 'openai', 'azure'
LLM_MODEL = os.environ.get('MODEL', 'deepseek-r1: 7b')  # 对于Ollama，使用支持的模型名称如 'llama2', 'mistral'
# 仅Ollama模型需要
LLM_API_URL = os.environ.get('LLM_API_URL', 'http://127.0.0.1:11434/')
# 仅OpenAI模型需要
LLM_API_KEY = os.environ.get('OPENAI_API_KEY', '')
# 为确保兼容性添加新别名
OPENAI_API_KEY = LLM_API_KEY

# 添加虚拟API密钥，当使用Ollama时不需要实际的API密钥
FAKE_API_KEY = 'sk-ollama-local-model-no-api-key-required'

# 系统编码配置
DEFAULT_ENCODING = os.environ.get('DEFAULT_ENCODING', 'utf-8')

# 网络相关配置
PROXY_ENABLED = os.environ.get('PROXY_ENABLED', 'False').lower() == 'true'
PROXY_HTTP = os.environ.get('PROXY_HTTP', None)  # 例如: 'http://127.0.0.1:7890'
PROXY_HTTPS = os.environ.get('PROXY_HTTPS', None)  # 例如: 'http://127.0.0.1:7890'
CONNECTION_TIMEOUT = 30  # 连接超时时间（秒）
REQUEST_TIMEOUT = 60  # 请求超时时间（秒）
MAX_RETRIES = 3  # 最大重试次数

# 检测Firefox安装路径
def detect_firefox_path():
    system = platform.system()
    if system == "Windows":
        # 检查常见安装路径
        common_paths = [
            os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"),
            os.path.expandvars(r"%LocalAppData%\Mozilla Firefox\firefox.exe")
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
                
        # 尝试使用where命令查找
        try:
            result = subprocess.run(["where", "firefox"], 
                                    capture_output=True, 
                                    text=True, 
                                    check=False)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split('\n')[0]
        except Exception:
            pass
            
    elif system == "Linux":
        # 尝试使用which命令查找
        try:
            result = subprocess.run(["which", "firefox"], 
                                    capture_output=True, 
                                    text=True, 
                                    check=False)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
    
    elif system == "Darwin":  # macOS
        common_paths = [
            "/Applications/Firefox.app/Contents/MacOS/firefox",
            os.path.expanduser("~/Applications/Firefox.app/Contents/MacOS/firefox")
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
    
    return None

# 检测Chrome安装路径
def detect_chrome_path():
    system = platform.system()
    if system == "Windows":
        # 检查常见安装路径
        common_paths = [
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
                
        # 尝试使用where命令查找
        try:
            result = subprocess.run(["where", "chrome"], 
                                    capture_output=True, 
                                    text=True, 
                                    check=False)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split('\n')[0]
        except Exception:
            pass
            
    elif system == "Linux":
        # 尝试使用which命令查找
        try:
            result = subprocess.run(["which", "google-chrome"], 
                                    capture_output=True, 
                                    text=True, 
                                    check=False)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
    
    elif system == "Darwin":  # macOS
        common_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
    
    return None

# 浏览器相关配置
BROWSER_TYPE = 'chrome'  # 默认改为chrome，因为Firefox检测有问题
HEADLESS_MODE = True  # 是否使用无头模式
BROWSER_WIDTH = 1920
BROWSER_HEIGHT = 1080
BROWSER_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/120.0'
GECKODRIVER_LOG_PATH = 'log/selenium.log'  # 修改为现有的Selenium日志文件
DOWNLOAD_DRIVER = True  # 是否自动下载浏览器驱动
DRIVER_PATH = None  # 自定义浏览器驱动路径，None表示自动查找
FIREFOX_BINARY = detect_firefox_path()  # 自动检测Firefox安装路径
CHROME_BINARY = detect_chrome_path()  # 自动检测Chrome安装路径

# PDF生成相关配置
PDF_MARGIN_TOP = 0.4
PDF_MARGIN_BOTTOM = 0.4
PDF_MARGIN_LEFT = 0.4
PDF_MARGIN_RIGHT = 0.4
PDF_PAPER_WIDTH = 8.27  # A4纸宽度（英寸）
PDF_PAPER_HEIGHT = 11.69  # A4纸高度（英寸）

# 求职信和简历输出目录
RESUME_OUTPUT_DIR = "log/resume"  # 与现有目录结构匹配
COVER_LETTER_OUTPUT_DIR = "log/cover_letter"  # 与现有目录结构匹配
