"""
Sends the HTTP requests to the FHIR server and keeps the communication log.

Every request gets a run-wide request ID (``REQ-0001``, ``REQ-0002``, ...). The run
log names this ID in one line per request, and the unfiltered request and response
are written to a folder of their own below ``communication_logs``::

    communication_logs/<run>/<NN>_<TestScript>/REQ-0001_POST_Patient/
        request.http     request line, headers and body as sent
        response.http    status line, headers and body as received
        error.txt        instead of response.http, if no response was received

Bodies are written byte for byte; a compressed response body is stored decompressed.
"""
import logging
import re
import time
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests

log = logging.getLogger("testrunner.http")

_HTTP_VERSIONS = {10: "HTTP/1.0", 11: "HTTP/1.1", 20: "HTTP/2"}

_run_dir: Path | None = None          # communication_logs/<run>, None if the files are disabled
_testscript_dir: Path | None = None   # folder of the TestScript that is running
_fhir_base: str = ""                  # stripped from the URL for the folder names
_include_in_log = False               # also write request and response into the run log
_request_count = 0


def configure(run_dir: Path | None, include_in_log: bool, fhir_base: str = "") -> None:
    """
    Starts the communication log of a test run.

    :param run_dir: Folder for the request/response files of this run, or None
        to write no files (the request IDs are logged anyway).
    :param include_in_log: Whether the full request and response are also
        written into the run log (at DEBUG level).
    :param fhir_base: Base URL of the FHIR server, used to name the folders.
    """
    global _run_dir, _testscript_dir, _fhir_base, _include_in_log, _request_count
    _run_dir = run_dir
    _testscript_dir = None
    _fhir_base = (fhir_base or "").rstrip("/")
    _include_in_log = include_in_log
    _request_count = 0


def start_testscript(index: int, testscript_path: str) -> None:
    """
    Files the following requests in a folder of their own for this TestScript.

    :param index: Position of the TestScript in the run (1-based).
    :param testscript_path: Path of the TestScript file, its name names the folder.
    """
    global _testscript_dir
    if _run_dir is None:
        return
    _testscript_dir = _run_dir / f"{index:02d}_{_safe_name(Path(testscript_path).stem)[:60]}"
    log.debug("Communication logs of this TestScript: %s", _testscript_dir)


def request_count() -> int:
    """Number of requests sent in this run."""
    return _request_count


def send_request(method: str, url: str, headers: dict[str, str] | None = None,
                 data: Any = None) -> tuple[str, requests.Response]:
    """
    Sends a request to the FHIR server and logs the exchange.

    Behaves like ``requests.request`` (``requests.head`` for HEAD, which does
    not follow redirects). The request and the response are written to the
    communication log, and a line naming the request ID goes to the run log.

    :param method: HTTP method, e.g. ``"get"``.
    :param url: Full request URL.
    :param headers: Request headers.
    :param data: Request body, ``None`` for none.
    :returns: Tuple of (request ID, response).
    :raises requests.RequestException: If no response was received; the
        request is logged before.
    """
    global _request_count
    _request_count += 1
    request_id = f"REQ-{_request_count:04d}"
    method = method.upper()

    with requests.Session() as session:
        prepared = session.prepare_request(requests.Request(method, url, headers=headers, data=data))
        settings = session.merge_environment_settings(prepared.url, {}, None, None, None)
        request_message = _request_message(prepared)
        start = time.perf_counter()
        try:
            response = session.send(prepared, allow_redirects=method != "HEAD", **settings)
        except requests.RequestException as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            failure = f"No response received.\n{type(e).__name__}: {e}\n"
            folder = _write_exchange(request_id, prepared, request_message, error_text=failure)
            log.error("%s %s %s -> no response, %s (%.0f ms)%s",
                      request_id, method, prepared.url, type(e).__name__, elapsed_ms, _reference(folder))
            _log_exchange(request_id, request_message, failure.encode("utf-8"))
            raise

    elapsed_ms = (time.perf_counter() - start) * 1000
    response_message = _response_message(response)
    folder = _write_exchange(request_id, prepared, request_message, response_message=response_message)
    reason = response.reason or _status_phrase(response.status_code)
    log.info("%s %s %s -> %s %s (%.0f ms)%s",
             request_id, method, prepared.url, response.status_code, reason, elapsed_ms, _reference(folder))
    if response.history:
        log.info("%s was redirected to %s", request_id, response.url)
    _log_exchange(request_id, request_message, response_message)
    return request_id, response


