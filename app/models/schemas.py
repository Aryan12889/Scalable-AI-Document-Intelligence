from pydantic import BaseModel
from enum import Enum
from typing import Optional, List

class TaskStatusEnum(str, Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"

class IngestResponse(BaseModel):
    task_id: str
    filename: str
    message: str

class TaskStatus(BaseModel):
    task_id: str
    status: TaskStatusEnum
    result: Optional[str] = None
    error: Optional[str] = None
