
from app.utils.HttpResponseUtils import response_format
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from config.apm import apm
import traceback

def setup_exception(app):
    def _preprocess_exception(exc, raw=False):
        original_exception = exc
        if not raw:
            if not hasattr(exc, 'detail'):
                return {}
            detail_payload = exc.detail if isinstance(exc.detail, dict) else {}
            original_exception = detail_payload.get('error')
            
            if not isinstance(original_exception, Exception):
                return {}
            
        try:
            last_frame = traceback.extract_tb(original_exception.__traceback__)[-1]
            return {
                "type": original_exception.__class__.__name__,
                "message": str(original_exception),
                "file_path" : last_frame.filename, 
                "file_name": last_frame.filename.split('\\')[-1],
                "line_no": last_frame.lineno, 
                "line": last_frame.line,
                "function": last_frame.name,
            }
        except (AttributeError, IndexError):
            return {}
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request, exc):
        apm.client.capture_exception(custom=_preprocess_exception(exc))
        detail = exc.detail if isinstance(exc.detail, dict) else { "msg": None, "data": None }
        return response_format(detail.get('msg'),exc.status_code, detail.get('data'))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        apm.client.capture_exception(custom=_preprocess_exception(exc, raw=True))
        return response_format("Terjadi kesalahan, silahkan coba lagi",400, str(exc))
