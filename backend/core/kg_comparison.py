"""
Algorithm 3: KG Comparison — 3-tier node similarity.
Algorithm 4: LLM Refinement — ADDITIVE PATCH architecture.

Key design (mirrors the prompt in the spec):
  - LLM never rewrites the full contract — only outputs ADDITIONS
  - Achieved accuracy is locked in each iteration ("bank" technique)
  - Each prompt only targets the REMAINING gap, not the full problem
  - Best-score checkpoint: if a new iteration scores LOWER, roll back to checkpoint
  - Patches are merged by injecting code before the final closing brace

Additive loop:
  iter 0: base score = 72.7%  → bank 72.7%, gap = 27.3%
  iter 1: LLM adds missing parts → new score = 78%  → bank 78%, gap = 22%
  iter 2: LLM adds more         → new score = 83%  → bank 83%, gap = 17%
  ...
  If LLM produces a worse score → discard, keep banked best, retry with tighter prompt
"""
import re, json
from difflib import SequenceMatcher
from typing import Tuple
import networkx as nx
import requests

OLLAMA_URL     = "http://localhost:11434/api/generate"
OLLAMA_MODEL   = "qwen2.5:7b"
MAX_ITERATIONS = 5

# ── Normalisation helpers ─────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())

def _words(s: str) -> set:
    """Split camelCase + extract words: 'releasePayment' → {'release','payment'}"""
    split = re.sub(r"([A-Z])", r" \1", s)
    return set(w for w in re.findall(r"[a-z]{3,}", split.lower()))

def _label_set_short(G: nx.DiGraph) -> set:
    return {_norm(G.nodes[n].get("label", n))
            for n in G.nodes if len(G.nodes[n].get("label", n)) <= 50}

# ── Type mapping ──────────────────────────────────────────────────────────────

EC_TO_SC_TYPES = {
    "PARTY":               {"VARIABLE", "CONTRACT"},
    "OBLIGATION":          {"FUNCTION", "EVENT", "STRUCT", "ENUM"},
    "CONDITION":           {"FUNCTION", "MODIFIER", "STRUCT"},
    "PAYMENT":             {"FUNCTION", "STRUCT", "VARIABLE"},
    "DATE_DEADLINE":       {"VARIABLE"},
    "TERMINATION":         {"FUNCTION"},
    "PENALTY_REMEDY":      {"FUNCTION", "VARIABLE"},
    "DISPUTE_ARBITRATION": {"FUNCTION", "STRUCT", "ENUM"},
    "CONFIDENTIALITY_IP":  {"FUNCTION", "STRUCT"},
    "FORCE_MAJEURE":       {"MODIFIER", "FUNCTION"},
    "MILESTONE":           {"FUNCTION", "STRUCT", "ENUM"},
}

SC_TO_EC_TYPES: dict = {}
for _ec, _sc_set in EC_TO_SC_TYPES.items():
    for _sc in _sc_set:
        SC_TO_EC_TYPES.setdefault(_sc, set()).add(_ec)

EC_TO_SC_SEMANTIC = {
    "FUNCTION":  {"OBLIGATION","TERMINATION","CONDITION","PENALTY_REMEDY",
                  "DISPUTE_ARBITRATION","CONFIDENTIALITY_IP","FORCE_MAJEURE","MILESTONE","PAYMENT"},
    "EVENT":     {"OBLIGATION","PENALTY_REMEDY","TERMINATION","DISPUTE_ARBITRATION",
                  "CONFIDENTIALITY_IP","FORCE_MAJEURE","MILESTONE","PAYMENT"},
    "STRUCT":    {"OBLIGATION","CONDITION","PAYMENT","MILESTONE","DISPUTE_ARBITRATION","CONFIDENTIALITY_IP"},
    "VARIABLE":  {"PARTY","PAYMENT","PENALTY_REMEDY","DATE_DEADLINE"},
    "CONTRACT":  {"PARTY"},
    "ENUM":      {"OBLIGATION","MILESTONE","DISPUTE_ARBITRATION"},
    "MODIFIER":  {"CONDITION","FORCE_MAJEURE"},
}

