#!/usr/bin/env python3
"""
ContractForge CLI — E-Contract → Smart Contract (terminal only)
Usage:
  python cli.py run       --file contract.txt  --name ServiceAgreement
  python cli.py run       --file contract.docx --name MyContract --output ./results
  python cli.py run-multi --file multipage.docx --name Contracts
  python cli.py demo
  python cli.py check
"""
import argparse, json, os, re, sys, time, shutil, zipfile, datetime, textwrap
from pathlib import Path

# ── Colour helpers ────────────────────────────────────────────────────────────
def _c(code, text): return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text
def red(t):    return _c("0;31", t)
def green(t):  return _c("0;32", t)
def yellow(t): return _c("1;33", t)
def cyan(t):   return _c("0;36", t)
def bold(t):   return _c("1",    t)
def dim(t):    return _c("2",    t)
def blue(t):   return _c("0;34", t)

# ── Progress bar ──────────────────────────────────────────────────────────────
def progress_bar(pct: float, width: int = 40) -> str:
    filled = int(width * pct / 100)
    bar    = "█" * filled + "░" * (width - filled)
    color  = green if pct >= 100 else cyan if pct >= 60 else yellow
    return f"[{color(bar)}] {bold(f'{pct:5.1f}%')}"

def print_progress(step: str, pct: float):
    bar = progress_bar(pct)
    print(f"\r  {bar}  {dim(step[:55]):<55}", end="", flush=True)

def print_step(icon: str, msg: str):
    print(f"\n  {icon}  {msg}")

# ── Banner ─────────────────────────────────────────────────────────────────────
BANNER = f"""
{cyan('  ╔════════════════════════════════════════════=====================══════════╗')}
{cyan('  ║')}  {bold('ContractForge')} — E-Contract → Smart Contract CLI      {cyan('║')}
{cyan('  ║')}  {dim('NLP · Knowledge Graph · Solidity 0.8.16 · qwen2.5:7b')}  {cyan('║')}
{cyan('  ╚════════════════════════════════════════════=====================══════════╝')}
"""

# ── Import backend core (must run from project root or backend/) ──────────────
def _setup_path():
    here = Path(__file__).resolve().parent
    candidates = [here, here / "backend", here.parent / "backend"]
    for c in candidates:
        if (c / "core" / "econtract_kg.py").exists():
            sys.path.insert(0, str(c))
            return str(c)
    print(red("  ✗  Cannot find backend/core. Run from econtract-system/ root."))
    sys.exit(1)

# ── Check dependencies ────────────────────────────────────────────────────────
def cmd_check(_args):
    print(BANNER)
    print(bold("  System Check\n"))
    ok = True
    checks = [
        ("spacy",          "import spacy"),
        ("networkx",       "import networkx"),
        ("matplotlib",     "import matplotlib"),
        ("numpy",          "import numpy"),
        ("pandas",         "import pandas"),
        ("web3",           "import web3"),
        ("solcx",          "import solcx"),
        ("docx",           "from docx import Document"),
        ("pytesseract",    "import pytesseract"),
        ("PIL",            "from PIL import Image"),
        ("ollama reachable","import requests; requests.get('http://localhost:11434/api/tags',timeout=3)"),
        ("spaCy model",    "import spacy; spacy.load('en_core_web_sm')"),
    ]
    for name, stmt in checks:
        try:
            exec(stmt)
            print(f"  {green('✓')}  {name}")
        except Exception as e:
            print(f"  {red('✗')}  {name}  {dim(str(e)[:60])}")
            ok = False
    print()
    if ok:
        print(green("  All checks passed — ready to run.\n"))
    else:
        print(yellow("  Fix missing items, then re-run: python cli.py check\n"))

