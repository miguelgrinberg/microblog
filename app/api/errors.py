from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.status import HTTP_400_BAD_REQUEST

HTTP_STATUS_PHRASES = {
    400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden',
    404: 'Not Found', 405: 'Method Not Allowed', 409: 'Conflict',
    422: 'Unprocessable Entity', 500: 'Internal Server Error',
}


def error_response(status_code: int, message: str = None) -> JSONResponse:
    payload = {'error': HTTP_STATUS_PHRASES.get(status_code, 'Unknown error')}
    if message:
        payload['message'] = message
    return JSONResponse(content=payload, status_code=status_code)


def bad_request(message: str) -> JSONResponse:
    return error_response(HTTP_400_BAD_REQUEST, message)
