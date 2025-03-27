"""
This module contains utility functions for the Resume and Cover Letter Builder service.
"""

# app/libs/resume_and_cover_builder/utils.py
import json
import openai
import time
from datetime import datetime
from typing import Dict, List, Optional, Union, Any
from langchain_core.messages.ai import AIMessage
from langchain_core.prompt_values import StringPromptValue
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from loguru import logger
from requests.exceptions import HTTPError as HTTPStatusError
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
)
from src.libs.resume_and_cover_builder.config import global_config
from pydantic import Field, PrivateAttr, BaseModel


class LLMLogger:

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    @staticmethod
    def log_request(prompts, parsed_reply: Dict[str, Dict]):
        calls_log = global_config.LOG_OUTPUT_FILE_PATH / "open_ai_calls.json"
        if isinstance(prompts, StringPromptValue):
            prompts = prompts.text
        elif isinstance(prompts, Dict):
            # Convert prompts to a dictionary if they are not in the expected format
            prompts = {
                f"prompt_{i+1}": prompt.content
                for i, prompt in enumerate(prompts.messages)
            }
        else:
            prompts = {
                f"prompt_{i+1}": prompt.content
                for i, prompt in enumerate(prompts.messages)
            }

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Extract token usage details from the response
        token_usage = parsed_reply["usage_metadata"]
        output_tokens = token_usage["output_tokens"]
        input_tokens = token_usage["input_tokens"]
        total_tokens = token_usage["total_tokens"]

        # Extract model details from the response
        model_name = parsed_reply["response_metadata"]["model_name"]
        prompt_price_per_token = 0.00000015
        completion_price_per_token = 0.0000006

        # Calculate the total cost of the API call
        total_cost = (input_tokens * prompt_price_per_token) + (
            output_tokens * completion_price_per_token
        )

        # Create a log entry with all relevant information
        log_entry = {
            "model": model_name,
            "time": current_time,
            "prompts": prompts,
            "replies": parsed_reply["content"],  # Response content
            "total_tokens": total_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_cost": total_cost,
        }

        # Write the log entry to the log file in JSON format
        with open(calls_log, "a", encoding="utf-8") as f:
            json_string = json.dumps(log_entry, ensure_ascii=False, indent=4)
            f.write(json_string + "\n")


class LoggerChatModel:
    """
    包装LLM模型以提供日志记录功能的类
    """
    def __init__(self, llm):
        """
        初始化LoggerChatModel
        
        Args:
            llm: 被包装的LLM模型
        """
        self.llm = llm
        logger.debug(f"初始化LoggerChatModel，使用LLM: {type(llm).__name__}")
    
    def __call__(self, messages):
        """
        调用LLM模型并记录请求/响应
        
        Args:
            messages: 发送给模型的消息
            
        Returns:
            模型的响应
        """
        logger.debug(f"调用__call__方法，消息类型: {type(messages)}")
        
        # 处理不同类型的消息
        try:
            # 尝试将ChatPromptValue转换为其包含的消息
            if hasattr(messages, 'messages'):
                logger.debug("检测到ChatPromptValue类型对象，提取其消息")
                messages = messages.messages
            
            # 尝试调用LLM API
            logger.debug(f"开始调用LLM API，消息数量: {len(messages) if isinstance(messages, list) else '未知'}")
            reply = self.llm.invoke(messages)
            logger.debug(f"收到LLM响应: {type(reply).__name__}")
            
            # 解析响应
            try:
                parsed_reply = self.parse_llmresult(reply)
                # 记录请求/响应
                LLMLogger.log_request(prompts=messages, parsed_reply=parsed_reply)
            except Exception as e:
                logger.warning(f"解析LLM响应失败: {e}，跳过日志记录")
            
            return reply
        except Exception as e:
            logger.error(f"调用LLM API时发生错误: {str(e)}")
            # 创建一个失败响应
            model_type = global_config.MODEL_TYPE.lower()
            if model_type == "gemini":
                from langchain_core.messages import AIMessage
                error_message = f"调用Gemini API时出错: {str(e)}"
                return AIMessage(content=error_message)
            elif model_type == "ollama":
                from langchain_core.messages import AIMessage
                error_message = f"调用Ollama API时出错: {str(e)}"
                return AIMessage(content=error_message)
            else:
                from langchain_core.messages import AIMessage
                error_message = f"调用API时出错: {str(e)}"
                return AIMessage(content=error_message)

    def parse_llmresult(self, llmresult):
        """
        解析LLM响应为可记录的格式
        
        Args:
            llmresult: LLM的原始响应
            
        Returns:
            dict: 包含响应内容和元数据的字典
        """
        logger.debug(f"解析LLM响应: {type(llmresult).__name__}")
        
        try:
            # 构建基本响应结构
            parsed_result = {
                "content": "",
                "response_metadata": {
                    "model_name": global_config.MODEL
                },
                "usage_metadata": {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0
                }
            }
            
            # 尝试提取内容
            if hasattr(llmresult, "content"):
                parsed_result["content"] = llmresult.content
            elif isinstance(llmresult, str):
                parsed_result["content"] = llmresult
            elif hasattr(llmresult, "choices") and llmresult.choices:
                parsed_result["content"] = llmresult.choices[0].message.content
            else:
                # 最后尝试
                parsed_result["content"] = str(llmresult)
            
            # 尝试提取元数据
            if hasattr(llmresult, "response_metadata") and llmresult.response_metadata:
                if isinstance(llmresult.response_metadata, dict):
                    for key, value in llmresult.response_metadata.items():
                        if key in parsed_result["response_metadata"]:
                            parsed_result["response_metadata"][key] = value
            
            # 尝试提取使用情况
            if hasattr(llmresult, "usage_metadata") and llmresult.usage_metadata:
                if isinstance(llmresult.usage_metadata, dict):
                    for key, value in llmresult.usage_metadata.items():
                        if key in parsed_result["usage_metadata"]:
                            parsed_result["usage_metadata"][key] = value
            
            logger.debug("成功解析LLM响应")
            return parsed_result
            
        except Exception as e:
            logger.error(f"解析LLM响应时出错: {str(e)}")
            # 返回最小可用结构
            return {
                "content": str(llmresult) if llmresult else "无内容",
                "response_metadata": {"model_name": global_config.MODEL},
                "usage_metadata": {
                    "input_tokens": 0, 
                    "output_tokens": 0, 
                    "total_tokens": 0
                }
            }