# ── Core pipeline (synchronous, prints live progress) ─────────────────────────
def run_pipeline(file_path: str, contract_name: str, output_dir: str):
    _setup_path()
    from core.econtract_kg    import (extract_text_from_file, extract_text_from_folder,
                                      build_econtract_knowledge_graph, graph_to_dict,
                                      render_graph_base64)
    from core.smartcontract_kg import (kg_to_solidity, build_smartcontract_knowledge_graph,
                                       graph_to_dict as sc_graph_to_dict,
                                       render_graph_base64 as sc_render)
    from core.kg_comparison    import compare_knowledge_graphs, refinement_loop

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ── Real Progress Tracking ────────────────────────────────
    # Base percentages for pipeline sections (adjusted by actual work units)
    progress_state = {
        "extraction_pct": 0.0,
        "ec_kg_pct": 0.0,
        "solidity_pct": 0.0,
        "sc_kg_pct": 0.0,
        "comparison_pct": 0.0,
        "refinement_pct": 0.0,
        "final_pct": 0.0,
        "save_pct": 0.0,
    }
    
    # Track sub-task progress to update main milestone
    def update_progress():
        """Calculate overall progress from component percentages."""
        # Weighted sections of the pipeline
        overall = (
            progress_state["extraction_pct"] * 0.05 +      # 5%
            progress_state["ec_kg_pct"] * 0.20 +           # 20%
            progress_state["solidity_pct"] * 0.05 +        # 5%
            progress_state["sc_kg_pct"] * 0.20 +           # 20%
            progress_state["comparison_pct"] * 0.10 +      # 10%
            progress_state["refinement_pct"] * 0.25 +      # 25%
            progress_state["final_pct"] * 0.10 +           # 10%
            progress_state["save_pct"] * 0.05              # 5%
        )
        return max(0, min(100, overall))

    # ── Step 1: Extract text ──────────────────────────────────
    print_progress("Extracting text from e-contract...", 1)
    if os.path.isdir(file_path):
        from core.econtract_kg import extract_text_from_folder
        text = extract_text_from_folder(file_path)
    else:
        text = extract_text_from_file(file_path)

    if not text.strip():
        print(f"\n  {red('✗')}  Could not extract text from file.")
        sys.exit(1)

    progress_state["extraction_pct"] = 100.0
    
    # Quality assessment — a real contract should be 2000+ chars
    chars     = len(text)
    sentences = len(re.findall(r'[.!?]', text))
    words     = len(text.split())
    if chars >= 3000:
        quality = green("good")
    elif chars >= 1500:
        quality = yellow("moderate — may miss some clauses")
    elif chars >= 500:
        quality = yellow("short — check if file has full content")
    else:
        quality = red("very short — extraction likely incomplete!")

    print_step(cyan("①"), f"Text extracted  "
               f"{dim(str(chars) + ' chars  ' + str(words) + ' words  ~' + str(sentences) + ' sentences')}  [{quality}]")

    # Warn explicitly if suspiciously short
    if chars < 1500:
        print(f"     {yellow('⚠  Warning:')} Only {chars} chars extracted.")
        print(f"     {dim('   If the document has more content, check for text boxes,')}")
        print(f"     {dim('   scanned images, or password protection.')}")

    # Show first 4 lines so user can verify content looks right
    preview_lines = [l.strip() for l in text.split('\n') if l.strip()][:4]
    for pl in preview_lines:
        print(f"     {dim(pl[:90])}")

    # ── Step 2: E-Contract KG ─────────────────────────────────
    print_progress("Building e-contract knowledge graph (NLP)...", update_progress())
    G_e     = build_econtract_knowledge_graph(text)
    ec_dict = graph_to_dict(G_e)
    
    ec_nodes = G_e.number_of_nodes()
    ec_edges = G_e.number_of_edges()
    progress_state["ec_kg_pct"] = 100.0  # EC KG is deterministic, finishes as completed
    
    print_step(cyan("②"), f"E-Contract KG built  "
               f"{dim(f'{ec_nodes} nodes, {ec_edges} edges')}")
    _print_kg_summary(ec_dict, "E-Contract")

    # ── Step 3: Generate Solidity ─────────────────────────────
    print_progress("Generating smart contract from KG...", update_progress())
    initial_solidity = kg_to_solidity(ec_dict, contract_name)
    sol_lines = len(initial_solidity.splitlines())
    progress_state["solidity_pct"] = 100.0
    
    print_step(cyan("③"), f"Initial Solidity generated  {dim(f'({sol_lines} lines)')}")

    # ── Step 4: Smart Contract KG ─────────────────────────────
    print_progress("Building smart contract knowledge graph (AST)...", update_progress())
    G_s_init = build_smartcontract_knowledge_graph(initial_solidity)
    
    sc_nodes_init = G_s_init.number_of_nodes()
    sc_edges_init = G_s_init.number_of_edges()
    progress_state["sc_kg_pct"] = 100.0  # SC KG is deterministic from input Solidity
    
    print_step(cyan("④"), f"Smart Contract KG built  "
               f"{dim(f'{sc_nodes_init} nodes, {sc_edges_init} edges')}")

    # ── Step 5: Initial comparison ────────────────────────────
    print_progress("Comparing knowledge graphs...", update_progress())
    initial_cmp = compare_knowledge_graphs(G_e, G_s_init, initial_solidity)
    progress_state["comparison_pct"] = 100.0
    
    print_step(cyan("⑤"), "KG Comparison (initial)")
    _print_comparison(initial_cmp, "Initial")

    history = [{"iteration": 0, **_cmp_row(initial_cmp)}]

    # ── Step 6: Refinement loop ───────────────────────────────
    final_solidity  = initial_solidity
    iterations_used = 0

    if not initial_cmp["is_valid"]:
        print_progress("Starting LLM refinement...", update_progress())
        acc_now = initial_cmp['accuracy']
        print_step(yellow("⑥"), f"Accuracy {acc_now}% < 85% or missing types — starting LLM refinement (max 5 iterations)...")
        final_solidity, llm_history, iterations_used = _refinement_with_progress(
            initial_solidity, text, G_e, refinement_loop, progress_state, update_progress
        )
        history.extend(llm_history)
        progress_state["refinement_pct"] = 100.0
    else:
        print_step(green("⑥"), f"Accuracy {initial_cmp['accuracy']}% ≥ 85% with full type coverage — validated, no LLM refinement needed!")
        progress_state["refinement_pct"] = 100.0

    # ── Step 7: Final KG + comparison ────────────────────────
    print_progress("Building final smart contract KG...", update_progress())
    G_s_final    = build_smartcontract_knowledge_graph(final_solidity)
    progress_state["final_pct"] = 100.0

    final_cmp = compare_knowledge_graphs(G_e, G_s_final, final_solidity)
    print_step(cyan("⑦"), "KG Comparison (final)")
    _print_comparison(final_cmp, "Final")

    # ── Save outputs ──────────────────────────────────────────
    print_progress("Saving output files...", update_progress())

    sol_path = out / f"{contract_name}.sol"
    sol_path.write_text(final_solidity, encoding="utf-8")
    progress_state["save_pct"] = 33.0

    print_progress(f"Saving results.json...", update_progress())
    results = _build_results_dict(
        contract_name, file_path, initial_cmp, final_cmp, history, iterations_used
    )
    json_path = out / "results.json"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    progress_state["save_pct"] = 66.0

    print_progress(f"Copying original contract...", update_progress())
    # Copy original e-contract
    orig_dest = out / ("econtract" + Path(file_path).suffix)
    try:
        shutil.copy2(file_path, orig_dest)
    except Exception:
        pass
    progress_state["save_pct"] = 100.0

    # Mark pipeline as 100% complete
    print_progress("Pipeline complete!", 100)

    # ── Final summary ─────────────────────────────────────────
    print(f"\n\n{'─'*60}")
    _print_final_summary(final_cmp, iterations_used, out, sol_path)

    return str(sol_path)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cmp_row(c: dict) -> dict:
    return {
        "accuracy":        c["accuracy"],
        "node_similarity": c["node_similarity"],
        "edge_similarity": c["edge_similarity"],
        "type_coverage":   c["type_coverage"]["type_coverage_pct"],
        "sc_nodes":        c["sc_node_count"],
        "is_valid":        c["is_valid"],
    }


