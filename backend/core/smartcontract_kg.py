"""
Algorithm 2: Smart Contract Generation & KG extraction (AST-driven).
Handles: arbitration, milestones, payment schedules, pro-rata, conditions,
carve-outs, confidentiality, force majeure, IP, reasonable-efforts clauses.
Dynamically extracts: jurisdiction, parties, dates, utilities, currency.
SECURITY: Implements Checks-Effects-Interactions, safe ETH transfers, input validation.
pragma solidity ^0.8.16 (pinned).
"""
import re, os, tempfile
from datetime import datetime
import networkx as nx

SOLC_VERSION = "0.8.16"

# ── Dynamic extraction helpers ────────────────────────────────────────
def _extract_governing_law(nodes: list) -> str:
    """Dynamically extract governing law from KG nodes."""
    for node in nodes:
        label = str(node.get("label", "")).lower()
        if re.search(r"indian|india", label): return "Indian Law"
        if re.search(r"english|england|uk|united kingdom", label): return "English Law"
        if re.search(r"delaware", label): return "Delaware Law"
        if re.search(r"new york", label): return "New York Law"
        if re.search(r"california", label): return "California Law"
    return "Indian Law"  # Default for Indian jurisdiction

def _extract_jurisdiction(nodes: list) -> str:
    """Dynamically extract jurisdiction/venue from KG nodes."""
    for node in nodes:
        label = str(node.get("label", "")) 
        if re.search(r"bengaluru|bangalore", label, re.I): return "Bangalore/Bengaluru"
        if re.search(r"mumbai", label, re.I): return "Mumbai"
        if re.search(r"delhi|new delhi", label, re.I): return "Delhi"
        if re.search(r"new york", label, re.I): return "New York"
        if re.search(r"los angeles|california", label, re.I): return "California"
    return "Indian Courts"  # Default

def _extract_arbitration_body(nodes: list) -> str:
    """Dynamically extract arbitration body from KG nodes."""
    for node in nodes:
        label = str(node.get("label", "")).upper()
        if re.search(r"\bAAA\b", label): return "AAA"
        if re.search(r"\bUNCITRAL\b", label): return "UNCITRAL"
        if re.search(r"\bICC\b", label): return "ICC"
        if re.search(r"\bARBITRATION", label):
            if re.search(r"indian", label, re.I): return "DRB (Delhi Seat)"
    return "arbitration with mutual consent"  # Default

def _extract_contract_dates(nodes: list) -> tuple:
    """Extract contract start and end dates (DDMMYYYY format)."""
    dates = []
    for node in nodes:
        label = str(node.get("label", ""))
        # Match DDMMYYYY pattern
        matches = re.findall(r"(\d{2})(\d{2})(\d{4})", label)
        for match in matches:
            day, month, year = match
            date_str = f"{day}{month}{year}"
            dates.append(date_str)
    return tuple(dates[:2]) if len(dates) >= 2 else (None, None)

def _extract_utility_references(nodes: list) -> dict:
    """Extract utility billing references (BESCOM, BWSSB, etc.)."""
    utilities = {"electricity": "", "water": "", "gas": "", "phone": ""}
    for node in nodes:
        label = str(node.get("label", ""))
        if re.search(r"BESCOM|electricity|meter", label, re.I):
            meter_match = re.search(r"[A-Z]{2,}-[A-Z]{2,}-\d+|\d{6,}", label)
            utilities["electricity"] = meter_match.group() if meter_match else "BESCOM"
        if re.search(r"BWSSB|water|supply", label, re.I):
            utilities["water"] = "BWSSB"
        if re.search(r"gas|lpg", label, re.I):
            utilities["gas"] = re.search(r"[A-Z0-9\-]+", label).group() or "GAS"
    return utilities

def _extract_tenant_obligations(nodes: list) -> list:
    """Extract tenant-specific obligations."""
    obligations = []
    for node in nodes:
        label = str(node.get("label", ""))
        if re.search(r"sublet|subletting|transfer|assign", label, re.I):
            obligations.append("NO_SUBLETTING")
        if re.search(r"structural|alteration|modification", label, re.I):
            obligations.append("NO_STRUCTURAL_CHANGES")
        if re.search(r"residential|dwel|use", label, re.I):
            obligations.append("RESIDENTIAL_USE_ONLY")
        if re.search(r"maintain|repair|upkeep", label, re.I):
            obligations.append("MAINTENANCE_REQUIRED")
    return list(set(obligations))  # Remove duplicates

def _ddmmyyyy_to_timestamp(date_str: str) -> str:
    """Convert DDMMYYYY to Unix timestamp (start of day)."""
    if len(date_str) != 8:
        return "0"
    try:
        day, month, year = int(date_str[:2]), int(date_str[2:4]), int(date_str[4:8])
        if not (1 <= month <= 12 and 1 <= day <= 31 and 1970 <= year <= 2100):
            return "0"
        # Convert to Unix timestamp
        dt_obj = datetime(year, month, day)
        timestamp = int(dt_obj.timestamp())
        return str(timestamp)
    except:
        return "0"

