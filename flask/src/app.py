import mimetypes
import os
import re
import shutil
import sys
import uuid
from io import BytesIO
from pathlib import Path

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

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/tmp/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allow alphanumeric characters, underscores, hyphens, and an optional file extension.
# The extension is a single dot followed by one or more alphanumeric characters.
# This prevents path traversal since ".." cannot match (requires chars after the dot).
SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*(\.[a-zA-Z0-9]+)?$')

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
    secret_key=os.environ.get("SECRET_KEY", "change-me-in-production"),
)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


def _get_session_dir(request: Request) -> Path:
    """Get or create a session-specific upload directory."""
    session_id = request.session.get('session_id')
    if not session_id or not SAFE_NAME_RE.match(session_id):
        session_id = uuid.uuid4().hex
        request.session['session_id'] = session_id
    session_dir = UPLOAD_DIR / session_id
    real_dir = os.path.realpath(str(session_dir))
    real_upload = os.path.realpath(str(UPLOAD_DIR))
    if real_dir == real_upload or not real_dir.startswith(real_upload + os.sep):
        session_id = uuid.uuid4().hex
        request.session['session_id'] = session_id
        session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _safe_path(session_dir: Path, filename: str):
    """Return a safe file path within session_dir, or None if invalid."""
    safe_name = os.path.basename(filename)
    if not safe_name or not SAFE_NAME_RE.match(safe_name):
        return None
    candidate = os.path.join(str(session_dir), safe_name)
    real_candidate = os.path.realpath(candidate)
    real_session = os.path.realpath(str(session_dir))
    if real_candidate == real_session or not real_candidate.startswith(real_session + os.sep):
        return None
    return Path(real_candidate)


@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    session_id = request.session.get('session_id')
    if session_id and SAFE_NAME_RE.match(session_id):
        session_dir = UPLOAD_DIR / session_id
        real_dir = os.path.realpath(str(session_dir))
        real_upload = os.path.realpath(str(UPLOAD_DIR))
        if real_dir.startswith(real_upload + os.sep) and session_dir.exists():
            shutil.rmtree(str(session_dir), ignore_errors=True)
    request.session.clear()
    questionConfig = QuestionConfigDto.example()
    return templates.TemplateResponse(request, 'index.html', questionConfig.model_dump())


@app.post('/run')
async def run_code(request: Request):
    body = await request.json()
    code = body['code']
    try:
        session_dir = _get_session_dir(request)
        file_data = {}
        for filepath in session_dir.iterdir():
            if filepath.is_file():
                file_data[filepath.name] = filepath.read_bytes()
        files = JobeWrapper.createFiles(file_data)
        jobe = JobeWrapper('jobe:80')
        result = jobe.run_test('python3', code, 'test.py', files)
        return JSONResponse({'output': result.__repr__()})
    except Exception:
        return JSONResponse({'output': 'Error running code'})


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
    except Exception:
        return JSONResponse({'output': 'Error checking code'})


@app.post('/upload')
async def upload(request: Request, file: UploadFile = File(None)):
    try:
        if file is None or file.filename is None or file.filename == '':
            msg = 'No file part in the form'
            return JSONResponse({'status': 1, 'msg': msg})

        raw_name = os.path.basename(file.filename)
        session_dir = _get_session_dir(request)
        filepath = _safe_path(session_dir, raw_name)
        if filepath is None:
            return JSONResponse({'status': 3, 'msg': 'invalid filename'})
        overwrite = filepath.exists()
        data = await file.read()
        filepath.write_bytes(data)
    except Exception:
        return JSONResponse({'status': 3, 'msg': 'exception uploading file'})
    if overwrite:
        return JSONResponse({'status': 1, 'msg': 'file exists, overwrite'})
    return JSONResponse({'status': 0, 'msg': 'success'})


@app.get('/download/{upload_id}')
async def download(request: Request, upload_id: str):
    session_dir = _get_session_dir(request)
    filepath = _safe_path(session_dir, upload_id)
    if filepath is not None and filepath.exists() and filepath.is_file():
        mime_type, _ = mimetypes.guess_type(filepath.name)
        if mime_type is None:
            mime_type = "application/octet-stream"
        return StreamingResponse(
            BytesIO(filepath.read_bytes()),
            media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filepath.name}"'}
        )
    return PlainTextResponse("File not found", status_code=404)


@app.get('/remove/{upload_id}')
async def remove(request: Request, upload_id: str):
    session_dir = _get_session_dir(request)
    filepath = _safe_path(session_dir, upload_id)
    if filepath is not None and filepath.exists() and filepath.is_file():
        filepath.unlink()
        return PlainTextResponse("Success", status_code=200)
    return PlainTextResponse("File not found", status_code=404)