def _print_kg_summary(kg: dict, label: str):
    types: dict = {}
    for n in kg.get("nodes", []):
        t = n.get("entity_type", "GENERIC")
        types[t] = types.get(t, 0) + 1
    top = sorted(types.items(), key=lambda x: -x[1])[:6]
    row = "  ".join(f"{dim(t)}:{cyan(str(c))}" for t, c in top)
    print(f"     {dim('Entities:')}  {row}")


def _print_comparison(cmp: dict, label: str):
    acc          = cmp["accuracy"]
    completeness = cmp.get("completeness", 100.0)
    status       = cmp.get("completeness_status", "")
    is_valid     = cmp.get("is_valid", False)

    # Color: green=validated(≥85%+full types), yellow=partial, red=poor
    color = green if is_valid else yellow if acc >= 70 else red

    # Accuracy line
    valid_tag = "  " + green("✓ VALIDATED") if is_valid else ""
    print("     " + bold("Accuracy") + "       " + color(str(round(acc, 1)) + "%") + valid_tag)

    # Show completeness status only when something is incomplete
    if completeness < 100.0 and status:
        print("     " + dim("Completeness") + "    " + (green if completeness >= 100 else yellow)(status))

    node_s = str(round(cmp["node_similarity"], 1)) + "%"
    edge_s = str(round(cmp["edge_similarity"], 1)) + "%"
    type_s = str(round(cmp["type_coverage"]["type_coverage_pct"], 1)) + "%"
    print("     Node similarity  " + cyan(node_s) + "   Edge similarity  " + cyan(edge_s) + "   Type coverage  " + cyan(type_s))
    tiers = cmp.get("node_tiers", {})
    if tiers:
        ta = str(round(tiers.get("tier_a", 0), 1)) + "%"
        tb = str(round(tiers.get("tier_b", 0), 1)) + "%"
        tc = str(round(tiers.get("tier_c", 0), 1)) + "%"
        print("     " + dim("  Node tiers →") + "  TypeMatch:" + cyan(ta) + "  LabelMatch:" + cyan(tb) + "  ValueCov:" + cyan(tc))
    missing_types = cmp.get("type_coverage", {}).get("missing_semantic", [])
    if missing_types:
        print("     " + yellow("Missing types:") + "  " + dim(", ".join(missing_types)))
    unmatched = [n for n in cmp.get("unmatched_nodes", []) if n and len(n) > 2]
    if unmatched:
        shown = ", ".join(unmatched[:5])
        extra = " +" + str(len(unmatched) - 5) + " more" if len(unmatched) > 5 else ""
        print("     " + yellow("Unmatched:") + "  " + dim(shown + extra))



