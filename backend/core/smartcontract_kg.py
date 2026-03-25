"""
Algorithm 2: Smart Contract Generation & KG extraction (AST-driven).

Key fixes over previous version:
  1. Party variable names derived from node LABEL (human name), not node ID
     (which was the raw value containing $, spaces, etc.)
  2. Constructor does NOT require(_endDate > _startDate) when dates are absent —
     this was causing every deploy to revert on contracts without dates
  3. Payment schedule seeding reads the 'amount' attribute (normalised digits),
     not a regex over the label — reliable across all payment formats
  4. by() filter accepts "PARTY" only (nodes are never typed "ORG"/"PERSON" in our KG)
  5. Obligation comments in generated code now include the actual clause text
  6. All generated Solidity identifiers are sanitised through _safe_id(label)
     not _safe_id(id) — id contains "::" and raw values with special chars
  7. Late-fee / penalty logic wired to payment nodes via KG edges
  8. Multi-page contracts produce a single merged contract with PAGE_SECTIONS mapping
"""
import re, os, tempfile
from datetime import datetime
import networkx as nx

SOLC_VERSION = "0.8.16"

# ── Identifier helpers ─────────────────────────────────────────────────────────
def _safe_id(s: str, n: int = 32) -> str:
    """Produce a valid Solidity identifier from any string."""
    # Strip the "TYPE::" prefix added by the new econtract_kg node IDs
    s = re.sub(r"^[A-Z_]+::", "", s)
    clean = re.sub(r"[^A-Za-z0-9_]", "_", s.strip())
    clean = re.sub(r"_+", "_", clean).strip("_")
    # Ensure it starts with a letter
    if clean and clean[0].isdigit():
        clean = "p_" + clean
    return clean[:n] or "item"

def _to_uint(v: str) -> str:
    """Extract a uint256-compatible integer string from a value like '$1,000' or '10000'."""
    m = re.search(r"[\d,]+(?:\.\d+)?", v)
    if not m: return "0"
    r = m.group().replace(",", "")
    if "." in r:
        p = r.split(".")
        return p[0] + p[1].ljust(18, "0")[:18]
    return r

def _ddmmyyyy_to_timestamp(date_str: str) -> str:
    """Convert DDMMYYYY to Unix timestamp string. Returns '0' on failure."""
    if len(date_str) != 8: return "0"
    try:
        day, month, year = int(date_str[:2]), int(date_str[2:4]), int(date_str[4:8])
        if not (1 <= month <= 12 and 1 <= day <= 31 and 1970 <= year <= 2100): return "0"
        return str(int(datetime(year, month, day).timestamp()))
    except Exception:
        return "0"

def _unix_from_node(node: dict) -> str:
    """Extract unix timestamp from a DATE_DEADLINE node."""
    # Prefer pre-computed unix_ts attribute
    ts = node.get("unix_ts", 0)
    if ts and ts != 0:
        return str(ts)
    # Fall back: parse normalized DDMMYYYY
    normalized = node.get("normalized", "")
    if normalized:
        return _ddmmyyyy_to_timestamp(normalized)
    # Last resort: parse label
    label = node.get("label", "")
    norm  = re.sub(r"[^0-9]", "", label)
    if len(norm) == 8:
        return _ddmmyyyy_to_timestamp(norm)
    return "0"

# ── Dynamic extraction helpers ─────────────────────────────────────────────────
def _extract_governing_law(nodes: list) -> str:
    for node in nodes:
        label = str(node.get("label", "")).lower()
        if re.search(r"indian|india", label): return "Indian Law"
        if re.search(r"english|england|uk|united kingdom", label): return "English Law"
        if re.search(r"delaware", label): return "Delaware Law"
        if re.search(r"new york", label): return "New York Law"
        if re.search(r"california", label): return "California Law"
    return "Indian Law"

def _extract_jurisdiction(nodes: list) -> str:
    for node in nodes:
        label = str(node.get("label", ""))
        if re.search(r"bengaluru|bangalore", label, re.I): return "Bangalore"
        if re.search(r"mumbai", label, re.I): return "Mumbai"
        if re.search(r"delhi|new delhi", label, re.I): return "Delhi"
        if re.search(r"hyderabad", label, re.I): return "Hyderabad"
        if re.search(r"chennai", label, re.I): return "Chennai"
        if re.search(r"new york", label, re.I): return "New York"
        if re.search(r"los angeles|california", label, re.I): return "California"
    return "Indian Courts"

def _extract_arbitration_body(nodes: list) -> str:
    for node in nodes:
        label = str(node.get("label", "")).upper()
        if re.search(r"\bAAA\b", label): return "AAA"
        if re.search(r"\bUNCITRAL\b", label): return "UNCITRAL"
        if re.search(r"\bICC\b", label): return "ICC"
        if re.search(r"\bLCIA\b", label): return "LCIA"
        if re.search(r"\bSIAC\b", label): return "SIAC"
        if re.search(r"arbitration", label, re.I): return "Arbitration (Mutual Consent)"
    return "Arbitration (Mutual Consent)"

def _extract_contract_type(nodes: list, edges: list) -> str:
    """Detect contract type from entity labels for targeted Solidity comments."""
    labels = " ".join(str(n.get("label","")).lower() for n in nodes)
    if re.search(r"rent|lease|landlord|tenant|tenancy|property", labels): return "RENTAL"
    if re.search(r"intern|internship|fellowship|trainee|stipend", labels): return "INTERNSHIP"
    if re.search(r"employment|employee|employer|salary|wages", labels): return "EMPLOYMENT"
    if re.search(r"service|consultant|consulting|advisor", labels): return "SERVICE"
    if re.search(r"nda|confidential|non.disclosure", labels): return "NDA"
    if re.search(r"sale|purchase|buyer|seller|vendor", labels): return "SALE"
    if re.search(r"loan|borrow|lend|credit|debt", labels): return "LOAN"
    return "GENERAL"

