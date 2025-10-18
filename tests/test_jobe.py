import unittest
import sys

from shared.jobe_wrapper import JobeWrapper
from shared.check import checkCode
from shared.check_result import CheckResult


class TestJobeWrapper(unittest.TestCase):

    def test_run(self):
        code = """
MESSAGE = 'Hello Jobe!'

def sillyFunc(message):
    '''Pointless function that prints the given message'''
    print("Message is", message)

sillyFunc(MESSAGE)
"""
        jobe = JobeWrapper('localhost:4000')
        result = jobe.run_test('python3', code, 'test.py')
        self.assertTrue(result.success())

    def test_check(self):
        code = """
def calculate_sum(a, b):
    print('the sum is ' + str(a + b))
    return a + b
"""
        testCode = """
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
        result = checkCode('localhost:4000', code, testCode)
        self.assertEqual(result.count, 2)
        self.assertTrue(result.wasSuccessful())

    def testUpload(self):
        jobe = JobeWrapper('localhost:4000')
        fileId = 'B00WHrZtSjfile1gasdfaserscasdfaserasdfaserqwcasrweas'
        self.assertIsNone(jobe.put_file(fileId, 'inhalt'))
        self.assertTrue(jobe.check_file(fileId))

    def testWithFiles(self):
        files = [('file1', 'The first file\nLine 2'),
                 ('file2', 'Second file')]
        code = """
print(open('file1').read())
print(open('file2').read())
"""
        fileSpec = JobeWrapper.createFiles(files)
        jobe = JobeWrapper('localhost:4000')
        result = jobe.run_test('python3', code, 'test.py', fileSpec)
        self.assertTrue(result.success())
        self.assertEqual(result.stdout, "The first file\nLine 2\nSecond file\n")