def _refinement_with_progress(initial_solidity, text, G_e, refinement_loop_fn, progress_state, update_progress_fn):
    """Delegates to the additive patch refinement_loop; shows per-iter progress."""
    # Import from core (not backend.core) — sys.path is already set to backend/ by _setup_path()
    from core.kg_comparison import refinement_loop
    import threading
    print("")

    # Run refinement in a thread with generous timeout.
    # MAX_ITERATIONS=5 × 60s Ollama timeout × 2 retries = 600s theoretical max.
    # We allow 660s (11 min) and warn the user if it stalls.
    THREAD_TIMEOUT = 660
    result = [None, None, 0]  # [final_code, history, iters_used]
    error  = [None]

    def run_refinement():
        try:
            result[0], result[1], result[2] = refinement_loop(initial_solidity, text, G_e)
        except Exception as e:
            error[0] = e

    thread = threading.Thread(target=run_refinement, daemon=False)
    thread.start()
    thread.join(timeout=THREAD_TIMEOUT)

    # If refinement timed out, warn explicitly so the user knows the output is unrefined
    if thread.is_alive():
        print(yellow(f"     ⚠  Refinement timed out after {THREAD_TIMEOUT}s — output is the initial (unrefined) contract."))
        print(yellow("     ⚠  Check that Ollama is running: ollama serve"))
        return initial_solidity, [], 0

    if error[0]:
        print(yellow(f"     ⚠  Refinement error: {error[0]} — using initial solidity"))
        return initial_solidity, [], 0

    final_code, history, iters_used = result

    if final_code is None:
        return initial_solidity, [], 0

    for h in history:
        i        = h["iteration"]
        acc      = h["accuracy"]
        banked   = h.get("banked", acc)
        improved = h.get("improved", False)
        patch    = h.get("patch_applied", False)
        color    = green if acc >= 85 else yellow if acc >= 70 else red
        b_color  = green if improved else dim

        status   = green("✓ DONE")       if h["is_valid"]  else (
                   green("↑ banked")     if improved       else
                   yellow("↺ rollback")  if patch          else
                   dim("→ refining..."))

        print("     Iter " + str(i) +
              "  accuracy=" + color(str(round(acc, 1)) + "%") +
              "  banked=" + b_color(str(round(banked, 1)) + "%") +
              "  nodes=" + cyan(str(h["sc_nodes"])) +
              "  patch=" + (green("YES") if patch else dim("NO")) +
              "  " + status)

        # Update refinement progress based on iteration completion
        if iters_used > 0:
            progress_state["refinement_pct"] = (i / iters_used) * 100.0
            print_progress(f"Refinement iteration {i}/{iters_used}...", update_progress_fn())

    return final_code, history, iters_used



