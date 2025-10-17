from shared.jobe_wrapper import JobeWrapper
from shared.check_result import CheckResult
import unittest
import json

def checkCode(server, code, testCode):
    code = """
import unittest
import sys
from io import StringIO
import json

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
""" + code + """
""" + testCode + """
def main():
    unittestOutput = StringIO()
    ret = {'count' : 0, 'errors': [], 'failures': []}
    try:
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
    return ret

if __name__ == '__main__':
    __magic_string__ = '__magic_string__'
    ret = main()
    print(f'{__magic_string__}{json.dumps(ret, separators=(',', ':'))}')
"""

    jobe = JobeWrapper(server)
    result = jobe.run_test('python3', code, 'test.py')
    if not result.success():
        return CheckResult({'count': 0, 'errors': ['error running code']})
    return CheckResult.from_str(result.stdout)
