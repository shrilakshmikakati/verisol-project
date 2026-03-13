"""
FastAPI backend – E-Contract to Smart Contract pipeline
"""
import os, json, shutil, tempfile, zipfile, io, datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from core.econtract_kg    import (extract_text_from_file, extract_text_from_folder,
                                   build_econtract_knowledge_graph, graph_to_dict,
                                   render_graph_base64)
from core.smartcontract_kg import (kg_to_solidity, build_smartcontract_knowledge_graph,
                                    graph_to_dict as sc_graph_to_dict,
                                    render_graph_base64 as sc_render)
from core.kg_comparison    import compare_knowledge_graphs, refinement_loop

app = FastAPI(title="E-Contract → Smart Contract API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (production: use Redis/DB)
JOBS: dict = {}


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "model": "qwen2.5:7b"}


# ── Upload & Process ───────────────────────────────────────────────────────────

@app.post("/api/process")
async def process_econtract(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    contract_name: str = Form("EContract"),
):
    if not file:
        raise HTTPException(400, "No file uploaded")

    # Save upload
    suffix   = Path(file.filename).suffix
    orig_name = file.filename
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    content = await file.read()
    tmp.write(content)
    tmp.flush()
    tmp_path = tmp.name
    tmp.close()

    job_id = os.urandom(8).hex()
    JOBS[job_id] = {"status": "processing", "progress": 0, "message": "Starting...",
                    "orig_filename": orig_name, "orig_bytes": content}

    background_tasks.add_task(_run_pipeline, job_id, tmp_path, contract_name, suffix)
    return {"job_id": job_id}


async def _run_pipeline(job_id: str, file_path: str, contract_name: str, suffix: str):
    try:
        _update_job(job_id, 5, "Extracting text from e-contract...")

        if os.path.isdir(file_path):
            text = extract_text_from_folder(file_path)
        else:
            text = extract_text_from_file(file_path)

        if not text.strip():
            raise ValueError("Could not extract text from uploaded file")

        _update_job(job_id, 20, "Building e-contract knowledge graph...")
        G_e      = build_econtract_knowledge_graph(text)
        ec_dict  = graph_to_dict(G_e)
        ec_img   = render_graph_base64(G_e, "E-Contract Knowledge Graph")

        _update_job(job_id, 40, "Generating smart contract from KG...")
        initial_solidity = kg_to_solidity(ec_dict, contract_name)

        _update_job(job_id, 55, "Building smart contract knowledge graph...")
        G_s_init   = build_smartcontract_knowledge_graph(initial_solidity)
        sc_init_dict = sc_graph_to_dict(G_s_init)
        sc_init_img  = sc_render(G_s_init, "Smart Contract KG (Initial)")

        _update_job(job_id, 65, "Comparing knowledge graphs...")
        initial_cmp = compare_knowledge_graphs(G_e, G_s_init)

        final_solidity = initial_solidity
        history        = [{"iteration": 0, "accuracy": initial_cmp["accuracy"],
                           "node_similarity": initial_cmp["node_similarity"],
                           "edge_similarity": initial_cmp["edge_similarity"],
                           "type_coverage": initial_cmp["type_coverage"]["type_coverage_pct"],
                           "sc_nodes": initial_cmp["sc_node_count"], "is_valid": initial_cmp["is_valid"]}]
        iterations_used = 0

        if not initial_cmp["is_valid"]:
            _update_job(job_id, 70, "Running LLM refinement loop (Ollama qwen2.5:7b)...")
            final_solidity, llm_history, iterations_used = refinement_loop(
                initial_solidity, text, G_e
            )
            history.extend(llm_history)

        # Final KGs
        G_s_final   = build_smartcontract_knowledge_graph(final_solidity)
        sc_final_dict = sc_graph_to_dict(G_s_final)
        sc_final_img  = sc_render(G_s_final, "Smart Contract KG (Final)")
        final_cmp     = compare_knowledge_graphs(G_e, G_s_final)

        _update_job(job_id, 95, "Finalising results...")

        JOBS[job_id].update({
            "status":           "completed",
            "progress":         100,
            "message":          "Pipeline completed successfully",
            "econtract_text":   text[:2000],
            "ec_graph":         ec_dict,
            "ec_graph_img":     ec_img,
            "sc_initial":       initial_solidity,
            "sc_final":         final_solidity,
            "sc_graph_initial": sc_init_dict,
            "sc_graph_final":   sc_final_dict,
            "sc_graph_img":     sc_final_img,
            "initial_cmp":      initial_cmp,
            "final_cmp":        final_cmp,
            "history":          history,
            "iterations_used":  iterations_used,
            "contract_name":    contract_name,
        })

    except Exception as e:
        JOBS[job_id].update({"status": "failed", "progress": 0, "message": str(e)})
    finally:
        try:
            os.unlink(file_path)
        except Exception:
            pass


def _update_job(job_id: str, progress: int, message: str):
    JOBS[job_id]["progress"] = progress
    JOBS[job_id]["message"]  = message


# ── Job Status ─────────────────────────────────────────────────────────────────

@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.get("/api/job/{job_id}/solidity")
async def get_solidity(job_id: str):
    job = JOBS.get(job_id)
    if not job or job.get("status") != "completed":
        raise HTTPException(404, "Job not ready")
    return {"solidity": job["sc_final"], "contract_name": job["contract_name"]}


