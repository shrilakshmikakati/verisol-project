#!/usr/bin/env python3
"""
ContractForge CLI — E-Contract → Smart Contract
Usage:
  python cli.py run       --file contract.txt  --name ServiceAgreement
  python cli.py run       --file contract.docx --name MyContract --output ./results
  python cli.py run-multi --file multipage.docx --name Contracts
  python cli.py demo
  python cli.py check
"""
import argparse, json, os, re, sys, shutil, datetime, textwrap, threading
from pathlib import Path

# ── Colour helpers ─────────────────────────────────────────────────────────────
def _c(code, t): return f"\033[{code}m{t}\033[0m" if sys.stdout.isatty() else t
def red(t):    return _c("0;31", t)
def green(t):  return _c("0;32", t)
def yellow(t): return _c("1;33", t)
def cyan(t):   return _c("0;36", t)
def bold(t):   return _c("1",    t)
def dim(t):    return _c("2",    t)

def progress_bar(pct, width=40):
    filled = int(width * pct / 100)
    bar = "█" * filled + "░" * (width - filled)
    color = green if pct >= 100 else cyan if pct >= 60 else yellow
    return f"[{color(bar)}] {bold(f'{pct:5.1f}%')}"

def print_progress(step, pct):
    print(f"\r  {progress_bar(pct)}  {dim(step[:55]):<55}", end="", flush=True)

def print_step(icon, msg):
    print(f"\n  {icon}  {msg}")

BANNER = f"""
{cyan('  ╔══════════════════════════════════════════════════════════════╗')}
{cyan('  ║')}  {bold('ContractForge')} — E-Contract → Smart Contract CLI  {cyan('║')}
{cyan('  ║')}  {dim('NLP · Knowledge Graph · Solidity 0.8.16 · qwen2.5:7b')}  {cyan('║')}
{cyan('  ╚══════════════════════════════════════════════════════════════╝')}
"""

def _setup_path():
    here = Path(__file__).resolve().parent
    for c in [here, here / "backend", here.parent / "backend"]:
        if (c / "core" / "econtract_kg.py").exists():
            sys.path.insert(0, str(c))
            return
    print(red("  ✗  Cannot find backend/core.")); sys.exit(1)

# ── Check ──────────────────────────────────────────────────────────────────────
def cmd_check(_args):
    print(BANNER); print(bold("  System Check\n"))
    checks = [
        ("spacy",          "import spacy"),
        ("networkx",       "import networkx"),
        ("matplotlib",     "import matplotlib"),
        ("web3",           "import web3"),
        ("solcx",          "import solcx"),
        ("docx",           "from docx import Document"),
        ("pytesseract",    "import pytesseract"),
        ("PIL",            "from PIL import Image"),
        ("ollama",         "import requests; requests.get('http://localhost:11434/api/tags',timeout=3)"),
        ("spaCy model",    "import spacy; spacy.load('en_core_web_sm')"),
    ]
    ok = True
    for name, stmt in checks:
        try:
            exec(stmt)
            print(f"  {green('✓')}  {name}")
        except Exception as e:
            print(f"  {red('✗')}  {name}  {dim(str(e)[:60])}"); ok = False
    print()
    print(green("  All checks passed.\n") if ok else yellow("  Fix missing items.\n"))

