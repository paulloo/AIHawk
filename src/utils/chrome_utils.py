import os
import time
import urllib.parse
import tempfile
import subprocess
import random
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from src.logging import logger
import config as cfg
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException
from datetime import datetime

class BrowserManager:
    """浏览器管理器单例类"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
            cls._instance.driver = None
            cls._instance.is_initialized = False
            cls._instance.restart_attempted = False  # 用于跟踪是否已尝试重启浏览器
        return cls._instance

    def initialize_browser(self):
        """初始化浏览器"""
        try:
            logger.info("开始初始化浏览器...")
            
            # 设置代理
            if cfg.PROXY_ENABLED and (cfg.PROXY_HTTP or cfg.PROXY_HTTPS):
                os.environ['HTTP_PROXY'] = cfg.PROXY_HTTP if cfg.PROXY_HTTP else ''
                os.environ['HTTPS_PROXY'] = cfg.PROXY_HTTPS if cfg.PROXY_HTTPS else ''
                logger.info(f"设置代理: HTTP={cfg.PROXY_HTTP}, HTTPS={cfg.PROXY_HTTPS}")
            
            browser_types = [cfg.BROWSER_TYPE.lower()]
            
            # 如果用户选择的浏览器不是chrome，添加chrome作为备选
            if cfg.BROWSER_TYPE.lower() != 'chrome':
                browser_types.append('chrome')
            
            # 如果既不是firefox也不是chrome，添加firefox作为另一个备选
            if cfg.BROWSER_TYPE.lower() not in ['firefox', 'chrome']:
                browser_types.append('firefox')
            
            # 尝试初始化浏览器，如果失败则尝试备选浏览器
            last_error = None
            for browser_type in browser_types:
                try:
                    logger.info(f"尝试初始化 {browser_type} 浏览器...")
                    
                    if browser_type == 'firefox':
                        self.driver = self._initialize_firefox()
                    elif browser_type == 'chrome':
                        self.driver = self._initialize_chrome()
                    elif browser_type == 'edge':
                        self.driver = self._initialize_edge()
                    else:
                        continue
                    
                    # 设置页面加载超时
                    self.driver.set_page_load_timeout(cfg.PAGE_LOAD_TIMEOUT)
                    self.driver.set_script_timeout(cfg.SCRIPT_TIMEOUT)
                    self.driver.implicitly_wait(cfg.IMPLICIT_WAIT)
                    
                    self.is_initialized = True
                    logger.info(f"{browser_type.capitalize()} 浏览器初始化成功")
                    
                    # 如果使用的不是首选浏览器，提示用户
                    if browser_type != browser_types[0]:
                        logger.warning(f"已使用备选浏览器 {browser_type.capitalize()} 代替 {browser_types[0].capitalize()}")
                    
                    return True
                    
                except Exception as e:
                    last_error = e
                    logger.error(f"初始化 {browser_type} 浏览器失败: {str(e)}")
                    # 继续尝试下一个浏览器类型
            
            # 如果所有浏览器类型都失败
            if last_error:
                logger.error(f"所有浏览器类型初始化均失败，最后错误: {str(last_error)}")
                logger.error("请确保您已安装至少一种受支持的浏览器：Firefox、Chrome 或 Edge")
                logger.error("如果已安装浏览器，请在config.py中设置正确的浏览器路径")
            
            self.is_initialized = False
            return False
            
        except Exception as e:
            logger.error(f"浏览器初始化过程中发生意外错误: {str(e)}")
            self.is_initialized = False
            return False
    
    def _initialize_firefox(self):
        """初始化 Firefox 浏览器"""
        try:
            logger.debug("初始化 Firefox 浏览器...")
            
            # 创建日志目录
            log_dir = os.path.dirname(cfg.GECKODRIVER_LOG_PATH)
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # 设置 Firefox 选项
            firefox_options = FirefoxOptions()
            if cfg.HEADLESS_MODE:
                firefox_options.add_argument('--headless')
            firefox_options.add_argument(f'--width={cfg.BROWSER_WIDTH}')
            firefox_options.add_argument(f'--height={cfg.BROWSER_HEIGHT}')
            
            # 设置用户代理
            firefox_options.set_preference('general.useragent.override', cfg.BROWSER_USER_AGENT)
            
            # 禁用 CORS 限制
            firefox_options.set_preference('security.fileuri.strict_origin_policy', False)
            firefox_options.set_preference('privacy.file_unique_origin', False)
            
            # 设置Firefox二进制文件路径
            firefox_found = False
            if hasattr(cfg, 'FIREFOX_BINARY') and cfg.FIREFOX_BINARY:
                logger.debug(f"使用配置中的 Firefox 路径: {cfg.FIREFOX_BINARY}")
                if os.path.exists(cfg.FIREFOX_BINARY):
                    firefox_options.binary_location = cfg.FIREFOX_BINARY
                    firefox_found = True
                else:
                    logger.warning(f"配置的Firefox路径不存在: {cfg.FIREFOX_BINARY}")
            
            if not firefox_found:
                logger.warning("未找到Firefox浏览器路径，尝试使用默认路径")
                
                # 尝试手动查找常见路径
                common_paths = []
                
                if os.name == 'nt':  # Windows
                    common_paths = [
                        r"C:\Program Files\Mozilla Firefox\firefox.exe",
                        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
                        os.path.expandvars(r"%LOCALAPPDATA%\Mozilla Firefox\firefox.exe"),
                        # 尝试特定的安装路径
                        r"C:\Program Files\Firefox Developer Edition\firefox.exe",
                        r"C:\Program Files\Firefox Nightly\firefox.exe",
                        # 可能从网站下载的便携版路径
                        os.path.expandvars(r"%USERPROFILE%\Downloads\Firefox\firefox.exe"),
                        os.path.expandvars(r"%USERPROFILE%\Desktop\Firefox\firefox.exe")
                    ]
                elif os.name == 'posix':  # Linux/Mac
                    common_paths = [
                        "/usr/bin/firefox",
                        "/usr/lib/firefox/firefox",
                        "/usr/local/bin/firefox",
                        "/snap/bin/firefox",
                        "/Applications/Firefox.app/Contents/MacOS/firefox",
                        os.path.expanduser("~/Applications/Firefox.app/Contents/MacOS/firefox")
                    ]
                
                for path in common_paths:
                    if os.path.exists(path):
                        logger.info(f"找到Firefox路径: {path}")
                        firefox_options.binary_location = path
                        firefox_found = True
                        break
            
            if not firefox_found:
                # 使用"where"或"which"命令查找Firefox
                try:
                    if os.name == 'nt':  # Windows
                        result = subprocess.run(["where", "firefox"], 
                                            capture_output=True, 
                                            text=True,
                                            encoding=cfg.DEFAULT_ENCODING,
                                            errors='replace')
                    else:  # Linux/Mac
                        result = subprocess.run(["which", "firefox"], 
                                            capture_output=True, 
                                            text=True,
                                            encoding=cfg.DEFAULT_ENCODING,
                                            errors='replace')
                    
                    if result.returncode == 0 and result.stdout.strip():
                        firefox_path = result.stdout.strip().split('\n')[0]
                        logger.info(f"通过系统命令找到Firefox路径: {firefox_path}")
                        firefox_options.binary_location = firefox_path
                        firefox_found = True
                except Exception as e:
                    logger.warning(f"通过系统命令查找Firefox失败: {e}")
            
            if not firefox_found:
                raise RuntimeError("无法找到Firefox浏览器，请在配置中指定正确的路径")
            
            # 使用自定义驱动路径或自动下载
            if cfg.DRIVER_PATH:
                logger.debug(f"使用自定义 Firefox 驱动路径: {cfg.DRIVER_PATH}")
                service = FirefoxService(executable_path=cfg.DRIVER_PATH, log_path=cfg.GECKODRIVER_LOG_PATH)
            elif cfg.DOWNLOAD_DRIVER:
                logger.debug("自动下载 Firefox 驱动")
                driver_path = GeckoDriverManager().install()
                service = FirefoxService(executable_path=driver_path, log_path=cfg.GECKODRIVER_LOG_PATH)
            else:
                logger.debug("使用系统默认 Firefox 驱动")
                service = FirefoxService(log_path=cfg.GECKODRIVER_LOG_PATH)
            
            # 初始化 Firefox 浏览器
            driver = webdriver.Firefox(service=service, options=firefox_options)
            logger.debug("Firefox 浏览器初始化成功")
            return driver
            
        except Exception as e:
            logger.error(f"初始化 Firefox 浏览器失败: {str(e)}")
            raise
    
    def _initialize_chrome(self):
        """初始化Chrome浏览器"""
        try:
            logger.debug("初始化 Chrome 浏览器...")
            
            # 设置Chrome选项
            chrome_options = ChromeOptions()
            if cfg.HEADLESS_MODE:
                chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument(f"--window-size={cfg.BROWSER_WIDTH},{cfg.BROWSER_HEIGHT}")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            
            # 添加用户代理
            chrome_options.add_argument(f"--user-agent={cfg.BROWSER_USER_AGENT}")
            
            # 添加代理支持
            if cfg.PROXY_ENABLED and (cfg.PROXY_HTTP or cfg.PROXY_HTTPS):
                chrome_options.add_argument(f"--proxy-server={cfg.PROXY_HTTP if cfg.PROXY_HTTP else cfg.PROXY_HTTPS}")
            
            # 尝试找到Chrome二进制文件
            chrome_binary = None
            try:
                chrome_binary = self._find_chrome_binary()
                logger.debug(f"找到Chrome二进制文件: {chrome_binary}")
                chrome_options.binary_location = str(chrome_binary)
            except Exception as e:
                logger.warning(f"未找到Chrome二进制文件: {e}")
                # 尝试继续，让WebDriver管理器处理
            
            # 初始化WebDriver
            try:
                driver = webdriver.Chrome(
                    service=ChromeService(ChromeDriverManager().install()),
                    options=chrome_options
                )
            except Exception as chrome_error:
                logger.error(f"使用ChromeDriverManager初始化失败: {chrome_error}")
                # 尝试使用不同的方式初始化
                try:
                    driver = webdriver.Chrome(options=chrome_options)
                    logger.info("使用默认Chrome驱动初始化成功")
                except Exception as e:
                    logger.error(f"使用默认Chrome驱动初始化也失败: {e}")
                    raise chrome_error  # 抛出原始错误
            
            # 设置页面加载超时
            driver.set_page_load_timeout(cfg.PAGE_LOAD_TIMEOUT)
            
            # 注入JavaScript来隐藏自动化特征
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                """
            })
            
            logger.debug("Chrome 浏览器初始化成功")
            return driver
            
        except Exception as e:
            logger.error(f"Chrome 浏览器初始化失败: {str(e)}")
            raise
    
    def _initialize_edge(self):
        """初始化 Edge 浏览器"""
        try:
            logger.debug("初始化 Edge 浏览器...")
            
            # 设置 Edge 选项
            edge_options = EdgeOptions()
            if cfg.HEADLESS_MODE:
                edge_options.add_argument('--headless')
            edge_options.add_argument('--no-sandbox')
            edge_options.add_argument('--disable-dev-shm-usage')
            edge_options.add_argument('--disable-gpu')
            edge_options.add_argument(f'--window-size={cfg.BROWSER_WIDTH},{cfg.BROWSER_HEIGHT}')
            
            # 设置用户代理
            edge_options.add_argument(f'--user-agent={cfg.BROWSER_USER_AGENT}')
            
            # 添加代理支持
            if cfg.PROXY_ENABLED and (cfg.PROXY_HTTP or cfg.PROXY_HTTPS):
                edge_options.add_argument(f"--proxy-server={cfg.PROXY_HTTP if cfg.PROXY_HTTP else cfg.PROXY_HTTPS}")
            
            # 使用自定义驱动路径或自动下载
            if cfg.DRIVER_PATH:
                logger.debug(f"使用自定义 Edge 驱动路径: {cfg.DRIVER_PATH}")
                service = EdgeService(executable_path=cfg.DRIVER_PATH)
            elif cfg.DOWNLOAD_DRIVER:
                logger.debug("自动下载 Edge 驱动")
                driver_path = EdgeChromiumDriverManager().install()
                service = EdgeService(executable_path=driver_path)
            else:
                logger.debug("使用系统默认 Edge 驱动")
                service = EdgeService()
            
            # 初始化 Edge 浏览器
            driver = webdriver.Edge(service=service, options=edge_options)
            logger.debug("Edge 浏览器初始化成功")
            return driver
            
        except Exception as e:
            logger.error(f"初始化 Edge 浏览器失败: {str(e)}")
            raise

    def get_page_content(self, url, wait_for_selector=None, wait_time=10, click_selectors=None, scroll=False, scroll_wait=1, max_scrolls=5, execute_scripts=None, cookies=None, check_content_size=True, browser_options=None):
        """
        获取页面内容，支持等待特定元素、点击元素和滚动页面
        
        Args:
            url: 页面URL
            wait_for_selector: 等待特定元素出现的CSS选择器
            wait_time: 页面加载后等待的基本时间(秒)
            click_selectors: 需要点击的元素的CSS选择器列表
            scroll: 是否滚动页面以加载更多内容
            scroll_wait: 每次滚动后等待的时间(秒)
            max_scrolls: 最大滚动次数
            execute_scripts: 要执行的JavaScript脚本列表
            cookies: 要添加的cookies列表，每个cookie为字典
            check_content_size: 是否检查内容大小
            browser_options: 浏览器配置选项，包括headers、stealth_mode、random_delay等
            
        Returns:
            str: 页面HTML内容
        """
        if not self.is_initialized:
            if not self.initialize_browser():
                raise Exception("浏览器初始化失败")
        
        # 处理browser_options参数
        headers = None
        stealth_mode = False
        random_delay = False
        emulate_device = None
        disable_images = False
        page_load_strategy = None
        
        if browser_options:
            headers = browser_options.get("headers")
            stealth_mode = browser_options.get("stealth_mode", False)
            random_delay = browser_options.get("random_delay", False)
            emulate_device = browser_options.get("emulate_device")
            disable_images = browser_options.get("disable_images", False)
            page_load_strategy = browser_options.get("page_load_strategy")
        
        # 尝试多次获取页面内容
        for attempt in range(cfg.MAX_RETRIES):
            try:
                logger.info(f"正在访问页面: {url} (尝试 {attempt + 1}/{cfg.MAX_RETRIES})")
                
                # 设置页面加载策略
                if page_load_strategy:
                    try:
                        # 可选值: normal, eager, none
                        # normal (默认) - 等待所有资源加载完成
                        # eager - 仅等待HTML和DOM完成
                        # none - 不等待任何资源加载
                        self.driver.execute_cdp_cmd('Page.setDocumentContent', {'content': ''})
                        self.driver.execute_cdp_cmd('Page.setLifecycleEventsEnabled', {'enabled': True})
                        
                        if page_load_strategy == 'eager':
                            logger.info("使用eager页面加载策略，仅等待DOM完成")
                            self.driver.execute_cdp_cmd('Network.setBlockedURLs', {
                                "urls": ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.css", "*.woff", "*.woff2", "*.ttf"]
                            })
                        elif page_load_strategy == 'none':
                            logger.info("使用none页面加载策略，不等待任何资源加载")
                            self.driver.execute_cdp_cmd('Network.setBlockedURLs', {
                                "urls": ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.css", "*.js", "*.woff", "*.woff2", "*.ttf"]
                            })
                        elif page_load_strategy == 'normal':
                            logger.info("使用normal页面加载策略，等待所有资源加载")
                        else:
                            logger.warning(f"未知的页面加载策略: {page_load_strategy}，使用默认策略")
                        
                        self.driver.execute_cdp_cmd('Network.enable', {})
                    except Exception as e:
                        logger.warning(f"设置页面加载策略失败: {str(e)}")
                
                # 应用隐身模式脚本，使浏览器更难被识别为自动化工具
                if stealth_mode:
                    logger.info("应用隐身模式以避免被检测为自动化工具")
                    stealth_script = """
                    // 覆盖navigator对象的一些属性，使其看起来更像真实浏览器
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => false
                    });
                    
                    // 清除自动化相关的标志
                    if (window.navigator.plugins) {
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => {
                                return {
                                    length: 5,
                                    item: function(index) { return this[index]; },
                                    0: {name: 'Chrome PDF Plugin'},
                                    1: {name: 'Chrome PDF Viewer'},
                                    2: {name: 'Native Client'},
                                    3: {name: 'Widevine Content Decryption Module'},
                                    4: {name: 'Microsoft Edge PDF Plugin'}
                                };
                            }
                        });
                    }
                    
                    // 添加语言和平台信息
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['zh-CN', 'zh', 'en-US', 'en']
                    });
                    
                    // 移除自动化测试标记
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                    );
                    
                    // 调整Chrome对象
                    if (window.chrome) {
                        window.chrome.runtime = {};
                    }
                    """
                    try:
                        self.driver.execute_script(stealth_script)
                        logger.debug("隐身模式脚本执行成功")
                    except Exception as e:
                        logger.warning(f"隐身模式脚本执行失败: {str(e)}")
                
                # 禁用图片加载以提高速度（如果需要）
                if disable_images:
                    logger.info("禁用图片加载以提高速度")
                    try:
                        self.driver.execute_cdp_cmd('Network.setBlockedURLs', {"urls": ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp"]})
                        self.driver.execute_cdp_cmd('Network.enable', {})
                    except Exception as e:
                        logger.warning(f"禁用图片加载失败: {str(e)}")
                
                # 设置设备模拟（如桌面、手机等）
                if emulate_device:
                    try:
                        if emulate_device.lower() == "mobile":
                            # 模拟移动设备
                            mobile_emulation = {
                                "deviceMetrics": { "width": 360, "height": 640, "pixelRatio": 3.0 },
                                "userAgent": "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
                            }
                            self.driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', mobile_emulation['deviceMetrics'])
                            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": mobile_emulation['userAgent']})
                            logger.info("已启用移动设备模拟")
                        elif emulate_device.lower() == "tablet":
                            # 模拟平板设备
                            tablet_emulation = {
                                "deviceMetrics": { "width": 768, "height": 1024, "pixelRatio": 2.0 },
                                "userAgent": "Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
                            }
                            self.driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', tablet_emulation['deviceMetrics'])
                            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": tablet_emulation['userAgent']})
                            logger.info("已启用平板设备模拟")
                    except Exception as e:
                        logger.warning(f"设备模拟设置失败: {str(e)}")
                
                # 设置自定义请求头（如果有）
                if headers:
                    try:
                        # 应用User-Agent
                        if "User-Agent" in headers:
                            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": headers["User-Agent"]})
                        
                        # 添加其他请求头
                        header_script = """
                        // 修改XMLHttpRequest以添加自定义头
                        const originalOpen = XMLHttpRequest.prototype.open;
                        XMLHttpRequest.prototype.open = function(method, url) {
                            originalOpen.apply(this, arguments);
                            
                            // 添加自定义请求头
                            """
                        
                        for header_name, header_value in headers.items():
                            if header_name not in ["User-Agent"]:  # User-Agent已单独处理
                                header_script += f'this.setRequestHeader("{header_name}", "{header_value}");\n'
                        
                        header_script += """
                        };
                        """
                        
                        self.driver.execute_script(header_script)
                        logger.info("已设置自定义请求头")
                    except Exception as e:
                        logger.warning(f"设置自定义请求头失败: {str(e)}")
                
                # 如果有cookies，先添加
                if cookies:
                    logger.info(f"添加 {len(cookies) if isinstance(cookies, list) else '未知数量'} 个cookies")
                    # 先访问域名根路径
                    domain = url.split('/')[2]
                    domain_url = f"{url.split(':')[0]}://{domain}"
                    self.driver.get(domain_url)
                    
                    # 随机延迟以模拟人类行为
                    if random_delay:
                        delay = random.uniform(1.0, 3.0)
                        time.sleep(delay)
                    else:
                        time.sleep(2)
                    
                    # 添加cookies
                    if isinstance(cookies, list):
                        for cookie in cookies:
                            try:
                                self.driver.add_cookie(cookie)
                                logger.debug(f"添加cookie: {cookie.get('name')}")
                            except Exception as e:
                                logger.warning(f"添加cookie失败: {str(e)}")
                    elif isinstance(cookies, dict):
                        # 如果cookies是字典格式
                        for name, value in cookies.items():
                            try:
                                self.driver.add_cookie({"name": name, "value": value, "domain": domain})
                                logger.debug(f"添加cookie: {name}")
                            except Exception as e:
                                logger.warning(f"添加cookie失败: {str(e)}")
                    
                    logger.info("所有cookies添加完成，准备重新加载页面")
                    # 随机延迟
                    if random_delay:
                        time.sleep(random.uniform(0.5, 1.5))
                    else:
                        time.sleep(1)
                
                # 访问目标URL
                self.driver.get(url)
                
                # 等待页面基本加载
                logger.info(f"等待页面加载，基本等待时间: {wait_time}秒")
                if random_delay:
                    actual_wait = wait_time + random.uniform(-1.0, 1.0)
                    actual_wait = max(1.0, actual_wait)  # 确保至少等待1秒
                    time.sleep(actual_wait)
                    logger.debug(f"随机等待时间: {actual_wait:.2f}秒")
                else:
                    time.sleep(wait_time)
                
                # 检查页面是否加载完成
                ready_state = self.driver.execute_script("return document.readyState")
                if ready_state != "complete":
                    logger.warning(f"页面未完全加载，状态: {ready_state}")
                    # 继续等待一段时间
                    extra_wait = 5
                    if random_delay:
                        extra_wait += random.uniform(0, 3)
                    logger.info(f"页面未完全加载，额外等待{extra_wait:.1f}秒")
                    time.sleep(extra_wait)
                else:
                    logger.info("页面加载完成")
                
                # 获取页面标题和URL，用于调试
                page_title = self.driver.title
                current_url = self.driver.current_url
                logger.info(f"当前页面标题: {page_title}, URL: {current_url}")
                
                # 检测是否需要登录（针对LinkedIn）
                if "linkedin.com" in url.lower() and ("login" in current_url.lower() or "sign-in" in current_url.lower()):
                    logger.warning("检测到LinkedIn登录页面，需要提供登录凭据")
                    # 这里可以添加自动登录的代码，或返回特殊状态
                    raise Exception("LinkedIn需要登录，请提供有效的登录Cookie")
                
                # 等待特定元素出现
                if wait_for_selector:
                    logger.info(f"等待元素出现: {wait_for_selector}")
                    try:
                        element = WebDriverWait(self.driver, wait_time).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
                        )
                        logger.info(f"元素已找到: {wait_for_selector}")
                        # 随机模拟人类行为 - 鼠标移动到元素上
                        if random_delay and not emulate_device:  # 移动设备不需要模拟鼠标移动
                            try:
                                action = ActionChains(self.driver)
                                action.move_to_element(element).perform()
                                logger.debug("已移动鼠标到目标元素")
                                time.sleep(random.uniform(0.3, 0.8))
                            except Exception as e:
                                logger.warning(f"鼠标移动失败: {str(e)}")
                    except TimeoutException:
                        logger.warning(f"等待元素超时: {wait_for_selector}")
                    except Exception as e:
                        logger.warning(f"等待元素时出错: {str(e)}")
                
                # 执行自定义JavaScript
                if execute_scripts:
                    for script in execute_scripts:
                        try:
                            logger.info(f"执行JavaScript脚本: {script[:50]}{'...' if len(script) > 50 else ''}")
                            self.driver.execute_script(script)
                            
                            # 随机延迟以模拟人类行为
                            if random_delay:
                                time.sleep(random.uniform(0.2, 1.0))
                            else:
                                time.sleep(0.5)
                        except Exception as e:
                            logger.warning(f"执行JavaScript脚本失败: {str(e)}")
                
                # 点击指定的元素
                if click_selectors:
                    for selector in click_selectors:
                        try:
                            logger.info(f"尝试点击元素: {selector}")
                            # 首先尝试用 JavaScript 点击，然后回退到 Selenium 点击
                            try:
                                element = WebDriverWait(self.driver, 5).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                                )
                                
                                # 随机模拟人类行为 - 鼠标移动和延迟
                                if random_delay and not emulate_device:
                                    try:
                                        action = ActionChains(self.driver)
                                        action.move_to_element(element).pause(random.uniform(0.1, 0.3)).perform()
                                    except Exception as e:
                                        logger.debug(f"鼠标移动模拟失败: {str(e)}")
                                
                                # 使用JavaScript点击
                                self.driver.execute_script("arguments[0].click();", element)
                                logger.info(f"成功通过JavaScript点击元素: {selector}")
                            except Exception as js_e:
                                logger.warning(f"JavaScript点击失败，尝试Selenium点击: {str(js_e)}")
                                try:
                                    element = WebDriverWait(self.driver, 5).until(
                                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                                    )
                                    element.click()
                                    logger.info(f"成功通过Selenium点击元素: {selector}")
                                except Exception as sel_e:
                                    logger.error(f"Selenium点击也失败: {str(sel_e)}")
                                    continue
                            
                            # 点击后等待页面响应
                            wait_after_click = 2
                            if random_delay:
                                wait_after_click = random.uniform(1.5, 3.0)
                            logger.info(f"点击后等待页面响应 {wait_after_click:.1f} 秒")
                            time.sleep(wait_after_click)
                            
                        except TimeoutException:
                            logger.warning(f"查找点击元素超时: {selector}")
                        except Exception as e:
                            logger.warning(f"点击元素时发生错误: {str(e)}")
                
                # 滚动页面以加载更多内容
                if scroll:
                    logger.info(f"开始滚动页面，最大滚动次数: {max_scrolls}")
                    
                    last_height = self.driver.execute_script("return document.body.scrollHeight")
                    scroll_count = 0
                    
                    while scroll_count < max_scrolls:
                        # 滚动到页面底部
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        
                        # 添加随机滚动行为以模拟人类
                        if random_delay:
                            # 有时随机滚动回上方一点
                            if random.random() < 0.3:  # 30%的概率
                                scroll_up = random.uniform(100, 300)
                                self.driver.execute_script(f"window.scrollBy(0, -{scroll_up});")
                                logger.debug(f"随机向上滚动 {scroll_up:.0f} 像素")
                                time.sleep(random.uniform(0.3, 0.7))
                        
                        # 等待页面加载
                        actual_scroll_wait = scroll_wait
                        if random_delay:
                            actual_scroll_wait = scroll_wait + random.uniform(-0.5, 0.8)
                            actual_scroll_wait = max(0.5, actual_scroll_wait)  # 确保最少等待0.5秒
                        
                        logger.debug(f"滚动等待时间: {actual_scroll_wait:.1f}秒")
                        time.sleep(actual_scroll_wait)
                        
                        # 计算新的滚动高度并与最后的滚动高度进行比较
                        new_height = self.driver.execute_script("return document.body.scrollHeight")
                        if new_height == last_height:
                            # 尝试再次滚动，有时第一次滚动可能没有触发加载
                            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(actual_scroll_wait)
                            
                            new_height = self.driver.execute_script("return document.body.scrollHeight")
                            if new_height == last_height:
                                logger.info("页面高度未变化，停止滚动")
                                break
                        
                        last_height = new_height
                        scroll_count += 1
                        logger.info(f"完成第 {scroll_count}/{max_scrolls} 次滚动")
                
                # 获取页面内容
                content = self.driver.page_source
                
                # 检查内容大小（如果需要）
                if check_content_size and content:
                    content_size = len(content)
                    if content_size < 1000:  # 内容太小可能表示加载不完整
                        logger.warning(f"页面内容大小过小 ({content_size} 字节)，可能未完全加载")
                        
                        # 再等待一段时间并重新获取
                        extra_wait = 5
                        if random_delay:
                            extra_wait += random.uniform(0, 3)
                        logger.info(f"内容过小，额外等待 {extra_wait:.1f} 秒")
                        time.sleep(extra_wait)
                        
                        # 再次尝试获取内容
                        content = self.driver.page_source
                        new_size = len(content)
                        
                        logger.info(f"重新获取内容大小: {new_size} 字节 (之前: {content_size} 字节)")
                    else:
                        logger.info(f"页面内容大小: {content_size} 字节")
                
                logger.info(f"成功获取页面内容: {url}")
                return content
                
            except Exception as e:
                logger.error(f"获取页面内容时出错: {str(e)}")
                # 捕获页面截图以便调试
                try:
                    screenshot_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "screenshots")
                    os.makedirs(screenshot_dir, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"error_{timestamp}_{attempt}.png"
                    screenshot_path = os.path.join(screenshot_dir, filename)
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"错误截图已保存: {screenshot_path}")
                except Exception as ss_e:
                    logger.warning(f"无法保存错误截图: {str(ss_e)}")
                
                if attempt < cfg.MAX_RETRIES - 1:
                    wait_time = (attempt + 1) * 3  # 递增等待时间
                    logger.info(f"将在 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    # 尝试刷新浏览器状态
                    try:
                        self.driver.delete_all_cookies()
                        self.driver.execute_script("window.localStorage.clear();")
                        self.driver.execute_script("window.sessionStorage.clear();")
                        logger.info("已清除cookies和存储")
                    except Exception as clear_e:
                        logger.warning(f"清除浏览器状态时出错: {str(clear_e)}")
                else:
                    logger.error(f"达到最大重试次数 ({cfg.MAX_RETRIES})，放弃获取页面内容")
                    if self.auto_restart and not self.restart_attempted:
                        logger.info("尝试重启浏览器...")
                        self.restart_attempted = True
                        self.close_browser()
                        time.sleep(5)
                        if self.initialize_browser():
                            logger.info("浏览器已重启，再次尝试获取页面内容")
                            # 递归调用，但不传递restart_attempted标志，以避免无限循环
                            return self.get_page_content(url, wait_for_selector, wait_time, 
                                                      click_selectors, scroll, scroll_wait, 
                                                      max_scrolls, execute_scripts, cookies, 
                                                      check_content_size, browser_options)
                        else:
                            logger.error("浏览器重启失败")
        
        # 所有尝试都失败
        logger.error(f"无法获取页面内容: {url}")
        return None

    def get_driver(self):
        """获取浏览器驱动实例"""
        if not self.is_initialized:
            self.initialize_browser()
        return self.driver

    def close(self):
        """关闭浏览器"""
        if self.driver:
            try:
                # 首先尝试正常关闭
                try:
                    self.driver.quit()
                    logger.info("浏览器已正常关闭")
                except Exception as e:
                    logger.warning(f"正常关闭浏览器失败，尝试强制关闭: {str(e)}")
                    # 如果正常关闭失败，尝试强制关闭
                    try:
                        self.driver.close()
                        logger.info("浏览器已强制关闭")
                    except Exception as e:
                        logger.error(f"强制关闭浏览器失败: {str(e)}")
                    finally:
                        # 确保状态被重置
                        self.is_initialized = False
                        self.driver = None
                        self.restart_attempted = False  # 重置重启标志
                        logger.info("浏览器状态已重置")
            except Exception as e:
                logger.error(f"关闭浏览器时发生意外错误: {str(e)}")
                # 确保状态被重置
                self.is_initialized = False
                self.driver = None
                self.restart_attempted = False  # 重置重启标志

    def close_browser(self):
        """关闭浏览器并重置状态，供get_page_content使用"""
        self.close()  # 复用已有的关闭逻辑

    def _find_chrome_binary(self) -> Path:
        """Find the Chrome binary on the system."""
        logger.debug("Looking for Chrome binary...")
        
        if os.name == 'nt':  # Windows
            try:
                result = subprocess.run(
                    ["where", "chrome"], 
                    capture_output=True, 
                    text=True,
                    encoding=cfg.DEFAULT_ENCODING,
                    errors='replace'  # 替换无法解码的字符
                )
                
                if result.returncode == 0:
                    # 第一行是可执行文件路径
                    chrome_path = result.stdout.strip().split('\n')[0]
                    logger.debug(f"Chrome found at: {chrome_path}")
                    return Path(chrome_path)
                else:
                    # 检查常见安装位置
                    logger.debug("Chrome not found with 'where', checking common locations...")
                    common_locations = [
                        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
                        Path(os.environ.get('LOCALAPPDATA', '')) / "Google/Chrome/Application/chrome.exe",
                    ]
                    
                    for location in common_locations:
                        if location.exists():
                            logger.debug(f"Chrome found at common location: {location}")
                            return location
            except Exception as e:
                logger.error(f"Error finding Chrome on Windows: {e}")
        else:  # Linux/Mac
            try:
                result = subprocess.run(
                    ["which", "google-chrome"], 
                    capture_output=True, 
                    text=True,
                    encoding=cfg.DEFAULT_ENCODING,
                    errors='replace'  # 替换无法解码的字符
                )
                
                if result.returncode == 0:
                    chrome_path = result.stdout.strip()
                    logger.debug(f"Chrome found at: {chrome_path}")
                    return Path(chrome_path)
                else:
                    # 尝试其他名字和位置
                    alternatives = ["google-chrome-stable", "chromium", "chromium-browser"]
                    for alt in alternatives:
                        result = subprocess.run(
                            ["which", alt], 
                            capture_output=True, 
                            text=True,
                            encoding=cfg.DEFAULT_ENCODING,
                            errors='replace'
                        )
                        if result.returncode == 0:
                            chrome_path = result.stdout.strip()
                            logger.debug(f"Chrome alternative found at: {chrome_path}")
                            return Path(chrome_path)
                    
                    # 检查Mac上的常见位置
                    mac_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
                    if mac_path.exists():
                        logger.debug(f"Chrome found at Mac location: {mac_path}")
                        return mac_path
            except Exception as e:
                logger.error(f"Error finding Chrome on Linux/Mac: {e}")
        
        raise FileNotFoundError("Unable to find Chrome browser on your system")

# 创建单例实例
browser_manager = BrowserManager()

def init_browser():
    """
    初始化并返回一个浏览器实例
    
    Returns:
        WebDriver: 浏览器驱动实例
    """
    try:
        return browser_manager.get_driver()
    except Exception as e:
        logger.error(f"浏览器初始化失败: {str(e)}")
        raise RuntimeError(f"浏览器初始化失败: {str(e)}")

def HTML_to_PDF(html_content, driver=None):
    """
    将 HTML 内容转换为 PDF
    
    Args:
        html_content (str): 要转换的 HTML 内容
        driver (WebDriver, optional): 现有的浏览器驱动实例
        
    Returns:
        str: Base64 编码的 PDF 内容
    """
    try:
        logger.info("开始将 HTML 转换为 PDF...")
        
        # 如果没有提供 driver，使用 browser_manager 初始化一个新的
        if driver is None:
            driver = browser_manager.get_driver()
        
        # 创建临时 HTML 文件
        with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            temp_path = f.name
        
        try:
            # 加载 HTML 文件
            driver.get(f'file:///{temp_path}')
            time.sleep(2)  # 等待页面加载
            
            # 获取页面高度
            height = driver.execute_script('return document.body.scrollHeight')
            driver.set_window_size(cfg.BROWSER_WIDTH, height)
            
            # 配置 PDF 打印选项
            print_options = {
                "printBackground": True,
                "landscape": False,
                "paperWidth": cfg.PDF_PAPER_WIDTH,
                "paperHeight": cfg.PDF_PAPER_HEIGHT,
                "marginTop": cfg.PDF_MARGIN_TOP,
                "marginBottom": cfg.PDF_MARGIN_BOTTOM,
                "marginLeft": cfg.PDF_MARGIN_LEFT,
                "marginRight": cfg.PDF_MARGIN_RIGHT,
                "displayHeaderFooter": False,
                "preferCSSPageSize": True,
                "scale": 1.0,
                "transferMode": "ReturnAsBase64"
            }

            # 执行 PDF 转换
            # 针对不同浏览器使用不同的 PDF 生成方法
            browser_type = cfg.BROWSER_TYPE.lower()
            pdf_base64 = None
            
            if browser_type == 'firefox':
                pdf_data = driver.print_page()
                return pdf_data
            else:  # Chrome 和 Edge 使用 CDP 命令
                pdf_base64 = driver.execute_cdp_cmd("Page.printToPDF", print_options)
                if not pdf_base64 or 'data' not in pdf_base64:
                    raise RuntimeError("PDF生成失败：未返回有效数据")
                return pdf_base64['data']
            
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {str(e)}")
        
    except Exception as e:
        logger.error(f"HTML 转换为 PDF 失败: {str(e)}")
        raise
