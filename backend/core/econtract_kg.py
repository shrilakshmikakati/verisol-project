"""
Algorithm 1: E-Contract Knowledge Graph
Improvements in this version:
 - ENTITY BLOCKLIST: filters out noise words (mobile, pi, dt, ref, etc.)
 - CARDINAL removed from spaCy PAYMENT map (grabbed phone/roll numbers)
 - Payment patterns tightened to require currency symbol or stipend keyword
 - Devanagari/non-ASCII stripped before matplotlib rendering (suppresses font warnings)
 - Semantic edge fuzzy lookup uses subtree phrase matching, not single token
 - _link_obligations_to_parties uses sentence-window proximity
 - Party pattern min-length enforced (>= 3 chars after blocklist)
"""
import re, io, base64, warnings, datetime
from datetime import datetime as dt, timedelta
import spacy
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

_nlp = None

def get_nlp():
    global _nlp
    if _nlp is not None:
        return _nlp
    for model in ("en_core_web_lg", "en_core_web_md", "en_core_web_sm"):
        try:
            _nlp = spacy.load(model)
            return _nlp
        except Exception:
            pass
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"], check=True)
    _nlp = spacy.load("en_core_web_sm")
    return _nlp

# ── Text Extraction ────────────────────────────────────────────────────────────

def extract_text_from_docx(path: str) -> str:
    """
    Comprehensive docx text extractor.
    Reads in this order (preserving document flow):
      1. Header of each section
      2. Body paragraphs and tables (XML walk, no deduplication)
      3. Footer of each section
      4. Text boxes / drawing frames
      5. Footnotes / endnotes
      6. Core properties (title, author, subject)
    NO deduplication — every paragraph kept in order.
    Falls back to raw XML scrape if result is under 300 chars.
    """
    from docx import Document
    from docx.oxml.ns import qn
    import lxml.etree as etree

    doc   = Document(path)
    parts = []

    def _para_text(elem) -> str:
        return "".join(n.text or "" for n in elem.iter(qn("w:t")))

    def _walk_body(elem):
        """Walk XML element, yielding text from paragraphs and table cells."""
        for child in elem:
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == "p":
                t = _para_text(child).strip()
                if t:
                    parts.append(t)
            elif local == "tbl":
                _walk_table(child)
            elif local in ("sdt",):
                # Content controls — recurse into sdtContent
                for content in child:
                    cl = content.tag.split("}")[-1] if "}" in content.tag else content.tag
                    if cl in ("sdtContent", "sdtBody"):
                        _walk_body(content)
            elif local in ("drawing", "pict", "object", "txbxContent"):
                # Text boxes and drawings
                for t_node in child.iter(qn("w:t")):
                    if t_node.text and t_node.text.strip():
                        parts.append(t_node.text.strip())
            else:
                # Recurse for any other container elements
                _walk_body(child)

    def _walk_table(tbl_elem):
        for tr in tbl_elem.findall(".//" + qn("w:tr")):
            row_parts = []
            for tc in tr.findall(".//" + qn("w:tc")):
                cell_text_parts = []
                for p in tc.findall(".//" + qn("w:p")):
                    t = _para_text(p).strip()
                    if t:
                        cell_text_parts.append(t)
                if cell_text_parts:
                    row_parts.append(" ".join(cell_text_parts))
            if row_parts:
                parts.append(" | ".join(row_parts))

    def _extract_from_part(part_element):
        """Extract text from a document part element (header/footer/body)."""
        if part_element is not None:
            _walk_body(part_element)

    # 1. Section headers
    for section in doc.sections:
        try:
            hdr = section.header
            if hdr and not hdr.is_linked_to_previous:
                _extract_from_part(hdr._element.body if hasattr(hdr._element, 'body') else hdr._element)
        except Exception:
            pass

    # 2. Main body (primary extraction)
    _walk_body(doc.element.body)

    # 3. Section footers
    for section in doc.sections:
        try:
            ftr = section.footer
            if ftr and not ftr.is_linked_to_previous:
                _extract_from_part(ftr._element.body if hasattr(ftr._element, 'body') else ftr._element)
        except Exception:
            pass

    # 4. Footnotes and endnotes (if present)
    for part_name in ("/word/footnotes.xml", "/word/endnotes.xml"):
        try:
            part = doc.part.package.part_related_by("http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes")
            if part:
                _walk_body(etree.fromstring(part.blob))
        except Exception:
            pass

    # 5. Core properties
    try:
        cp = doc.core_properties
        for attr in ("title", "subject", "description", "author", "keywords"):
            val = getattr(cp, attr, None)
            if val and str(val).strip():
                parts.append("[META] " + str(val).strip())
    except Exception:
        pass

    full_text = "\n".join(p for p in parts if p.strip())

    # Fallback: raw XML scrape if structured walk gave very little
    if len(full_text.replace("\n", "").strip()) < 300:
        try:
            raw_xml  = etree.tostring(doc.element, encoding="unicode")
            raw_text = re.sub(r"<[^>]+>", " ", raw_xml)
            raw_text = re.sub(r"\s+", " ", raw_text).strip()
            if len(raw_text) > len(full_text):
                return raw_text
        except Exception:
            pass

    return full_text

