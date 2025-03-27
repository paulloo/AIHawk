"""职位相关类"""
from typing import Dict, Any, Optional

class Job:
    """职位类，存储职位相关信息"""
    
    def __init__(self):
        """初始化职位"""
        self.role: str = ""
        self.company: str = ""
        self.description: str = ""
        self.location: str = ""
        self.link: str = ""
        self.recruiter: Optional[str] = None
        self.salary: Optional[str] = None
        self.requirements: Optional[str] = None
        self.responsibilities: Optional[str] = None
        self.benefits: Optional[str] = None
        self.date_posted: Optional[str] = None
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "role": self.role,
            "company": self.company,
            "description": self.description,
            "location": self.location,
            "link": self.link,
            "recruiter": self.recruiter,
            "salary": self.salary,
            "requirements": self.requirements,
            "responsibilities": self.responsibilities,
            "benefits": self.benefits,
            "date_posted": self.date_posted
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """从字典创建职位实例"""
        job = cls()
        job.role = data.get('role', '')
        job.company = data.get('company', '')
        job.description = data.get('description', '')
        job.location = data.get('location', '')
        job.link = data.get('link', '')
        job.recruiter = data.get('recruiter')
        job.salary = data.get('salary')
        job.requirements = data.get('requirements')
        job.responsibilities = data.get('responsibilities')
        job.benefits = data.get('benefits')
        job.date_posted = data.get('date_posted')
        return job 