def _safe_id(s: str, n: int = 32) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", s.strip())[:n].strip("_") or "item"

def _to_uint(v: str) -> str:
    m = re.search(r"[\d,]+(?:\.\d+)?", v)
    if not m: return "0"
    r = m.group().replace(",", "")
    if "." in r:
        p = r.split(".")
        return p[0] + p[1].ljust(18, "0")[:18]
    return r

def kg_to_solidity(kg: dict, contract_name: str = "EContract", party_addresses: dict = None,
                   page_number: int = 0, page_title: str = "") -> str:
    """
    Generate Solidity contract from knowledge graph.

    Args:
        kg:              Knowledge graph dict with nodes/edges
        contract_name:   Solidity contract name
        party_addresses: Optional mapping of party IDs to Ethereum addresses
        page_number:     Page number in multi-page mode (0 = single-page)
        page_title:      Section/page title embedded as PAGE_CONTEXT constant
    """
    nodes = kg.get("nodes", [])
    name  = re.sub(r"[^A-Za-z0-9]", "", contract_name) or "EContract"
    def by(*t): return [n for n in nodes if n.get("entity_type") in t]

    parties      = by("PARTY","ORG","PERSON");   obligations  = by("OBLIGATION")
    payments     = by("PAYMENT","MONEY");         milestones   = by("MILESTONE")
    conditions   = by("CONDITION");               terminations = by("TERMINATION")
    penalties    = by("PENALTY_REMEDY","PENALTY"); disputes    = by("DISPUTE_ARBITRATION")
    confidential = by("CONFIDENTIALITY_IP");      force_maj    = by("FORCE_MAJEURE")
    date_nodes   = by("DATE_DEADLINE")

    governing_law    = _extract_governing_law(nodes)
    jurisdiction     = _extract_jurisdiction(nodes)
    arbitration_body = _extract_arbitration_body(nodes)
    utilities        = _extract_utility_references(nodes)
    tenant_obligations = _extract_tenant_obligations(nodes)

    if party_addresses is None:
        party_addresses = {}

    # ── Detect joining/reporting deadline (e.g. "report by 08/08/2025 or cancelled") ──
    reporting_deadline_ts: str = "0"
    for dn in date_nodes:
        label = dn.get("label", "").replace("-", "")
        d8 = re.search(r"(\d{2})(\d{2})(\d{4})", label)
        if d8:
            ts = _ddmmyyyy_to_timestamp(d8.group(1) + d8.group(2) + d8.group(3))
            if ts != "0":
                reporting_deadline_ts = ts
                break
    has_deadline = reporting_deadline_ts != "0" and (terminations or obligations)

    # ── Unified, deduplicated, noise-cleaned party list ──────────────────────
    # Single source of truth: used in state vars, modifier, constructor params, body.
    _NOISE_SUFFIX_RE = re.compile(r"(_[Dd]t|_[Dd]ate|_[Nn]o|_[Rr]ef)$")
    party_pairs: list = []
    _seen_norm: set = set()
    _seen_pid:  set = set()
    for i, p in enumerate(parties[:10]):
        raw_pid   = _safe_id(p["id"])
        clean_pid = _NOISE_SUFFIX_RE.sub("", raw_pid)
        norm      = re.sub(r"[^a-z0-9]", "", clean_pid.lower())
        if not norm or norm in _seen_norm:
            continue
        _seen_norm.add(norm)
        pid = f"{clean_pid}_{i}" if clean_pid in _seen_pid else clean_pid
        _seen_pid.add(pid)
        party_pairs.append((pid, p))

    L=[]; w=L.extend
    w(["// SPDX-License-Identifier: MIT","pragma solidity ^0.8.16;","",
       f"/// @title {name} — Auto-generated from E-Contract KG",
       f"/// @notice Jurisdiction: {jurisdiction} | Governing Law: {governing_law}",
       f"contract {name} {{","",
       "    address public owner; bool public isActive; bool public isTerminated;",
       "    bool public forceMajeureActive; uint256 public deployedAt;",
       "    uint256 public contractStartDate; uint256 public contractEndDate;",
       "    string public currency; string public jurisdiction;",""])

    if page_number > 0:
        safe_title = (page_title or "").replace('"', "").replace("'", "")[:60]
        w([f'    uint256 public constant PAGE_NUMBER = {page_number};',
           f'    string  public constant PAGE_CONTEXT = "{safe_title}";', ""])

    for pid, _ in party_pairs:
        w([f"    address public {pid};"])
    w([""])

    # ─ CORE contract parameters (always declared) ─
    w(["    uint256 public totalContractValue; uint256 public paidAmount;",
       "    uint256 public penaltyRateBps; uint256 public penaltyPeriod; uint256 public liabilityCap; uint256 public accruedPenalties;",
       ""])

    # ─ PAYMENT SCHEDULES (ALWAYS DECLARED - required by _calcSurplus() which is always generated) ─
    w(["    struct PaymentSchedule { uint256 amount; uint256 dueDate; bool released; string description; }",
       "    PaymentSchedule[] public paymentSchedules;",""])
    
    # Add utility billing structures if utilities are referenced
    if utilities and any(utilities.values()):
        w(["    struct UtilityBilling { string utilityName; string meterId; uint256 lastReading; uint256 currentReading; uint256 amountDue; uint256 dueDate; bool paid; }",
           "    UtilityBilling[] public utilityBillings;",""])
    
    # ─ OBLIGATION TRACKING (always declared for consistency) ─
    w(["    enum ObligationStatus { PENDING, FULFILLED, BREACHED, WAIVED }",
       "    struct ObligationRecord { string description; ObligationStatus status; address assignedTo; uint256 deadline; bool bestEfforts; }",
       "    mapping(uint256 => ObligationRecord) public obligationRecords; uint256 public obligationCount;",
       ""])
    
    # ─ TENANT OBLIGATION TRACKING (only for lease/rental/tenant contracts) ─
    if tenant_obligations:
        w(["    enum TenantObligationStatus { PENDING, ACKNOWLEDGED, COMPLIANT, BREACHED }",
           "    struct TenantObligation { string description; TenantObligationStatus status; uint256 deadline; bool isSubletProhibition; bool isStructuralProhibition; bool isResidentialUseOnly; }",
           "    mapping(uint256 => TenantObligation) public tenantObligations; uint256 public tenantObligationCount;",
           ""])
    
    if milestones:
        w(["    enum MilestoneStatus { PENDING, IN_PROGRESS, COMPLETED, DISPUTED }",
           "    struct Milestone { string name; uint256 dueDate; uint256 paymentIndex; MilestoneStatus status; bool acceptanceSigned; }",
           "    Milestone[] public milestones;",""])
    
    if conditions:
        w(["    struct ConditionRecord { string description; bool isFulfilled; bool isCarveOut; bool isNested; uint256 parentCondId; }",
           "    mapping(uint256 => ConditionRecord) public conditionRecords; uint256 public conditionCount;",""])
    if disputes:
        w([f'    string public constant GOVERNING_LAW = "{governing_law}";',
           f'    string public constant JURISDICTION = "{jurisdiction}";',
           f'    string public constant ARBITRATION_BODY = "{arbitration_body}";',
           "    enum DisputeStatus { NONE, RAISED, MEDIATION, ARBITRATION, RESOLVED }",
           "    struct Dispute { uint256 raisedAt; address raisedBy; string description; DisputeStatus status; string resolution; }",
           "    Dispute[] public disputes;",""])
    if confidential:
        w(["    struct ConfidentialityRecord { address disclosingParty; address receivingParty; uint256 disclosedAt; uint256 expiresAt; bool breached; }",
           "    ConfidentialityRecord[] public ndaRecords; mapping(address => bool) public ipAssigned;",""])

    # Events
    w(["    event ContractActivated(address indexed by, uint256 at);",
       "    event FundsDeposited(address indexed from, uint256 amount, uint256 at);",
       "    event ObligationAdded(uint256 indexed id, string desc, bool bestEfforts);",
       "    event ObligationFulfilled(uint256 indexed id, address by);",
       "    event ObligationBreached(uint256 indexed id);",
       "    event ConditionFulfilled(uint256 indexed id);",
       "    event PaymentReleased(uint256 indexed idx, address to, uint256 amount);",
       "    event MilestoneCompleted(uint256 indexed idx); event MilestoneAccepted(uint256 indexed idx);",
       "    event PenaltyApplied(address indexed party, uint256 amount, string reason);",
       "    event DisputeRaised(uint256 indexed idx, address by); event DisputeResolved(uint256 indexed idx);",
       "    event ForceMajeureActivated(string reason); event ForceMajeureLifted(uint256 at);",
       "    event NDAdded(address indexed d, address indexed r, uint256 exp); event NDBreached(address indexed p);",
       "    event ContractTerminated(string reason, uint256 at);",""])

    # Modifiers — use party_pairs (same cleaned, deduped IDs as state vars)
    cond = " || ".join(f"msg.sender=={pid}" for pid, _ in party_pairs) or "msg.sender==owner"
    w(["    modifier onlyOwner() { require(msg.sender==owner,'Not owner'); _; }",
       "    modifier whenActive() { require(isActive&&!isTerminated,'Not active'); require(!forceMajeureActive,'Force majeure'); _; }",
       f"    modifier onlyParty() {{ require({cond}||msg.sender==owner,'Not a party'); _; }}",""])

    # Constructor with enhanced initialization
    # Deduplicate payment entries by amount — same Rs. 10,000 from 3 KG nodes must not
    # produce 3 identical PaymentSchedule entries.
    init_payments = []
    seen_init_amounts: set = set()
    for p in payments:
        label = p.get("label", "")
        amt_match = re.search(r"\d{1,3}(?:,\d{3})+|\d{4,}", label)
        if not amt_match:
            continue
        amount = _to_uint(amt_match.group())
        if amount == "0" or amount in seen_init_amounts:
            continue
        seen_init_amounts.add(amount)
        date_match = re.search(r"\d{8}", label)
        due_date = date_match.group() if date_match else "0"
        safe_label = label.replace('"', '').replace("'", "")[:30]
        init_payments.append(f'paymentSchedules.push(PaymentSchedule({amount},{due_date},false,"{safe_label}"));')
        if len(init_payments) >= 6:
            break

    # ── Value constants — only genuine monetary amounts and real dates ────────
    # Rules: skip year numbers (1900-2100), skip 8-digit dates already in DATE_
    # only emit VALUE_ for PAYMENT-typed nodes or labels with currency keywords.
    value_declarations = []
    all_amounts: dict = {}
    all_dates:   dict = {}
    payment_node_ids = {n["id"] for n in nodes if n.get("entity_type") == "PAYMENT"}
    for node in nodes:
        label_str = str(node.get("label", ""))
        if not label_str:
            continue
        node_id    = node.get("id", "")
        is_payment = node_id in payment_node_ids
        has_currency = bool(re.search(
            r"(?:rs\.?|inr|usd|\$|€|£|stipend|salary|amount|payment|fee|fine|penalty)",
            label_str, re.I))
        # Dates: always collect DDMMYYYY
        for d8 in re.findall(r"\d{8}", label_str):
            ts = _ddmmyyyy_to_timestamp(d8)
            if ts != "0":
                all_dates[f"DATE_{d8}"] = ts
        # Amounts: only from payment nodes or currency-labelled nodes
        for amt_raw in re.findall(r"\d{1,3}(?:,\d{3})+|\d{4,}", label_str):
            normalized = amt_raw.replace(",", "")
            if re.fullmatch(r"(?:19|20)\d{2}", normalized): continue  # year
            if re.fullmatch(r"\d{8}", normalized):           continue  # date
            if is_payment or has_currency:
                all_amounts[normalized] = all_amounts.get(normalized, 0) + 1
    # Always emit reporting deadline as a DATE_ constant even if no 8-digit in labels
    if has_deadline and reporting_deadline_ts not in all_dates.values():
        # Find the DDMMYYYY key that maps to reporting_deadline_ts
        for dn in date_nodes:
            lbl = dn.get("label", "").replace("-", "")
            d8m = re.search(r"(\d{2})(\d{2})(\d{4})", lbl)
            if d8m:
                key = f"DATE_{d8m.group(1)}{d8m.group(2)}{d8m.group(3)}"
                all_dates[key] = reporting_deadline_ts
                break
    if all_amounts or all_dates:
        value_declarations.append("    // ── Values extracted from e-contract ────────────────────────────")
        for amt in sorted(all_amounts.keys()):
            value_declarations.append(f"    uint256 public constant VALUE_{amt} = {amt};")
        for date_label, ts in sorted(all_dates.items()):
            value_declarations.append(f"    uint256 public constant {date_label} = {ts}; // Unix timestamp")
    if value_declarations:
        w(value_declarations + [""])

    # Build constructor — use party_pairs (same IDs as state vars and modifier)
    party_params = ", ".join([f"address _{pid}" for pid, _ in party_pairs])
    if party_params:
        party_params = ", " + party_params
    
    w(["    constructor(",
       f"        uint256 _totalValue,",
       f"        uint256 _penaltyBps,",
       f"        uint256 _penaltyPeriod,",
       f"        uint256 _liabilityCap{party_params},",
       f"        string memory _currency,",
       f"        uint256 _startDate,",
       f"        uint256 _endDate",
       "    ) {"])
    
    w(["        owner=msg.sender; isActive=true; deployedAt=block.timestamp;",
       "        totalContractValue=_totalValue; penaltyRateBps=_penaltyBps;",
       "        penaltyPeriod=_penaltyPeriod; liabilityCap=_liabilityCap;",
       "        require(_totalValue>0,'totalValue=0');",
       "        // penaltyBps=0 is valid for non-penalty contracts (internship, NDA, etc.)",
       "        currency=_currency; contractStartDate=_startDate; contractEndDate=_endDate;",
       "        require(_endDate>_startDate,'end<=start');",
       f'        jurisdiction="{jurisdiction}";'])
    
    # Assign party addresses — use party_pairs (in sync with state vars)
    for pid, _ in party_pairs:
        w([f"        {pid}=_{pid};"])
    
    # Add payment schedule initialization
    if init_payments:
        w(["        // Initialize payment schedules from e-contract:"])
        w(["        " + line for line in init_payments])
    
    w(["        emit ContractActivated(msg.sender,block.timestamp);",'    }',''])
    
    # Helper function for contract term validation
    w(["    function isContractTermExpired() external view returns(bool){",
       "        if(contractEndDate == 0) return false;",
       "        return block.timestamp > contractEndDate;",
       "    }",
       "",
       "    function getDaysRemaining() external view returns(int256){",
       "        if(contractEndDate == 0) return -1;",
       "        int256 remaining = int256(contractEndDate) - int256(block.timestamp);",
       "        return remaining > 0 ? remaining / 86400 : -1;",
       "    }",""])

    if obligations or tenant_obligations:
        # TerminationReason enum for conduct/progress-based termination clauses
        w(["    enum TerminationReason { CONDUCT_UNSATISFACTORY, PROGRESS_UNSATISFACTORY, MUTUAL, BREACH, DEADLINE_MISSED, OTHER }",
           ""])
        # Reporting/joining deadline: if a DATE_DEADLINE + TERMINATION both exist,
        # expose a reportingDeadline variable and enforce it in fulfillObligation.
        if has_deadline:
            w([f"    uint256 public reportingDeadline = {reporting_deadline_ts}; // Joining deadline (Unix ts)",
               "    bool   public reportingFulfilled;",
               "    event  DeadlineMissed(uint256 deadline, uint256 checkedAt);",
               ""])
        w(["    function addObligation(string calldata desc,address to,uint256 deadline,bool bestEfforts) external onlyOwner whenActive returns(uint256 id){",
           "        id=obligationCount++; obligationRecords[id]=ObligationRecord(desc,ObligationStatus.PENDING,to,deadline,bestEfforts);",
           "        emit ObligationAdded(id,desc,bestEfforts);","    }",
           "    function fulfillObligation(uint256 id) external whenActive onlyParty{",
           "        require(obligationRecords[id].status==ObligationStatus.PENDING,'Not pending');"])
        if has_deadline:
            w(["        // Enforce reporting deadline — if missed, mark as breached and terminate",
               "        if(reportingDeadline > 0 && !reportingFulfilled){",
               "            require(block.timestamp <= reportingDeadline,'Reporting deadline passed — appointment cancelled');",
               "            reportingFulfilled = true;",
               "        }"])
        w(["        obligationRecords[id].status=ObligationStatus.FULFILLED; emit ObligationFulfilled(id,msg.sender);","    }",
           "    function markObligationBreached(uint256 id) external onlyOwner{",
           "        obligationRecords[id].status=ObligationStatus.BREACHED; emit ObligationBreached(id);","    }",""])
        # Auto-cancellation: callable by anyone after deadline passes
        if has_deadline:
            w(["    /// @notice Cancel appointment if intern did not report by the deadline.",
               "    /// Mirrors clause: 'this order will be treated as cancelled'.",
               "    function checkAndCancelIfOverdue() external {",
               "        require(reportingDeadline > 0,'No deadline set');",
               "        require(!reportingFulfilled,'Already reported');",
               "        require(block.timestamp > reportingDeadline,'Deadline not yet passed');",
               "        isTerminated = true; isActive = false;",
               "        emit DeadlineMissed(reportingDeadline, block.timestamp);",
               "        emit ContractTerminated('Deadline missed — appointment cancelled', block.timestamp);",
               "    }",""])
    
    # Add tenant-specific obligation functions ONLY when tenant clauses exist
    if tenant_obligations:
        w(["    function addTenantObligation(string calldata desc,uint256 deadline,bool isSublet,bool isStructural,bool isResidentialOnly) external onlyOwner returns(uint256 id){",
           "        id=tenantObligationCount++; tenantObligations[id]=TenantObligation(desc,TenantObligationStatus.PENDING,deadline,isSublet,isStructural,isResidentialOnly);","    }",
           "    function acknowledgeTenantObligation(uint256 id) external whenActive onlyParty{",
           "        require(tenantObligations[id].status==TenantObligationStatus.PENDING,'Not pending');",
           "        tenantObligations[id].status=TenantObligationStatus.ACKNOWLEDGED;","    }",
           "    function markTenantObligationCompliant(uint256 id) external onlyOwner whenActive{",
           "        if(tenantObligations[id].deadline > 0) require(block.timestamp <= tenantObligations[id].deadline,'Deadline passed');",
           "        tenantObligations[id].status=TenantObligationStatus.COMPLIANT;","    }",
           "    function flagTenantObligationBreach(uint256 id) external onlyOwner{",
           "        tenantObligations[id].status=TenantObligationStatus.BREACHED;","    }",""])
    
    # Add utility billing functions if utilities are referenced
    if utilities and any(utilities.values()):
        w(["    function recordUtilityBilling(string calldata utilName,string calldata meterId,uint256 currentReading,uint256 amount,uint256 dueDate) external onlyOwner returns(uint256 idx){",
           "        idx=utilityBillings.length; utilityBillings.push(UtilityBilling(utilName,meterId,0,currentReading,amount,dueDate,false));","    }",
           "    function markUtilityPaid(uint256 idx) external onlyOwner{",
           "        utilityBillings[idx].paid=true; paidAmount+=utilityBillings[idx].amountDue;","    }",
           "    function updateUtilityReading(uint256 idx,uint256 newReading) external onlyOwner{",
           "        utilityBillings[idx].lastReading=utilityBillings[idx].currentReading;",
           "        utilityBillings[idx].currentReading=newReading;","    }",""])

    if conditions:
        w(["    function addCondition(string calldata desc,bool isCarveOut,bool isNested,uint256 parentId) external onlyOwner returns(uint256 id){",
           "        id=conditionCount++; conditionRecords[id]=ConditionRecord(desc,false,isCarveOut,isNested,parentId);","    }",
           "    function fulfillCondition(uint256 id) external onlyOwner whenActive{",
           "        if(conditionRecords[id].isNested) require(conditionRecords[conditionRecords[id].parentCondId].isFulfilled,'Parent not met');",
           "        conditionRecords[id].isFulfilled=true; emit ConditionFulfilled(id);","    }",""])

    if payments or milestones:
        w(["    function addPaymentSchedule(uint256 amount,uint256 dueDate,string calldata desc) external onlyOwner returns(uint256 idx){",
           "        require(amount>0,'amount=0'); idx=paymentSchedules.length;",
           "        paymentSchedules.push(PaymentSchedule(amount,dueDate,false,desc));","    }",
           "    function releaseScheduledPayment(uint256 idx,address payable recipient) external onlyOwner whenActive{",
           "        require(recipient!=address(0),'zero addr'); PaymentSchedule storage ps=paymentSchedules[idx];",
           "        require(!ps.released,'already paid'); require(address(this).balance>=ps.amount,'insufficient balance');",
           "        if(ps.dueDate>0) require(block.timestamp>=ps.dueDate,'not yet due');",
           "        // CHECKS-EFFECTS-INTERACTIONS: Update state BEFORE external call to prevent reentrancy",
           "        ps.released=true;",
           "        paidAmount+=ps.amount;",
           "        emit PaymentReleased(idx,recipient,ps.amount);",
           "        // Safe transfer using low-level call (post-EIP-1884)",
           "        (bool success,)=recipient.call{value:ps.amount}('');",
           "        require(success,'transfer failed');","    }",
           "    function proRataRelease(address payable recipient,uint256 numerator,uint256 denominator) external onlyOwner whenActive{",
           "        require(recipient!=address(0),'zero addr'); require(denominator>0,'denom=0');",
           "        require(numerator<=denominator,'num>denom'); // Prevent owner from extracting >100%",
           "        uint256 contractBalance=address(this).balance;",
           "        require(contractBalance>0,'no funds');",
           "        uint256 share=(contractBalance*numerator)/denominator;",
           "        require(share>0,'share=0');",
           "        // Update state before transfer",
           "        paidAmount+=share;",
           "        // Safe transfer using low-level call",
           "        (bool success,)=recipient.call{value:share}('');",
           "        require(success,'transfer failed');","    }",""])

    if milestones:
        w(["    function addMilestone(string calldata mName,uint256 dueDate,uint256 payIdx) external onlyOwner returns(uint256 idx){",
           "        require(bytes(mName).length>0,'empty name'); require(dueDate>0,'dueDate=0');",
           "        idx=milestones.length; milestones.push(Milestone(mName,dueDate,payIdx,MilestoneStatus.PENDING,false));","    }",
           "    function completeMilestone(uint256 idx) external whenActive onlyParty{",
           "        require(idx<milestones.length,'invalid id'); milestones[idx].status=MilestoneStatus.COMPLETED;",
           "        emit MilestoneCompleted(idx);","    }",
           "    function acceptMilestone(uint256 idx) external onlyOwner whenActive{",
           "        require(idx<milestones.length,'invalid id'); require(milestones[idx].status==MilestoneStatus.COMPLETED,'not done');",
           "        milestones[idx].acceptanceSigned=true; emit MilestoneAccepted(idx);","    }",""])

    if penalties:
        w(["    function applyPenalty(address party,uint256 periods,string calldata reason) external onlyOwner{",
           "        require(party!=address(0),'zero addr'); require(periods>0,'periods=0');",
           "        require(penaltyRateBps>0,'rate=0'); require(totalContractValue>0,'value=0');",
           "        uint256 base=(totalContractValue*penaltyRateBps*periods)/10000;",
           "        require(base>0,'penalty=0');",
           "        if(liabilityCap>0&&base>liabilityCap) base=liabilityCap;",
           "        accruedPenalties+=base; emit PenaltyApplied(party,base,reason);","    }",""])

    if disputes:
        w(["    function raiseDispute(string calldata desc) external onlyParty whenActive{",
           "        disputes.push(Dispute(block.timestamp,msg.sender,desc,DisputeStatus.RAISED,''));",
           "        emit DisputeRaised(disputes.length-1,msg.sender);","    }",
           "    function escalateToArbitration(uint256 idx) external onlyParty{",
           "        require(disputes[idx].status!=DisputeStatus.RESOLVED,'Done');",
           "        disputes[idx].status=DisputeStatus.ARBITRATION;","    }",
           "    function resolveDispute(uint256 idx,string calldata resolution) external onlyOwner{",
           "        disputes[idx].status=DisputeStatus.RESOLVED; disputes[idx].resolution=resolution;",
           "        emit DisputeResolved(idx);","    }",""])

    if confidential:
        w(["    function recordNDA(address disclosing,address receiving,uint256 dur) external onlyOwner returns(uint256 idx){",
           "        idx=ndaRecords.length; ndaRecords.push(ConfidentialityRecord(disclosing,receiving,block.timestamp,block.timestamp+dur,false));",
           "        emit NDAdded(disclosing,receiving,block.timestamp+dur);","    }",
           "    function recordNDABreach(uint256 idx) external onlyOwner{ ndaRecords[idx].breached=true; emit NDBreached(ndaRecords[idx].receivingParty); }",
           "    function assignIP(address party) external onlyOwner{ ipAssigned[party]=true; }",""])

    if force_maj:
        w(["    function activateForceMajeure(string calldata reason) external onlyOwner{",
           "        require(!forceMajeureActive,'already active'); forceMajeureActive=true;",
           "        emit ForceMajeureActivated(reason);","    }",
           "    function liftForceMajeure() external onlyOwner{",
           "        require(forceMajeureActive,'not active'); forceMajeureActive=false;",
           "        emit ForceMajeureLifted(block.timestamp);","    }",""])

    if terminations:
        w(["    function terminateContract(string calldata reason) external onlyOwner{",
           "        require(!isTerminated,'Done'); isTerminated=true; isActive=false;",
           "        emit ContractTerminated(reason,block.timestamp);","    }",
           "    function terminateForBreach(uint256 id) external onlyOwner{",
           "        require(obligationRecords[id].status==ObligationStatus.BREACHED,'Not breached');",
           "        isTerminated=true; isActive=false; emit ContractTerminated('Breach',block.timestamp);","    }",""])

    w(["    function getStatus() external view returns(bool,bool,bool,uint256){",
       "        return(isActive,isTerminated,forceMajeureActive,deployedAt);",'    }',
       "    function getContractBalance() external view returns(uint256){",
       "        return address(this).balance;","    }",
       "    // Private helper — avoids external CALL opcode used by this.getSurplusBalance()",
       "    function _calcSurplus() private view returns(uint256){",
       "        uint256 total=0;",
       "        for(uint256 i=0;i<paymentSchedules.length;i++){ if(paymentSchedules[i].released) total+=paymentSchedules[i].amount; }",
       "        return address(this).balance > total ? address(this).balance-total : 0;","    }",
       "    function getSurplusBalance() external view returns(uint256){ return _calcSurplus(); }",
       "    function withdrawSurplus(address payable recipient) external onlyOwner{",
       "        require(recipient!=address(0),'zero addr');",
       "        uint256 surplus=_calcSurplus();",
       "        require(surplus>0,'no surplus');",
       "        (bool success,)=recipient.call{value:surplus}('');",
       "        require(success,'transfer failed');","    }"])
    
    # Only add array length functions if the arrays are declared
    if payments or milestones:
        w(["    function paymentLen() external view returns(uint256){ return paymentSchedules.length; }"])
    if milestones:
        w(["    function milestoneLen() external view returns(uint256){ return milestones.length; }"])
    if disputes:
        w(["    function disputeLen()   external view returns(uint256){ return disputes.length; }"])
    
    w(["    receive() external payable {",
       "        require(isActive,'contract inactive');",
       "        emit FundsDeposited(msg.sender,msg.value,block.timestamp);","    }",
       "}"])
    # Post-process: Remove ALL assert(!(...)) lines.
    # The LLM refinement loop injects assert(!(X)); assert(!(!(X))); before every require(X).
    # These always revert BEFORE the require fires, making every transaction fail.
    _ASSERT_RE = re.compile(r"^\s*assert\s*\(", re.IGNORECASE)
    solidity_lines = [line for line in L if not _ASSERT_RE.match(line)]
    return "\n".join(solidity_lines)


