from io import BytesIO
from flask import Flask, request, jsonify, render_template, session, send_file
from flask_cors import CORS
from flask_session import Session


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
app.config["SESSION_PERMANENT"] = False     # Sessions expire when the browser is closed
app.config["SESSION_TYPE"] = "filesystem"     # Store session data in files

CORS(app)
Session(app)

@app.route('/')
def index():
    session.clear()
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run_code():
    code = request.json['code']
    files = {}
    try:
        files = JobeWrapper.createFiles(session.get('files', {}))
        jobe = JobeWrapper('jobe:80')
        result = jobe.run_test('python3', code, 'test.py', files)
        return jsonify({'output': result.__repr__()})
    except Exception as e:
        return jsonify({'output': f'Error running code: {e}'})
    
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

@app.route('/upload', methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            msg = 'No file part in the form'
            return jsonify({'status': 1, 'msg': msg})

        file = request.files['file']
        if file.filename == '':
            msg = 'filename empty'
            return jsonify({'status': 2, 'msg': msg})

        filename = file.filename.split('.')[0] if '.' in file.filename else file.filename
        files = session.get('files', {})
        data = file.read()
        overwrite = filename in files
        files[filename] = data
        session['files'] = files
    except Exception as e:
        return jsonify({'status': 3, 'msg': f'exception uploading: {e}'})
    return jsonify({'status': 1, 'msg': 'file exists, overwrite'}) if overwrite else jsonify({'status': 0, 'msg': 'success'})

@app.route('/download/<upload_id>')
def download(upload_id):
    files = session.get('files', {})
    if upload_id in files:
        data = files[upload_id]
        return send_file(BytesIO(data), download_name=upload_id, as_attachment=True )
    return "File not found", 404

@app.route('/remove/<upload_id>')
def remove(upload_id):
    files = session.get('files', {})
    if upload_id in files:
        files.pop(upload_id)
        session['files'] = files
        return "Success", 200
    return "File not found", 404