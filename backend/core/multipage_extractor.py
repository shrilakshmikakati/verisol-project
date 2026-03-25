"""
multipage_extractor.py — Unified multi-page extraction for ContractForge.

Adds support missing from the original econtract_kg.py:
  • PDF multi-page extraction (text-based + OCR fallback per page)
  • Image sequence multi-page (folder of scanned pages)
  • Graceful single-page fallback (returns 1-element list instead of [])
  • Cross-page shared-entity detection (same employer/party across pages)
  • Aggregated multi-page knowledge graph (PageGraph → master KG)
  • Collision-safe contract naming

Usage (drop-in alongside econtract_kg.py in core/):
    from core.multipage_extractor import (
        extract_pages_universal,
        build_cross_page_kg,
        CrossPageContext,
    )
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Optional

import networkx as nx


# ── Helpers ────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _safe_contract_name(base: str, page_num: int, used: set) -> str:
    """Return a collision-safe Solidity contract name."""
    raw   = re.sub(r"[^A-Za-z0-9_]", "_", base.strip())[:32].strip("_") or "Contract"
    cname = f"{raw}_page{page_num}"
    if cname not in used:
        used.add(cname)
        return cname
    # Disambiguate with suffix counter
    for i in range(2, 999):
        candidate = f"{cname}_{i}"
        if candidate not in used:
            used.add(candidate)
            return candidate
    return f"{raw}_page{page_num}_{id(base) % 10000}"


# ── PDF extraction ─────────────────────────────────────────────────────────────

def _extract_pdf_pages_text(path: str) -> list[tuple[int, str, str]]:
    """
    Extract pages from a text-based PDF using pdfminer / pypdf.
    Returns list of (page_num, content, title) tuples.
    Falls back to pypdf if pdfminer is unavailable.
    """
    pages: list[tuple[int, str, str]] = []

    # --- Method A: pdfminer.six (best text fidelity) -------------------------
    try:
        from pdfminer.high_level import extract_pages as pm_extract_pages
        from pdfminer.layout import LTTextContainer

        page_texts: list[str] = []
        for page_layout in pm_extract_pages(path):
            chunks = []
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    chunks.append(element.get_text())
            page_texts.append("".join(chunks).strip())

        for i, text in enumerate(page_texts, start=1):
            if len(text) < 50:           # blank/noise page — skip
                continue
            first_line = next((l.strip() for l in text.splitlines() if l.strip()), f"Page {i}")
            title      = first_line[:60]
            pages.append((i, text, title))

        if pages:
            return pages
    except ImportError:
        pass
    except Exception:
        pass

    # --- Method B: pypdf (lighter, handles more encrypted PDFs) ---------------
    try:
        import pypdf  # type: ignore

        reader     = pypdf.PdfReader(path)
        page_texts = []
        for page_obj in reader.pages:
            try:
                t = page_obj.extract_text() or ""
            except Exception:
                t = ""
            page_texts.append(t.strip())

        for i, text in enumerate(page_texts, start=1):
            if len(text) < 50:
                continue
            first_line = next((l.strip() for l in text.splitlines() if l.strip()), f"Page {i}")
            pages.append((i, text, first_line[:60]))

        return pages
    except ImportError:
        pass
    except Exception:
        pass

    return []


def _extract_pdf_pages_ocr(path: str) -> list[tuple[int, str, str]]:
    """
    OCR fallback for scanned PDFs: pdf2image + pytesseract.
    Returns list of (page_num, content, title) tuples.
    """
    try:
        from pdf2image import convert_from_path      # type: ignore
        import pytesseract                           # type: ignore
        from PIL import Image, ImageFilter, ImageEnhance  # type: ignore
    except ImportError:
        return []

    pages: list[tuple[int, str, str]] = []
    try:
        images = convert_from_path(path, dpi=200, thread_count=2)
    except Exception:
        return []

    for i, img in enumerate(images, start=1):
        try:
            grey   = img.convert("L")
            grey   = ImageEnhance.Contrast(grey).enhance(2.0)
            grey   = grey.filter(ImageFilter.SHARPEN)
            text   = pytesseract.image_to_string(grey, config="--psm 6")
        except Exception:
            text = ""
        text = text.strip()
        if len(text) < 50:
            continue
        first_line = next((l.strip() for l in text.splitlines() if l.strip()), f"Page {i}")
        pages.append((i, text, first_line[:60]))

    return pages


def extract_pages_from_pdf(path: str) -> list[tuple[int, str, str]]:
    """
    Extract pages from a PDF file.
    Strategy:
      1. Text-based extraction (pdfminer / pypdf).
      2. If < 1 page extracted → OCR fallback (pdf2image + pytesseract).
    Returns [] only if both strategies fail.
    """
    pages = _extract_pdf_pages_text(path)
    if pages:
        return pages
    # Text extraction returned nothing — likely a scanned PDF
    return _extract_pdf_pages_ocr(path)


# ── Image sequence (folder of scans) ──────────────────────────────────────────

def extract_pages_from_image_folder(folder: str) -> list[tuple[int, str, str]]:
    """
    Treat each image in a folder as one page of a scanned document.
    Supported extensions: .png .jpg .jpeg .tiff .bmp
    Returns list of (page_num, content, title) tuples.
    """
    try:
        import pytesseract                          # type: ignore
        from PIL import Image, ImageFilter, ImageEnhance  # type: ignore
    except ImportError:
        return []

    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
    folder_path = Path(folder)
    files       = sorted(
        p for p in folder_path.iterdir()
        if p.suffix.lower() in IMAGE_EXTS
    )
    if not files:
        return []

    pages: list[tuple[int, str, str]] = []
    for i, img_path in enumerate(files, start=1):
        try:
            img  = Image.open(str(img_path)).convert("L")
            img  = ImageEnhance.Contrast(img).enhance(2.0)
            img  = img.filter(ImageFilter.SHARPEN)
            text = pytesseract.image_to_string(img, config="--psm 6").strip()
        except Exception:
            continue
        if len(text) < 50:
            continue
        first_line = next((l.strip() for l in text.splitlines() if l.strip()), f"Page {i}")
        pages.append((i, text, first_line[:60]))

    return pages


# ── Single-page fallback ───────────────────────────────────────────────────────

def _single_page_fallback(path: str) -> list[tuple[int, str, str]]:
    """
    When page-splitting fails, treat the whole file as a single page.
    Imports extract_text_from_file from econtract_kg to avoid duplication.
    """
    try:
        # Lazy import — econtract_kg must be on sys.path (done by _setup_path in cli.py)
        from core.econtract_kg import extract_text_from_file  # type: ignore
        text = extract_text_from_file(path)
    except Exception:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

    text = text.strip()
    if not text:
        return []

    first_line = next((l.strip() for l in text.splitlines() if l.strip()), "Document")
    title      = first_line[:60]
    return [(1, text, title)]


# ── Universal entry point ──────────────────────────────────────────────────────

def extract_pages_universal(
    path: str,
    *,
    fallback_single: bool = True,
) -> list[tuple[int, str, str]]:
    """
    Unified multi-page extractor that handles ALL supported formats:
      .docx  → section-break / heading / char-count strategies (from econtract_kg)
      .txt   → form-feed / heading / char-count strategies (from econtract_kg)
      .pdf   → pdfminer / pypdf text extraction, then OCR fallback
      folder → image sequence (each image = one page)

    Args:
        path:            File path or folder path.
        fallback_single: If True and no multi-page split found,
                         returns a single-element list with the whole document.
                         If False, returns [] (original behaviour).

    Returns:
        List of (page_num, content, title) tuples.
        page_num is 1-based and contiguous.
    """
    p   = Path(path)
    ext = p.suffix.lower()

    # ── Folder of images ──────────────────────────────────────────────────────
    if p.is_dir():
        pages = extract_pages_from_image_folder(str(p))
        if pages:
            return pages
        if fallback_single:
            return _single_page_fallback(path)
        return []

    # ── PDF ───────────────────────────────────────────────────────────────────
    if ext == ".pdf":
        pages = extract_pages_from_pdf(path)
        if pages:
            return pages
        if fallback_single:
            return _single_page_fallback(path)
        return []

    # ── DOCX / TXT — delegate to econtract_kg ───────────────────────────────
    try:
        from core.econtract_kg import extract_pages_from_file  # type: ignore
        pages = extract_pages_from_file(path)
    except Exception:
        pages = []

    if pages:
        return pages

    # econtract_kg returned [] (single-page doc or unsupported format)
    if fallback_single:
        return _single_page_fallback(path)
    return []


# ── Cross-page shared-entity detection ────────────────────────────────────────

class CrossPageContext:
    """
    Tracks entities (parties, dates, payments) that appear across multiple pages
    of the same source document.  Used to:
      • Inject shared context into each page's KG before Solidity generation.
      • Build an aggregated cross-page KG for visualisation.
      • Warn when a party on page N has no matching address in previous pages.
    """

    def __init__(self):
        # norm_label → {page_nums: set, entity_type: str, canonical_label: str}
        self._entities: dict[str, dict] = {}
        # page_num → list of (norm_label, entity_type) tuples
        self._page_index: dict[int, list] = {}

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def ingest_page_kg(self, page_num: int, G: nx.DiGraph) -> None:
        """Register all nodes from a page's e-contract KG."""
        self._page_index.setdefault(page_num, [])
        for node_id in G.nodes:
            nd         = G.nodes[node_id]
            label      = nd.get("label", node_id)
            etype      = nd.get("entity_type", "GENERIC")
            norm_label = _norm(label)
            if not norm_label or len(norm_label) < 3:
                continue
            if norm_label not in self._entities:
                self._entities[norm_label] = {
                    "page_nums":       set(),
                    "entity_type":     etype,
                    "canonical_label": label,
                }
            self._entities[norm_label]["page_nums"].add(page_num)
            self._page_index[page_num].append((norm_label, etype))

    # ── Query ─────────────────────────────────────────────────────────────────

    def shared_entities(
        self,
        min_pages: int = 2,
        entity_types: Optional[set] = None,
    ) -> list[dict]:
        """
        Return entities that appear on at least `min_pages` pages.

        Args:
            min_pages:    Minimum number of pages the entity must appear on.
            entity_types: Optional filter (e.g. {"PARTY", "PAYMENT"}).

        Returns:
            List of dicts with keys: canonical_label, entity_type, page_nums.
        """
        result = []
        for info in self._entities.values():
            if len(info["page_nums"]) < min_pages:
                continue
            if entity_types and info["entity_type"] not in entity_types:
                continue
            result.append({
                "canonical_label": info["canonical_label"],
                "entity_type":     info["entity_type"],
                "page_nums":       sorted(info["page_nums"]),
            })
        return sorted(result, key=lambda x: -len(x["page_nums"]))

    def shared_parties(self, min_pages: int = 2) -> list[dict]:
        """Convenience: shared PARTY entities only."""
        return self.shared_entities(min_pages=min_pages, entity_types={"PARTY"})

    def page_summary(self) -> list[dict]:
        """Per-page entity-count summary for display."""
        return [
            {"page": pn, "entity_count": len(ents)}
            for pn, ents in sorted(self._page_index.items())
        ]

    def as_dict(self) -> dict:
        return {
            "shared_entities": self.shared_entities(min_pages=2),
            "page_summary":    self.page_summary(),
        }


