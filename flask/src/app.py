import base64
import os
import sys
import uuid
from io import BytesIO

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

try:
    from shared.jobe_wrapper import *
    from shared.lint import *
    from shared.check import *
    from shared.question_config import QuestionConfigDto, EvalConfigDto
except ImportError:
    # need to append paths
    sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))
    sys.path.append(os.path.join(os.path.dirname(__file__), "../../.."))
    from shared.jobe_wrapper import *
    from shared.lint import *
    from shared.check import *
    from shared.question_config import QuestionConfigDto, EvalConfigDto

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY", uuid.uuid4().hex),
)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    request.session.clear()
    questionConfig = QuestionConfigDto.example()
    return templates.TemplateResponse(request, 'index.html', questionConfig.model_dump())


@app.post('/run')
async def run_code(request: Request):
    body = await request.json()
    code = body['code']
    try:
        session_files = request.session.get('files', {})
        # Decode base64 file data back to bytes
        decoded_files = {k: base64.b64decode(v) for k, v in session_files.items()}
        files = JobeWrapper.createFiles(decoded_files)
        jobe = JobeWrapper('jobe:80')
        result = jobe.run_test('python3', code, 'test.py', files)
        return JSONResponse({'output': result.__repr__()})
    except Exception as e:
        return JSONResponse({'output': f'Error running code: {e}'})


@app.post('/lint')
async def lint_code(request: Request):
    body = await request.json()
    code = body['code']
    score, messages = lintCode(code)
    messagesText = f'Your code has been rated: {score:.2f}/10.0'
    for m in messages:
        messagesText += f'\nline: {m.line}: {m.msg_id}: {m.msg}, {m.category}'
    return JSONResponse({'output': messagesText})


@app.post('/check')
async def check_code(request: Request):
    body = await request.json()
    code = body['code']
    score, messages = lintCode(code)
    messagesText = f'Your code has been rated: {score:.2f}/10.0'
    testcode = body['testcode']
    try:
        result = checkCode('jobe:80', code, testcode)
        return JSONResponse({'output': result.__repr__()})
    except Exception as e:
        return JSONResponse({'output': str(e)})


@app.post('/upload')
async def upload(request: Request, file: UploadFile = File(None)):
    try:
        if file is None or file.filename is None or file.filename == '':
            msg = 'No file part in the form'
            return JSONResponse({'status': 1, 'msg': msg})

        if file.filename == '':
            msg = 'filename empty'
            return JSONResponse({'status': 2, 'msg': msg})

        filename = file.filename.split('.')[0] if '.' in file.filename else file.filename
        files = request.session.get('files', {})
        data = await file.read()
        overwrite = filename in files
        # Store file data as base64 string for JSON-serializable session
        files[filename] = base64.b64encode(data).decode('ascii')
        request.session['files'] = files
    except Exception as e:
        return JSONResponse({'status': 3, 'msg': f'exception uploading: {e}'})
    if overwrite:
        return JSONResponse({'status': 1, 'msg': 'file exists, overwrite'})
    return JSONResponse({'status': 0, 'msg': 'success'})


@app.get('/download/{upload_id}')
async def download(request: Request, upload_id: str):
    files = request.session.get('files', {})
    if upload_id in files:
        data = base64.b64decode(files[upload_id])
        return StreamingResponse(
            BytesIO(data),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{upload_id}"'}
        )
    return PlainTextResponse("File not found", status_code=404)


@app.get('/remove/{upload_id}')
async def remove(request: Request, upload_id: str):
    files = request.session.get('files', {})
    if upload_id in files:
        files.pop(upload_id)
        request.session['files'] = files
        return PlainTextResponse("Success", status_code=200)
    return PlainTextResponse("File not found", status_code=404)