def _build_results_dict(name, file_path, initial_cmp, final_cmp, history, iterations):
    return {
        "contract_name":    name,
        "source_file":      str(file_path),
        "generated_at":     datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z'),
        "solidity_version": "0.8.16",
        "pipeline": {
            "iterations_used": iterations,
            "llm_model":       "qwen2.5:7b",
        },
        "initial_comparison": {
            "accuracy":            initial_cmp.get("accuracy"),
            "base_accuracy":       initial_cmp.get("base_accuracy"),
            "completeness":        initial_cmp.get("completeness", 100.0),
            "completeness_status": initial_cmp.get("completeness_status", "✓ VALIDATED (100%)"),
            "node_similarity":     initial_cmp.get("node_similarity"),
            "edge_similarity":     initial_cmp.get("edge_similarity"),
            "type_coverage_pct":   initial_cmp.get("type_coverage", {}).get("type_coverage_pct"),
            "ec_nodes":            initial_cmp.get("ec_node_count"),
            "sc_nodes":            initial_cmp.get("sc_node_count"),
        },
        "final_comparison": {
            "accuracy":            final_cmp.get("accuracy"),
            "base_accuracy":       final_cmp.get("base_accuracy"),
            "completeness":        final_cmp.get("completeness", 100.0),
            "completeness_status": final_cmp.get("completeness_status", "✓ VALIDATED (100%)"),
            "node_similarity":     final_cmp.get("node_similarity"),
            "edge_similarity":     final_cmp.get("edge_similarity"),
            "type_coverage_pct":   final_cmp.get("type_coverage", {}).get("type_coverage_pct"),
            "ec_nodes":            final_cmp.get("ec_node_count"),
            "sc_nodes":            final_cmp.get("sc_node_count"),
            "ec_edges":            final_cmp.get("ec_edge_count"),
            "sc_edges":            final_cmp.get("sc_edge_count"),
            "matched_nodes":       final_cmp.get("matched_nodes", []),
            "unmatched_nodes":     final_cmp.get("unmatched_nodes", []),
            "is_validated":        final_cmp.get("is_valid", False),
        },
        "refinement_history": history,
    }


