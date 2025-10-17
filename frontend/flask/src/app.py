from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sys
import os

try:
    from shared.jobe_wrapper import *
    from shared.lint import *
    from shared.check import *
except ImportError:
    # need to append paths
    sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))
    sys.path.append(os.path.join(os.path.dirname(__file__), "../../.."))
    from shared.jobe_wrapper import *
    from shared.lint import *
    from shared.check import *


app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run_code():
    code = request.json['code']
    try:
        jobe = JobeWrapper('jobe:80')
        result = jobe.run_test('python3', code, 'test.py')
        return jsonify({'output': result.__repr__()})
    except Exception as e:
        return jsonify({'output': str(e)})
    
@app.route('/lint', methods=['POST'])
def lint_code():
    code = request.json['code']
    score, messages = lintCode(code)
    messagesText = f'Your code has been rated: {score:.2f}/10.0'
    for m in messages:
        messagesText += f'\nline: {m.line}: {m.msg_id}: {m.msg}, {m.category}'
    return jsonify({'output': messagesText})

@app.route('/check', methods=['POST'])
def check_code():
    code = request.json['code']
    score, messages = lintCode(code)
    messagesText = f'Your code has been rated: {score:.2f}/10.0'
    testcode = request.json['testcode']
    try:
        result = checkCode('jobe:80', code, testcode)
        return jsonify({'output': result.__repr__()})
    except Exception as e:
        return jsonify({'output': str(e)})

