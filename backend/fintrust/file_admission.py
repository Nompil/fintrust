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
        details={"EMPTY_FILE":"The file is empty.","HEADER_ONLY_FILE":"The file has column headings but no transaction rows.","DUPLICATE_HEADERS":"Column headings must not repeat.","UNSUPPORTED_HEADERS":"The file contains columns outside the current transaction template.","MALFORMED_CSV":"The CSV structure is malformed.","INVALID_FILE_FORMAT":"The file is not readable CSV text.","TOO_MANY_ROWS":"The file exceeds 5,000 rows."}
        detail=details.get(error.code,"Use the current transaction CSV template and try again.")
        if error.code=="MISSING_HEADERS" and not legacy:
            import csv,io
            from .release_ingest import REQUIRED
            headers=set(csv.reader(io.StringIO(payload.decode("utf-8-sig"))).__next__())
            missing=sorted(REQUIRED-headers)
            if not {"source_transaction_id","source_reference"}&headers:missing.append("source_transaction_id (or source_reference)")
            detail="Missing columns: "+", ".join(missing)+". Use the current transaction CSV template."
        raise AdmissionError(codes.get(error.code,error.code),detail) from None
    return name,payload