def _make_zip(zip_path: Path, out_dir: Path, name: str, orig_file: str,
              solidity: str, results: dict):
    fc = results["final_comparison"]
    ic = results["initial_comparison"]
    readme = textwrap.dedent(f"""
        ContractForge Results — {name}
        Generated : {results['generated_at']}
        Solidity  : pragma ^0.8.16

        FILES
          econtract/*          — original e-contract
          {name}.sol           — generated smart contract
          accuracy_results.json
          econtract_kg.png     — e-contract knowledge graph
          smartcontract_kg_final.png

        ACCURACY
          Initial : {ic.get('accuracy','N/A')}%
          Final   : {fc.get('accuracy','N/A')}%
          Valid   : {'YES' if fc.get('is_validated') else 'NO'}
          Iters   : {results['pipeline']['iterations_used']}
    """).strip()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"econtract/{Path(orig_file).name}", Path(orig_file).read_bytes())
        zf.writestr(f"{name}.sol", solidity.encode())
        zf.writestr("results.json", json.dumps(results, indent=2).encode())
        zf.writestr("README.txt", readme.encode())
        

def _print_final_summary(cmp, iterations, out, sol_path):
    acc   = cmp["accuracy"]
    valid = cmp["is_valid"]
    color = green if valid else yellow
    type_cov_pct = cmp.get("type_coverage", {}).get("type_coverage_pct", 0)

    print("\n  " + bold("RESULTS") + "\n")
    print("  " + "Accuracy".ljust(22) + " " + color(bold(str(round(acc, 1)) + "%")))
    print("  " + "Type coverage".ljust(22) + " " + (green if type_cov_pct >= 100 else yellow)(str(round(type_cov_pct, 1)) + "%"))
    print("  " + "Status".ljust(22) + " " + (green("✓ VALIDATED") if valid else yellow("⚠ NEEDS REFINEMENT")))
    print("  " + "LLM iterations".ljust(22) + " " + cyan(str(iterations)))
    print("  " + "EC nodes".ljust(22) + " " + dim(str(cmp["ec_node_count"])) + "   SC nodes  " + dim(str(cmp["sc_node_count"])))
    print("\n  " + bold("OUTPUT FILES") + "\n")

    # Find the copied econtract file
    econtract_files = list(out.glob("econtract.*"))
    if econtract_files:
        print("  " + green("→") + "  Original contract " + cyan(str(econtract_files[0])))

    print("  " + green("→") + "  Smart contract    " + cyan(str(sol_path)))
    print("  " + green("→") + "  Results JSON      " + cyan(str(out / "results.json")))
    print("\n" + "─" * 60 + "\n")


# ── Demo command ──────────────────────────────────────────────────────────────
DEMO_CONTRACT = """\
SERVICE AGREEMENT

This Service Agreement ("Agreement") is entered into as of January 15, 2025,
between TechCorp Inc. ("Vendor") and ClientCo LLC ("Client").

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
Services shall commence provided that Client has paid the deposit of $10,000.
Vendor shall not subcontract without prior written consent of Client.

5. CONFIDENTIALITY
Both parties agree to maintain confidentiality of all proprietary information.
Vendor shall assign all intellectual property to Client upon final payment.

6. DISPUTE RESOLUTION
Any disputes shall be resolved by ICC arbitration under English Law.
"""


def cmd_demo(args):
    print(BANNER)
    print(bold("  Demo Mode — built-in Service Agreement\n"))
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w")
    tmp.write(DEMO_CONTRACT); tmp.flush(); tmp.close()
    out = getattr(args, "output", None) or "./contractforge_output/demo"
    run_pipeline(tmp.name, "ServiceAgreement", out)
    os.unlink(tmp.name)


