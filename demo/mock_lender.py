from fastapi import FastAPI, Header

app = FastAPI(title="Custos demo lender")


@app.post("/loan")
async def loan(x_custos_attestation: str | None = Header(default=None)):
    if not x_custos_attestation:
        return {"accepted": False, "reason": "missing Custos attestation"}
    return {"accepted": True, "message": "loan request reached the lender with a Custos attestation"}