# ── Core pipeline ──────────────────────────────────────────────────────────────
def run_pipeline(file_path, contract_name, output_dir, page_number=0, page_title=""):
    _setup_path()
    from core.econtract_kg    import extract_text_from_file, build_econtract_knowledge_graph, graph_to_dict
    from core.smartcontract_kg import kg_to_solidity, build_smartcontract_knowledge_graph
    from core.kg_comparison    import compare_knowledge_graphs, refinement_loop

    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    pct = {"e": 0, "kg": 0, "sol": 0, "sc": 0, "cmp": 0, "ref": 0, "fin": 0, "sav": 0}
    def overall():
        return max(0, min(100,
            pct["e"]*0.05 + pct["kg"]*0.20 + pct["sol"]*0.05 + pct["sc"]*0.20 +
            pct["cmp"]*0.10 + pct["ref"]*0.25 + pct["fin"]*0.10 + pct["sav"]*0.05))

    # ① Extract
    print_progress("Extracting text...", 1)
    text = extract_text_from_file(file_path)
    if not text.strip():
        print(f"\n  {red('✗')}  Could not extract text."); sys.exit(1)
    pct["e"] = 100
    chars, words = len(text), len(text.split())
    quality = green("good") if chars >= 3000 else yellow("moderate") if chars >= 1500 else yellow("short") if chars >= 500 else red("very short")
    print_step(cyan("①"), f"Text extracted  {dim(f'{chars} chars  {words} words')}  [{quality}]")
    if chars < 1500:
        print(f"     {yellow('⚠  Warning:')} Only {chars} chars. Check for text boxes or scanned images.")
    for pl in [l.strip() for l in text.split('\n') if l.strip()][:3]:
        print(f"     {dim(pl[:90])}")

    # ② E-Contract KG
    print_progress("Building e-contract KG (NLP)...", overall())
    G_e = build_econtract_knowledge_graph(text)
    ec_dict = graph_to_dict(G_e)
    pct["kg"] = 100
    print_step(cyan("②"), f"E-Contract KG  {dim(f'{G_e.number_of_nodes()} nodes, {G_e.number_of_edges()} edges')}")
    types = {}
    for n in ec_dict.get("nodes", []):
        t = n.get("entity_type", "GENERIC"); types[t] = types.get(t, 0) + 1
    print(f"     {dim('Entities:')}  {'  '.join(f'{dim(t)}:{cyan(str(c))}' for t,c in sorted(types.items(), key=lambda x:-x[1])[:6])}")

    # ③ Initial Solidity
    print_progress("Generating smart contract...", overall())
    initial_sol = kg_to_solidity(ec_dict, contract_name, page_number=page_number, page_title=page_title)
    pct["sol"] = 100
    print_step(cyan("③"), f"Initial Solidity  {dim(f'({len(initial_sol.splitlines())} lines)')}")

    # ④ SC KG
    print_progress("Building smart contract KG (AST)...", overall())
    G_s_init = build_smartcontract_knowledge_graph(initial_sol)
    pct["sc"] = 100
    print_step(cyan("④"), f"SC KG  {dim(f'{G_s_init.number_of_nodes()} nodes, {G_s_init.number_of_edges()} edges')}")

    # ⑤ Compare
    print_progress("Comparing KGs...", overall())
    init_cmp = compare_knowledge_graphs(G_e, G_s_init, initial_sol)
    pct["cmp"] = 100
    print_step(cyan("⑤"), "KG Comparison (initial)")
    _print_cmp(init_cmp)

    # ⑥ Refinement
    final_sol, iters = initial_sol, 0
    if not init_cmp["is_valid"]:
        print_step(yellow("⑥"), f"Accuracy {init_cmp['accuracy']}% — starting LLM refinement (max 5 iters)...")
        final_sol, hist, iters = _run_refinement(initial_sol, text, G_e, refinement_loop, pct, overall)
        pct["ref"] = 100
    else:
        print_step(green("⑥"), f"Accuracy {init_cmp['accuracy']}% ✓ VALIDATED — no refinement needed")
        pct["ref"] = 100

    # ⑦ Final
    print_progress("Building final SC KG...", overall())
    G_s_final = build_smartcontract_knowledge_graph(final_sol)
    pct["fin"] = 100
    final_cmp = compare_knowledge_graphs(G_e, G_s_final, final_sol)
    print_step(cyan("⑦"), "KG Comparison (final)")
    _print_cmp(final_cmp)

    # Save
    print_progress("Saving...", overall())
    sol_path = out / f"{contract_name}.sol"
    sol_path.write_text(final_sol, encoding="utf-8")
    results = {
        "contract_name": contract_name, "source_file": str(file_path),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),
        "solidity_version": "0.8.16",
        "pipeline": {"iterations_used": iters, "llm_model": "qwen2.5:7b"},
        "initial_comparison": {k: init_cmp.get(k) for k in ("accuracy","node_similarity","edge_similarity","is_valid")},
        "final_comparison": {k: final_cmp.get(k) for k in ("accuracy","node_similarity","edge_similarity","is_valid","ec_node_count","sc_node_count")},
        "final_comparison_is_validated": final_cmp.get("is_valid", False),
    }
    (out / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    try: shutil.copy2(file_path, out / ("econtract" + Path(file_path).suffix))
    except Exception: pass
    pct["sav"] = 100
    print_progress("Pipeline complete!", 100)

    # Summary
    acc, valid = final_cmp["accuracy"], final_cmp["is_valid"]
    tc = final_cmp.get("type_coverage", {}).get("type_coverage_pct", 0)
    print(f"\n\n{'─'*60}")
    print(f"\n  {bold('RESULTS')}\n")
    print(f"  {'Accuracy':<22} {(green if valid else yellow)(bold(f'{round(acc,1)}%'))}")
    print(f"  {'Type coverage':<22} {(green if tc>=100 else yellow)(f'{round(tc,1)}%')}")
    print(f"  {'Status':<22} {green('✓ VALIDATED') if valid else yellow('⚠ PARTIAL')}")
    print(f"  {'LLM iterations':<22} {cyan(str(iters))}")
    print(f"\n  {bold('OUTPUT FILES')}\n")
    print(f"  {green('→')}  Smart contract    {cyan(str(sol_path))}")
    print(f"  {green('→')}  Results JSON      {cyan(str(out/'results.json'))}")
    print(f"\n{'─'*60}\n")
    return str(sol_path)

def _print_cmp(cmp):
    acc, valid = cmp["accuracy"], cmp.get("is_valid", False)
    color = green if valid else yellow if acc >= 70 else red
    print("     " + bold("Accuracy") + "  " + color(f"{round(acc,1)}%") + ("  " + green("✓ VALIDATED") if valid else ""))
    tiers = cmp.get("node_tiers", {})
    if tiers:
        ns = round(cmp.get("node_similarity", 0), 1)
        es = round(cmp.get("edge_similarity", 0), 1)
        tc2 = round(cmp.get("type_coverage", {}).get("type_coverage_pct", 0), 1)
        vc = round(tiers.get("tier_c", 0), 1)
        print(f"     NodeSim:{cyan(f'{ns}%')}  EdgeSim:{cyan(f'{es}%')}  TypeCov:{cyan(f'{tc2}%')}  ValueCov:{cyan(f'{vc}%')}")
    missing = cmp.get("type_coverage", {}).get("missing_semantic", [])
    if missing: print("     " + yellow("Missing: ") + dim(", ".join(missing)))
    unmatched = [n for n in cmp.get("unmatched_nodes", []) if n and len(n) > 2]
    if unmatched: print("     " + yellow("Unmatched: ") + dim(", ".join(unmatched[:5])))

def _run_refinement(initial_sol, text, G_e, refinement_loop_fn, pct, overall_fn):
    result = [initial_sol, [], 0]; err = [None]
    def _go():
        try: result[0], result[1], result[2] = refinement_loop_fn(initial_sol, text, G_e)
        except Exception as e: err[0] = e
    t = threading.Thread(target=_go, daemon=False); t.start(); t.join(timeout=660)
    if t.is_alive():
        print(yellow("\n     ⚠  Refinement timed out — using initial contract.")); return initial_sol, [], 0
    if err[0]:
        print(yellow(f"\n     ⚠  Refinement error: {err[0]}")); return initial_sol, [], 0
    if result[0] is None: return initial_sol, [], 0
    for h in result[1]:
        i, acc, banked = h["iteration"], h["accuracy"], h.get("banked", h["accuracy"])
        col = green if acc >= 85 else yellow if acc >= 70 else red
        st  = green("✓ DONE") if h["is_valid"] else (green("↑ banked") if h.get("improved") else yellow("↺ rollback") if h.get("patch_applied") else dim("→ refining"))
        print(f"     Iter {i}  acc={col(f'{round(acc,1)}%')}  banked={dim(f'{round(banked,1)}%')}  nodes={cyan(str(h['sc_nodes']))}  {st}")
        if result[2] > 0:
            pct["ref"] = (i / result[2]) * 100
            print_progress(f"Refinement {i}/{result[2]}...", overall_fn())
    return result[0], result[1], result[2]



# ── Run single ─────────────────────────────────────────────────────────────────
def cmd_run(args):
    print(BANNER)
    path = Path(args.file)
    if not path.exists(): print(red(f"  ✗  File not found: {args.file}")); sys.exit(1)
    name = args.name or path.stem.replace(" ", "_") or "Contract"
    out  = args.output or f"./Results/{name}"
    print(f"  {bold('Input')}   {cyan(str(path.resolve()))}")
    print(f"  {bold('Name')}    {cyan(name)}")
    print(f"  {bold('Output')}  {cyan(str(Path(out).resolve()))}\n")
    run_pipeline(str(path), name, out)

# ── Run multi ──────────────────────────────────────────────────────────────────
def cmd_run_multi(args):
    print(BANNER)
    path = Path(args.file)
    if not path.exists(): print(red(f"  ✗  File not found: {args.file}")); sys.exit(1)
    if path.suffix.lower() not in (".docx", ".txt"):
        print(red(f"  ✗  run-multi supports .docx and .txt only")); sys.exit(1)

    _setup_path()
    from core.econtract_kg import extract_pages_from_file
    pages = extract_pages_from_file(str(path))
    if not pages:
        print(yellow("  ⚠  Could not detect multiple pages — use 'run' for single-page files.")); return

    base_name = args.name or path.stem.replace(" ", "_") or "Contract"
    base_out  = Path(args.output or f"./Results/{base_name}_multi")
    base_out.mkdir(parents=True, exist_ok=True)
    total = len(pages)

    print(f"  {bold('Input')}    {cyan(str(path.resolve()))}")
    print(f"  {bold('Pages')}    {cyan(str(total))}")
    print(f"  {bold('Output')}   {cyan(str(base_out.resolve()))}\n")

    page_results = []
    for page_num, content, title in pages:
        contract_name = f"{base_name}_page{page_num}"
        page_out_dir  = base_out / f"page{page_num}"
        page_out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{cyan('═'*62)}")
        print(f"  {bold(f'PAGE {page_num} / {total}')}  {dim(title[:50])}")
        print(f"{cyan('═'*62)}\n")

        temp_txt = page_out_dir / "_page_content.txt"
        temp_txt.write_text(content, encoding="utf-8")

        sol_path, accuracy, status = None, None, "ERROR"
        try:
            sol_path = run_pipeline(str(temp_txt), contract_name, str(page_out_dir), page_number=page_num, page_title=title)
            gen_sol   = page_out_dir / f"{contract_name}.sol"
            final_sol = base_out / f"{contract_name}.sol"
            if gen_sol.exists(): shutil.copy2(gen_sol, final_sol)
            rj = page_out_dir / "results.json"
            if rj.exists():
                rd = json.loads(rj.read_text())
                accuracy = rd.get("final_comparison", {}).get("accuracy")
                status   = "✓ VALIDATED" if rd.get("final_comparison_is_validated") else "⚠ PARTIAL"
            page_results.append({"page": page_num, "title": title[:60],
                "contract_name": contract_name,
                "sol_file": final_sol.name if final_sol.exists() else "—",
                "accuracy": accuracy, "status": status})
        except Exception as exc:
            print(red(f"\n  ✗  Page {page_num} error: {str(exc)[:100]}"))
            page_results.append({"page": page_num, "title": title[:60],
                "contract_name": contract_name, "sol_file": "—", "accuracy": None, "status": "ERROR"})
        finally:
            if temp_txt.exists(): temp_txt.unlink()

    # Summary
    summary = {"source_file": str(path.resolve()), "base_name": base_name,
               "total_pages": total, "pages": page_results,
               "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00","Z")}
    (base_out / "multi_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n\n{'═'*62}")
    print(f"  {bold('MULTI-PAGE SUMMARY')}  ({total} pages → {total} smart contracts)\n")
    print(f"  {'Page':<6}  {'Accuracy':<10}  {'Status':<18}  Output File")
    print(f"  {'─'*4}  {'─'*8}  {'─'*16}  {'─'*28}")
    for r in page_results:
        acc_str = f"{round(r['accuracy'],1)}%" if r['accuracy'] is not None else "—"
        sf = r["status"]
        cf = green if "VALIDATED" in sf else (yellow if "PARTIAL" in sf else red)
        print(f"  {str(r['page']):<6}  {acc_str:<10}  {cf(sf):<27}  {dim(r['sol_file'])}")
    print(f"\n  {bold('Output')}  {cyan(str(base_out.resolve()))}")
    print(f"{'═'*62}\n")

# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(prog="contractforge",
        description="E-Contract → Smart Contract (terminal CLI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
          Examples:
            python cli.py run       --file agreement.txt  --name ServiceAgreement
            python cli.py run       --file contract.docx  --name NDA --output ./out
            python cli.py run-multi --file multipage.docx --name Contracts
            python cli.py run-multi --file multipage.txt  --name Contracts
            python cli.py demo
            python cli.py check
        """))
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("run", help="Single-page contract")
    p.add_argument("--file", required=True); p.add_argument("--name", default="")
    p.add_argument("--output", default="")
    m = sub.add_parser("run-multi", help="Multi-page contract (one .sol per page)")
    m.add_argument("--file", required=True); m.add_argument("--name", default="")
    m.add_argument("--output", default="")
    d = sub.add_parser("demo"); d.add_argument("--output", default="./Results/demo")
    sub.add_parser("check")
    args = parser.parse_args()
    {"run": cmd_run, "run-multi": cmd_run_multi}.get(
        args.cmd, lambda _: parser.print_help())(args)

if __name__ == "__main__":
    main()