def extract_text_from_image(path: str) -> str:
    import pytesseract
    from PIL import Image, ImageFilter, ImageEnhance
    img = Image.open(path).convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    best = ""
    for cfg in ["--psm 6", "--psm 4", "--psm 3"]:
        try:
            t = pytesseract.image_to_string(img, config=cfg)
            if len(t) > len(best):
                best = t
        except Exception:
            pass
    return best

def extract_text_from_file(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".docx":
        # Try multiple extraction methods and use the longest result
        methods = [extract_text_from_docx]
        try:
            import zipfile
            # Alternative method 1: direct zipfile extraction
            def alt1(p):
                with zipfile.ZipFile(p) as z:
                    xml = z.read('word/document.xml').decode('utf-8', errors='ignore')
                    return re.sub(r'<[^>]+>', ' ', xml)
            methods.append(alt1)
        except:
            pass
        
        results = []
        for method in methods:
            try:
                text = method(path)
                if text and len(text.strip()) > 100:
                    results.append(text)
            except:
                pass
        
        if results:
            # Return longest extraction
            return max(results, key=lambda x: len(x.replace('\n', '').replace(' ', '')))
        return ""
    
    if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        return extract_text_from_image(path)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def extract_pages_from_docx(path: str) -> list:
    """
    Extract pages/sections from multi-page DOCX.
    Returns list of (page_num, content, title) tuples
    
    Detection strategy (in order of preference):
    1. Heading styles (Heading 1, 2, 3, etc.) - must have 2+
    2. Title-style paragraphs - must have 2+
    3. Physical page estimation (adaptively: document_chars / 7 sections as default)
    """
    try:
        from docx import Document
    except:
        return []
    
    doc = Document(path)
    if not doc.paragraphs:
        return []
    
    # Strategy 1: Detect explicit heading styles
    heading_markers = []
    for i, para in enumerate(doc.paragraphs):
        style = para.style.name if para.style else ""
        text = para.text.strip()
        
        # Only Heading 1, 2, 3 - stricter filtering
        if any(h in style for h in ["Heading 1", "Heading 2", "Heading 3"]) and text:
            heading_markers.append((i, text))
    
    # Use headings ONLY if:
    # 1. We have 3+ distinct heading markers, OR
    # 2. We have 2+ headings with significantly different text (not duplicates)
    use_headings = False
    if len(heading_markers) >= 3:
        use_headings = True
    elif len(heading_markers) == 2:
        # Check if headers are meaningfully different
        h1_text = heading_markers[0][1]
        h2_text = heading_markers[1][1]
        if h1_text != h2_text:  # Only use if headers are different
            use_headings = True
    
    if use_headings:
        pages = []
        for section_idx, (start_idx, title_text) in enumerate(heading_markers):
            next_idx = heading_markers[section_idx + 1][0] if section_idx + 1 < len(heading_markers) else len(doc.paragraphs)
            
            section_text = []
            for para_idx in range(start_idx, next_idx):
                para = doc.paragraphs[para_idx]
                if para.text.strip():
                    section_text.append(para.text)
            
            if section_text:
                content = "\n".join(section_text)
                pages.append((section_idx + 1, content, title_text[:50]))
        
        return pages
    
    # Strategy 2: Physical page estimation with adaptive chunking
    # Calculate total chars and estimate pages based on document structure
    total_chars = sum(len(p.text) for p in doc.paragraphs)
    num_word_sections = len(doc.sections) if hasattr(doc, 'sections') else 1
    
    # Estimate: if doc has multiple Word sections, aim to create one contract per section
    # Word sections often correspond to page breaks or logical document divisions
    if num_word_sections >= 3:
        # For documents with 3+ sections, split to roughly match section count
        # chars_per_page = total_chars / num_sections (rounded up to minimum 300)
        chars_per_page = max(300, total_chars // num_word_sections)
    elif num_word_sections == 2:
        # For documents with 2 sections, create 2 pages
        chars_per_page = max(400, total_chars // 2)
    elif total_chars > 5000:
        # Large docs without sections: use 2000 chars per page
        chars_per_page = 2000
    else:
        # Small docs: more granular splitting (1000 chars per page)
        chars_per_page = 1000
    
    pages = []
    current_page = []
    page_num = 1
    page_char_count = 0
    
    for para in doc.paragraphs:
        if para.text.strip():
            current_page.append(para.text)
            page_char_count += len(para.text)
            
            if page_char_count >= chars_per_page:
                content = "\n".join(current_page)
                title = current_page[0][:50] if current_page else f"Page {page_num}"
                pages.append((page_num, content, title))
                current_page = []
                page_char_count = 0
                page_num += 1
    
    # Don't lose the last page
    if current_page:
        content = "\n".join(current_page)
        title = current_page[0][:50] if current_page else f"Page {page_num}"
        pages.append((page_num, content, title))
    
    return pages if len(pages) > 1 else []

def extract_text_from_folder(folder: str) -> str:
    texts = []
    for p in sorted(Path(folder).iterdir()):
        if p.suffix.lower() in (".txt", ".docx", ".png", ".jpg", ".jpeg"):
            texts.append(extract_text_from_file(str(p)))
    return "\n\n".join(texts)

# ── Preprocessing ──────────────────────────────────────────────────────────────

def preprocess_text(text: str) -> str:
    """Clean text: remove XML garbage but KEEP dates with 8 digits, fix quotes."""
    # Remove MULTIPLE 6+ digit sequences (XML artifacts: "640490    193675", etc.)
    # This handles: 640490    193675 (paired) or 640490    193675    ... (multiple)
    text = re.sub(r'(?:\d{6,}\s+)+\d{6,}', '', text)
    # Remove any remaining isolated 6-digit sequences that aren't part of dates
    # Negative lookbehind/lookahead to avoid breaking DDMMYYYY dates
    text = re.sub(r'(?<!\d)\d{6}(?![\d/\-])', '', text)
    # Fix smart quotes
    text = text.replace("\u2019","'").replace("\u2018","'")
    text = text.replace("\u201c",'"').replace("\u201d",'"')
    text = text.replace("\u2013","-").replace("\u2014"," - ")
    # Remove XML entity codes
    text = re.sub(r'&#?\w+;', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def _ascii_label(s: str) -> str:
    """Strip non-ASCII (Devanagari, CJK, etc.) for matplotlib rendering."""
    clean = re.sub(r"[^\x00-\x7F]+", "?", s)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:30] if clean.replace("?","").strip() else s[:20]

def detect_language(text: str) -> str:
    sample = text[:500].lower()
    scores = {
        "en": len(re.findall(r"\b(?:the|shall|will|party|agreement|contract)\b", sample)),
        "de": len(re.findall(r"\b(?:der|die|das|vertrag|partei|soll|muss)\b", sample)),
        "fr": len(re.findall(r"\b(?:le|la|les|contrat|partie|doit|accord)\b", sample)),
        "es": len(re.findall(r"\b(?:el|la|los|contrato|parte|debe|acuerdo)\b", sample)),
        "hi": len(re.findall(r"[\u0900-\u097F]", sample)),
        "zh": len(re.findall(r"[\u4e00-\u9fff]", sample)),
    }
    return max(scores, key=scores.get)

# ── Entity Blocklist ───────────────────────────────────────────────────────────
# Words that pattern-match as entities but are just noise/formatting artefacts

ENTITY_BLOCKLIST = {
    # Document formatting
    "mobile","phone","email","fax","tel","no","ref","date","sir","dear",
    "sub","madam","regards","yours","sincerely","faithfully","truly",
    # Prepositions / conjunctions
    "the","and","for","from","to","in","of","on","at","by","is","be",
    "as","an","or","if","re","a","an","it","its","this","that","these",
    # Common abbreviations that slip through
    "pi","pg","ug","dt","mr","ms","dr","st","nd","rd","th",
    "etc","viz","ie","eg","nb","pp","cf","vs","op","id",
    # Indian official document noise
    "govt","estt","sno","sl","sr","no","ref","reg","sub","advt",
    "circular","office","order","letter","memo","minutes",
}

def _is_valid_entity(val: str, etype: str) -> bool:
    """Return True if this value should be kept as a node."""
    val_stripped = val.strip()
    val_lower    = val_stripped.lower()

    # Minimum length: 3 chars for all, 4 for PARTY
    min_len = 4 if etype == "PARTY" else 3
    if len(val_stripped) < min_len:
        return False

    # Blocklist check (exact lowercase match)
    if val_lower in ENTITY_BLOCKLIST:
        return False

    # For PARTY: reject pure numbers, phone-number patterns
    if etype == "PARTY":
        if re.fullmatch(r"[\d\s\+\-\(\)\.]+", val_stripped):
            return False
        if re.fullmatch(r"\d{5,}", val_stripped.replace(" ","")):
            return False
        # Reject single-word all-lowercase common words
        if re.fullmatch(r"[a-z]+", val_stripped) and len(val_stripped) < 6:
            return False

    # For PAYMENT: must contain digit
    if etype == "PAYMENT" and not re.search(r"\d", val_stripped):
        return False

    # For DATE_DEADLINE: must contain digit or date keyword
    if etype == "DATE_DEADLINE":
        if not re.search(r"\d", val_stripped):
            if not re.search(r"\b(?:effective|commencement|expiry|joining|reporting|start|end)\s+date\b",
                             val_stripped, re.I):
                return False

    return True

# ── Pattern Library ────────────────────────────────────────────────────────────

PARTY_PATTERNS = [
    # Explicit role keywords (titlecase or uppercase)
    r"\b(Buyer|Seller|Vendor|Client|Customer|Contractor|Subcontractor|"
    r"Licensor|Licensee|Franchisor|Franchisee|Lessor|Lessee|Landlord|Tenant|"
    r"Employer|Employee|Principal|Agent|Borrower|Lender|Creditor|Debtor|"
    r"Guarantor|Surety|Service\s+Provider|Service\s+Recipient|"
    r"Intern|Candidate|Supervisor|Director|Professor|Faculty|"
    r"Researcher|Scientist|Fellow|Scholar|Trainee|Apprentice)\b",
    # Indian institutes: NIT/IIT/IIM etc. + location
    r"\b((?:NIT|IIT|IIM|AIIMS|BITS|TIFR|ISRO|DRDO|CSIR|BARC)\s+"
    r"[A-Za-z]+(?:\s+[A-Za-z]+)?)\b",
    # Named orgs with legal suffix
    r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,4})\s+"
    r"(?:Inc\.|LLC|Ltd\.|Corp\.|GmbH|S\.A\.|B\.V\.|PLC|LLP|LP|AG|SA)\b",
    # Dr./Mr./Ms./Prof. Name  — captures the name part
    r"\b(?:Dr\.|Mr\.|Ms\.|Mrs\.|Prof\.)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\b",
    # Parenthetical label ("the Vendor")
    r'[("\']((?:the\s+)?[A-Z][a-zA-Z\s]{3,30})[)"\']',
]

# PAYMENT: explicit currency or stipend/salary keyword — NO bare numbers
PAYMENT_PATTERNS = [
    # Currency symbol + number (with optional per-period)
    r"(?:Rs\.?\s*|INR\s*|USD\s*|\$|€|£)[\d,]+(?:\.\d{1,2})?"
    r"(?:\s*(?:/-\s*)?(?:per\s+month|p\.m\.|pm|/month|/annum|lakhs?|crores?|thousands?))?\b",
    # "10000 per month" — explicit period
    r"\b[\d,]+(?:\.\d{1,2})?\s*(?:per\s+month|p\.m\.|/month|per\s+annum)\b",
    # "stipend/salary of [Rs.] NNNN"
    r"\b(?:stipend|salary|remuneration|honorarium|allowance|fellowship|"
    r"emolument|wages?|pay)\s+of\s+(?:Rs\.?\s*|INR\s*)?[\d,]+\b",
    # "consolidated stipend of Rs NNNN [per month]"
    r"\bconsolidated\s+(?:stipend|salary)\s+of\s+(?:Rs\.?\s*|INR\s*)?[\d,]+\b",
    # "Rs. 10,000/- per month"
    r"Rs\.?\s*[\d,]+\s*(?:/-\s*)?(?:per\s+month|p\.m\.|/month)",
]

def normalize_date(date_str: str) -> str:
    """Normalize various date formats to YYYY-MM-DD for comparison."""
    date_str = date_str.strip()
    
    # Try DDMMYYYY format (8 consecutive digits)
    if re.match(r"^\d{8}$", date_str):
        try:
            d = dt.strptime(date_str, "%d%m%Y")
            return d.strftime("%Y-%m-%d")
        except:
            pass
    
    # Try DD/MM/YYYY or DD-MM-YYYY
    if re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{4}$", date_str):
        try:
            d = dt.strptime(date_str.replace("-", "/"), "%d/%m/%Y")
            return d.strftime("%Y-%m-%d")
        except:
            pass
    
    # Try YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
    
    # Return as-is if no pattern matched
    return date_str

DATE_PATTERNS = [
    # Standard formats
    r"\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b",  # DD/MM/YYYY or DD-MM-YY
    r"\b\d{4}-\d{2}-\d{2}\b",  # YYYY-MM-DD
    # DDMMYYYY format - match even when concatenated to text
    r"(?:0[1-9]|[12]\d|3[01])(?:0[1-9]|1[0-2])(?:19|20)\d{2}",
    # Named dates
    r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b",
    r"\b(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
    # Relative dates (days, weeks, months)
    r"\b\d+\s+(?:calendar\s+)?(?:days?|business\s+days?|weeks?|months?|years?)\b",
    # Date keywords alone
    r"\b(?:effective|commencement|expiry|joining|reporting|start|end|before|after|during)\s+date\b",
]

DISPUTE_PATTERNS   = [
    r"\b(?:arbitration|mediation|dispute\s+resolution|governing\s+law|"
    r"jurisdiction|competent\s+court|ICC|AAA|UNCITRAL|LCIA|SIAC)\b",
]
CONFIDENTIAL_PATTERNS = [
    r"\b(?:confidential(?:ity)?|non[\s\-]?disclosure|proprietary\s+information|"
    r"trade\s+secret|intellectual\s+property|IP\s+rights?|copyright|patent|trademark)\b",
]
FORCE_MAJEURE_PATTERNS = [
    r"\b(?:force\s+majeure|act\s+of\s+God|beyond\s+(?:the\s+)?(?:reasonable\s+)?control|"
    r"pandemic|natural\s+disaster|government\s+(?:action|order))\b",
]
MILESTONE_PATTERNS = [
    r"\b(?:milestone|deliverable|phase\s+[1-9]|stage\s+[1-9]|"
    r"checkpoint|acceptance\s+criteria|sign[\s\-]?off|handover)\b",
]

OBLIGATION_KEYWORDS  = [
    "shall","must","is required to","agrees to","undertakes to","covenants to",
    "is obligated to","is bound to","will provide","shall deliver","shall supply",
    "shall report","shall complete","shall maintain","shall submit","shall perform",
    "shall pay","shall receive","will receive","shall be paid","must report",
    "reasonable efforts","best efforts",
]
CONDITION_KEYWORDS   = [
    "if and only if","provided that","subject to","on condition that",
    "contingent upon","in the event that","unless","notwithstanding",
    "except where","save as otherwise","to the extent that",
    "condition precedent","failing which","in case of",
]
TERMINATION_KEYWORDS = [
    "terminate","termination","cancellation","rescind","void",
    "expire","expiry","cancelled","treat as cancelled",
    "terminable","terminated at any time","appointment is cancelled",
    "appointment is purely temporary",
]
PENALTY_KEYWORDS = [
    "penalty","liquidated damages","late fee","interest per",
    "default interest","indemnify","indemnification","hold harmless",
]

# ── spaCy NER ─────────────────────────────────────────────────────────────────

def extract_entities_spacy(text: str) -> list:
    nlp = get_nlp()
    doc = nlp(text[:80000])
    # CARDINAL intentionally removed — grabs phone/roll/CGPA numbers
    LABEL_MAP = {
        "PERSON": "PARTY",
        "ORG":    "PARTY",
        "GPE":    "PARTY",
        "DATE":   "DATE_DEADLINE",
        "TIME":   "DATE_DEADLINE",
        "MONEY":  "PAYMENT",
        "LAW":    "CONFIDENTIALITY_IP",
    }
    entities, seen = [], set()
    for ent in doc.ents:
        mapped = LABEL_MAP.get(ent.label_)
        if not mapped:
            continue
        val = ent.text.strip()
        if not _is_valid_entity(val, mapped):
            continue
        if len(val) > 60:
            continue
        # Skip sentence-fragment entities
        if re.search(r"\b(?:shall|must|will|if|unless|because|therefore)\b", val, re.I):
            continue
        key = (mapped, val.lower()[:50])
        if key not in seen:
            seen.add(key)
            entities.append({"type": mapped, "value": val})
    return entities

# ── Atomic pattern extraction ──────────────────────────────────────────────────

def extract_entities_atomic(text: str) -> list:
    entities, seen = [], set()

    def add(etype, raw):
        val = re.sub(r"\s+", " ", raw).strip()[:50]
        if not _is_valid_entity(val, etype):
            return
        key = (etype, val.lower()[:40])
        if key not in seen:
            seen.add(key)
            entities.append({"type": etype, "value": val})

    for pat in PARTY_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            add("PARTY", m.group(1) if m.lastindex else m.group())

    for pat in PAYMENT_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            add("PAYMENT", m.group())

    for pat in DATE_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            add("DATE_DEADLINE", m.group())

    for etype, patterns in [
        ("DISPUTE_ARBITRATION",  DISPUTE_PATTERNS),
        ("CONFIDENTIALITY_IP",   CONFIDENTIAL_PATTERNS),
        ("FORCE_MAJEURE",        FORCE_MAJEURE_PATTERNS),
        ("MILESTONE",            MILESTONE_PATTERNS),
    ]:
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                add(etype, m.group())

    return entities

# ── Keyword clause entities ────────────────────────────────────────────────────

def extract_clause_entities(text: str) -> list:
    """One canonical keyword node per matched legal keyword in a sentence."""
    nlp    = get_nlp()
    doc    = nlp(text[:60000])
    kw_map = [
        ("OBLIGATION",     OBLIGATION_KEYWORDS),
        ("CONDITION",      CONDITION_KEYWORDS),
        ("TERMINATION",    TERMINATION_KEYWORDS),
        ("PENALTY_REMEDY", PENALTY_KEYWORDS),
    ]
    entities, seen = [], set()
    for sent in doc.sents:
        s = sent.text.lower()
        for etype, keywords in kw_map:
            for kw in keywords:
                if kw in s:
                    key = (etype, kw)
                    if key not in seen:
                        seen.add(key)
                        entities.append({"type": etype, "value": kw})
    return entities

# ── Semantic edge extraction ───────────────────────────────────────────────────

SEMANTIC_VERB_MAP = {
    "pay":       "PAYS",         "receive":   "RECEIVES",
    "report":    "REPORTS_TO",   "provide":   "PROVIDES",
    "deliver":   "DELIVERS",     "terminate": "TERMINATES",
    "assign":    "ASSIGNS",      "complete":  "COMPLETES",
    "fulfill":   "FULFILLS",     "submit":    "SUBMITS",
    "notify":    "NOTIFIES",     "appoint":   "APPOINTS",
    "engage":    "ENGAGES",      "employ":    "EMPLOYS",
    "sign":      "SIGNS",        "cancel":    "CANCELS",
    "breach":    "BREACHES",     "penalize":  "PENALIZES",
    "join":      "JOINS",        "work":      "WORKS_FOR",
    "conduct":   "CONDUCTS",     "carry":     "CARRIES_OUT",
    "supervise": "SUPERVISES",   "guide":     "GUIDES",
    "apply":     "APPLIES",      "allow":     "ALLOWS",
    "require":   "REQUIRES",     "enter":     "ENTERS",
}

def _build_node_index(G: nx.DiGraph) -> dict:
    """
    Build lookup: norm(label) -> node_id.
    Also adds partial-word entries for fuzzy lookup.
    """
    idx = {}
    for n in G.nodes:
        label  = G.nodes[n].get("label", n)
        normed = re.sub(r"[^a-z0-9]", "", label.lower())
        idx[normed] = n
        # Also index individual words (len >= 4) from multi-word labels
        for word in re.findall(r"[a-z]{4,}", label.lower()):
            if word not in idx:
                idx[word] = n
    return idx

def _fuzzy_node_lookup(phrase: str, node_idx: dict) -> str | None:
    """
    Multi-tier fuzzy lookup:
      1. Exact normalised match
      2. Any significant word (len>=4) from phrase is in index
      3. Phrase is prefix of an index key or vice-versa
    """
    if not phrase or len(phrase) < 2:
        return None
    normed = re.sub(r"[^a-z0-9]", "", phrase.lower())

    # Tier 1: exact
    if normed in node_idx:
        return node_idx[normed]

    # Tier 2: word-level match
    words = re.findall(r"[a-z]{4,}", phrase.lower())
    for w in words:
        if w in node_idx:
            return node_idx[w]

    # Tier 3: prefix
    for key in node_idx:
        if len(normed) >= 4 and (normed.startswith(key) or key.startswith(normed)):
            return node_idx[key]

    return None

def extract_semantic_edges(text: str, G: nx.DiGraph):
    """Extract semantic edges via verb-based dependency parsing only."""
    nlp      = get_nlp()
    node_idx = _build_node_index(G)

    for sent in nlp(text[:40000]).sents:
        tokens = list(sent)
        subjs  = [t for t in tokens if t.dep_ in ("nsubj", "nsubjpass")]
        objs   = [t for t in tokens if t.dep_ in ("dobj", "pobj", "attr")]
        verbs  = [t for t in tokens if t.pos_ == "VERB"]

        for subj in subjs:
            subj_phrase = " ".join(t.text for t in subj.subtree
                                   if t.pos_ in ("NOUN", "PROPN", "ADJ") or t == subj)
            src = _fuzzy_node_lookup(subj_phrase, node_idx) or _fuzzy_node_lookup(subj.text, node_idx)
            if not src:
                continue

            verb = min(verbs, key=lambda v: abs(v.i - subj.i), default=None)
            if not verb:
                continue
            
            lemma = verb.lemma_.lower()
            neg = any(c.dep_ == "neg" for c in verb.children)
            sem_label = SEMANTIC_VERB_MAP.get(lemma)
            if not sem_label:
                continue
            if neg:
                sem_label = "NOT_" + sem_label

            for obj in objs:
                obj_phrase = " ".join(t.text for t in obj.subtree
                                     if t.pos_ in ("NOUN", "PROPN", "ADJ") or t == obj)
                tgt = _fuzzy_node_lookup(obj_phrase, node_idx) or _fuzzy_node_lookup(obj.text, node_idx)
                if tgt and src != tgt and not G.has_edge(src, tgt):
                    G.add_edge(src, tgt, relation=sem_label)

# ── Obligation → Party linking ─────────────────────────────────────────────────

def _link_obligations_to_parties(text: str, G: nx.DiGraph):
    """Link obligations/conditions to parties and payments to parties."""
    party_nodes  = [n for n in G.nodes if G.nodes[n].get("entity_type") == "PARTY"]
    payment_nodes = [n for n in G.nodes if G.nodes[n].get("entity_type") == "PAYMENT"]
    target_types = {"OBLIGATION", "CONDITION", "TERMINATION"}
    target_nodes = [n for n in G.nodes if G.nodes[n].get("entity_type") in target_types]

    sentences = re.split(r"[.;\n]", text)
    
    # OBLIGATION/CONDITION/TERMINATION → PARTY edges
    for kw_node in target_nodes:
        kw = kw_node.lower()
        counts: dict = {}
        for sent in sentences:
            sent_lower = sent.lower()
            if kw not in sent_lower:
                continue
            for p in party_nodes:
                plabel = G.nodes[p].get("label", p).lower()
                words = re.findall(r"[a-z]{4,}", plabel)
                hit = plabel in sent_lower or plabel[:5] in sent_lower or any(w in sent_lower for w in words)
                if hit:
                    counts[p] = counts.get(p, 0) + 1
        if counts:
            best = max(counts, key=counts.get)
            if not G.has_edge(best, kw_node):
                G.add_edge(best, kw_node, relation="HAS_OBLIGATION")

    # PAYMENT → PARTY edges
    for pay_node in payment_nodes:
        for sent in sentences:
            if not re.search(r"(?:stipend|salary|pay|receive|payment|rs\.|inr)", sent.lower()):
                continue
            for p in party_nodes:
                plabel = G.nodes[p].get("label", p).lower()
                words = re.findall(r"[a-z]{4,}", plabel)
                hit = plabel in sent.lower() or any(w in sent.lower() for w in words)
                if hit and not G.has_edge(p, pay_node):
                    G.add_edge(p, pay_node, relation="RECEIVES")

# ── Build KG ───────────────────────────────────────────────────────────────────

def build_econtract_knowledge_graph(raw_text: str) -> nx.DiGraph:
    text = preprocess_text(raw_text)
    lang = detect_language(text)
    G    = nx.DiGraph()
    G.graph["language"] = lang

    all_ents = (
        extract_entities_atomic(text) +
        extract_entities_spacy(text)  +
        extract_clause_entities(text)
    )

    for e in all_ents:
        val = e["value"].strip()
        if not val:
            continue
        
        # Normalize date values for better matching
        if e["type"] == "DATE_DEADLINE":
            normalized = normalize_date(val)
            nid = normalized[:60]
            # Create better labels for dates
            if re.search(r"\d{8}", val):
                label = f"date_{normalized}"
            elif re.search(r"\d+\s+(?:days?|months?|years?|weeks?)", val, re.I):
                label = f"duration_{nid}"
            else:
                label = f"date_{normalized}"
        else:
            nid = val[:60]
            label = nid
        
        if not G.has_node(nid):
            G.add_node(nid, entity_type=e["type"], label=label, lang=lang)

    extract_semantic_edges(text, G)
    _link_obligations_to_parties(text, G)
    return G

def graph_to_dict(G: nx.DiGraph) -> dict:
    return {
        "nodes": [{"id": n, **G.nodes[n]} for n in G.nodes],
        "edges": [{"source": u, "target": v, **G.edges[u, v]} for u, v in G.edges],
        "meta":  {"language": G.graph.get("language", "en")},
    }

# ── Visualisation ──────────────────────────────────────────────────────────────

TYPE_COLORS = {
    "PARTY":"#38bdf8","OBLIGATION":"#fb923c","DATE_DEADLINE":"#4ade80",
    "PAYMENT":"#facc15","CONDITION":"#c084fc","TERMINATION":"#f87171",
    "PENALTY_REMEDY":"#ff6b6b","DISPUTE_ARBITRATION":"#e879f9",
    "CONFIDENTIALITY_IP":"#a3e635","FORCE_MAJEURE":"#67e8f9",
    "MILESTONE":"#fbbf24","GENERIC":"#64748b",
}

def render_graph_base64(G: nx.DiGraph, title: str = "Knowledge Graph") -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fig, ax = plt.subplots(figsize=(16, 10))
        ax.set_facecolor("#0f172a"); fig.patch.set_facecolor("#0f172a")

        if G.number_of_nodes() == 0:
            ax.text(0.5, 0.5, "No entities extracted", ha="center", color="white",
                    transform=ax.transAxes)
            ax.axis("off")
        else:
            color_map  = [TYPE_COLORS.get(G.nodes[n].get("entity_type","GENERIC"),"#64748b")
                          for n in G.nodes]
            k_val      = max(1.5, 5.0 / max(1, G.number_of_nodes() ** 0.4))
            pos        = nx.spring_layout(G, k=k_val, seed=42)
            node_sizes = [800 if G.nodes[n].get("entity_type") != "GENERIC" else 350
                          for n in G.nodes]
            nx.draw_networkx_nodes(G, pos, node_color=color_map,
                                   node_size=node_sizes, alpha=0.92, ax=ax)
            # ASCII-safe labels to suppress font warnings
            labels = {n: _ascii_label(G.nodes[n].get("label", n)) for n in G.nodes}
            nx.draw_networkx_labels(G, pos, labels, font_size=6.5,
                                    font_color="white", ax=ax)
            nx.draw_networkx_edges(G, pos, edge_color="#334155", arrows=True,
                                   arrowsize=12, connectionstyle="arc3,rad=0.08", ax=ax)
            el = {e: G.edges[e].get("relation","")[:16] for e in G.edges}
            nx.draw_networkx_edge_labels(G, pos, el, font_size=5.5,
                                         font_color="#94a3b8", ax=ax)
            legend = [mpatches.Patch(color=c, label=t) for t, c in TYPE_COLORS.items()]
            ax.legend(handles=legend, loc="upper left", fontsize=6.5,
                      facecolor="#1e293b", labelcolor="white",
                      framealpha=0.85, ncol=2)
            lang = G.graph.get("language","en")
            ax.set_title(f"{title}  [lang={lang}]", color="white", fontsize=13, pad=10)
            ax.axis("off")

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight",
                    dpi=120, facecolor=fig.get_facecolor())
        plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()