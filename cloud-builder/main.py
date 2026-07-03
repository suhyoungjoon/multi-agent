import io
import os
import zipfile
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from models import WizardRequest, GenerateResponse, ScaleConfig
from providers.aws import generate_aws
from providers.azure import generate_azure

app = FastAPI(title="Cloud Project Builder")


@app.post("/generate", response_model=GenerateResponse)
def generate(req: WizardRequest) -> GenerateResponse:
    if req.provider == "aws":
        return generate_aws(req)
    return generate_azure(req)


@app.get("/download/terraform")
def download_terraform(
    provider: str = Query(...),
    app_type: str = Query(...),
    components: list[str] = Query(default=[]),
    traffic: str = Query("medium"),
    ha: bool = Query(False),
    multi_region: bool = Query(False),
):
    req = WizardRequest(
        provider=provider,
        app_type=app_type,
        components=components,
        scale=ScaleConfig(traffic=traffic, ha=ha, multi_region=multi_region),
    )
    result = generate_aws(req) if provider == "aws" else generate_azure(req)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for fname, content in result.terraform.items():
            zf.writestr(fname, content)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=terraform.zip"},
    )


_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
