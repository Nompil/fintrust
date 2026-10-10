"""Authoritative CSV-only admission. Reject entire unsupported file before processing."""
from werkzeug.utils import secure_filename
from .release_ingest import parse_file,FileRejected
MAX_FILE_BYTES=1048576
MAX_FILES_PER_BATCH=1
MIMES={"text/csv","application/csv","text/plain","application/octet-stream","application/vnd.ms-excel",""}
class AdmissionError(ValueError):
    def __init__(self,code,detail):self.code=code;self.detail=detail;super().__init__(detail)
def admit(file,*,legacy=False):
    name=secure_filename(file.filename or "")
    if not name.lower().endswith(".csv") or file.mimetype not in MIMES:
        raise AdmissionError("UNSUPPORTED_FILE_TYPE","Exactly one UTF-8 CSV file is supported")
    payload=file.stream.read(MAX_FILE_BYTES+1)
    if len(payload)>MAX_FILE_BYTES:raise AdmissionError("FILE_TOO_LARGE","CSV exceeds 1 MiB")
    try:
        if legacy:
            import csv,io
            text=payload.decode("utf-8-sig")
            if any(ord(c)<32 and c not in "\t\r\n" for c in text):raise FileRejected("INVALID_FILE_FORMAT")
            reader=csv.DictReader(io.StringIO(text),strict=True);headers=reader.fieldnames or []
            if not headers:raise FileRejected("EMPTY_FILE")
            if len(headers)!=len(set(headers)) or not {"account_id","amount","tx_date","tx_type"}<=set(headers):raise FileRejected("MISSING_HEADERS")
            if not list(reader):raise FileRejected("HEADER_ONLY_FILE")
        else:parse_file(payload)
    except UnicodeDecodeError:raise AdmissionError("UNSUPPORTED_ENCODING","UTF-8 CSV required") from None
    except __import__("csv").Error:raise AdmissionError("INVALID_FILE_FORMAT","Malformed CSV") from None
    except FileRejected as error:
        codes={"INVALID_ENCODING":"UNSUPPORTED_ENCODING","MISSING_HEADERS":"INVALID_CSV_SCHEMA","DUPLICATE_HEADERS":"INVALID_CSV_SCHEMA","UNSUPPORTED_HEADERS":"INVALID_CSV_SCHEMA","MALFORMED_CSV":"INVALID_FILE_FORMAT"}
        raise AdmissionError(codes.get(error.code,error.code),"CSV admission rejected: "+error.code) from None
    return name,payload