IMPORTANT_TYPES = {
    "PARTY","OBLIGATION","PAYMENT","CONDITION","TERMINATION",
    "PENALTY_REMEDY","DISPUTE_ARBITRATION","CONFIDENTIALITY_IP",
    "FORCE_MAJEURE","MILESTONE","DATE_DEADLINE",
}

EC_EDGE_TO_SC = {
    "PAYS":           {"releasePayment","releaseScheduledPayment","CONTAINS"},
    "RECEIVES":       {"releasePayment","CONTAINS"},
    "REPORTS_TO":     {"CONTAINS","fulfillObligation"},
    "PROVIDES":       {"fulfillObligation","CONTAINS"},
    "DELIVERS":       {"completeMilestone","fulfillObligation"},
    "TERMINATES":     {"terminateContract","terminateForBreach","CONTAINS"},
    "ASSIGNS":        {"assignIP","CONTAINS"},
    "COMPLETES":      {"completeMilestone","CONTAINS"},
    "FULFILLS":       {"fulfillObligation","fulfillCondition"},
    "SUBMITS":        {"fulfillObligation","CONTAINS"},
    "NOTIFIES":       {"CONTAINS"},
    "APPOINTS":       {"CONTAINS"},
    "ENGAGES":        {"CONTAINS"},
    "EMPLOYS":        {"CONTAINS"},
    "SIGNS":          {"CONTAINS"},
    "CANCELS":        {"terminateContract","CONTAINS"},
    "BREACHES":       {"markObligationBreached","terminateForBreach"},
    "PENALIZES":      {"applyPenalty"},
    "HAS_OBLIGATION": {"addObligation","CONTAINS"},
    "CO_OCCURS_WITH": {"CONTAINS"},
}

# ── Algorithm 3: node similarity (3 tiers) ────────────────────────────────────

def _tier_a_type_similarity(G_e, G_s):
    sc_ast_types = {G_s.nodes[n].get("entity_type","").upper() for n in G_s.nodes}
    covered_ec: set = set()
    for sc_t in sc_ast_types:
        covered_ec.update(SC_TO_EC_TYPES.get(sc_t, set()))

    matched, unmatched = [], []
    for n in G_e.nodes:
        label  = G_e.nodes[n].get("label", n)
        ec_typ = G_e.nodes[n].get("entity_type", "")
        if ec_typ in covered_ec:
            matched.append(_norm(label))
        else:
            unmatched.append(_norm(label))

    total = len(matched) + len(unmatched)
    pct   = round(len(matched) / total * 100, 2) if total else 100.0
    return pct, matched, unmatched

def _tier_b_label_similarity(G_e, G_s) -> float:
    sc_all_words: set = set()
    for n in G_s.nodes:
        sc_all_words |= _words(G_s.nodes[n].get("label", n))
        sc_all_words |= _words(str(n))

    matched = total = 0
    for n in G_e.nodes:
        label    = G_e.nodes[n].get("label", n)
        ec_words = _words(label)
        if not ec_words:
            continue
        total += 1
        if any(w in sc_all_words for w in ec_words if len(w) >= 4):
            matched += 1
        elif re.search(r"\d{4,}", label):
            nums    = re.findall(r"\d{4,}", label)
            sc_text = " ".join(str(G_s.nodes[n].get("label", n)) for n in G_s.nodes)
            if any(num in sc_text for num in nums):
                matched += 1
    return round(matched / total * 100, 2) if total else 100.0

def _tier_c_value_coverage(G_e, G_s) -> float:
    sc_text      = " ".join(str(n) + " " + str(G_s.nodes[n].get("label","")) for n in G_s.nodes)
    concrete_ec  = []
    for n in G_e.nodes:
        label  = G_e.nodes[n].get("label", n)
        ec_typ = G_e.nodes[n].get("entity_type", "")
        if ec_typ in ("PAYMENT", "DATE_DEADLINE"):
            nums = re.findall(r"\d{4,}", label)
            if nums:
                concrete_ec.extend(nums)
    if not concrete_ec:
        return 100.0
    covered = sum(1 for v in concrete_ec if v in sc_text)
    return round(covered / len(concrete_ec) * 100, 2)