def _request_message(prepared: requests.PreparedRequest) -> bytes:
    """Request line, headers and body of a prepared request."""
    head = [f"{prepared.method} {prepared.url} HTTP/1.1"]
    head += [f"{name}: {value}" for name, value in prepared.headers.items()]
    body = prepared.body
    if body is None:
        body = b""
    elif isinstance(body, str):
        body = body.encode("utf-8")  # urllib3 sends str bodies UTF-8 encoded
    elif not isinstance(body, bytes):
        body = f"<{type(body).__name__} body not captured>".encode("utf-8")
    return _http_message(head, body)


def _response_message(response: requests.Response) -> bytes:
    """Status line, headers and body of a response, as received from the server."""
    version = _HTTP_VERSIONS.get(getattr(response.raw, "version", 11), "HTTP/1.1")
    head = [f"{version} {response.status_code} {response.reason or ''}".rstrip()]
    # the raw headers keep repeated header fields apart
    raw_headers = getattr(response.raw, "headers", None) or response.headers
    head += [f"{name}: {value}" for name, value in raw_headers.items()]
    return _http_message(head, response.content)


def _http_message(head: list[str], body: bytes) -> bytes:
    return ("\n".join(head) + "\n\n").encode("utf-8") + body


def _write_exchange(request_id: str, prepared: requests.PreparedRequest, request_message: bytes,
                    response_message: bytes | None = None, error_text: str | None = None) -> Path | None:
    """
    Writes request and response of one exchange to their folder.

    :returns: The folder, or None if the files are disabled or could not be written.
    """
    if _run_dir is None:
        return None
    folder = (_testscript_dir or _run_dir) / _folder_name(request_id, prepared)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "request.http").write_bytes(request_message)
        if response_message is not None:
            (folder / "response.http").write_bytes(response_message)
        if error_text is not None:
            (folder / "error.txt").write_text(error_text, encoding="utf-8")
    except OSError as e:
        log.warning("Could not write the communication log of %s to %s: %s", request_id, folder, e)
        return None
    return folder


def _log_exchange(request_id: str, request_message: bytes, response_message: bytes) -> None:
    """Writes the full exchange into the run log, if ``includeCommunicationInLog`` is set."""
    if not (_include_in_log and log.isEnabledFor(logging.DEBUG)):
        return
    log.debug("\n".join([
        f"----- {request_id} request -----",
        request_message.decode("utf-8", errors="replace"),
        f"----- {request_id} response -----",
        response_message.decode("utf-8", errors="replace"),
        f"----- end of {request_id} -----",
    ]))


def _folder_name(request_id: str, prepared: requests.PreparedRequest) -> str:
    """``REQ-0001_POST_Patient_123``: request ID, method and the URL path below the FHIR base."""
    url = (prepared.url or "").split("?", 1)[0]
    if _fhir_base and url.startswith(_fhir_base):
        path = url[len(_fhir_base):]
    else:
        path = urlsplit(url).path
    name = f"{request_id}_{prepared.method}"
    path = _safe_name(path)
    return f"{name}_{path}"[:60] if path else name


def _safe_name(text: str) -> str:
    """Replaces everything but letters, digits, ``.``, ``_`` and ``-`` to get a folder name."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")


def _reference(folder: Path | None) -> str:
    """Location of an exchange in the run log, relative to the communication log folder of the run."""
    if folder is None or _run_dir is None:
        return ""
    return f" [{folder.relative_to(_run_dir).as_posix()}]"


def _status_phrase(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return ""