@app.get("/api/job/{job_id}/download-zip")
async def download_results_zip(job_id: str):
    """Stream a ZIP containing: original e-contract, final .sol, accuracy_results.json"""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.get("status") != "completed":
        raise HTTPException(400, "Job not completed yet")

    name      = job.get("contract_name", "contract")
    orig_name = job.get("orig_filename", "econtract.txt")
    orig_bytes = job.get("orig_bytes", b"")
    if isinstance(orig_bytes, str):
        orig_bytes = orig_bytes.encode()

    # Build accuracy results JSON
    fc = job.get("final_cmp", {})
    ic = job.get("initial_cmp", {})
    results = {
        "contract_name":     name,
        "generated_at":      datetime.datetime.utcnow().isoformat() + "Z",
        "solidity_version":  "0.8.16",
        "pipeline_summary": {
            "iterations_used":    job.get("iterations_used", 0),
            "llm_model":          "qwen2.5:7b",
        },
        "initial_comparison": {
            "accuracy":           ic.get("accuracy"),
            "node_similarity":    ic.get("node_similarity"),
            "edge_similarity":    ic.get("edge_similarity"),
            "type_coverage_pct":  ic.get("type_coverage", {}).get("type_coverage_pct"),
            "ec_nodes":           ic.get("ec_node_count"),
            "sc_nodes":           ic.get("sc_node_count"),
        },
        "final_comparison": {
            "accuracy":           fc.get("accuracy"),
            "node_similarity":    fc.get("node_similarity"),
            "edge_similarity":    fc.get("edge_similarity"),
            "type_coverage_pct":  fc.get("type_coverage", {}).get("type_coverage_pct"),
            "ec_nodes":           fc.get("ec_node_count"),
            "sc_nodes":           fc.get("sc_node_count"),
            "ec_edges":           fc.get("ec_edge_count"),
            "sc_edges":           fc.get("sc_edge_count"),
            "matched_nodes":      fc.get("matched_nodes", []),
            "unmatched_nodes":    fc.get("unmatched_nodes", []),
            "is_validated":       fc.get("is_valid", False),
        },
        "refinement_history": job.get("history", []),
        "ec_graph": {
            "node_count": fc.get("ec_node_count"),
            "edge_count": fc.get("ec_edge_count"),
            "nodes": [n["id"] for n in job.get("ec_graph", {}).get("nodes", [])[:50]],
        },
        "sc_graph": {
            "node_count": fc.get("sc_node_count"),
            "edge_count": fc.get("sc_edge_count"),
        },
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Original e-contract
        zf.writestr(f"econtract/{orig_name}", orig_bytes)
        # 2. Smart contract .sol
        zf.writestr(f"smart_contract/{name}.sol", (job.get("sc_final") or "").encode())
        # 3. Accuracy results JSON
        zf.writestr("accuracy_results.json", json.dumps(results, indent=2).encode())
        # 4. README
        readme = f"""# {name} — ContractForge Results
Generated: {results['generated_at']}
Solidity version: {results['solidity_version']}

## Files
- econtract/{orig_name}         → Original e-contract you uploaded
- smart_contract/{name}.sol     → Generated & validated Solidity smart contract
- accuracy_results.json         → Full KG comparison metrics & refinement log

## Accuracy Summary
Initial accuracy : {ic.get('accuracy', 'N/A')}%
Final accuracy   : {fc.get('accuracy', 'N/A')}%
Validated        : {'YES' if fc.get('is_valid') else 'NO (approximate)'}
LLM iterations   : {job.get('iterations_used', 0)}
"""
        zf.writestr("README.txt", readme.encode())

    buf.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="{name}_results.zip"'}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)


# ── Demo endpoint ──────────────────────────────────────────────────────────────

@app.post("/api/demo")
async def demo_pipeline(background_tasks: BackgroundTasks):
    """Run demo with a built-in sample e-contract."""
    demo_text = """SERVICE AGREEMENT

This Service Agreement ("Agreement") is entered into as of January 15, 2025, between
TechCorp Inc. ("Vendor") and ClientCo LLC ("Client").

1. SERVICES
Vendor shall provide software development services as described in Schedule A.
The Vendor agrees to deliver the software by March 31, 2025.

2. PAYMENT
Client shall pay Vendor $50,000 USD within 30 days of invoice.
Late payments shall incur a penalty of 1.5% per month.

3. TERMINATION
Either party may terminate this Agreement with 30 days written notice.
In the event of breach, the non-breaching party may terminate immediately.

4. CONDITIONS
Services shall commence provided that Client has paid the initial deposit of $10,000.
Vendor shall not subcontract without prior written consent of Client.

5. CONFIDENTIALITY
Both parties agree to maintain confidentiality of all proprietary information.
"""
    import tempfile, asyncio
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w")
    tmp.write(demo_text)
    tmp.flush()
    tmp_path = tmp.name
    tmp.close()

    job_id = os.urandom(8).hex()
    JOBS[job_id] = {"status": "processing", "progress": 0, "message": "Starting demo...",
                    "orig_filename": "demo_service_agreement.txt",
                    "orig_bytes": demo_text.encode()}
    background_tasks.add_task(_run_pipeline, job_id, tmp_path, "ServiceAgreement", ".txt")
    return {"job_id": job_id}