def _node_similarity(G_e, G_s):
    tier_a, matched, unmatched = _tier_a_type_similarity(G_e, G_s)
    tier_b = _tier_b_label_similarity(G_e, G_s)
    tier_c = _tier_c_value_coverage(G_e, G_s)
    score  = round(0.50 * tier_a + 0.30 * tier_b + 0.20 * tier_c, 2)
    return score, matched, unmatched, {"tier_a": tier_a, "tier_b": tier_b, "tier_c": tier_c}

def _edge_similarity(G_e, G_s) -> float:
    ec_rels  = {G_e.edges[e].get("relation","") for e in G_e.edges}
    sc_rels  = {G_s.edges[e].get("relation","") for e in G_s.edges}
    valid_ec = [r for r in ec_rels if r]
    if not valid_ec:
        return 100.0
    covered = 0
    for ec_rel in valid_ec:
        sc_equiv = EC_EDGE_TO_SC.get(ec_rel, {ec_rel})
        if sc_rels & sc_equiv:
            covered += 1
        elif any(_norm(ec_rel) == _norm(sr) for sr in sc_rels):
            covered += 1
    return round(covered / len(valid_ec) * 100, 2)

def _type_coverage(G_e, G_s) -> dict:
    ec_types = {G_e.nodes[n].get("entity_type") for n in G_e.nodes}
    sc_types = {G_s.nodes[n].get("entity_type","").upper() for n in G_s.nodes}
    covered_sc: set = set()
    for sc_t in sc_types:
        covered_sc.update(EC_TO_SC_SEMANTIC.get(sc_t, {sc_t}))
    required = ec_types & IMPORTANT_TYPES
    covered  = required & covered_sc
    missing  = required - covered_sc
    return {
        "ec_types":          sorted(ec_types),
        "sc_types":          sorted(sc_types),
        "covered_semantic":  sorted(covered),
        "missing_semantic":  sorted(missing),
        "type_coverage_pct": round(len(covered)/len(required)*100, 2) if required else 100.0,
    }

def compare_knowledge_graphs(G_e: nx.DiGraph, G_s: nx.DiGraph) -> dict:
    node_score, matched, unmatched, tiers = _node_similarity(G_e, G_s)
    edge_sim = _edge_similarity(G_e, G_s)
    type_cov = _type_coverage(G_e, G_s)
    accuracy = round(0.40 * node_score + 0.25 * edge_sim + 0.35 * type_cov["type_coverage_pct"], 2)
    return {
        "accuracy":        accuracy,
        "node_similarity": node_score,
        "node_tiers":      tiers,
        "edge_similarity": edge_sim,
        "type_coverage":   type_cov,
        "matched_nodes":   matched,
        "unmatched_nodes": unmatched,
        "ec_node_count":   G_e.number_of_nodes(),
        "sc_node_count":   G_s.number_of_nodes(),
        "ec_edge_count":   G_e.number_of_edges(),
        "sc_edge_count":   G_s.number_of_edges(),
        "is_valid":        accuracy >= 100.0,
    }

# ── Patch merger ──────────────────────────────────────────────────────────────

def _merge_patch(base_code: str, patch: str) -> str:
    """
    Inject patch Solidity code into base_code just before the final closing brace.
    Handles: standalone function/struct/event/variable blocks.
    Duplicate function guard: skip patch if its first function name already exists.
    """
    if not patch or not patch.strip():
        return base_code

    # Strip any stray pragma/import/contract wrapper the LLM may have output
    patch = re.sub(r"//\s*SPDX[^\n]*\n", "", patch)
    patch = re.sub(r"pragma solidity[^\n]*\n", "", patch)
    patch = re.sub(r"import\s+[^\n]+\n", "", patch)
    # Strip outer contract { ... } wrapper if present
    contract_body = re.search(
        r"contract\s+\w+[^{]*\{(.*)\}\s*$", patch, re.DOTALL | re.IGNORECASE
    )
    if contract_body:
        patch = contract_body.group(1).strip()

    patch = patch.strip()
    if not patch:
        return base_code

    # Duplicate guard: extract first function/struct name from patch
    first_name = re.search(r"\b(?:function|struct|event|modifier)\s+(\w+)", patch)
    if first_name and first_name.group(1) in base_code:
        return base_code  # already present, skip

    # Find the last closing brace of the contract
    last_brace = base_code.rfind("}")
    if last_brace == -1:
        return base_code + "\n" + patch

    injected = (
        base_code[:last_brace].rstrip()
        + "\n\n    // ── Patch ──────────────────────────────────────────\n"
        + "    " + patch.replace("\n", "\n    ")
        + "\n}"
    )
    return injected