# ── AST → KG (Algorithm 2) ───────────────────────────────────────────────────

def compile_solidity_to_ast(code: str) -> dict:
    try:
        import solcx
        solcx.install_solc(SOLC_VERSION, show_progress=False)
        solcx.set_solc_version(SOLC_VERSION)
        with tempfile.NamedTemporaryFile(suffix=".sol",mode="w",delete=False) as f:
            f.write(code); tmp=f.name
        result=solcx.compile_files([tmp],output_values=["ast"],solc_version=SOLC_VERSION)
        os.unlink(tmp)
        for _,v in result.items():
            if "ast" in v: return v["ast"]
    except Exception: pass
    return _fallback_ast_parse(code)

def _fallback_ast_parse(code: str) -> dict:
    ast={"nodeType":"SourceUnit","children":[]}
    cm=re.search(r"contract\s+(\w+)\s*\{",code)
    if not cm: return ast
    node={"nodeType":"ContractDefinition","name":cm.group(1),"children":[]}
    
    # Extract functions
    for fn in re.finditer(r"function\s+(\w+)\s*\(([^)]*)\)\s*(external|public|internal|private)?"
                          r"\s*(view|pure|payable)?\s*(?:returns\s*\([^)]*\))?\s*\{",code):
        node["children"].append({"nodeType":"FunctionDefinition","name":fn.group(1),
                                  "params":fn.group(2),"visibility":fn.group(3) or "public"})
    
    # Extract events
    for ev in re.finditer(r"event\s+(\w+)\s*\(([^)]*)\)",code):
        node["children"].append({"nodeType":"EventDefinition","name":ev.group(1)})
    
    # Extract state variables - match any public/private/internal variable declaration before first function/struct/enum
    # Pattern: type_name visibility? variableName;
    for sv in re.finditer(r"(?:address|uint\d*|bool|string|bytes\d*|mapping|[\w\.]+(?:\[\])*)\s+(?:public|private|internal)?\s*(\w+)\s*[;=]",code):
        # Make sure it's not inside a function or struct definition
        var_name = sv.group(1)
        # Skip common keywords that might match
        if var_name not in ["returns", "memory", "storage", "calldata", "view", "pure", "payable"]:
            node["children"].append({"nodeType":"StateVariableDeclaration","name":var_name})
    
    # Extract structs
    for st in re.finditer(r"struct\s+(\w+)\s*\{",code):
        node["children"].append({"nodeType":"StructDefinition","name":st.group(1)})
    
    # Extract enums
    for en in re.finditer(r"enum\s+(\w+)\s*\{",code):
        node["children"].append({"nodeType":"EnumDefinition","name":en.group(1)})
    ast["children"].append(node)
    return ast

