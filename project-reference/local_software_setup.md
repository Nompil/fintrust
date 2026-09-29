# Local Software Setup

## Already available

- **Git for Windows** is installed. The project is on local branch `main` with six local commits.
- **Python 3.14** is installed and was used for the passing local test suite. The CI workflow targets Python 3.11.
- **Visual Studio Code** is the current editor.
- **PostgreSQL 18.6** is installed; its Windows service is running and `localhost:5432` accepts connections. Its `psql.exe` is at `C:\Program Files\PostgreSQL\18\bin\psql.exe`, but that folder is not on `PATH`. CI uses PostgreSQL 16; local 18 is usable for development, with CI providing the version-parity check.
- **AWS CLI 2.37.5** is installed at `C:\Program Files\Amazon\AWSCLIV2\aws.exe`, but that folder is not on `PATH` and no CLI profiles are configured yet.
- **MySQL Workbench** is not required; this project uses PostgreSQL, not MySQL. Its executable was not found at the default installation path during the check.

## Install for the next development steps

### Required

1. **Python 3.11 (64-bit)**: recommended to match GitHub Actions and the intended Lambda runtime. Python 3.14 can remain installed; create the project virtual environment with the Python 3.11 executable when available.
2. **PostgreSQL client UI (optional)**: pgAdmin is convenient, but `psql.exe` is already installed. Use the running PostgreSQL 18 service locally; a separate PostgreSQL 16 install is optional if you want exact parity with CI.
3. **Configure AWS CLI credentials**: the CLI is installed but has no profiles. Follow the training account's approved login/profile process, not root access keys. Do not run resource-creation scripts until the correct account, region, and billing alarm are confirmed.
4. **Python extension for VS Code**: the screenshot shows installation in progress. Finish installing Microsoft's Python extension and select the project virtual environment as the interpreter.

### Needed for required portfolio artefacts / convenient testing

- **draw.io Desktop (diagrams.net)**: export the architecture and annotated ERD as the diagram deliverables required by the brief. The Mermaid diagrams in Markdown are useful source documentation but do not replace a submitted PDF/image export if the rubric asks for one.
- **Postman** is optional for API evidence; PowerShell `curl.exe` or the Flask test client can also exercise the routes.
- **AWS Toolkit for VS Code** is optional; the AWS console and CLI are sufficient for this project's scripts.
- **MySQL Workbench** is not used by this capstone and does not replace PostgreSQL/pgAdmin.

### Optional deployment helper

- **Docker Desktop with WSL 2**, or an equivalent Linux build environment, is needed if you build the Lambda deployment package locally. `psycopg2` must be packaged for the Lambda Linux runtime; a Windows-installed wheel cannot be copied into the Lambda zip. AWS CloudShell or an approved Linux build environment is an alternative.
- AWS SAM CLI is only needed if you choose to package/deploy with SAM; this repository currently uses boto3 provisioning scripts and does not require SAM for local tests.
- GitHub CLI is not required. Create the private GitHub repository in a browser, then add its URL as the local `origin` remote. There is currently no remote configured.

## Suggested setup commands (PowerShell)

After installing Python 3.11, open a new terminal in the project root and use the full executable path if `python` still points to the Windows Store alias:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m pytest -q
```

The current CLI folders are not on `PATH`. For this PowerShell window, add them with:

```powershell
$env:Path += ';C:\Program Files\PostgreSQL\18\bin;C:\Program Files\Amazon\AWSCLIV2'
psql --version
aws --version
```

Set local database values in `.env`. Do not put AWS access keys or production credentials in `.env` or Git. For the database integration tests, set `FINTRUST_TEST_DATABASE_URL` to a disposable local database only:

```powershell
$env:FINTRUST_TEST_DATABASE_URL = 'postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/fintrust_test'
python -m pytest tests/data_quality/test_constraints.py -q
```

The placeholder above is for a local test account. Never commit a real password.