def _extract_patch_only(response_text: str) -> str:
    """
    Extract ONLY the patch fragment from LLM output.
    Accepts: ```solidity...``` block, or raw Solidity starting with function/struct/event/uint/address.
    """
    # Prefer ```solidity block
    m = re.search(r"```solidity\s*(.*?)```", response_text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Fallback: take lines from the first function/struct/event/variable declaration
    lines = response_text.split("\n")
    start = None
    for i, line in enumerate(lines):
        if re.match(r"\s*(?:function|struct|event|modifier|uint|address|bool|mapping|enum)\b",
                    line):
            start = i
            break
    if start is not None:
        return "\n".join(lines[start:]).strip()

    return ""

# ── Patch-focused prompts ─────────────────────────────────────────────────────

TYPE_GUIDANCE = {
    "DISPUTE_ARBITRATION":
        "function raiseDispute(string calldata reason) external whenActive { ... }\n"
        "function resolveDispute(uint256 id) external onlyOwner { ... }\n"
        "struct Dispute { string reason; bool resolved; address raisedBy; }",
    "FORCE_MAJEURE":
        "bool public forceMajeureActive;\n"
        "function activateForceMajeure(string calldata reason) external onlyOwner { forceMajeureActive=true; emit ForceMajeureActivated(reason); }\n"
        "function liftForceMajeure() external onlyOwner { forceMajeureActive=false; emit ForceMajeureLifted(block.timestamp); }",
    "CONFIDENTIALITY_IP":
        "struct ConfidentialityRecord { address discloser; address recipient; uint256 expiry; bool breached; }\n"
        "mapping(uint256=>ConfidentialityRecord) public ndaRecords; uint256 public ndaCount;\n"
        "function recordNDA(address discloser, address recipient, uint256 expiry) external onlyOwner { ... }\n"
        "function recordNDABreach(uint256 id) external onlyOwner { ... }",
    "MILESTONE":
        "struct Milestone { string description; bool completed; bool accepted; }\n"
        "mapping(uint256=>Milestone) public milestones; uint256 public milestoneCount;\n"
        "function addMilestone(string calldata desc) external onlyOwner returns(uint256 id) { ... }\n"
        "function completeMilestone(uint256 id) external whenActive { ... }\n"
        "function acceptMilestone(uint256 id) external onlyOwner { ... }",
    "PAYMENT":
        "uint256 public stipendAmount;\n"
        "function releaseStipend(address payable recipient) external onlyOwner whenActive {\n"
        "    require(address(this).balance >= stipendAmount, 'Insufficient balance');\n"
        "    recipient.transfer(stipendAmount);\n"
        "    emit PaymentReleased(0, recipient, stipendAmount);\n}",
    "PENALTY_REMEDY":
        "uint256 public penaltyRateBps; uint256 public accruedPenalties; uint256 public liabilityCap;\n"
        "function applyPenalty(address party, uint256 amount, string calldata reason) external onlyOwner {\n"
        "    uint256 pen = (amount * penaltyRateBps) / 10000;\n"
        "    if(liabilityCap > 0) pen = pen > liabilityCap ? liabilityCap : pen;\n"
        "    accruedPenalties += pen;\n"
        "    emit PenaltyApplied(party, pen, reason);\n}",
    "CONDITION":
        "struct ConditionRecord { string description; bool isFulfilled; bool isCarveOut; }\n"
        "mapping(uint256=>ConditionRecord) public conditionRecords; uint256 public conditionCount;\n"
        "function addCondition(string calldata desc, bool carveOut) external onlyOwner returns(uint256 id) { ... }\n"
        "function fulfillCondition(uint256 id) external whenActive { conditionRecords[id].isFulfilled=true; emit ConditionFulfilled(id); }",
    "TERMINATION":
        "function terminateContract(string calldata reason) external onlyOwner whenActive {\n"
        "    isTerminated=true; emit ContractTerminated(reason, block.timestamp);\n}\n"
        "function terminateForBreach(string calldata reason) external onlyOwner {\n"
        "    isTerminated=true; emit ContractTerminated(reason, block.timestamp);\n}",
    "OBLIGATION":
        "enum ObligationStatus { PENDING, FULFILLED, BREACHED, WAIVED }\n"
        "struct ObligationRecord { string description; ObligationStatus status; address assignedTo; uint256 deadline; bool bestEfforts; }\n"
        "mapping(uint256=>ObligationRecord) public obligationRecords; uint256 public obligationCount;\n"
        "function addObligation(string calldata desc, address to, uint256 deadline, bool bestEfforts) external onlyOwner returns(uint256 id) { ... }\n"
        "function fulfillObligation(uint256 id) external whenActive { obligationRecords[id].status=ObligationStatus.FULFILLED; emit ObligationFulfilled(id, msg.sender); }",
    "PARTY":
        "// Add address state variable for each party:\n"
        "address public internAddress;\n"
        "address public supervisorAddress;\n"
        "// Update onlyParty() modifier to include these addresses",
    "DATE_DEADLINE":
        "uint256 public reportingDeadline; // set in constructor as Unix timestamp\n"
        "// In fulfillObligation: require(block.timestamp <= reportingDeadline, 'Deadline passed');",
}

def _build_patch_prompt(
    base_code: str,
    cmp: dict,
    econtract_text: str,
    iteration: int,
    banked_accuracy: float,
    resolved_components: list,
    all_history: list,
) -> str:
    """
    Build the incremental patch prompt.
    The LLM sees ONLY the remaining gap and outputs ONLY new code to add.
    Previously achieved accuracy is locked — shown as 'already correct'.
    """
    tiers         = cmp.get("node_tiers", {})
    missing_types = cmp.get("type_coverage", {}).get("missing_semantic", [])
    unmatched     = [n for n in cmp.get("unmatched_nodes", []) if n and 2 < len(n) < 30][:10]
    gap           = round(100.0 - banked_accuracy, 1)

    # Per-missing-type Solidity scaffolds
    type_scaffolds = "\n\n".join(
        f"// === ADD for {t} ===\n{TYPE_GUIDANCE.get(t, '// Add appropriate constructs for ' + t)}"
        for t in missing_types
    )

    # Concrete values to encode
    amounts = list(dict.fromkeys(re.findall(r"\d{4,}", " ".join(unmatched))))[:3]
    dates   = list(dict.fromkeys(re.findall(r"\d{6,}", " ".join(unmatched))))[:2]

    value_hint = ""
    if amounts:
        value_hint += f"\n// PAYMENT AMOUNTS to encode as constants: {amounts}"
        value_hint += "\n// Example: uint256 public constant STIPEND_AMOUNT = " + amounts[0] + ";"
    if dates:
        value_hint += f"\n// DEADLINE DATES (YYYYMMDD) to encode: {dates}"
        value_hint += "\n// Example: uint256 public reportingDeadline = <convert to unix timestamp>;"

    # Progress summary for context
    history_summary = ""
    if all_history:
        history_summary = "Iteration history:\n" + "\n".join(
            f"  iter {h['iteration']}: accuracy={h['accuracy']}%  sc_nodes={h['sc_nodes']}"
            for h in all_history[-3:]
        )

    resolved_summary = ""
    if resolved_components:
        resolved_summary = "Already resolved (DO NOT touch these):\n  " + ", ".join(resolved_components[:10])

    return f"""You are an intelligent smart contract reconstruction engine.
Your task: produce ONLY the NEW Solidity code fragments needed to fix the remaining {gap}% coverage gap.
DO NOT rewrite or repeat existing contract code. DO NOT output pragma, import, or contract wrapper.
Output ONLY new state variables, structs, events, modifiers, and functions to ADD to the existing contract.

=== CONTEXT ===
Iteration: {iteration} / 5
Banked accuracy (already correct, DO NOT regress): {banked_accuracy}%
Remaining gap to close: {gap}%
{history_summary}

=== ORIGINAL E-CONTRACT (excerpt) ===
{econtract_text[:1000]}

=== CURRENT CONTRACT (DO NOT repeat this, only ADD to it) ===
```solidity
{base_code[:2500]}
```

=== WHAT IS ALREADY CORRECT ===
{resolved_summary if resolved_summary else "  (see banked accuracy above)"}
Covered semantic types: {sorted(cmp.get('type_coverage',{}).get('covered_semantic',[]))}

=== WHAT STILL NEEDS TO BE ADDED (the remaining {gap}%) ===
Missing semantic types: {missing_types}
Unmatched entity labels: {unmatched}

=== REQUIRED ADDITIONS (Solidity 0.8.16 code snippets to insert) ===
{type_scaffolds if type_scaffolds else "// All types covered — add address variables and value constants"}
{value_hint}

=== OUTPUT RULES ===
1. Output ONLY new Solidity code fragments (state variables + functions + structs + events)
2. NO pragma line. NO contract {{ }} wrapper. NO existing code repeated.
3. NO markdown. NO explanations. Only valid Solidity 0.8.16 syntax.
4. Each addition should close the gap for ONE specific missing component.
5. Do NOT remove or modify any existing function — only append new ones."""


# ── Additive refinement loop (Algorithm 4) ────────────────────────────────────

def _ollama_patch(prompt: str) -> str:
    """Call Ollama and extract the patch fragment."""
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model":   OLLAMA_MODEL,
            "prompt":  prompt,
            "stream":  False,
            "options": {"temperature": 0.1, "num_predict": 2048},
        }, timeout=180)
        resp.raise_for_status()
        raw = resp.json().get("response", "")
        return _extract_patch_only(raw)
    except Exception:
        return ""


