from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException
import elasticapm

def response_error(exception: Exception, msg = 'Terjadi kesalahan, silahkan coba lagi', code = 400, data = None):
    _msg = str(exception) if '[WARN]' in str(exception) else msg
    raise HTTPException(
        code,
        {
            "msg": _msg,
            "data": data,
            "error": exception
        },
    )

def response_format(msg, code , data = None):
    return JSONResponse(status_code = code, content = jsonable_encoder({
        "status":0,
        "data": data,
        "message": msg
    }))

def response_success(data):
    elasticapm.label(response_success=jsonable_encoder(data))
    return JSONResponse(status_code = 200, content = jsonable_encoder({
        "status":1,
        "data": data,
        "message": "Success."
    }))
