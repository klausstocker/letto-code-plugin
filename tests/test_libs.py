import unittest
import json
import uuid
import time
import base64

class TestLibs(unittest.TestCase):

    def test_multiline(self):
        text = """multiline
text"""
        print(text)
        repr = json.dumps({"text": text}, separators=(',', ':'))
        print(repr)
        obj = json.loads(repr)
        print(obj["text"])
        
    def test_uuid(self):
        for _ in range(10):
            r_uuid = uuid.uuid4().hex
            print(r_uuid)