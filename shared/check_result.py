import json

class CheckResult():
    __magic_string__ = '__magic_string__'
    def __init__(self, resultDict: dict):
        self.count = resultDict['count'] if 'count' in resultDict else 0
        self.failures = resultDict['failures'] if 'failures' in resultDict else []
        self.errors = resultDict['errors'] if 'errors' in resultDict else []

    @classmethod
    def from_str(res, text):
        resultJson = text[text.find(CheckResult.__magic_string__)+len(CheckResult.__magic_string__):]
        return CheckResult(json.loads(resultJson))

    def wasSuccessful(self):
        return len(self.failures) == 0 and len(self.errors) == 0

    def __repr__(self):
        ret = ''
        for failure in self.failures:
            ret += f'{failure}\n'
        for error in self.errors:
            ret += f'{error}\n'
        return ret + f'Ran {self.count} Test, {len(self.failures)} failures, {len(self.errors)} errors\n'