# ── Run multi-page command ────────────────────────────────────────────────────
def cmd_run_multi(args):
    """Process multi-page DOCX: generates one smart contract per page/section."""
    print(BANNER)
    path = Path(args.file)
    if not path.exists():
        print(red(f"  ✗  File not found: {args.file}"))
        sys.exit(1)
    
    # Extract pages from document
    _setup_path()
    from core.econtract_kg import extract_pages_from_docx
    
    if path.suffix.lower() != ".docx":
        print(red(f"  ✗  run-multi only supports .docx files (got {path.suffix})"))
        sys.exit(1)
    
    pages = extract_pages_from_docx(str(path))
    if not pages:
        print(yellow(f"  ⚠  Document doesn't have multiple pages/sections, using single-page mode"))
        print(f"     (Use 'python cli.py run' instead)\n")
        return
    
    base_name = args.name or path.stem.replace(" ", "_") or "Contract"
    base_out  = args.output or f"./contractforge_output/{base_name}_multi"
    
    print(f"  {bold('Input')}   {cyan(str(path.resolve()))}")
    print(f"  {bold('Pages')}   {cyan(str(len(pages)))}")
    print(f"  {bold('Output')}  {cyan(str(Path(base_out).resolve()))}\n")
    
    # Process each page as separate contract
    for page_num, content, title in pages:
        page_name = f"{base_name}_page{page_num}"
        page_out  = f"{base_out}/{page_name}"
        
        print(f"\n{cyan('─'*60)}")
        print(f"    Page {page_num}/{len(pages)}  {dim(title[:40])}")
        print(f"{cyan('─'*60)}\n")
        
        # Create temp file for this page
        temp_file = Path(page_out) / "temp.txt"
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file.write_text(content)
        
        try:
            run_pipeline(str(temp_file), page_name, page_out)
        except Exception as e:
            print(red(f"\n  ✗  Error processing page {page_num}: {str(e)[:80]}"))
            continue
        finally:
            # Clean up temp file
            if temp_file.exists():
                temp_file.unlink()
    
    print(f"\n{green('✓')} All pages processed! Check {base_out} for results.")


# ── Run command ───────────────────────────────────────────────────────────────
def cmd_run(args):
    print(BANNER)
    path = Path(args.file)
    if not path.exists():
        print(red(f"  ✗  File not found: {args.file}"))
        sys.exit(1)
    name = args.name or path.stem.replace(" ", "_") or "Contract"
    out  = args.output or f"./contractforge_output/{name}"
    print(f"  {bold('Input')}   {cyan(str(path.resolve()))}")
    print(f"  {bold('Name')}    {cyan(name)}")
    print(f"  {bold('Output')}  {cyan(str(Path(out).resolve()))}\n")
    run_pipeline(str(path), name, out)


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="contractforge",
        description="E-Contract → Smart Contract (terminal CLI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
          Examples:
            python cli.py run       --file agreement.txt       --name ServiceAgreement
            python cli.py run       --file contract.docx       --name NDA --output ./out
            python cli.py run       --file scan.png            --name ImageContract
            python cli.py run-multi --file multipage.docx      --name Contracts
            python cli.py demo
            python cli.py check
        """)
    )
    sub = parser.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="Process a single-page e-contract file")
    p_run.add_argument("--file",   required=True, help="Path to .txt/.docx/.png/.jpg or folder")
    p_run.add_argument("--name",   default="",    help="Contract name (default: filename stem)")
    p_run.add_argument("--output", default="",    help="Output directory (default: ./contractforge_output/<name>)")

    p_multi = sub.add_parser("run-multi", help="Process multi-page DOCX (separate contract per page)")
    p_multi.add_argument("--file",   required=True, help="Path to .docx file with multiple pages/sections")
    p_multi.add_argument("--name",   default="",    help="Base contract name for all pages")
    p_multi.add_argument("--output", default="",    help="Output directory (default: ./contractforge_output/<name>_multi)")

    p_demo = sub.add_parser("demo", help="Run with built-in sample contract")
    p_demo.add_argument("--output", default="./contractforge_output/demo", help="Output directory")

    sub.add_parser("check", help="Check all dependencies are installed")

    args = parser.parse_args()
    if   args.cmd == "run":       cmd_run(args)
    elif args.cmd == "run-multi": cmd_run_multi(args)
    elif args.cmd == "demo":      cmd_demo(args)
    elif args.cmd == "check":     cmd_check(args)
    else:                         parser.print_help()


if __name__ == "__main__":
    main()