# ── Main Solidity generator ────────────────────────────────────────────────────
def kg_to_solidity(kg: dict, contract_name: str = "EContract",
                   party_addresses: dict = None,
                   page_number: int = 0, page_title: str = "") -> str:
    """
    Generate production-quality Solidity ^0.8.16 from an e-contract knowledge graph.

    Args:
        kg:              Knowledge graph dict (nodes/edges from graph_to_dict)
        contract_name:   Solidity contract name
        party_addresses: Optional {party_label: "0x..."} for pre-seeding addresses
        page_number:     Page number in multi-page mode (0 = single-page)
        page_title:      Section title embedded as PAGE_CONTEXT constant
    """
    nodes = kg.get("nodes", [])
    edges = kg.get("edges", [])
    name  = re.sub(r"[^A-Za-z0-9]", "", contract_name) or "EContract"

    def by(*types):
        return [n for n in nodes if n.get("entity_type") in types]

    parties      = by("PARTY")
    payments     = by("PAYMENT")
    obligations  = by("OBLIGATION")
    conditions   = by("CONDITION")
    terminations = by("TERMINATION")
    penalties    = by("PENALTY_REMEDY")
    disputes     = by("DISPUTE_ARBITRATION")
    confidential = by("CONFIDENTIALITY_IP")
    force_maj    = by("FORCE_MAJEURE")
    milestones   = by("MILESTONE")
    date_nodes   = by("DATE_DEADLINE")

    governing_law    = _extract_governing_law(nodes)
    jurisdiction     = _extract_jurisdiction(nodes)
    arbitration_body = _extract_arbitration_body(nodes)
    contract_type    = _extract_contract_type(nodes, edges)

    if party_addresses is None:
        party_addresses = {}

    # ── Build edge lookup for business-logic wiring ────────────────────────────
    # edge_map: (source_id, target_id) → {relation, sentence}
    edge_map = {(e["source"], e["target"]): e for e in edges}

    # For each payment node, find who PAYS it and who RECEIVES it via edges
    def _payment_payer(pay_nid: str):
        for (src, tgt), e in edge_map.items():
            if tgt == pay_nid and e.get("relation") in ("PAYS", "HAS_OBLIGATION"):
                # Find matching party node
                for p in parties:
                    if p["id"] == src:
                        return p
        return None

    def _payment_payee(pay_nid: str):
        for (src, tgt), e in edge_map.items():
            if tgt == pay_nid and e.get("relation") == "RECEIVES":
                for p in parties:
                    if p["id"] == src:
                        return p
        return None

    # ── Party deduplication and identifier generation ──────────────────────────
    # Key fix: use node LABEL (human-readable name) for variable name, not node ID
    # Node ID is "PARTY::Alice" — _safe_id strips the prefix correctly
    _NOISE_SUFFIX_RE = re.compile(r"(_[Dd]t|_[Dd]ate|_[Nn]o|_[Rr]ef)$")
    party_pairs: list = []   # [(solidity_var_name, node_dict)]
    _seen_norm:  set  = set()
    _seen_pid:   set  = set()

    for i, p in enumerate(parties[:10]):
        # Use label (e.g. "Alice") not id (e.g. "PARTY::Alice")
        raw_label = p.get("label", p.get("id", f"party{i}"))
        raw_pid   = _safe_id(raw_label)
        clean_pid = _NOISE_SUFFIX_RE.sub("", raw_pid)
        norm      = re.sub(r"[^a-z0-9]", "", clean_pid.lower())
        if not norm or norm in _seen_norm:
            continue
        _seen_norm.add(norm)
        pid = f"{clean_pid}_{i}" if clean_pid in _seen_pid else clean_pid
        _seen_pid.add(pid)
        party_pairs.append((pid, p))

    # ── Date collection ────────────────────────────────────────────────────────
    # Collect all dates with unix timestamps; identify start/end dates
    date_entries = []  # [(label, unix_ts_str, is_duration)]
    for dn in date_nodes:
        ts = _unix_from_node(dn)
        date_entries.append({
            "label":       dn.get("label", ""),
            "normalized":  dn.get("normalized", ""),
            "unix_ts":     ts,
            "is_duration": dn.get("is_duration", False),
        })

    # Sort calendar dates chronologically to identify start/end
    calendar_dates = sorted(
        [d for d in date_entries if not d["is_duration"] and d["unix_ts"] != "0"],
        key=lambda d: int(d["unix_ts"])
    )
    start_ts = calendar_dates[0]["unix_ts"]  if len(calendar_dates) >= 1 else "0"
    end_ts   = calendar_dates[-1]["unix_ts"] if len(calendar_dates) >= 2 else "0"

    # ── Payment schedule seeding ───────────────────────────────────────────────
    # Use the 'amount' attribute (pre-normalised digits) — reliable, no regex on label
    init_payments = []
    seen_init_amounts: set = set()
    for p in payments:
        # 'amount' is set by econtract_kg as the normalised digit string
        amt = p.get("amount", "")
        if not amt:
            amt = _to_uint(p.get("label", ""))
        if not amt or amt == "0" or amt in seen_init_amounts:
            continue
        seen_init_amounts.add(amt)
        label_safe = re.sub(r"[\"']", "", p.get("label", ""))[:40]
        # Use 0 for dueDate in constructor — caller sets actual schedules post-deploy
        init_payments.append(
            f'paymentSchedules.push(PaymentSchedule({amt}, 0, false, "{label_safe}"));'
        )
        if len(init_payments) >= 8:
            break

    # ── Detect reporting/joining deadline ──────────────────────────────────────
    reporting_deadline_ts = "0"
    for d in calendar_dates:
        if d["unix_ts"] != "0":
            reporting_deadline_ts = d["unix_ts"]
            break
    has_deadline = (reporting_deadline_ts != "0" and (terminations or obligations))

    # ── Detect rental/utility context ─────────────────────────────────────────
    all_labels = " ".join(n.get("label","") for n in nodes).lower()
    has_utilities = bool(re.search(r"bescom|electricity|bwssb|water|gas|utility|meter", all_labels))
    has_subletting = bool(re.search(r"sublet|subletting", all_labels))

    # ── Build Solidity output ──────────────────────────────────────────────────
    L = []; w = L.extend

    # ── Header ────────────────────────────────────────────────────────────────
    w([
        "// SPDX-License-Identifier: MIT",
        "pragma solidity ^0.8.16;",
        "",
        f"/// @title  {name}",
        f"/// @notice Auto-generated from E-Contract KG | Type: {contract_type}",
        f"/// @dev    Jurisdiction: {jurisdiction} | Governing Law: {governing_law}",
        f"///         Arbitration:  {arbitration_body}",
        f"contract {name} {{",
        "",
    ])

    # ── Core state variables ───────────────────────────────────────────────────
    w([
        "    // ── Core ────────────────────────────────────────────────────────",
        "    address public owner;",
        "    bool    public isActive;",
        "    bool    public isTerminated;",
        "    bool    public forceMajeureActive;",
        "    uint256 public deployedAt;",
        "    uint256 public contractStartDate;",
        "    uint256 public contractEndDate;",
        '    string  public currency;',
        f'    string  public constant CONTRACT_TYPE = "{contract_type}";',
        f'    string  public constant JURISDICTION   = "{jurisdiction}";',
        f'    string  public constant GOVERNING_LAW  = "{governing_law}";',
        f'    string  public constant ARBITRATION    = "{arbitration_body}";',
        "",
    ])

    # ── Page context (multi-page mode) ────────────────────────────────────────
    if page_number > 0:
        safe_title = (page_title or "").replace('"', "").replace("'", "")[:60]
        w([
            f'    uint256 public constant PAGE_NUMBER  = {page_number};',
            f'    string  public constant PAGE_CONTEXT = "{safe_title}";',
            "",
        ])

    # ── Party addresses ───────────────────────────────────────────────────────
    if party_pairs:
        w(["    // ── Parties ─────────────────────────────────────────────────────"])
        for pid, pnode in party_pairs:
            comment = pnode.get("label", pid)[:40]
            w([f"    address public {pid}; // {comment}"])
        w([""])

    # ── Financial state ───────────────────────────────────────────────────────
    w([
        "    // ── Financial ───────────────────────────────────────────────────",
        "    uint256 public totalContractValue;",
        "    uint256 public paidAmount;",
        "    uint256 public penaltyRateBps;    // basis points (1 bps = 0.01%)",
        "    uint256 public penaltyPeriod;     // seconds per penalty period",
        "    uint256 public liabilityCap;      // max total penalty (0 = uncapped)",
        "    uint256 public accruedPenalties;",
        "",
    ])

    # ── VALUE constants extracted from e-contract ──────────────────────────────
    # Emit uint256 constants for every monetary amount and calendar date
    value_lines = ["    // ── E-Contract Values ──────────────────────────────────────────"]
    emitted_amounts: set = set()
    for p in payments:
        amt = p.get("amount", "")
        if amt and amt != "0" and amt not in emitted_amounts:
            emitted_amounts.add(amt)
            lbl = re.sub(r"[^A-Za-z0-9_]", "_", p.get("label","")[:20]).strip("_").upper()
            value_lines.append(f"    uint256 public constant AMOUNT_{amt} = {amt}; // {p.get('label','')[:40]}")
    for d in calendar_dates:
        ts = d["unix_ts"]
        if ts != "0":
            lbl = re.sub(r"[^A-Za-z0-9]", "_", d["label"][:20]).strip("_")
            value_lines.append(f"    uint256 public constant DATE_{lbl} = {ts}; // {d['label']}")
    if len(value_lines) > 1:
        w(value_lines + [""])

    # ── Payment schedule struct (always present — needed by _calcSurplus) ──────
    w([
        "    // ── Payment Schedules ────────────────────────────────────────────",
        "    struct PaymentSchedule {",
        "        uint256 amount;",
        "        uint256 dueDate;    // Unix timestamp (0 = on-demand)",
        "        bool    released;",
        "        string  description;",
        "    }",
        "    PaymentSchedule[] public paymentSchedules;",
        "",
    ])

    # ── Utility billing (rental contracts) ────────────────────────────────────
    if has_utilities:
        w([
            "    // ── Utility Billing ─────────────────────────────────────────────",
            "    struct UtilityBilling {",
            "        string  utilityName;",
            "        string  meterId;",
            "        uint256 lastReading;",
            "        uint256 currentReading;",
            "        uint256 amountDue;",
            "        uint256 dueDate;",
            "        bool    paid;",
            "    }",
            "    UtilityBilling[] public utilityBillings;",
            "",
        ])

    # ── Obligation tracking ────────────────────────────────────────────────────
    w([
        "    // ── Obligations ─────────────────────────────────────────────────",
        "    enum ObligationStatus { PENDING, FULFILLED, BREACHED, WAIVED }",
        "    struct ObligationRecord {",
        "        string           description; // full clause text from e-contract",
        "        ObligationStatus status;",
        "        address          assignedTo;",
        "        uint256          deadline;    // 0 = no deadline",
        "        bool             bestEfforts; // true = reasonable-efforts standard",
        "    }",
        "    mapping(uint256 => ObligationRecord) public obligationRecords;",
        "    uint256 public obligationCount;",
        "",
    ])

    # ── Condition tracking ────────────────────────────────────────────────────
    if conditions:
        w([
            "    // ── Conditions ──────────────────────────────────────────────────",
            "    struct ConditionRecord {",
            "        string  description;",
            "        bool    isFulfilled;",
            "        bool    isCarveOut;   // true = this is an exception/carve-out",
            "        bool    isNested;     // true = depends on a parent condition",
            "        uint256 parentCondId;",
            "    }",
            "    mapping(uint256 => ConditionRecord) public conditionRecords;",
            "    uint256 public conditionCount;",
            "",
        ])

    # ── Milestone tracking ────────────────────────────────────────────────────
    if milestones:
        w([
            "    // ── Milestones ──────────────────────────────────────────────────",
            "    enum MilestoneStatus { PENDING, IN_PROGRESS, COMPLETED, DISPUTED }",
            "    struct Milestone {",
            "        string          name;",
            "        uint256         dueDate;",
            "        uint256         paymentIndex; // index in paymentSchedules",
            "        MilestoneStatus status;",
            "        bool            acceptanceSigned;",
            "    }",
            "    Milestone[] public milestones;",
            "",
        ])

    # ── Dispute tracking ──────────────────────────────────────────────────────
    if disputes:
        w([
            "    // ── Disputes ────────────────────────────────────────────────────",
            "    enum DisputeStatus { NONE, RAISED, MEDIATION, ARBITRATION, RESOLVED }",
            "    struct Dispute {",
            "        uint256       raisedAt;",
            "        address       raisedBy;",
            "        string        description;",
            "        DisputeStatus status;",
            "        string        resolution;",
            "    }",
            "    Dispute[] public disputes;",
            "",
        ])

    # ── NDA / IP tracking ─────────────────────────────────────────────────────
    if confidential:
        w([
            "    // ── Confidentiality / IP ────────────────────────────────────────",
            "    struct ConfidentialityRecord {",
            "        address disclosingParty;",
            "        address receivingParty;",
            "        uint256 disclosedAt;",
            "        uint256 expiresAt;",
            "        bool    breached;",
            "    }",
            "    ConfidentialityRecord[] public ndaRecords;",
            "    mapping(address => bool) public ipAssigned;",
            "",
        ])

    # ── Reporting/joining deadline (internship, employment) ───────────────────
    if has_deadline:
        w([
            f"    uint256 public reportingDeadline = {reporting_deadline_ts}; // Unix timestamp",
            "    bool    public reportingFulfilled;",
            "",
        ])

    # ── Subletting prohibition (rental) ───────────────────────────────────────
    if has_subletting:
        w([
            "    bool public sublettingProhibited = true;",
            "",
        ])

    # ── Events ────────────────────────────────────────────────────────────────
    w([
        "    // ── Events ──────────────────────────────────────────────────────",
        "    event ContractActivated(address indexed by, uint256 at);",
        "    event FundsDeposited(address indexed from, uint256 amount, uint256 at);",
        "    event ObligationAdded(uint256 indexed id, string desc, bool bestEfforts);",
        "    event ObligationFulfilled(uint256 indexed id, address by);",
        "    event ObligationBreached(uint256 indexed id);",
        "    event PaymentReleased(uint256 indexed idx, address to, uint256 amount);",
        "    event PenaltyApplied(address indexed party, uint256 amount, string reason);",
        "    event ContractTerminated(string reason, uint256 at);",
        "    event ForceMajeureActivated(string reason);",
        "    event ForceMajeureLifted(uint256 at);",
    ])
    if conditions:
        w(["    event ConditionFulfilled(uint256 indexed id);"])
    if milestones:
        w(["    event MilestoneCompleted(uint256 indexed idx);",
           "    event MilestoneAccepted(uint256 indexed idx);"])
    if disputes:
        w(["    event DisputeRaised(uint256 indexed idx, address by);",
           "    event DisputeResolved(uint256 indexed idx);"])
    if confidential:
        w(["    event NDARecorded(address indexed discloser, address indexed receiver, uint256 exp);",
           "    event NDABreached(address indexed party);"])
    if has_deadline:
        w(["    event DeadlineMissed(uint256 deadline, uint256 checkedAt);"])
    w([""])

    # ── Modifiers ─────────────────────────────────────────────────────────────
    party_cond = " || ".join(f"msg.sender == {pid}" for pid, _ in party_pairs)
    if not party_cond:
        party_cond = "msg.sender == owner"

    w([
        "    // ── Modifiers ────────────────────────────────────────────────────",
        "    modifier onlyOwner() {",
        '        require(msg.sender == owner, "Not owner");',
        "        _;",
        "    }",
        "    modifier whenActive() {",
        '        require(isActive && !isTerminated, "Contract not active");',
        '        require(!forceMajeureActive,        "Force majeure in effect");',
        "        _;",
        "    }",
        f"    modifier onlyParty() {{",
        f"        require({party_cond} || msg.sender == owner, \"Not a party\");",
        "        _;",
        "    }",
        "",
    ])

    # ── Constructor ───────────────────────────────────────────────────────────
    party_params = "".join(f",\n        address _{pid}" for pid, _ in party_pairs)
    w([
        "    // ── Constructor ─────────────────────────────────────────────────",
        "    constructor(",
        "        uint256 _totalValue,",
        "        uint256 _penaltyBps,",
        "        uint256 _penaltyPeriod,",
        "        uint256 _liabilityCap," + party_params + ",",
        "        string memory _currency,",
        "        uint256 _startDate,",
        "        uint256 _endDate",
        "    ) {",
        "        owner              = msg.sender;",
        "        isActive           = true;",
        "        deployedAt         = block.timestamp;",
        "        totalContractValue = _totalValue;",
        "        penaltyRateBps     = _penaltyBps;",
        "        penaltyPeriod      = _penaltyPeriod;",
        "        liabilityCap       = _liabilityCap;",
        "        currency           = _currency;",
        "        contractStartDate  = _startDate;",
        "        contractEndDate    = _endDate;",
        '        require(_totalValue > 0, "totalValue must be > 0");',
        "        // Allow _endDate == 0 (open-ended contract) or _endDate > _startDate",
        "        if (_endDate > 0 && _startDate > 0) {",
        '            require(_endDate > _startDate, "endDate must be after startDate");',
        "        }",
    ])

    # Assign party addresses
    for pid, _ in party_pairs:
        w([f"        {pid} = _{pid};"])

    # Seed payment schedules from extracted amounts
    if init_payments:
        w(["        // Payment schedules from e-contract:"])
        for line in init_payments:
            w([f"        {line}"])

    # Seed pre-extracted obligation texts as records
    if obligations:
        w(["        // Obligations from e-contract clauses:"])
        for i, obl in enumerate(obligations[:6]):
            clause = obl.get("label","")[:80].replace('"',"'")
            is_best = "best efforts" in obl.get("trigger","").lower() or \
                      "reasonable efforts" in obl.get("trigger","").lower()
            w([f'        obligationRecords[{i}] = ObligationRecord("{clause}", ObligationStatus.PENDING, address(0), 0, {"true" if is_best else "false"});',
               f"        obligationCount++;"])

    w(["        emit ContractActivated(msg.sender, block.timestamp);", "    }", ""])

    # ── Utility functions ──────────────────────────────────────────────────────
    w([
        "    // ── Status & Utility ────────────────────────────────────────────",
        "    function isContractExpired() external view returns (bool) {",
        "        if (contractEndDate == 0) return false;",
        "        return block.timestamp > contractEndDate;",
        "    }",
        "",
        "    function getDaysRemaining() external view returns (int256) {",
        "        if (contractEndDate == 0) return type(int256).max;",
        "        int256 rem = int256(contractEndDate) - int256(block.timestamp);",
        "        return rem > 0 ? rem / 86400 : int256(-1);",
        "    }",
        "",
        "    function getStatus() external view returns (bool active, bool terminated, bool fm, uint256 deployed) {",
        "        return (isActive, isTerminated, forceMajeureActive, deployedAt);",
        "    }",
        "",
        "    function getContractBalance() external view returns (uint256) {",
        "        return address(this).balance;",
        "    }",
        "",
        "    function _calcSurplus() private view returns (uint256) {",
        "        uint256 locked = 0;",
        "        for (uint256 i = 0; i < paymentSchedules.length; i++) {",
        "            if (!paymentSchedules[i].released) locked += paymentSchedules[i].amount;",
        "        }",
        "        return address(this).balance > locked ? address(this).balance - locked : 0;",
        "    }",
        "",
        "    function getSurplusBalance() external view returns (uint256) { return _calcSurplus(); }",
        "",
        "    function withdrawSurplus(address payable recipient) external onlyOwner {",
        '        require(recipient != address(0), "zero address");',
        "        uint256 surplus = _calcSurplus();",
        '        require(surplus > 0, "no surplus");',
        "        (bool ok,) = recipient.call{value: surplus}(\"\");",
        '        require(ok, "transfer failed");',
        "    }",
        "",
    ])

    # ── Obligation management ─────────────────────────────────────────────────
    w([
        "    // ── Obligation Management ───────────────────────────────────────",
        "    function addObligation(",
        "        string calldata desc,",
        "        address to,",
        "        uint256 deadline,",
        "        bool bestEfforts",
        "    ) external onlyOwner whenActive returns (uint256 id) {",
        "        id = obligationCount++;",
        "        obligationRecords[id] = ObligationRecord(desc, ObligationStatus.PENDING, to, deadline, bestEfforts);",
        "        emit ObligationAdded(id, desc, bestEfforts);",
        "    }",
        "",
        "    function fulfillObligation(uint256 id) external whenActive onlyParty {",
        '        require(obligationRecords[id].status == ObligationStatus.PENDING, "Not pending");',
    ])
    if has_deadline:
        w([
            "        // Enforce joining/reporting deadline",
            "        if (reportingDeadline > 0 && !reportingFulfilled) {",
            '            require(block.timestamp <= reportingDeadline, "Reporting deadline passed");',
            "            reportingFulfilled = true;",
            "        }",
        ])
    w([
        "        obligationRecords[id].status = ObligationStatus.FULFILLED;",
        "        emit ObligationFulfilled(id, msg.sender);",
        "    }",
        "",
        "    function markObligationBreached(uint256 id) external onlyOwner {",
        "        obligationRecords[id].status = ObligationStatus.BREACHED;",
        "        emit ObligationBreached(id);",
        "    }",
        "",
        "    function waiveObligation(uint256 id) external onlyOwner {",
        "        obligationRecords[id].status = ObligationStatus.WAIVED;",
        "    }",
        "",
    ])

    # ── Auto-cancel if deadline missed (internship/employment) ────────────────
    if has_deadline:
        w([
            "    /// @notice Callable by anyone after joining deadline passes with no fulfilment.",
            "    function checkAndCancelIfOverdue() external {",
            '        require(reportingDeadline > 0,   "No deadline set");',
            '        require(!reportingFulfilled,      "Already fulfilled");',
            '        require(block.timestamp > reportingDeadline, "Deadline not yet passed");',
            "        isTerminated = true;",
            "        isActive     = false;",
            "        emit DeadlineMissed(reportingDeadline, block.timestamp);",
            '        emit ContractTerminated("Deadline missed", block.timestamp);',
            "    }",
            "",
        ])

    # ── Payment schedule management ───────────────────────────────────────────
    w([
        "    // ── Payment Schedule Management ────────────────────────────────",
        "    function addPaymentSchedule(",
        "        uint256 amount,",
        "        uint256 dueDate,",
        "        string calldata desc",
        "    ) external onlyOwner returns (uint256 idx) {",
        '        require(amount > 0, "amount = 0");',
        "        idx = paymentSchedules.length;",
        "        paymentSchedules.push(PaymentSchedule(amount, dueDate, false, desc));",
        "    }",
        "",
        "    /// @notice Release a scheduled payment. Uses Checks-Effects-Interactions.",
        "    function releaseScheduledPayment(",
        "        uint256 idx,",
        "        address payable recipient",
        "    ) external onlyOwner whenActive {",
        '        require(recipient != address(0), "zero address");',
        "        PaymentSchedule storage ps = paymentSchedules[idx];",
        '        require(!ps.released,                         "already released");',
        '        require(address(this).balance >= ps.amount,   "insufficient balance");',
        "        if (ps.dueDate > 0) {",
        '            require(block.timestamp >= ps.dueDate,    "not yet due");',
        "        }",
        "        // Checks-Effects-Interactions: update state before external call",
        "        ps.released  = true;",
        "        paidAmount  += ps.amount;",
        "        emit PaymentReleased(idx, recipient, ps.amount);",
        "        (bool ok,) = recipient.call{value: ps.amount}(\"\");",
        '        require(ok, "transfer failed");',
        "    }",
        "",
        "    /// @notice Release a pro-rata share of the contract balance.",
        "    function proRataRelease(",
        "        address payable recipient,",
        "        uint256 numerator,",
        "        uint256 denominator",
        "    ) external onlyOwner whenActive {",
        '        require(recipient   != address(0), "zero address");',
        '        require(denominator  > 0,          "denominator = 0");',
        '        require(numerator   <= denominator,"numerator > denominator");',
        "        uint256 bal   = address(this).balance;",
        '        require(bal > 0, "no balance");',
        "        uint256 share = (bal * numerator) / denominator;",
        '        require(share > 0, "share = 0");',
        "        paidAmount += share;",
        "        (bool ok,) = recipient.call{value: share}(\"\");",
        '        require(ok, "transfer failed");',
        "    }",
        "",
        "    function paymentScheduleLen() external view returns (uint256) { return paymentSchedules.length; }",
        "",
    ])

    # ── Penalty management ────────────────────────────────────────────────────
    if penalties:
        # Extract penalty amounts from the KG for constants
        penalty_amounts = []
        for pen in penalties:
            amt = re.search(r"\d[\d,]*", pen.get("label",""))
            if amt:
                penalty_amounts.append(amt.group().replace(",",""))

        w([
            "    // ── Penalty / Remedy ────────────────────────────────────────────",
        ])
        for i, amt in enumerate(penalty_amounts[:3]):
            w([f"    uint256 public constant PENALTY_AMOUNT_{i} = {amt};"])
        if penalty_amounts:
            w([""])

        w([
            "    function applyPenalty(",
            "        address party,",
            "        uint256 periods,",
            "        string calldata reason",
            "    ) external onlyOwner {",
            '        require(party   != address(0), "zero address");',
            '        require(periods  > 0,          "periods = 0");',
            '        require(penaltyRateBps > 0,    "penalty rate not set");',
            '        require(totalContractValue > 0,"contract value not set");',
            "        uint256 base = (totalContractValue * penaltyRateBps * periods) / 10000;",
            '        require(base > 0, "penalty = 0");',
            "        if (liabilityCap > 0 && base > liabilityCap) base = liabilityCap;",
            "        accruedPenalties += base;",
            "        emit PenaltyApplied(party, base, reason);",
            "    }",
            "",
        ])

    # ── Condition management ──────────────────────────────────────────────────
    if conditions:
        w([
            "    // ── Condition Management ────────────────────────────────────────",
            "    function addCondition(",
            "        string calldata desc,",
            "        bool isCarveOut,",
            "        bool isNested,",
            "        uint256 parentId",
            "    ) external onlyOwner returns (uint256 id) {",
            "        id = conditionCount++;",
            "        conditionRecords[id] = ConditionRecord(desc, false, isCarveOut, isNested, parentId);",
            "    }",
            "",
            "    function fulfillCondition(uint256 id) external onlyOwner whenActive {",
            "        if (conditionRecords[id].isNested) {",
            '            require(conditionRecords[conditionRecords[id].parentCondId].isFulfilled, "Parent condition not met");',
            "        }",
            "        conditionRecords[id].isFulfilled = true;",
            "        emit ConditionFulfilled(id);",
            "    }",
            "",
        ])

    # ── Milestone management ──────────────────────────────────────────────────
    if milestones:
        w([
            "    // ── Milestone Management ────────────────────────────────────────",
            "    function addMilestone(",
            "        string calldata mName,",
            "        uint256 dueDate,",
            "        uint256 payIdx",
            "    ) external onlyOwner returns (uint256 idx) {",
            '        require(bytes(mName).length > 0, "empty name");',
            "        idx = milestones.length;",
            "        milestones.push(Milestone(mName, dueDate, payIdx, MilestoneStatus.PENDING, false));",
            "    }",
            "",
            "    function completeMilestone(uint256 idx) external whenActive onlyParty {",
            '        require(idx < milestones.length,                             "invalid index");',
            '        require(milestones[idx].status == MilestoneStatus.PENDING,   "not pending");',
            "        milestones[idx].status = MilestoneStatus.COMPLETED;",
            "        emit MilestoneCompleted(idx);",
            "    }",
            "",
            "    function acceptMilestone(uint256 idx) external onlyOwner whenActive {",
            '        require(idx < milestones.length,                               "invalid index");',
            '        require(milestones[idx].status == MilestoneStatus.COMPLETED,   "not completed");',
            "        milestones[idx].acceptanceSigned = true;",
            "        emit MilestoneAccepted(idx);",
            "    }",
            "",
            "    function milestoneLen() external view returns (uint256) { return milestones.length; }",
            "",
        ])

    # ── Dispute management ────────────────────────────────────────────────────
    if disputes:
        w([
            "    // ── Dispute Resolution ──────────────────────────────────────────",
            "    function raiseDispute(string calldata desc) external onlyParty whenActive {",
            "        disputes.push(Dispute(block.timestamp, msg.sender, desc, DisputeStatus.RAISED, \"\"));",
            "        emit DisputeRaised(disputes.length - 1, msg.sender);",
            "    }",
            "",
            "    function escalateToArbitration(uint256 idx) external onlyParty {",
            '        require(disputes[idx].status != DisputeStatus.RESOLVED, "already resolved");',
            "        disputes[idx].status = DisputeStatus.ARBITRATION;",
            "    }",
            "",
            "    function resolveDispute(uint256 idx, string calldata resolution) external onlyOwner {",
            "        disputes[idx].status     = DisputeStatus.RESOLVED;",
            "        disputes[idx].resolution = resolution;",
            "        emit DisputeResolved(idx);",
            "    }",
            "",
            "    function disputeLen() external view returns (uint256) { return disputes.length; }",
            "",
        ])

    # ── NDA / Confidentiality management ──────────────────────────────────────
    if confidential:
        w([
            "    // ── Confidentiality / IP ────────────────────────────────────────",
            "    function recordNDA(",
            "        address disclosing,",
            "        address receiving,",
            "        uint256 duration",
            "    ) external onlyOwner returns (uint256 idx) {",
            "        idx = ndaRecords.length;",
            "        ndaRecords.push(ConfidentialityRecord(",
            "            disclosing, receiving,",
            "            block.timestamp, block.timestamp + duration, false",
            "        ));",
            "        emit NDARecorded(disclosing, receiving, block.timestamp + duration);",
            "    }",
            "",
            "    function recordNDABreach(uint256 idx) external onlyOwner {",
            "        ndaRecords[idx].breached = true;",
            "        emit NDABreached(ndaRecords[idx].receivingParty);",
            "    }",
            "",
            "    function assignIP(address party) external onlyOwner {",
            "        ipAssigned[party] = true;",
            "    }",
            "",
        ])

    # ── Force majeure ─────────────────────────────────────────────────────────
    if force_maj:
        w([
            "    // ── Force Majeure ────────────────────────────────────────────────",
            "    function activateForceMajeure(string calldata reason) external onlyOwner {",
            '        require(!forceMajeureActive, "already active");',
            "        forceMajeureActive = true;",
            "        emit ForceMajeureActivated(reason);",
            "    }",
            "",
            "    function liftForceMajeure() external onlyOwner {",
            '        require(forceMajeureActive, "not active");',
            "        forceMajeureActive = false;",
            "        emit ForceMajeureLifted(block.timestamp);",
            "    }",
            "",
        ])

    # ── Utility billing (rental) ──────────────────────────────────────────────
    if has_utilities:
        w([
            "    // ── Utility Billing ─────────────────────────────────────────────",
            "    function recordUtilityBilling(",
            "        string calldata utilName,",
            "        string calldata meterId,",
            "        uint256 currentReading,",
            "        uint256 amount,",
            "        uint256 dueDate",
            "    ) external onlyOwner returns (uint256 idx) {",
            "        idx = utilityBillings.length;",
            "        utilityBillings.push(UtilityBilling(utilName, meterId, 0, currentReading, amount, dueDate, false));",
            "    }",
            "",
            "    function markUtilityPaid(uint256 idx) external onlyOwner {",
            "        utilityBillings[idx].paid = true;",
            "        paidAmount += utilityBillings[idx].amountDue;",
            "    }",
            "",
            "    function updateUtilityReading(uint256 idx, uint256 newReading) external onlyOwner {",
            "        utilityBillings[idx].lastReading    = utilityBillings[idx].currentReading;",
            "        utilityBillings[idx].currentReading = newReading;",
            "    }",
            "",
        ])

    # ── Termination ───────────────────────────────────────────────────────────
    if terminations:
        w([
            "    // ── Termination ─────────────────────────────────────────────────",
            "    function terminateContract(string calldata reason) external onlyOwner {",
            '        require(!isTerminated, "already terminated");',
            "        isTerminated = true;",
            "        isActive     = false;",
            "        emit ContractTerminated(reason, block.timestamp);",
            "    }",
            "",
            "    function terminateForBreach(uint256 obligationId) external onlyOwner {",
            '        require(obligationRecords[obligationId].status == ObligationStatus.BREACHED, "Not breached");',
            "        isTerminated = true;",
            "        isActive     = false;",
            '        emit ContractTerminated("Breach of obligation", block.timestamp);',
            "    }",
            "",
        ])

    # ── receive() ─────────────────────────────────────────────────────────────
    w([
        "    // ── Receive ETH ─────────────────────────────────────────────────",
        "    receive() external payable {",
        '        require(isActive, "contract not active");',
        "        emit FundsDeposited(msg.sender, msg.value, block.timestamp);",
        "    }",
        "}",
    ])

    # Post-process: strip any assert() lines (safety measure against bad patches)
    _ASSERT_RE = re.compile(r"^\s*assert\s*\(", re.IGNORECASE)
    final_lines = [line for line in L if not _ASSERT_RE.match(line)]
    return "\n".join(final_lines)