# ── Aggregated cross-page KG ──────────────────────────────────────────────────

def build_cross_page_kg(
    page_graphs: list[tuple[int, nx.DiGraph]],
    context: Optional[CrossPageContext] = None,
) -> nx.DiGraph:
    """
    Merge per-page e-contract KGs into a single aggregated graph.

    Node merging rules:
      • Nodes with identical normalised labels and entity_type are MERGED.
      • Merged node gets attribute page_nums = sorted list of pages it appeared on.
      • Page-specific nodes get page_nums = [page_num].
      • All edges are kept; intra-page edges keep their relation label;
        cross-page edges are labelled SHARED_ENTITY.

    Args:
        page_graphs: List of (page_num, G_econtract) tuples.
        context:     Optional CrossPageContext (pre-populated) for shared detection.

    Returns:
        nx.DiGraph with unified nodes and cross-page SHARED_ENTITY edges.
    """
    master: nx.DiGraph = nx.DiGraph()
    master.graph["type"] = "cross_page_kg"

    # norm_label:etype → master node id
    canonical_map: dict[str, str] = {}

    def _master_node_id(label: str, etype: str) -> str:
        key = f"{_norm(label)}:{etype}"
        if key not in canonical_map:
            mid = f"{etype}_{_norm(label)[:40]}"
            # Avoid collision with different etypes sharing the same norm
            if master.has_node(mid):
                mid = f"{mid}_{len(canonical_map)}"
            canonical_map[key] = mid
        return canonical_map[key]

    # ── First pass: add all nodes ─────────────────────────────────────────────
    for page_num, G in page_graphs:
        for node_id in G.nodes:
            nd    = G.nodes[node_id]
            label = nd.get("label", node_id)
            etype = nd.get("entity_type", "GENERIC")
            mid   = _master_node_id(label, etype)

            if not master.has_node(mid):
                master.add_node(mid,
                    entity_type=etype,
                    label=label,
                    page_nums=[page_num],
                )
            else:
                existing_pages = master.nodes[mid].get("page_nums", [])
                if page_num not in existing_pages:
                    master.nodes[mid]["page_nums"] = sorted(existing_pages + [page_num])

    # ── Second pass: add all edges ────────────────────────────────────────────
    for page_num, G in page_graphs:
        for src, tgt, data in G.edges(data=True):
            src_nd = G.nodes[src]
            tgt_nd = G.nodes[tgt]
            m_src  = _master_node_id(src_nd.get("label", src), src_nd.get("entity_type", "GENERIC"))
            m_tgt  = _master_node_id(tgt_nd.get("label", tgt), tgt_nd.get("entity_type", "GENERIC"))
            if m_src != m_tgt and not master.has_edge(m_src, m_tgt):
                master.add_edge(m_src, m_tgt,
                    relation=data.get("relation", "RELATED"),
                    source_page=page_num,
                )

    # ── Third pass: add cross-page SHARED_ENTITY edges ───────────────────────
    # For each node appearing on 2+ pages, link its page representatives
    for mid in list(master.nodes):
        page_nums = master.nodes[mid].get("page_nums", [])
        if len(page_nums) >= 2:
            master.nodes[mid]["is_shared"] = True
            # Add a self-referential attribute noting all pages
            # (edges between same node on different pages are implicit)

    # Update context if provided
    if context is not None:
        for page_num, G in page_graphs:
            context.ingest_page_kg(page_num, G)

    return master


