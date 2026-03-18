"""
Algorithm 2: Smart Contract Generation & KG extraction (AST-driven).
Handles: arbitration, milestones, payment schedules, pro-rata, conditions,
carve-outs, confidentiality, force majeure, IP, reasonable-efforts clauses.
pragma solidity ^0.8.16 (pinned).
"""
import re, os, tempfile
import networkx as nx

SOLC_VERSION = "0.8.16"

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

def kg_to_solidity(kg: dict, contract_name: str = "EContract") -> str:
    nodes = kg.get("nodes", [])
    name  = re.sub(r"[^A-Za-z0-9]", "", contract_name) or "EContract"
    def by(*t): return [n for n in nodes if n.get("entity_type") in t]

    parties=by("PARTY","ORG","PERSON"); obligations=by("OBLIGATION")
    payments=by("PAYMENT","MONEY"); milestones=by("MILESTONE")
    conditions=by("CONDITION"); terminations=by("TERMINATION")
    penalties=by("PENALTY_REMEDY","PENALTY"); disputes=by("DISPUTE_ARBITRATION")
    confidential=by("CONFIDENTIALITY_IP"); force_maj=by("FORCE_MAJEURE")
    
    # Also check for entity type presence (even if 0 nodes) to ensure all types are covered
    all_entity_types = {n.get("entity_type", "") for n in nodes if n.get("entity_type")}
    has_obligations = obligations or "OBLIGATION" in all_entity_types
    has_conditions = conditions or "CONDITION" in all_entity_types
    has_terminations = terminations or "TERMINATION" in all_entity_types
    has_disputes = disputes or "DISPUTE_ARBITRATION" in all_entity_types
    has_confidential = confidential or "CONFIDENTIALITY_IP" in all_entity_types
    has_force_maj = force_maj or "FORCE_MAJEURE" in all_entity_types
    has_payments = (payments or milestones) or ("PAYMENT" in all_entity_types or "MILESTONE" in all_entity_types)
    has_penalties = penalties or "PENALTY_REMEDY" in all_entity_types

    L=[]; w=L.extend
    w(["// SPDX-License-Identifier: MIT","pragma solidity ^0.8.16;","",
       f"/// @title {name} — Auto-generated from E-Contract KG",
       f"contract {name} {{","",
       "    address public owner; bool public isActive; bool public isTerminated;",
       "    bool public forceMajeureActive; uint256 public deployedAt;",""])

    seen_p: set = set()
    for i,p in enumerate(parties[:6]):
        pid=_safe_id(p["id"]); pid = f"{pid}_{i}" if pid in seen_p else pid; seen_p.add(pid)
        w([f"    address public {pid};"])
    w([""])

    if has_payments:
        w(["    struct PaymentSchedule { uint256 amount; uint256 dueDate; bool released; string description; }",
           "    PaymentSchedule[] public paymentSchedules;",
           "    uint256 public totalContractValue; uint256 public paidAmount;",""])
    if has_payments or milestones:
        w(["    enum MilestoneStatus { PENDING, IN_PROGRESS, COMPLETED, DISPUTED }",
           "    struct Milestone { string name; uint256 dueDate; uint256 paymentIndex; MilestoneStatus status; bool acceptanceSigned; }",
           "    Milestone[] public milestones;",""])
    if has_obligations:
        w(["    enum ObligationStatus { PENDING, FULFILLED, BREACHED, WAIVED }",
           "    struct ObligationRecord { string description; ObligationStatus status; address assignedTo; uint256 deadline; bool bestEfforts; }",
           "    mapping(uint256 => ObligationRecord) public obligationRecords; uint256 public obligationCount;",""])
    if has_conditions:
        w(["    struct ConditionRecord { string description; bool isFulfilled; bool isCarveOut; bool isNested; uint256 parentCondId; }",
           "    mapping(uint256 => ConditionRecord) public conditionRecords; uint256 public conditionCount;",""])
    if has_penalties:
        w(["    uint256 public penaltyRateBps; uint256 public penaltyPeriod; uint256 public liabilityCap; uint256 public accruedPenalties;",""])
    if has_disputes:
        arb="ICC"; gl="English Law"
        for d in disputes:
            if re.search(r"\bAAA\b",d["id"],re.I): arb="AAA"
            elif re.search(r"\bUNCITRAL\b",d["id"],re.I): arb="UNCITRAL"
            if re.search(r"Delaware",d["id"],re.I): gl="Delaware Law"
            elif re.search(r"New York",d["id"],re.I): gl="New York Law"
        w([f'    string public constant GOVERNING_LAW = "{gl}";',
           f'    string public constant ARBITRATION_BODY = "{arb}";',
           "    enum DisputeStatus { NONE, RAISED, MEDIATION, ARBITRATION, RESOLVED }",
           "    struct Dispute { uint256 raisedAt; address raisedBy; string description; DisputeStatus status; string resolution; }",
           "    Dispute[] public disputes;",""])
    if has_confidential:
        w(["    struct ConfidentialityRecord { address disclosingParty; address receivingParty; uint256 disclosedAt; uint256 expiresAt; bool breached; }",
           "    ConfidentialityRecord[] public ndaRecords; mapping(address => bool) public ipAssigned;",""])

    # Events
    w(["    event ContractActivated(address indexed by, uint256 at);",
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

    # Modifiers
    cond=" || ".join(f"msg.sender=={_safe_id(p['id'])}" for p in parties[:6] if _safe_id(p["id"])) or "msg.sender==owner"
    w(["    modifier onlyOwner() { require(msg.sender==owner,'Not owner'); _; }",
       "    modifier whenActive() { require(isActive&&!isTerminated,'Not active'); require(!forceMajeureActive,'Force majeure'); _; }",
       f"    modifier onlyParty() {{ require({cond}||msg.sender==owner,'Not a party'); _; }}",""])

    # Constructor + extract ALL numeric values from KG for embedding
    # Extract amounts and dates from ALL nodes (not just payment nodes)
    all_amounts = {}  # amount -> count
    all_dates = {}    # date -> count
    date_nodes = []   # List of DATE_DEADLINE nodes to create variables for
    
    for node in nodes:
        node_id = node.get("id", "")
        label = node.get("label", "")
        entity_type = node.get("entity_type", "")
        
        if not label:
            continue
        
        # Track DATE_DEADLINE nodes specifically
        if entity_type == "DATE_DEADLINE":
            date_nodes.append((node_id, label))
        
        label_str = str(label)
        
        # Extract 4+ digit sequences (amounts): "10000", "1,000", etc.
        amounts = re.findall(r"\d{1,3}(?:,\d{3})+|\d{4,}", label_str)
        for amt in amounts:
            normalized = amt.replace(",", "")
            # Don't extract as amounts if it's clearly a year or date component
            if len(normalized) <= 4 or (len(normalized) == 4 and normalized.startswith("20")):
                continue
            all_amounts[normalized] = all_amounts.get(normalized, 0) + 1
        
        # Extract 8-digit sequences (dates like DDMMYYYY or YYYYMMDD)
        dates = re.findall(r"\d{8}", label_str)
        for dt in dates:
            all_dates[dt] = all_dates.get(dt, 0) + 1
        
        # Extract dashed dates (YYYY-MM-DD or DD/MM/YYYY, etc.)
        if entity_type == "DATE_DEADLINE":
            # Extract YYYY-MM-DD format
            dashed_dates = re.findall(r"(\d{4})-(\d{2})-(\d{2})", label_str)
            for y, m, d in dashed_dates:
                # Convert to YYYYMMDD
                dt = f"{y}{m}{d}"
                all_dates[dt] = all_dates.get(dt, 0) + 1
            
            # Also try from node_id
            dashed_id = re.findall(r"(\d{4})-(\d{2})-(\d{2})", node_id)
            for y, m, d in dashed_id:
                dt = f"{y}{m}{d}"
                all_dates[dt] = all_dates.get(dt, 0) + 1
    
    # Add state variable declarations for all unique amounts/dates at the top (after events/modifiers, before functions)
    value_declarations = []
    value_var_count = 0
    if all_amounts or all_dates or date_nodes:
        value_declarations.append("    // ── Values extracted from e-contract ────────────────────────────")
    
    # Create explicit variables for all amounts
    if all_amounts:
        for amt in sorted(all_amounts.keys()):
            safe_amt_label = f"amount{amt}"[:32]
            value_declarations.append(f"    uint256 public {safe_amt_label} = {amt};")
            value_var_count += 1
    
    # Create explicit variables for all dates (from labels)
    if all_dates:
        for dt in sorted(all_dates.keys()):
            safe_date_label = f"deadline{dt}"[:32]
            value_declarations.append(f"    uint256 public {safe_date_label} = {dt};")
            value_var_count += 1
    
    # Create explicit variables for each date node (ensures all date nodes are covered)
    seen_date_vars = set()
    if date_nodes:
        for node_id, label in date_nodes:
            # Try to extract date from node ID first (YYYY-MM-DD format)
            date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", node_id)
            if date_match:
                y, m, d = date_match.groups()
                dt = f"{y}{m}{d}"
                var_name = f"deadline{dt}"[:32]
                if var_name not in seen_date_vars:
                    value_declarations.append(f"    uint256 public {var_name} = {dt};")
                    seen_date_vars.add(var_name)
                    value_var_count += 1
            else:
                # Try extracting from label
                label_date = re.search(r"(\d{4})-(\d{2})-(\d{2})", label)
                if label_date:
                    y, m, d = label_date.groups()
                    dt = f"{y}{m}{d}"
                    var_name = f"deadline{dt}"[:32]
                    if var_name not in seen_date_vars:
                        value_declarations.append(f"    uint256 public {var_name} = {dt};")
                        seen_date_vars.add(var_name)
                        value_var_count += 1
    
    # Constructor with enhanced initialization
    init_payments = []
    for p in payments[:3]:  # Process up to 3 payment entities
        label = p.get("label", "")
        # Extract amount: look for patterns like "10000", "10,000", etc.
        amt_match = re.search(r"\d{1,3}(?:,\d{3})+|\d{4,}", label)
        if amt_match:
            amount = _to_uint(amt_match.group())
            # Extract date: look for 8-digit dates
            date_match = re.search(r"\d{8}", label)
            due_date = date_match.group() if date_match else "0"
            if amount != "0":
                safe_label = label.replace('"', '').replace("'", "")[:30]
                init_payments.append(f'paymentSchedules.push(PaymentSchedule({amount},{due_date},false,"{safe_label}"));')
    
    # Only generate constructor if there are penalties or payments/milestones
    if has_penalties or has_payments:
        w(["    constructor(uint256 _totalValue,uint256 _penaltyBps,uint256 _penaltyPeriod,uint256 _liabilityCap) {",
           "        owner=msg.sender; isActive=true; deployedAt=block.timestamp;",
           "        totalContractValue=_totalValue; penaltyRateBps=_penaltyBps;",
           "        penaltyPeriod=_penaltyPeriod; liabilityCap=_liabilityCap;"])
        
        # Add payment schedule initialization
        if init_payments:
            w(["        // Initialize payment schedules from e-contract:"])
            w(["        " + line for line in init_payments])
        
        w(["        emit ContractActivated(msg.sender,block.timestamp);",'    }',''])
    
    # Insert value declarations before first function
    w(value_declarations + [""])

    if has_obligations:
        w(["    function addObligation(string calldata desc,address to,uint256 deadline,bool bestEfforts) external onlyOwner whenActive returns(uint256 id){",
           "        id=obligationCount++; obligationRecords[id]=ObligationRecord(desc,ObligationStatus.PENDING,to,deadline,bestEfforts);",
           "        emit ObligationAdded(id,desc,bestEfforts);","    }",
           "    function fulfillObligation(uint256 id) external whenActive onlyParty{",
           "        require(obligationRecords[id].status==ObligationStatus.PENDING,'Not pending');",
           "        obligationRecords[id].status=ObligationStatus.FULFILLED; emit ObligationFulfilled(id,msg.sender);","    }",
           "    function markObligationBreached(uint256 id) external onlyOwner{",
           "        obligationRecords[id].status=ObligationStatus.BREACHED; emit ObligationBreached(id);","    }",""])

    if has_conditions:
        w(["    function addCondition(string calldata desc,bool isCarveOut,bool isNested,uint256 parentId) external onlyOwner returns(uint256 id){",
           "        id=conditionCount++; conditionRecords[id]=ConditionRecord(desc,false,isCarveOut,isNested,parentId);","    }",
           "    function fulfillCondition(uint256 id) external onlyOwner whenActive{",
           "        if(conditionRecords[id].isNested) require(conditionRecords[conditionRecords[id].parentCondId].isFulfilled,'Parent not met');",
           "        conditionRecords[id].isFulfilled=true; emit ConditionFulfilled(id);","    }",""])

    if has_payments:
        w(["    function addPaymentSchedule(uint256 amount,uint256 dueDate,string calldata desc) external onlyOwner returns(uint256 idx){",
           "        idx=paymentSchedules.length; paymentSchedules.push(PaymentSchedule(amount,dueDate,false,desc));","    }",
           "    function releaseScheduledPayment(uint256 idx,address payable recipient) external payable onlyOwner whenActive{",
           "        PaymentSchedule storage ps=paymentSchedules[idx];",
           "        require(!ps.released,'Done'); require(msg.value>=ps.amount,'Low');",
           "        if(ps.dueDate>0) require(block.timestamp>=ps.dueDate,'Not due');",
           "        ps.released=true; paidAmount+=ps.amount; recipient.transfer(ps.amount);",
           "        emit PaymentReleased(idx,recipient,ps.amount);","    }",
           "    function proRataRelease(address payable recipient,uint256 numerator,uint256 denominator) external payable onlyOwner whenActive{",
           "        require(denominator>0,'Zero denom'); uint256 share=(msg.value*numerator)/denominator;",
           "        require(share>0,'Zero share'); recipient.transfer(share);","    }",""])

    if milestones:
        w(["    function addMilestone(string calldata mName,uint256 dueDate,uint256 payIdx) external onlyOwner returns(uint256 idx){",
           "        idx=milestones.length; milestones.push(Milestone(mName,dueDate,payIdx,MilestoneStatus.PENDING,false));","    }",
           "    function completeMilestone(uint256 idx) external whenActive onlyParty{",
           "        milestones[idx].status=MilestoneStatus.COMPLETED; emit MilestoneCompleted(idx);","    }",
           "    function acceptMilestone(uint256 idx) external onlyOwner whenActive{",
           "        require(milestones[idx].status==MilestoneStatus.COMPLETED,'Not done');",
           "        milestones[idx].acceptanceSigned=true; emit MilestoneAccepted(idx);","    }",""])

    if has_penalties:
        w(["    function applyPenalty(address party,uint256 periods,string calldata reason) external onlyOwner{",
           "        uint256 base=(totalContractValue*penaltyRateBps*periods)/10000;",
           "        if(liabilityCap>0&&base>liabilityCap) base=liabilityCap;",
           "        accruedPenalties+=base; emit PenaltyApplied(party,base,reason);","    }",""])

    if has_disputes:
        w(["    function raiseDispute(string calldata desc) external onlyParty whenActive{",
           "        disputes.push(Dispute(block.timestamp,msg.sender,desc,DisputeStatus.RAISED,''));",
           "        emit DisputeRaised(disputes.length-1,msg.sender);","    }",
           "    function escalateToArbitration(uint256 idx) external onlyParty{",
           "        require(disputes[idx].status!=DisputeStatus.RESOLVED,'Done');",
           "        disputes[idx].status=DisputeStatus.ARBITRATION;","    }",
           "    function resolveDispute(uint256 idx,string calldata resolution) external onlyOwner{",
           "        disputes[idx].status=DisputeStatus.RESOLVED; disputes[idx].resolution=resolution;",
           "        emit DisputeResolved(idx);","    }",""])

    if has_confidential:
        w(["    function recordNDA(address disclosing,address receiving,uint256 dur) external onlyOwner returns(uint256 idx){",
           "        idx=ndaRecords.length; ndaRecords.push(ConfidentialityRecord(disclosing,receiving,block.timestamp,block.timestamp+dur,false));",
           "        emit NDAdded(disclosing,receiving,block.timestamp+dur);","    }",
           "    function recordNDABreach(uint256 idx) external onlyOwner{ ndaRecords[idx].breached=true; emit NDBreached(ndaRecords[idx].receivingParty); }",
           "    function assignIP(address party) external onlyOwner{ ipAssigned[party]=true; }",""])

    if has_force_maj:
        w(["    function activateForceMajeure(string calldata reason) external onlyOwner{",
           "        forceMajeureActive=true; emit ForceMajeureActivated(reason);","    }",
           "    function liftForceMajeure() external onlyOwner{ forceMajeureActive=false; emit ForceMajeureLifted(block.timestamp); }",""])

    if has_terminations:
        w(["    function terminateContract(string calldata reason) external onlyOwner{",
           "        require(!isTerminated,'Done'); isTerminated=true; isActive=false;",
           "        emit ContractTerminated(reason,block.timestamp);","    }",
           "    function terminateForBreach(uint256 id) external onlyOwner{",
           "        require(obligationRecords[id].status==ObligationStatus.BREACHED,'Not breached');",
           "        isTerminated=true; isActive=false; emit ContractTerminated('Breach',block.timestamp);","    }",""])

    w(["    function getStatus() external view returns(bool,bool,bool,uint256){",
       "        return(isActive,isTerminated,forceMajeureActive,deployedAt);",'    }'])
    
    # Only add array length functions if the arrays are declared
    if has_payments:
        w(["    function paymentLen() external view returns(uint256){ return paymentSchedules.length; }"])
    if milestones:
        w(["    function milestoneLen() external view returns(uint256){ return milestones.length; }"])
    if has_disputes:
        w(["    function disputeLen()   external view returns(uint256){ return disputes.length; }"])
    
    w(["    receive() external payable {}","}"])
    return "\n".join(L)


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
