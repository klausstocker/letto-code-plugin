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
from pydantic import BaseModel, Field
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

# Only allow alphanumeric characters, underscores, and hyphens in names.
# This prevents any path traversal since no dots, slashes, or special chars are permitted.
SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$')


# --- Pydantic request/response models for API documentation ---

class RunCodeRequest(BaseModel):
    """Request body for executing Python code."""
    code: str = Field(..., description="Python source code to execute")

    model_config = {"json_schema_extra": {"examples": [{"code": "print('Hello World!')"}]}}


class RunCodeResponse(BaseModel):
    """Response body after code execution."""
    output: str = Field(..., description="Execution output including stdout and stderr")


class LintCodeRequest(BaseModel):
    """Request body for linting Python code."""
    code: str = Field(..., description="Python source code to lint")

    model_config = {"json_schema_extra": {"examples": [{"code": "def foo():\n    return 42\n"}]}}


class LintCodeResponse(BaseModel):
    """Response body after linting code."""
    output: str = Field(
        ...,
        description="Lint results including score and individual messages",
    )


class CheckCodeRequest(BaseModel):
    """Request body for checking code against unit tests."""
    code: str = Field(..., description="Student Python source code to test")
    testcode: str = Field(
        ...,
        description="Unit test code containing a Checker(unittest.TestCase) class",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "code": "def add(a, b):\n    return a + b\n",
                    "testcode": (
                        "class Checker(unittest.TestCase):\n"
                        "    def test_add(self):\n"
                        "        self.assertEqual(add(1, 2), 3)\n"
                    ),
                }
            ]
        }
    }


class CheckCodeResponse(BaseModel):
    """Response body after running code checks."""
    output: str = Field(
        ...,
        description="Check results including test count, failures, and errors",
    )


class UploadResponse(BaseModel):
    """Response body after a file upload attempt."""
    status: int = Field(
        ...,
        description="Status code: 0 = success, 1 = no file provided or file overwritten, 3 = invalid filename or error",
    )
    msg: str = Field(..., description="Human-readable status message")


# --- FastAPI application ---

TAGS_METADATA = [
    {
        "name": "Code Execution",
        "description": "Run, lint, or test Python code via the Jobe sandbox.",
    },
    {
        "name": "File Management",
        "description": "Upload, download, and remove session-scoped files.",
    },
    {
        "name": "UI",
        "description": "Web interface served via Jinja2 templates.",
    },
]

app = FastAPI(
    title="Letto Code Plugin API",
    description=(
        "A Python code evaluation platform that executes untrusted code in a "
        "sandboxed Jobe environment, provides pylint-based linting, and runs "
        "unit tests with detailed feedback."
    ),
    version="1.0.0",
    openapi_tags=TAGS_METADATA,
)

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


@app.get(
    '/',
    response_class=HTMLResponse,
    tags=["UI"],
    summary="Index page",
    description="Serves the main web interface. Clears the previous session and uploaded files.",
)
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


@app.post(
    '/run',
    response_model=RunCodeResponse,
    tags=["Code Execution"],
    summary="Execute Python code",
    description=(
        "Executes the provided Python source code in a sandboxed Jobe environment. "
        "Any files previously uploaded in the current session are available to the code."
    ),
)
async def run_code(request: Request, body: RunCodeRequest):
    code = body.code
    try:
        session_dir = _get_session_dir(request)
        file_data = {}
        for filepath in session_dir.iterdir():
            if filepath.is_file():
                file_data[filepath.name] = filepath.read_bytes()
        files = JobeWrapper.createFiles(file_data)
        jobe = JobeWrapper('jobe:80')
        result = jobe.run_test('python3', code, 'test.py', files)
        return RunCodeResponse(output=result.__repr__())
    except Exception:
        return RunCodeResponse(output='Error running code')


@app.post(
    '/lint',
    response_model=LintCodeResponse,
    tags=["Code Execution"],
    summary="Lint Python code",
    description=(
        "Analyses the provided Python source code with pylint and returns a "
        "quality score (0–10) together with individual lint messages."
    ),
)
async def lint_code(body: LintCodeRequest):
    code = body.code
    score, messages = lintCode(code)
    messagesText = f'Your code has been rated: {score:.2f}/10.0'
    for m in messages:
        messagesText += f'\nline: {m.line}: {m.msg_id}: {m.msg}, {m.category}'
    return LintCodeResponse(output=messagesText)


@app.post(
    '/check',
    response_model=CheckCodeResponse,
    tags=["Code Execution"],
    summary="Check code against unit tests",
    description=(
        "Runs the student's Python code against the provided unit tests in a "
        "sandboxed Jobe environment. Returns the number of tests run, failures, "
        "and errors."
    ),
)
async def check_code(body: CheckCodeRequest):
    code = body.code
    score, messages = lintCode(code)
    messagesText = f'Your code has been rated: {score:.2f}/10.0'
    testcode = body.testcode
    try:
        result = checkCode('jobe:80', code, testcode)
        return CheckCodeResponse(output=result.__repr__())
    except Exception:
        return CheckCodeResponse(output='Error checking code')


@app.post(
    '/upload',
    response_model=UploadResponse,
    tags=["File Management"],
    summary="Upload a file",
    description=(
        "Uploads a file to the current session's storage. The file is available "
        "for subsequent code executions. Filenames must be alphanumeric "
        "(underscores and hyphens allowed). The file extension is stripped."
    ),
)
async def upload(request: Request, file: UploadFile = File(None)):
    try:
        if file is None or file.filename is None or file.filename == '':
            msg = 'No file part in the form'
            return UploadResponse(status=1, msg=msg)

        raw_name = file.filename.split('.')[0] if '.' in file.filename else file.filename
        session_dir = _get_session_dir(request)
        filepath = _safe_path(session_dir, raw_name)
        if filepath is None:
            return UploadResponse(status=3, msg='invalid filename')
        overwrite = filepath.exists()
        data = await file.read()
        filepath.write_bytes(data)
    except Exception:
        return UploadResponse(status=3, msg='exception uploading file')
    if overwrite:
        return UploadResponse(status=1, msg='file exists, overwrite')
    return UploadResponse(status=0, msg='success')


@app.get(
    '/download/{upload_id}',
    tags=["File Management"],
    summary="Download a file",
    description="Downloads a previously uploaded file from the current session by its name.",
    responses={
        200: {
            "description": "File returned as binary stream",
            "content": {"application/octet-stream": {}},
        },
        404: {"description": "File not found"},
    },
)
async def download(request: Request, upload_id: str):
    session_dir = _get_session_dir(request)
    filepath = _safe_path(session_dir, upload_id)
    if filepath is not None and filepath.exists() and filepath.is_file():
        return StreamingResponse(
            BytesIO(filepath.read_bytes()),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filepath.name}"'}
        )
    return PlainTextResponse("File not found", status_code=404)


@app.get(
    '/remove/{upload_id}',
    tags=["File Management"],
    summary="Remove a file",
    description="Deletes a previously uploaded file from the current session by its name.",
    responses={
        200: {"description": "File successfully deleted", "content": {"text/plain": {"example": "Success"}}},
        404: {"description": "File not found", "content": {"text/plain": {"example": "File not found"}}},
    },
)
async def remove(request: Request, upload_id: str):
    session_dir = _get_session_dir(request)
    filepath = _safe_path(session_dir, upload_id)
    if filepath is not None and filepath.exists() and filepath.is_file():
        filepath.unlink()
        return PlainTextResponse("Success", status_code=200)
    return PlainTextResponse("File not found", status_code=404)