def _walk_ast(node: dict, G: nx.DiGraph, parent_id: str = None, counter: list = None):
    if counter is None: counter=[0]
    if not isinstance(node,dict): return
    READABLE={"FunctionDefinition":"FUNCTION","EventDefinition":"EVENT",
              "StateVariableDeclaration":"VARIABLE","ContractDefinition":"CONTRACT",
              "ModifierDefinition":"MODIFIER","StructDefinition":"STRUCT","EnumDefinition":"ENUM"}
    ntype=node.get("nodeType","Unknown"); name=node.get("name","")
    nid=f"{ntype}_{name}_{counter[0]}"; counter[0]+=1
    G.add_node(nid,entity_type=READABLE.get(ntype,"AST_NODE"),label=name or ntype,
               params=node.get("params",""),visibility=node.get("visibility",""))
    if parent_id: G.add_edge(parent_id,nid,relation="CONTAINS")
    for child in node.get("children",[]): _walk_ast(child,G,nid,counter)
    if isinstance(node.get("nodes"),list):
        for child in node["nodes"]: _walk_ast(child,G,nid,counter)

def build_smartcontract_knowledge_graph(code: str) -> nx.DiGraph:
    G=nx.DiGraph(); _walk_ast(compile_solidity_to_ast(code),G)
    for fn in re.finditer(r"function\s+(\w+)\s*\(([^)]*)\)",code):
        nid=f"fn_{fn.group(1)}"
        if not G.has_node(nid): G.add_node(nid,entity_type="FUNCTION",label=fn.group(1),params=fn.group(2))
    for ev in re.finditer(r"event\s+(\w+)",code):
        nid=f"ev_{ev.group(1)}"
        if not G.has_node(nid): G.add_node(nid,entity_type="EVENT",label=ev.group(1))
    for st in re.finditer(r"struct\s+(\w+)",code):
        nid=f"st_{st.group(1)}"
        if not G.has_node(nid): G.add_node(nid,entity_type="STRUCT",label=st.group(1))
    return G

def graph_to_dict(G: nx.DiGraph) -> dict:
    return {"nodes":[{"id":n,**G.nodes[n]} for n in G.nodes],
            "edges":[{"source":u,"target":v,**G.edges[u,v]} for u,v in G.edges]}

def render_graph_base64(G: nx.DiGraph, title: str = "Smart Contract KG") -> str:
    from core.econtract_kg import render_graph_base64 as _r
    return _r(G,title)