def refinement_loop(
    initial_solidity: str,
    econtract_text: str,
    G_e: nx.DiGraph,
) -> Tuple[str, list, int]:
    """
    Additive patch loop:
      - Best code checkpoint is saved every time accuracy improves
      - If an iteration makes things worse → discard, keep checkpoint
      - Prompt tells LLM only about the REMAINING gap
      - Patch is MERGED into existing code, not replacing it
    """
    from core.smartcontract_kg import build_smartcontract_knowledge_graph

    best_code     = initial_solidity
    best_accuracy = 0.0
    history       = []
    resolved_components: list = []

    # Evaluate starting point
    G_s0  = build_smartcontract_knowledge_graph(best_code)
    cmp0  = compare_knowledge_graphs(G_e, G_s0)
    best_accuracy = cmp0["accuracy"]

    for iteration in range(1, MAX_ITERATIONS + 1):
        # Build patch prompt targeting only the remaining gap
        G_s_current = build_smartcontract_knowledge_graph(best_code)
        cmp_current = compare_knowledge_graphs(G_e, G_s_current)

        # Track which types are already covered as "resolved"
        covered = cmp_current.get("type_coverage", {}).get("covered_semantic", [])
        for c in covered:
            if c not in resolved_components:
                resolved_components.append(c)

        prompt = _build_patch_prompt(
            base_code           = best_code,
            cmp                 = cmp_current,
            econtract_text      = econtract_text,
            iteration           = iteration,
            banked_accuracy     = best_accuracy,
            resolved_components = resolved_components,
            all_history         = history,
        )

        # Get patch from LLM
        patch = _ollama_patch(prompt)

        # Merge patch into best code
        if patch:
            candidate = _merge_patch(best_code, patch)
        else:
            candidate = best_code  # nothing to add

        # Evaluate candidate
        G_s_new  = build_smartcontract_knowledge_graph(candidate)
        cmp_new  = compare_knowledge_graphs(G_e, G_s_new)
        new_acc  = cmp_new["accuracy"]

        history.append({
            "iteration":       iteration,
            "accuracy":        new_acc,
            "node_similarity": cmp_new["node_similarity"],
            "edge_similarity": cmp_new["edge_similarity"],
            "type_coverage":   cmp_new["type_coverage"]["type_coverage_pct"],
            "sc_nodes":        cmp_new["sc_node_count"],
            "is_valid":        cmp_new["is_valid"],
            "banked":          best_accuracy,
            "patch_applied":   bool(patch),
            "improved":        new_acc > best_accuracy,
        })

        if new_acc >= 100.0:
            best_code     = candidate
            best_accuracy = new_acc
            break

        if new_acc > best_accuracy:
            # IMPROVEMENT: bank it
            best_code     = candidate
            best_accuracy = new_acc
        # else: REGRESSION — discard candidate, keep best_code (checkpoint)
        # next iteration will retry with the same base but tighter prompt

    return best_code, history, len(history)