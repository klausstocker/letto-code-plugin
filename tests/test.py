import unittest
import sys
import os
from io import StringIO
import json

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from shared.check_result import *

class RedirectedStdout:
    def __init__(self):
        self._stdout = None
        self._string_io = None

    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = self._string_io = StringIO()
        return self

    def __exit__(self, type, value, traceback):
        sys.stdout = self._stdout

    def __str__(self):
        return self._string_io.getvalue()

def student_sum(a, b):
    print('Die Summe ist ' + str(a + b))
    return a + b

def correctImplementation(arg1, arg2):
    sum = arg1 + arg2
    print(f'Die Summe ist {sum}')
    return sum

class Checker(unittest.TestCase): # do not rename
    def test_return(self): # names must start with 'test_'
        args = (1, 2)
        student_result = student_sum(*args)
        expected_result = correctImplementation(*args)
        self.assertEqual(student_result, expected_result)
        
    def test_output(self):
        args = (3, 4)
        with RedirectedStdout() as student_out:
            student_sum(*args)
        with RedirectedStdout() as expected_out:
            correctImplementation(*args)
        self.assertEqual(str(student_out), str(expected_out))
            

def main():
    __magic_string__ = '__magic_string__'
    ret = {'count' : 0, 'errors': [], 'failures': []}
    try:
        unittestOutput = StringIO()
        suite = unittest.TestLoader().loadTestsFromTestCase(Checker)
        runner = unittest.TextTestRunner(verbosity=0, stream=unittestOutput)
        result = runner.run(suite)
        ret['count'] = result.testsRun
        for error in result.errors:
            ret['errors'].append(str(error))
        for failure in result.failures:
            ret['failures'].append(str(failure))
    except Exception as e:
        ret['errors'].append(str(e))
    resultJson = 'some invalid text' + __magic_string__ + json.dumps(ret)
    result = CheckResult.from_str(resultJson)
    print(result)


if __name__ == '__main__':
    main()