from pydantic import BaseModel


class EvalConfigDto(BaseModel):
    runAtTest: bool = True
    unitTestAtTest: bool = False
    lintAtTest: bool = True


class QuestionConfigDto(BaseModel):
    indication: str = ""
    validation: str = ""
    files: dict[str, str] = {}
    evalConfig: EvalConfigDto = EvalConfigDto()
    
    @staticmethod
    def example():
        return QuestionConfigDto(
        indication="""
def calculate_sum(a, b):
    print('the sum is ' + str(a + b))
    return a + b
""",
        validation="""
def correctImplementation(arg1, arg2):
    sum = arg1 + arg2
    print(f'the sum is {sum}')
    return sum

class Checker(unittest.TestCase): # do not rename
    def test_return(self): # names must start with 'test_'
        args = (1, 2)
        student_result = calculate_sum(*args) # call to students implementation 
        expected_result = correctImplementation(*args)
        self.assertEqual(student_result, expected_result)
        
    def test_output(self):
        args = (3, 4)
        with RedirectedStdout() as student_out:
            calculate_sum(*args)
        with RedirectedStdout() as expected_out:
            correctImplementation(*args)
        self.assertEqual(str(student_out), str(expected_out))
"""
    )
