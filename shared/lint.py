import os
import json
import tempfile
import pylint.lint
from pylint.reporters import CollectingReporter


class ScopedTemporaryFile():
    """Creates a temporary file which gets deleted when instance gets out of scope."""

    def __init__(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)

    def __del__(self):
        try:
            self.tmp.close()
            os.unlink(self.tmp.name)
        except IOError:
            pass

    def name(self):
        return self.tmp.name


def lintCode(code :str):
    tmp = ScopedTemporaryFile()
    with open(tmp.name(), 'w') as f:
        f.write(code)
    if not os.path.exists(tmp.name()):
        return (0.0, 'Error while linting')

    reporter = CollectingReporter()
    results = pylint.lint.Run([tmp.name()], reporter=reporter, exit=False)
    return (results.linter.stats.global_note, reporter.messages)