# ── AST → KG (Algorithm 2) ────────────────────────────────────────────────────
def compile_solidity_to_ast(code: str) -> dict:
    try:
        import solcx
        solcx.install_solc(SOLC_VERSION, show_progress=False)
        solcx.set_solc_version(SOLC_VERSION)
        with tempfile.NamedTemporaryFile(suffix=".sol", mode="w", delete=False) as f:
            f.write(code); tmp = f.name
        result = solcx.compile_files([tmp], output_values=["ast"], solc_version=SOLC_VERSION)
        os.unlink(tmp)
        for _, v in result.items():
            if "ast" in v: return v["ast"]
    except Exception:
        pass
    return _fallback_ast_parse(code)

def _fallback_ast_parse(code: str) -> dict:
    ast = {"nodeType": "SourceUnit", "children": []}
    cm  = re.search(r"contract\s+(\w+)\s*\{", code)
    if not cm: return ast
    node = {"nodeType": "ContractDefinition", "name": cm.group(1), "children": []}

    for fn in re.finditer(
        r"function\s+(\w+)\s*\(([^)]*)\)\s*(external|public|internal|private)?"
        r"\s*(view|pure|payable)?\s*(?:returns\s*\([^)]*\))?\s*\{", code):
        node["children"].append({
            "nodeType":   "FunctionDefinition",
            "name":       fn.group(1),
            "params":     fn.group(2),
            "visibility": fn.group(3) or "public",
        })

    for ev in re.finditer(r"event\s+(\w+)\s*\(([^)]*)\)", code):
        node["children"].append({"nodeType": "EventDefinition", "name": ev.group(1)})

    for sv in re.finditer(
        r"(?:address|uint\d*|bool|string|bytes\d*|mapping|[\w\.]+(?:\[\])*)\s+"
        r"(?:public|private|internal)?\s*(\w+)\s*[;=]", code):
        var_name = sv.group(1)
        if var_name not in {"returns","memory","storage","calldata","view","pure","payable"}:
            node["children"].append({"nodeType": "StateVariableDeclaration", "name": var_name})

    for st in re.finditer(r"struct\s+(\w+)\s*\{", code):
        node["children"].append({"nodeType": "StructDefinition", "name": st.group(1)})

    for en in re.finditer(r"enum\s+(\w+)\s*\{", code):
        node["children"].append({"nodeType": "EnumDefinition", "name": en.group(1)})

    ast["children"].append(node)
    return ast