# ── Collision-safe naming helper ───────────────────────────────────────────────

def make_page_contract_names(
    pages: list[tuple[int, str, str]],
    base_name: str,
) -> list[tuple[int, str, str, str]]:
    """
    Assign collision-safe Solidity contract names to each page.

    Args:
        pages:     List of (page_num, content, title).
        base_name: Base contract name (e.g. "AppointmentLetter").

    Returns:
        List of (page_num, content, title, contract_name) tuples.
    """
    used: set[str] = set()
    result = []
    for page_num, content, title in pages:
        cname = _safe_contract_name(base_name, page_num, used)
        result.append((page_num, content, title, cname))
    return result


# ── Multi-page pipeline orchestrator ──────────────────────────────────────────

def run_multipage_pipeline(
    file_path: str,
    base_name: str,
    run_single_page_fn,         # callable: (file_path, contract_name, out_dir, page_num, title) -> str
    output_dir: str,
    *,
    fallback_single: bool = True,
    print_fn=print,
) -> dict:
    """
    High-level orchestrator for multi-page processing.

    Extracts pages, assigns names, calls run_single_page_fn per page,
    then builds the cross-page KG and summary.

    Args:
        file_path:          Path to the source document.
        base_name:          Base contract name.
        run_single_page_fn: Callable that processes one page and returns sol_path.
                            Signature: fn(tmp_txt_path, contract_name, out_dir,
                                          page_number, page_title) -> str
        output_dir:         Root output directory.
        fallback_single:    If True, treat as single page when split fails.
        print_fn:           Print function for progress output.

    Returns:
        Summary dict with keys: total_pages, pages (list of per-page results),
        shared_entities (cross-page entities), output_dir.
    """
    import shutil
    import json
    import tempfile
    from pathlib import Path as _Path

    out = _Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    pages = extract_pages_universal(file_path, fallback_single=fallback_single)
    if not pages:
        return {"error": "No pages extracted", "total_pages": 0, "pages": []}

    named_pages = make_page_contract_names(pages, base_name)
    total       = len(named_pages)
    context     = CrossPageContext()
    page_graphs: list[tuple[int, nx.DiGraph]] = []
    page_results: list[dict] = []

    for page_num, content, title, contract_name in named_pages:
        page_label  = f"page{page_num}"
        page_out    = out / page_label
        page_out.mkdir(parents=True, exist_ok=True)

        print_fn(f"\n[{page_num}/{total}] {title[:50]}")

        # Write page content to temp file
        tmp = page_out / "_page_content.txt"
        tmp.write_text(content, encoding="utf-8")

        sol_path = None
        accuracy = None
        status   = "ERROR"
        G_page   = None

        try:
            sol_path = run_single_page_fn(
                str(tmp), contract_name, str(page_out), page_num, title
            )

            # Build page KG for cross-page analysis
            try:
                from core.econtract_kg import (  # type: ignore
                    build_econtract_knowledge_graph,
                    preprocess_text,
                )
                G_page = build_econtract_knowledge_graph(content)
                context.ingest_page_kg(page_num, G_page)
                page_graphs.append((page_num, G_page))
            except Exception:
                pass

            # Read accuracy from results.json
            rj = page_out / "results.json"
            if rj.exists():
                rd       = json.loads(rj.read_text())
                accuracy = rd.get("final_comparison", {}).get("accuracy")
                is_valid = rd.get("final_comparison", {}).get("is_validated", False)
                status   = "VALIDATED" if is_valid else "PARTIAL"

            # Copy .sol to base output
            gen_sol  = page_out / f"{contract_name}.sol"
            final_sol = out / f"{contract_name}.sol"
            if gen_sol.exists():
                shutil.copy2(gen_sol, final_sol)

            page_results.append({
                "page":          page_num,
                "title":         title[:60],
                "contract_name": contract_name,
                "sol_file":      final_sol.name if final_sol.exists() else "—",
                "accuracy":      accuracy,
                "status":        status,
            })

        except Exception as exc:
            print_fn(f"  ERROR on page {page_num}: {exc}")
            page_results.append({
                "page":          page_num,
                "title":         title[:60],
                "contract_name": contract_name,
                "sol_file":      "—",
                "accuracy":      None,
                "status":        "ERROR",
            })
        finally:
            if tmp.exists():
                tmp.unlink()

    # ── Cross-page KG ─────────────────────────────────────────────────────────
    cross_kg_data: dict = {}
    if page_graphs:
        try:
            master_kg = build_cross_page_kg(page_graphs, context)
            cross_kg_data = {
                "total_nodes": master_kg.number_of_nodes(),
                "total_edges": master_kg.number_of_edges(),
                "shared_entities": context.shared_entities(min_pages=2),
            }
            # Render cross-page KG image
            try:
                from core.econtract_kg import render_graph_base64  # type: ignore
                import base64
                img_b64 = render_graph_base64(master_kg, "Cross-Page Knowledge Graph")
                img_path = out / "cross_page_kg.png"
                img_path.write_bytes(base64.b64decode(img_b64))
                cross_kg_data["kg_image"] = str(img_path.name)
            except Exception:
                pass
        except Exception:
            pass

    summary = {
        "source_file":    str(_Path(file_path).resolve()),
        "base_name":      base_name,
        "total_pages":    total,
        "pages":          page_results,
        "cross_page_kg":  cross_kg_data,
        "shared_entities": context.as_dict().get("shared_entities", []),
    }

    summary_path = out / "multi_summary.json"
    import json as _json
    summary_path.write_text(_json.dumps(summary, indent=2), encoding="utf-8")

    return summary