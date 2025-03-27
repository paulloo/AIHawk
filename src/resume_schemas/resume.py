from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
import yaml
from pydantic import BaseModel, EmailStr, HttpUrl, Field, validator



class PersonalInformation(BaseModel):
    name: Optional[str]
    surname: Optional[str]
    date_of_birth: Optional[str]
    country: Optional[str]
    city: Optional[str]
    address: Optional[str]
    zip_code: Optional[str] = Field(None, min_length=5, max_length=10)
    phone_prefix: Optional[str]
    phone: Optional[str]
    email: Optional[EmailStr]
    github: Optional[HttpUrl] = None
    linkedin: Optional[HttpUrl] = None


class EducationDetails(BaseModel):
    education_level: Optional[str]
    institution: Optional[str]
    field_of_study: Optional[str]
    final_evaluation_grade: Optional[str]
    start_date: Optional[str]
    year_of_completion: Optional[int]
    exam: Optional[Union[List[Dict[str, str]], Dict[str, str]]] = None


class ExperienceDetails(BaseModel):
    position: Optional[str]
    company: Optional[str]
    employment_period: Optional[str]
    location: Optional[str]
    industry: Optional[str]
    key_responsibilities: Optional[List[Dict[str, str]]] = None
    skills_acquired: Optional[List[str]] = None


class Project(BaseModel):
    """项目经历模型"""
    name: str
    description: str
    technologies: Optional[List[str]] = []  # 设置为可选字段，默认空列表
    link: Optional[HttpUrl] = None  # 允许为None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    current: Optional[bool] = False
    achievements: Optional[List[str]] = []

    @validator('link', pre=True)
    def validate_link(cls, v):
        """验证项目链接"""
        if v is None or v == 'N/A' or v == '':
            return None
        try:
            return HttpUrl(v)
        except ValueError:
            return None

    @validator('technologies', pre=True)
    def validate_technologies(cls, v):
        """验证技术栈列表"""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v


class Achievement(BaseModel):
    name: Optional[str]
    description: Optional[str]


class Certifications(BaseModel):
    name: Optional[str]
    description: Optional[str]


class Language(BaseModel):
    language: Optional[str]
    proficiency: Optional[str]


class Availability(BaseModel):
    notice_period: Optional[str]


class SalaryExpectations(BaseModel):
    salary_range_usd: Optional[str]


class SelfIdentification(BaseModel):
    gender: Optional[str]
    pronouns: Optional[str]
    veteran: Optional[str]
    disability: Optional[str]
    ethnicity: Optional[str]


class LegalAuthorization(BaseModel):
    eu_work_authorization: Optional[str]
    us_work_authorization: Optional[str]
    requires_us_visa: Optional[str]
    requires_us_sponsorship: Optional[str]
    requires_eu_visa: Optional[str]
    legally_allowed_to_work_in_eu: Optional[str]
    legally_allowed_to_work_in_us: Optional[str]
    requires_eu_sponsorship: Optional[str]


class Resume(BaseModel):
    personal_information: Optional[PersonalInformation]
    education_details: Optional[List[EducationDetails]] = None
    experience_details: Optional[List[ExperienceDetails]] = None
    projects: Optional[List[Project]] = None
    achievements: Optional[List[Achievement]] = None
    certifications: Optional[List[Certifications]] = None
    languages: Optional[List[Language]] = None
    interests: Optional[List[str]] = None

    @staticmethod
    def normalize_exam_format(exam):
        if isinstance(exam, dict):
            return [{k: v} for k, v in exam.items()]
        return exam

    def __init__(self, yaml_str: str):
        try:
            # Parse the YAML string
            data = yaml.safe_load(yaml_str)

            if 'education_details' in data:
                for ed in data['education_details']:
                    if 'exam' in ed:
                        ed['exam'] = self.normalize_exam_format(ed['exam'])

            # Create an instance of Resume from the parsed data
            super().__init__(**data)
        except yaml.YAMLError as e:
            raise ValueError("Error parsing YAML file.") from e
        except Exception as e:
            raise Exception(f"Unexpected error while parsing YAML: {e}") from e

    def to_dict(self) -> Dict[str, Any]:
        """
        将Resume对象转换为字典格式，便于处理
        
        Returns:
            Dict[str, Any]: 表示Resume的字典
        """
        try:
            # 使用model_dump方法获取模型的字典表示
            if hasattr(self, 'model_dump'):
                # Pydantic v2
                data = self.model_dump(exclude_none=True)
            else:
                # Pydantic v1
                data = self.dict(exclude_none=True)
                
            # 处理嵌套的Pydantic模型
            for key, value in data.items():
                if isinstance(value, list):
                    # 处理列表中的嵌套模型
                    new_list = []
                    for item in value:
                        if hasattr(item, 'dict'):
                            # 如果是嵌套模型，转换为字典
                            new_list.append(item.dict(exclude_none=True))
                        else:
                            new_list.append(item)
                    data[key] = new_list
                elif hasattr(value, 'dict'):
                    # 如果是单个嵌套模型，转换为字典
                    data[key] = value.dict(exclude_none=True)
                    
            return data
        except Exception as e:
            # 如果转换失败，返回空字典
            import logging
            logging.error(f"转换Resume对象为字典时出错: {str(e)}")
            # 尝试使用简单方法
            return {
                'personal_information': getattr(self, 'personal_information', {}),
                'education_details': getattr(self, 'education_details', []),
                'experience_details': getattr(self, 'experience_details', []),
                'projects': getattr(self, 'projects', []),
                'skills': getattr(self, 'skills', []),
                'languages': getattr(self, 'languages', []),
                'interests': getattr(self, 'interests', [])
            }


@dataclass
class Exam:
    name: str
    grade: str

@dataclass
class Responsibility:
    description: str

    def to_dict(self) -> Dict[str, Any]:
        """
        将Resume对象转换为字典格式，便于处理
        
        Returns:
            Dict[str, Any]: 表示Resume的字典
        """
        try:
            # 使用model_dump方法获取模型的字典表示
            if hasattr(self, 'model_dump'):
                # Pydantic v2
                data = self.model_dump(exclude_none=True)
            else:
                # Pydantic v1
                data = self.dict(exclude_none=True)
                
            # 处理嵌套的Pydantic模型
            for key, value in data.items():
                if isinstance(value, list):
                    # 处理列表中的嵌套模型
                    new_list = []
                    for item in value:
                        if hasattr(item, 'dict'):
                            # 如果是嵌套模型，转换为字典
                            new_list.append(item.dict(exclude_none=True))
                        else:
                            new_list.append(item)
                    data[key] = new_list
                elif hasattr(value, 'dict'):
                    # 如果是单个嵌套模型，转换为字典
                    data[key] = value.dict(exclude_none=True)
                    
            return data
        except Exception as e:
            # 如果转换失败，返回空字典
            import logging
            logging.error(f"转换Resume对象为字典时出错: {str(e)}")
            # 尝试使用简单方法
            return {
                'personal_information': getattr(self, 'personal_information', {}),
                'education_details': getattr(self, 'education_details', []),
                'experience_details': getattr(self, 'experience_details', []),
                'projects': getattr(self, 'projects', []),
                'skills': getattr(self, 'skills', []),
                'languages': getattr(self, 'languages', []),
                'interests': getattr(self, 'interests', [])
            }