"""
字符串配置文件 - 提供用于简历和求职信的提示模板
"""

# 简历模板
prompt_header = """
你需要按照标准HTML格式输出一个简历的Header部分。
基于下面的个人信息：
{personal_information}

如果工作描述提供了，请考虑这些信息：
{job_description}

生成一个专业的简历标题部分，包含姓名、联系信息和专业摘要。
"""

prompt_education = """
你需要按照标准HTML格式输出一个简历的Education部分。
基于下面的教育经历：
{education_details}

如果工作描述提供了，请考虑这些信息：
{job_description}

生成一个专业的教育经历部分，按照时间倒序排列。
"""

prompt_working_experience = """
你需要按照标准HTML格式输出一个简历的Work Experience部分。
基于下面的工作经历：
{experience_details}

如果工作描述提供了，请考虑这些信息：
{job_description}

生成一个专业的工作经历部分，突出与目标职位相关的技能和成就。按照时间倒序排列。
"""

prompt_projects = """
你需要按照标准HTML格式输出一个简历的Projects部分。
基于下面的项目经历：
{projects}

如果工作描述提供了，请考虑这些信息：
{job_description}

生成一个专业的项目经历部分，突出与目标职位相关的技术和成就。
"""

prompt_achievements = """
你需要按照标准HTML格式输出一个简历的Achievements & Certifications部分。
基于下面的成就和证书：
{achievements}
{certifications}

如果工作描述提供了，请考虑这些信息：
{job_description}

生成一个专业的成就和证书部分，突出最相关的内容。
"""

prompt_additional_skills = """
你需要按照标准HTML格式输出一个简历的Additional Skills部分。
基于下面的技能列表：
语言: {languages}
兴趣: {interests}
技能: {skills}

如果工作描述提供了，请考虑这些信息：
{job_description}

生成一个专业的附加技能部分，突出最相关的技能。
"""

prompt_certifications = """
你需要按照标准HTML格式输出一个简历的Certifications部分。
基于下面的证书信息：
{certifications}

如果工作描述提供了，请考虑这些信息：
{job_description}

生成一个专业的证书部分，突出最相关的证书。
"""

summarize_prompt_template = """
请根据以下文本生成一个简短的摘要，突出最重要的信息：

{text}

请提供一个简洁的摘要，不超过200字。
"""

# 求职信模板
prompt_cover_letter = """
生成一封针对以下信息的专业求职信。使用清晰的段落和适当的格式。

简历信息：
{resume}

职位名称：
{job_title}

公司名称：
{company}

请确保包含以下部分：
1. 一个正式的问候语，使用公司名称（例如"尊敬的{company}招聘团队："）
2. 一个简短的介绍段落，包含应聘者的姓名和专业背景
3. 一个明确表明申请的职位名称({job_title})和公司名称的段落
4. 2-3个描述应聘者为何是该职位理想人选的段落
5. 一个总结段落，表达对进一步沟通的期待
6. 一个适当的结束语和签名

求职信应当使用HTML格式输出，包含适当的HTML标签（如<div>、<p>、<h1>等标签）。整体设计应简洁专业，易于阅读。
"""

# 求职信模板 (带工作描述)
prompt_cover_letter_job_description = """
生成一封针对以下信息的专业求职信。使用清晰的段落和适当的格式。

简历信息：
{resume}

职位描述：
{job_description}

职位名称：
{job_title}

公司名称：
{company}

请确保包含以下部分：
1. 一个正式的问候语，使用公司名称（例如"尊敬的{company}招聘团队："）
2. 一个简短的介绍段落，包含应聘者的姓名和专业背景
3. 一个明确表明申请的职位名称({job_title})和公司名称的段落
4. 2-3个描述应聘者为何是该职位理想人选的段落，突出与职位描述相匹配的技能和经验
5. 一个强调对公司价值观和文化认同的段落
6. 一个总结段落，表达对进一步沟通的期待
7. 一个适当的结束语和签名

求职信应当使用HTML格式输出，包含适当的HTML标签（如<div>、<p>、<h1>等标签）。整体设计应简洁专业，易于阅读。
""" 