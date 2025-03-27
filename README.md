# Jobs Applier AI Agent - AIHawk 🦅

一个智能求职助手，帮助您自动生成针对特定职位的定制简历和求职信。

## 功能特点

- **智能定制简历**：根据职位描述智能定制简历内容
- **专业求职信生成**：生成专业、有针对性的求职信
- **LinkedIn 职位解析**：自动提取 LinkedIn 职位信息
- **多模型支持**：支持 OpenAI 和 Ollama 本地模型
- **模拟数据模式**：当无法访问 LinkedIn 时，使用模拟数据生成功能
- **反爬虫机制**：内置反爬虫功能，减少被封禁风险
- **多浏览器支持**：支持 Chrome、Firefox 和 Edge 浏览器
- **多样化简历样式**：提供多种简历和求职信样式选择
- **PDF 导出**：生成专业的 PDF 格式简历和求职信

## 安装要求

- Python 3.8+
- Chrome、Firefox 或 Edge 浏览器
- Ollama（可选，用于本地模型）或 OpenAI API 密钥

## 安装步骤

1. 克隆仓库：
   ```bash
   git clone https://github.com/yourusername/Jobs_Applier_AI_Agent_AIHawk.git
   cd Jobs_Applier_AI_Agent_AIHawk
   ```

2. 创建并激活虚拟环境：
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

4. 配置 `.env` 文件（可选，如果使用 OpenAI）：
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

## 使用方法

1. 启动程序：
   ```bash
   python main.py
   ```

2. 选择要执行的操作：
   - 生成针对职位描述的简历
   - 生成针对职位描述的求职信

3. 按照提示输入信息：
   - 选择样式
   - 输入职位链接
   - 提供个人信息

4. 程序将自动：
   - 解析职位信息
   - 生成定制化内容
   - 创建 PDF 文件

## 配置选项

在 `config.py` 中可以调整以下配置：

- **模型类型**：设置 `MODEL_TYPE` 为 "ollama" 或 "openai"
- **模型名称**：通过 `MODEL` 指定使用的具体模型
- **API 密钥**：设置 OpenAI API 密钥（如果使用 OpenAI）
- **浏览器设置**：选择浏览器类型、设置代理等
- **模拟数据模式**：配置无法访问 LinkedIn 时的备选方案

## 新功能

- **LinkedIn 反爬虫支持**：添加了高级反爬虫功能，使用随机用户代理和行为模拟
- **本地模型增强**：优化了 Ollama 模型的参数配置，提高了生成质量
- **模拟数据支持**：即使无法访问 LinkedIn，也能生成相关的简历和求职信
- **错误处理优化**：增强了错误捕获和恢复机制
- **浏览器多重备选**：如首选浏览器失败，会自动尝试备选浏览器

## 常见问题

**Q: 为什么我无法访问 LinkedIn 职位？**
A: LinkedIn 有反爬虫机制。尝试设置代理或使用模拟数据模式。

**Q: 如何使用本地 Ollama 模型？**
A: 安装 Ollama，启动服务，然后在配置中设置 `MODEL_TYPE="ollama"`。

**Q: 生成的 PDF 有问题怎么办？**
A: 确保正确安装了浏览器，并在配置中设置了正确的路径。

## 贡献

欢迎提交 Pull Request 或创建 Issue 来帮助改进这个项目！

## 许可证

MIT
