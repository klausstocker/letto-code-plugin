from pydantic import BaseModel


class EvalConfigDto(BaseModel):
    runAtTest: bool
    unitTestAtTest: bool
    lintAtTest: bool


class QuestionConfigDto(BaseModel):
    indication: str
    solution: str
    files: dict[str, str]
    evalConfig: EvalConfigDto
