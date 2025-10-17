from urllib.error import HTTPError
import json
import http.client

RESOURCE_BASE = '/jobe/index.php/restapi'

PYTHON_CODE = """
MESSAGE = 'Hello Jobe!'

def sillyFunc(message):
    '''Pointless function that prints the given message'''
    print("Message is", message)

sillyFunc(MESSAGE)
"""

# =============================================================

class RunResult():
    outcomes = {
        0:  'Successful run',
        11: 'Compile error',
        12: 'Runtime error',
        13: 'Time limit exceeded',
        15: 'Successful run',
        17: 'Memory limit exceeded',
        19: 'Illegal system call',
        20: 'Internal error, please report',
        21: 'Server overload'}

    def outcome(self):
        if self._outcome in RunResult.outcomes:
            return self._outcome, RunResult.outcomes[self._outcome]
        return 2, 'unknown error while running code'
    
    def success(self)->bool:
        return self._outcome in [0, 15]
    
    def __init__(self, ro: dict):
        if not isinstance(ro, dict) or 'outcome' not in ro:
            print("Bad result object", ro)
            self._outcome = 1
            return
        self._outcome = ro['outcome']
        self.cmpinfo = ro['cmpinfo'] if ro['cmpinfo'] else None
        self.stdout =  ro['stdout'] if ro['stdout'] else None
        self.stderr =  ro['stderr'] if ro['stderr'] else None

    def __repr__(self):
        if not self.success():
            return 'Error while running code.'
        out = self.outcome()
        ret = f'outcome: {out[0]}: {out[1]}\n'
        ret += f'Compiler output: {self.cmpinfo}\n' if self.cmpinfo else ''
        ret += f'stdout: {self.stdout}\n' if self.stdout else ''
        ret += f'stderr: {self.stderr}\n' if self.stderr else ''
        return ret


def trim(s):
    '''Return the string s limited to 10k chars'''
    MAX_LEN = 10000
    if len(s) > MAX_LEN:
        return s[:MAX_LEN] + '... [etc]'
    else:
        return s

class JobeWrapper():
    def __init__(self, server):
        self.server = server

    def http_request(self, method, resource, data, headers):
        '''Send a request to Jobe with given HTTP method to given resource on
        the currently configured Jobe server and given data and headers.
        Return the connection object. '''
        connect = http.client.HTTPConnection(self.server)
        connect.request(method, resource, data, headers)
        return connect


    def run_test(self, language, code, filename):
        '''Execute the given code in the given language.
        Return the result object.'''
        runspec = {
            'language_id': language,
            'sourcefilename': filename,
            'sourcecode': code,
        }

        resource = f'{RESOURCE_BASE}/runs'
        data = json.dumps({ 'run_spec' : runspec })
        result = self.do_http('POST', resource, data)
        return RunResult(result)


    def do_http(self, method, resource, data=None):
        """Send the given HTTP request to Jobe, return json-decoded result as
        a dictionary (or the empty dictionary if a 204 response is given).
        """
        result = {}
        headers = {"Content-type": "application/json; charset=utf-8",
                "Accept": "application/json"}
        try:
            connect = self.http_request(method, resource, data, headers)
            response = connect.getresponse()
            if response.status not in [200, 204]:
                print(f"do_http({method}, {resource}) returned status of {response.status}")
                print(f"content = '{response.read().decode('utf8')}'")
            elif response.status == 200:
                content = response.read().decode('utf8')
                if content:
                    result = json.loads(content)
            connect.close()

        except (HTTPError, ValueError) as e:
            print("\n***************** HTTP ERROR ******************\n")
            if response:
                print(' Response:', response.status, response.reason, content)
            else:
                print(e)
        return result

    def languages(self):
        resource = f'{RESOURCE_BASE}/languages'
        lang_versions = self.do_http('GET', resource)
        ret = {lang: version for lang, version in lang_versions}
        return ret
    
def main():
    '''Demo or get languages, a run of Python3 then C++ then Java'''
    jobe = JobeWrapper('localhost:4000')
    print("Supported languages:")
    for lang, version in jobe.languages().items():
        print("    {}: {}".format(lang, version))
    print()
    print("Running python...")
    result_obj = jobe.run_test('python3', PYTHON_CODE, 'test.py')
    print(result_obj)

if __name__ == '__main__':
    main()