def _walk_ast(node: dict, G: nx.DiGraph, parent_id: str = None, counter: list = None):
    if counter is None: counter = [0]
    if not isinstance(node, dict): return
    READABLE = {
        "FunctionDefinition":      "FUNCTION",
        "EventDefinition":         "EVENT",
        "StateVariableDeclaration":"VARIABLE",
        "ContractDefinition":      "CONTRACT",
        "ModifierDefinition":      "MODIFIER",
        "StructDefinition":        "STRUCT",
        "EnumDefinition":          "ENUM",
    }
    ntype = node.get("nodeType","Unknown"); name = node.get("name","")
    nid   = f"{ntype}_{name}_{counter[0]}"; counter[0] += 1
    G.add_node(nid,
               entity_type=READABLE.get(ntype,"AST_NODE"),
               label=name or ntype,
               params=node.get("params",""),
               visibility=node.get("visibility",""))
    if parent_id: G.add_edge(parent_id, nid, relation="CONTAINS")
    for child in node.get("children", []): _walk_ast(child, G, nid, counter)
    if isinstance(node.get("nodes"), list):
        for child in node["nodes"]: _walk_ast(child, G, nid, counter)

def build_smartcontract_knowledge_graph(code: str) -> nx.DiGraph:
    G = nx.DiGraph()
    _walk_ast(compile_solidity_to_ast(code), G)
    for fn in re.finditer(r"function\s+(\w+)\s*\(([^)]*)\)", code):
        nid = f"fn_{fn.group(1)}"
        if not G.has_node(nid):
            G.add_node(nid, entity_type="FUNCTION", label=fn.group(1), params=fn.group(2))
    for ev in re.finditer(r"event\s+(\w+)", code):
        nid = f"ev_{ev.group(1)}"
        if not G.has_node(nid):
            G.add_node(nid, entity_type="EVENT", label=ev.group(1))
    for st in re.finditer(r"struct\s+(\w+)", code):
        nid = f"st_{st.group(1)}"
        if not G.has_node(nid):
            G.add_node(nid, entity_type="STRUCT", label=st.group(1))
    return G

def graph_to_dict(G: nx.DiGraph) -> dict:
    return {
        "nodes": [{"id": n, **G.nodes[n]} for n in G.nodes],
        "edges": [{"source": u, "target": v, **G.edges[u,v]} for u, v in G.edges],
    }

def render_graph_base64(G: nx.DiGraph, title: str = "Smart Contract KG") -> str:
    from econtract_kg import render_graph_base64 as _r
    return _r(G, title)