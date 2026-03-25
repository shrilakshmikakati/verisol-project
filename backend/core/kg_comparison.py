"""
Algorithm 3: KG Comparison — 3-tier node similarity.
Algorithm 4: LLM Refinement — ADDITIVE PATCH architecture.

Scoring:
  Tier A (50%) — type-level semantic mapping  EC → SC
  Tier B (30%) — label / word-level fuzzy match
  Tier C (20%) — numeric value / date coverage in Solidity code
  Final accuracy = 50% node_score + 10% edge_sim + 40% type_completeness

Additive loop:
  iter 0: base score  → banked; gap = 100 - base
  iter N: LLM adds missing parts → re-score → bank if improved, else roll back
  Best-score checkpoint prevents regression.
  Minimum 1 iteration always runs for validation.
"""
import re, json
from datetime import datetime as _dt
from difflib import SequenceMatcher
from typing import Tuple
import networkx as nx
import requests

OLLAMA_URL     = "http://localhost:11434/api/generate"
OLLAMA_MODEL   = "qwen2.5-coder-7b"
MAX_ITERATIONS = 5

# ── Normalisation helpers ─────────────────────────────────────────────────────
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())

def _words(s: str) -> set:
    split = re.sub(r"([A-Z])", r" \1", s)
    return set(w for w in re.findall(r"[a-z]{3,}", split.lower()))

# ── Type-mapping tables ───────────────────────────────────────────────────────
EC_TO_SC_TYPES = {
    "PARTY":               {"VARIABLE","CONTRACT"},
    "OBLIGATION":          {"FUNCTION","EVENT","STRUCT","ENUM"},
    "CONDITION":           {"FUNCTION","MODIFIER","STRUCT"},
    "PAYMENT":             {"FUNCTION","STRUCT","VARIABLE"},
    "DATE_DEADLINE":       {"VARIABLE"},
    "TERMINATION":         {"FUNCTION"},
    "PENALTY_REMEDY":      {"FUNCTION","VARIABLE"},
    "DISPUTE_ARBITRATION": {"FUNCTION","STRUCT","ENUM"},
    "CONFIDENTIALITY_IP":  {"FUNCTION","STRUCT"},
    "FORCE_MAJEURE":       {"MODIFIER","FUNCTION"},
    "MILESTONE":           {"FUNCTION","STRUCT","ENUM"},
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
IMPORTANT_TYPES = {"PARTY","OBLIGATION","PAYMENT","CONDITION","TERMINATION",
                   "PENALTY_REMEDY","DISPUTE_ARBITRATION","CONFIDENTIALITY_IP",
                   "FORCE_MAJEURE","MILESTONE","DATE_DEADLINE"}
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
    "CANCELS":        {"terminateContract","CONTAINS"},
    "BREACHES":       {"markObligationBreached","terminateForBreach"},
    "PENALIZES":      {"applyPenalty"},
    "HAS_OBLIGATION": {"addObligation","CONTAINS"},
    "CO_OCCURS_WITH": {"CONTAINS"},
}

# ── Tier A: type similarity ───────────────────────────────────────────────────
def _tier_a_type_similarity(G_e, G_s):
    sc_ast_types = {G_s.nodes[n].get("entity_type","").upper() for n in G_s.nodes}
    covered_ec: set = set()
    for sc_t in sc_ast_types:
        covered_ec.update(SC_TO_EC_TYPES.get(sc_t, set()))
    if "VARIABLE" in sc_ast_types: covered_ec.update(["PARTY","PAYMENT","DATE_DEADLINE","PENALTY_REMEDY"])
    if "FUNCTION" in sc_ast_types: covered_ec.update(["OBLIGATION","TERMINATION","CONDITION","PENALTY_REMEDY","DISPUTE_ARBITRATION","MILESTONE"])
    if "MODIFIER" in sc_ast_types: covered_ec.update(["CONDITION","FORCE_MAJEURE"])
    if "STRUCT"   in sc_ast_types: covered_ec.update(["OBLIGATION","CONDITION","PAYMENT","MILESTONE","DISPUTE_ARBITRATION","CONFIDENTIALITY_IP"])
    if "EVENT"    in sc_ast_types: covered_ec.update(["OBLIGATION","PAYMENT","TERMINATION","PENALTY_REMEDY","DISPUTE_ARBITRATION"])
    matched, unmatched = [], []
    for n in G_e.nodes:
        label  = G_e.nodes[n].get("label", n)
        ec_typ = G_e.nodes[n].get("entity_type", "")
        (matched if ec_typ in covered_ec else unmatched).append(_norm(label))
    total = len(matched) + len(unmatched)
    return round(len(matched)/total*100, 2) if total else 100.0, matched, unmatched

# ── Tier B: label similarity ──────────────────────────────────────────────────
def _tier_b_label_similarity(G_e, G_s) -> float:
    sc_flags = {t: any(G_s.nodes[n].get("entity_type","").upper() == t for n in G_s.nodes)
                for t in ("VARIABLE","FUNCTION","EVENT","STRUCT","MODIFIER")}
    sc_all_words: set = set(); sc_labels = []
    for n in G_s.nodes:
        label = G_s.nodes[n].get("label", n)
        sc_labels.append(_norm(label))
        sc_all_words |= _words(label); sc_all_words |= _words(str(n))

    matched = total = 0
    for n in G_e.nodes:
        label   = G_e.nodes[n].get("label", n)
        ec_type = G_e.nodes[n].get("entity_type", "")
        if not label or not label.strip(): continue
        total += 1; is_matched = False
        if   ec_type == "PARTY"              and sc_flags["VARIABLE"]:
            norm_p = _norm(label); pw = _words(label)
            is_matched = any(norm_p in sl for sl in sc_labels) or any(w in sc_all_words for w in pw if len(w)>=4)
        elif ec_type == "DATE_DEADLINE"      and sc_flags["VARIABLE"]: is_matched = True
        elif ec_type == "PAYMENT"            and (sc_flags["VARIABLE"] or sc_flags["FUNCTION"]): is_matched = True
        elif ec_type == "OBLIGATION"         and (sc_flags["FUNCTION"] or sc_flags["STRUCT"]): is_matched = True
        elif ec_type == "TERMINATION"        and sc_flags["FUNCTION"]: is_matched = True
        elif ec_type == "CONDITION"          and (sc_flags["FUNCTION"] or sc_flags["MODIFIER"]): is_matched = True
        elif ec_type == "PENALTY_REMEDY"     and (sc_flags["FUNCTION"] or sc_flags["VARIABLE"]): is_matched = True
        elif ec_type == "DISPUTE_ARBITRATION"and (sc_flags["FUNCTION"] or sc_flags["STRUCT"]): is_matched = True
        elif ec_type == "CONFIDENTIALITY_IP" and (sc_flags["FUNCTION"] or sc_flags["STRUCT"]): is_matched = True
        elif ec_type == "FORCE_MAJEURE"      and (sc_flags["MODIFIER"] or sc_flags["FUNCTION"]): is_matched = True
        elif ec_type == "MILESTONE"          and (sc_flags["FUNCTION"] or sc_flags["STRUCT"]): is_matched = True
        if not is_matched:
            ec_words = _words(label)
            if any(w in sc_all_words for w in ec_words if len(w)>=4): is_matched = True
        if not is_matched:
            norm_label = _norm(label)
            for sl in sc_labels:
                if norm_label == sl or (norm_label and sl and SequenceMatcher(None,norm_label,sl).ratio()>=0.5):
                    is_matched = True; break
        if not is_matched and re.search(r"\d{4,}", label):
            nums = re.findall(r"\d{4,}", label); sc_text = " ".join(sc_labels)
            if any(num in sc_text for num in nums): is_matched = True
        if is_matched: matched += 1
    return round(matched/total*100, 2) if total else 100.0

# ── Tier C: value coverage ────────────────────────────────────────────────────
def _tier_c_value_coverage(G_e: nx.DiGraph, G_s: nx.DiGraph, solidity_code: str = "") -> float:
    extracted: list = []
    for n in G_e.nodes:
        label = str(G_e.nodes[n].get("label", n))
        for num in re.findall(r"\d{1,3}(?:,\d{3})+|\d{3,}", label):
            norm = num.replace(",","")
            if norm not in extracted: extracted.append(norm)
    if not extracted or not solidity_code: return 100.0
    search_space = solidity_code.replace(",","").replace(" ","")
    ts_aliases: dict = {}
    for val in extracted:
        if len(val) == 8 and val.isdigit():
            try:
                dd, mm, yyyy = int(val[:2]), int(val[2:4]), int(val[4:])
                if 1<=mm<=12 and 1<=dd<=31 and 1970<=yyyy<=2100:
                    ts_aliases[val] = str(int(_dt(yyyy,mm,dd).timestamp()))
            except Exception: pass
    found = sum(1 for v in extracted
                if v in search_space or (v in ts_aliases and ts_aliases[v] in search_space))
    return round(found/len(extracted)*100, 2)

def _node_similarity(G_e, G_s, solidity_code: str = ""):
    tier_a, matched, unmatched = _tier_a_type_similarity(G_e, G_s)
    tier_b = _tier_b_label_similarity(G_e, G_s)
    tier_c = _tier_c_value_coverage(G_e, G_s, solidity_code)
    score  = round(0.50*tier_a + 0.30*tier_b + 0.20*tier_c, 2)
    return score, matched, unmatched, {"tier_a":tier_a,"tier_b":tier_b,"tier_c":tier_c}

# ── Edge similarity ───────────────────────────────────────────────────────────
def _edge_similarity(G_e, G_s) -> Tuple[float, int, int, int]:
    ec_rels   = {G_e.edges[e].get("relation","") for e in G_e.edges}
    sc_rels   = {G_s.edges[e].get("relation","") for e in G_s.edges}
    valid_ec  = [r for r in ec_rels if r]
    total_sc  = len(G_s.edges)
    if not valid_ec: return 100.0, 0, 0, total_sc
    covered = sum(1 for r in valid_ec
                  if (EC_EDGE_TO_SC.get(r, {r}) & sc_rels) or
                     any(_norm(r) == _norm(sr) for sr in sc_rels))
    sim = round(covered/len(valid_ec)*100, 2)
    return sim, covered, len(valid_ec), total_sc

# ── Type coverage ─────────────────────────────────────────────────────────────
def _type_coverage(G_e, G_s) -> dict:
    ec_types = {G_e.nodes[n].get("entity_type") for n in G_e.nodes}
    sc_types = {G_s.nodes[n].get("entity_type","").upper() for n in G_s.nodes}
    covered_sc: set = set()
    for sc_t in sc_types:
        covered_sc.update(EC_TO_SC_SEMANTIC.get(sc_t, {sc_t}))
    # Structs with date fields implicitly cover DATE_DEADLINE
    if "STRUCT" in sc_types:
        for n in G_s.nodes:
            if G_s.nodes[n].get("label","").lower() in ("paymentschedule","milestone","dispute"):
                covered_sc.add("DATE_DEADLINE"); break
    for n in G_s.nodes:
        if G_s.nodes[n].get("entity_type","").upper() == "VARIABLE":
            if re.search(r"date|deadline|duedate", G_s.nodes[n].get("label",""), re.I):
                covered_sc.add("DATE_DEADLINE"); break
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

def _detect_duplicate_nodes(G_e: nx.DiGraph) -> dict:
    norm_map: dict = {}
    for n in G_e.nodes:
        key = _norm(G_e.nodes[n].get("label", n))
        norm_map.setdefault(key, []).append(n)
    return {v[0]: v[1:] for v in norm_map.values() if len(v) > 1}

# ── Main comparison ───────────────────────────────────────────────────────────
def compare_knowledge_graphs(G_e: nx.DiGraph, G_s: nx.DiGraph, solidity_code: str = "") -> dict:
    node_score, matched, unmatched, tiers = _node_similarity(G_e, G_s, solidity_code)
    edge_sim, matched_edges, total_ec_edges, total_sc_edges = _edge_similarity(G_e, G_s)
    type_cov  = _type_coverage(G_e, G_s)
    dup_nodes = _detect_duplicate_nodes(G_e)
    ec_count  = G_e.number_of_nodes()

    type_coverage_pct = type_cov["type_coverage_pct"]
    missing_types     = type_cov["missing_semantic"]
    if   type_coverage_pct >= 100.0: base_completeness, cs = 100.0, "✓ VALIDATED (100%)"
    elif type_coverage_pct >=  80.0: base_completeness, cs = 90.0,  f"⚠ PARTIAL ({type_coverage_pct:.0f}%) — missing: {', '.join(missing_types)}"
    elif type_coverage_pct >=  60.0: base_completeness, cs = 75.0,  f"⚠ INCOMPLETE ({type_coverage_pct:.0f}%) — missing: {', '.join(missing_types)}"
    else:                             base_completeness, cs = 50.0,  f"✗ POOR ({type_coverage_pct:.0f}%) — missing: {', '.join(missing_types)}"

    raw_accuracy   = (0.50*node_score + 0.10*edge_sim + 0.40*base_completeness) / 100.0
    final_accuracy = round(raw_accuracy*100, 2)
    confidence     = ("HIGH" if final_accuracy>=90.0 and not missing_types else
                      "MEDIUM" if final_accuracy>=75.0 else
                      "LOW"    if final_accuracy>=50.0 else "VERY LOW")
    dedup_count    = len(dup_nodes)
    unique_ec      = ec_count - sum(len(v) for v in dup_nodes.values())

    return {
        "accuracy":            final_accuracy,
        "base_accuracy":       round(raw_accuracy*100, 2),
        "confidence":          confidence,
        "completeness":        base_completeness,
        "completeness_status": cs,
        "node_similarity":     node_score,
        "node_tiers":          tiers,
        "edge_similarity":     edge_sim,
        "edge_metadata": {
            "matched_edges":  matched_edges,
            "total_ec_edges": total_ec_edges,
            "total_sc_edges": total_sc_edges,
            "explanation":    f"EC:{total_ec_edges} edges; SC:{total_sc_edges} edges; {matched_edges} EC edges found in SC",
        },
        "type_coverage":       type_cov,
        "matched_nodes":       matched,
        "unmatched_nodes":     unmatched,
        "ec_node_count":       ec_count,
        "sc_node_count":       G_s.number_of_nodes(),
        "ec_edge_count":       G_e.number_of_edges(),
        "sc_edge_count":       G_s.number_of_edges(),
        "is_valid":            final_accuracy >= 85.0 and not missing_types and tiers.get("tier_c", 0) >= 80.0,
        "deduplication": {
            "duplicate_node_groups": dedup_count,
            "unique_ec_nodes":       unique_ec,
            "raw_ec_nodes":          ec_count,
            "recommendation": ("Deduplication improves fidelity." if dedup_count > 0
                                else "✓ No duplicate nodes detected"),
        },
        "boilerplate_analysis": {
            "sc_nodes":          G_s.number_of_nodes(),
            "ec_nodes":          ec_count,
            "boilerplate_ratio": round(total_sc_edges/total_ec_edges, 2) if total_ec_edges else 1.0,
        },
    }

# ── Patch merger ──────────────────────────────────────────────────────────────
def _merge_patch(base_code: str, patch: str) -> str:
    """Inject patch Solidity into base_code just before the final closing brace."""
    if not patch or not patch.strip(): return base_code
    patch = re.sub(r"//\s*SPDX[^\n]*\n", "", patch)
    patch = re.sub(r"pragma solidity[^\n]*\n", "", patch)
    patch = re.sub(r"import\s+[^\n]+\n", "", patch)
    m = re.search(r"contract\s+\w+[^{]*\{(.*)\}\s*$", patch, re.DOTALL|re.IGNORECASE)
    if m: patch = m.group(1).strip()
    _assert_re = re.compile(r"^\s*assert\s*\(", re.IGNORECASE)
    patch = "\n".join(l for l in patch.split("\n") if not _assert_re.match(l)).strip()
    if not patch: return base_code
    first_name = re.search(r"\b(?:function|struct|event|modifier)\s+(\w+)", patch)
    if first_name and first_name.group(1) in base_code: return base_code
    last = base_code.rfind("}")
    if last == -1: return base_code + "\n" + patch
    return (base_code[:last].rstrip()
            + "\n\n    // ── Patch ───────────────────────────────────────────\n"
            + "    " + patch.replace("\n", "\n    ") + "\n}")

def _extract_patch_only(response_text: str) -> str:
    m = re.search(r"```solidity\s*(.*?)```", response_text, re.DOTALL)
    if m: return m.group(1).strip()
    lines = response_text.split("\n"); start = None
    for i, line in enumerate(lines):
        if re.match(r"\s*(?:function|struct|event|modifier|uint|address|bool|mapping|enum)\b", line):
            start = i; break
    return "\n".join(lines[start:]).strip() if start is not None else ""

# ── Type-guidance scaffolds for patch prompt ──────────────────────────────────
TYPE_GUIDANCE = {
    "DISPUTE_ARBITRATION":
        "function raiseDispute(string calldata reason) external whenActive { ... }\n"
        "function resolveDispute(uint256 id) external onlyOwner { ... }\n"
        "struct Dispute { string reason; bool resolved; address raisedBy; }",
    "FORCE_MAJEURE":
        "bool public forceMajeureActive;\n"
        "function activateForceMajeure(string calldata reason) external onlyOwner { forceMajeureActive=true; }\n"
        "function liftForceMajeure() external onlyOwner { forceMajeureActive=false; }",
    "CONFIDENTIALITY_IP":
        "struct ConfidentialityRecord { address discloser; address recipient; uint256 expiry; bool breached; }\n"
        "mapping(uint256=>ConfidentialityRecord) public ndaRecords; uint256 public ndaCount;\n"
        "function recordNDA(address d, address r, uint256 exp) external onlyOwner { ... }",
    "MILESTONE":
        "struct Milestone { string description; bool completed; bool accepted; }\n"
        "mapping(uint256=>Milestone) public milestones; uint256 public milestoneCount;\n"
        "function addMilestone(string calldata desc) external onlyOwner returns(uint256) { ... }\n"
        "function completeMilestone(uint256 id) external whenActive { ... }",
    "PAYMENT":
        "uint256 public stipendAmount;\n"
        "function releaseStipend(address payable recipient) external onlyOwner whenActive {\n"
        "    require(address(this).balance >= stipendAmount,'Insufficient');\n"
        "    (bool ok,) = recipient.call{value: stipendAmount}('');\n"
        "    require(ok,'transfer failed');\n}",
    "PENALTY_REMEDY":
        "uint256 public penaltyRateBps; uint256 public accruedPenalties; uint256 public liabilityCap;\n"
        "function applyPenalty(address party, uint256 amount, string calldata reason) external onlyOwner {\n"
        "    uint256 pen=(amount*penaltyRateBps)/10000;\n"
        "    if(liabilityCap>0&&pen>liabilityCap) pen=liabilityCap;\n"
        "    accruedPenalties+=pen; emit PenaltyApplied(party,pen,reason);\n}",
    "CONDITION":
        "struct ConditionRecord { string description; bool isFulfilled; bool isCarveOut; }\n"
        "mapping(uint256=>ConditionRecord) public conditionRecords; uint256 public conditionCount;\n"
        "function addCondition(string calldata desc, bool carveOut) external onlyOwner returns(uint256) { ... }\n"
        "function fulfillCondition(uint256 id) external whenActive { conditionRecords[id].isFulfilled=true; }",
    "TERMINATION":
        "function terminateContract(string calldata reason) external onlyOwner {\n"
        "    isTerminated=true; emit ContractTerminated(reason,block.timestamp);\n}\n"
        "function terminateForBreach(string calldata reason) external onlyOwner {\n"
        "    isTerminated=true; emit ContractTerminated(reason,block.timestamp);\n}",
    "OBLIGATION":
        "enum ObligationStatus { PENDING, FULFILLED, BREACHED, WAIVED }\n"
        "struct ObligationRecord { string description; ObligationStatus status; address assignedTo; uint256 deadline; }\n"
        "mapping(uint256=>ObligationRecord) public obligationRecords; uint256 public obligationCount;\n"
        "function addObligation(string calldata desc, address to, uint256 deadline) external onlyOwner returns(uint256) { ... }\n"
        "function fulfillObligation(uint256 id) external whenActive { obligationRecords[id].status=ObligationStatus.FULFILLED; }",
    "PARTY":
        "address public internAddress;\naddress public supervisorAddress;\n"
        "// Update onlyParty() modifier to include these addresses",
    "DATE_DEADLINE":
        "uint256 public reportingDeadline;\n"
        "// In fulfillObligation: require(block.timestamp <= reportingDeadline,'Deadline passed');",
}

# ── Patch prompt builder ──────────────────────────────────────────────────────
def _build_patch_prompt(base_code, cmp, econtract_text, iteration,
                        banked_accuracy, resolved_components, all_history, G_e=None) -> str:
    tiers         = cmp.get("node_tiers", {})
    missing_types = cmp.get("type_coverage", {}).get("missing_semantic", [])
    unmatched     = [n for n in cmp.get("unmatched_nodes",[]) if n and 2 < len(n) < 30][:10]
    gap           = round(100.0 - banked_accuracy, 1)

    type_scaffolds = "\n\n".join(
        f"// === ADD for {t} ===\n{TYPE_GUIDANCE.get(t,'// Add appropriate constructs for '+t)}"
        for t in missing_types)

    amounts = []; dates = []
    if G_e:
        labels = [str(G_e.nodes[n].get("label",n)) for n in G_e.nodes]
        amounts = list(dict.fromkeys(re.findall(r"\d{4,}", " ".join(labels))))[:5]
        dates   = list(dict.fromkeys(re.findall(r"\d{6,}", " ".join(labels))))[:3]
    else:
        amounts = list(dict.fromkeys(re.findall(r"\d{4,}", " ".join(unmatched))))[:3]
        dates   = list(dict.fromkeys(re.findall(r"\d{6,}", " ".join(unmatched))))[:2]

    ta, tb, tc = tiers.get("tier_a",0.), tiers.get("tier_b",0.), tiers.get("tier_c",0.)
    es = cmp.get("edge_similarity",0.); tc_pct = cmp.get("type_coverage",{}).get("type_coverage_pct",0.)
    bottleneck = (f"TypeMatch ({ta}%)"    if ta  < 100 else
                  f"LabelMatch ({tb}%)"   if tb  < 100 else
                  f"ValueCov ({tc}%)"     if tc  < 100 else
                  f"EdgeSimilarity ({es}%)" if es < 100 else
                  f"TypeCoverage ({tc_pct}%)")

    history_summary = ("Iteration history:\n" +
                       "\n".join(f"  iter {h['iteration']}: accuracy={h['accuracy']}% sc_nodes={h['sc_nodes']}"
                                 for h in (all_history or [])[-3:])) if all_history else ""
    resolved_summary = ("Already resolved (DO NOT touch):\n  " +
                        ", ".join(resolved_components[:10])) if resolved_components else ""

    value_hint = ""
    if amounts: value_hint += f"\n// AMOUNTS to encode: {amounts}\n// e.g. uint256 public constant AMOUNT_{amounts[0]} = {amounts[0]};"
    if dates:   value_hint += f"\n// DATES (YYYYMMDD) to encode: {dates}\n// e.g. uint256 public reportingDeadline = <unix_ts>;"

    return f"""You are an intelligent smart contract reconstruction engine.
Your task: AGGRESSIVELY close the remaining {gap}% accuracy gap.
DO NOT rewrite or repeat existing contract code. DO NOT output pragma, import, or contract wrapper.
Output ONLY new state variables, structs, events, modifiers, and functions to ADD.

=== CRITICAL BOTTLENECK ===
The metric blocking further improvement is: {bottleneck}
This is the ONLY thing you should focus on fixing.

=== ITERATION CONTEXT ===
Iteration: {iteration} / {MAX_ITERATIONS}
Banked accuracy: {banked_accuracy}%  |  Gap to close: {gap}%
Node/Edge/Type metrics:
  TypeMatch={ta}%  LabelMatch={tb}%  ValueCov={tc}%
  EdgeSimilarity={es}%  TypeCoverage={tc_pct}%
{history_summary}
{resolved_summary}

=== ORIGINAL E-CONTRACT (excerpt) ===
{econtract_text[:1000]}

=== CURRENT SMART CONTRACT ===
```solidity
{base_code[:2500]}
```

=== TYPE SCAFFOLDS FOR MISSING TYPES ===
{type_scaffolds or '// All types covered'}

=== VALUE HINTS ===
{value_hint or '// No specific values required'}

=== OUTPUT RULES ===
1. Output ONLY new code targeting: {bottleneck}
2. Do NOT repeat any existing function or struct.
3. NO pragma, import, or contract wrapper.
4. NO markdown. Only valid Solidity ^0.8.16.
5. All variables MUST be declared before use — NO assert() with undeclared vars.
6. Even 1-2 well-crafted targeted functions beats generic code."""

# ── Ollama call ───────────────────────────────────────────────────────────────
def _ollama_patch(prompt: str, temperature: float = 0.1) -> str:
    for attempt in range(2):
        try:
            resp = requests.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                "options": {"temperature": 0.75, "num_predict": 2048},
            }, timeout=60)
            resp.raise_for_status()
            patch = _extract_patch_only(resp.json().get("response",""))
            if patch: return patch
        except requests.exceptions.Timeout:
            if attempt == 0: continue
        except Exception:
            pass
    return ""

# ── Refinement loop ───────────────────────────────────────────────────────────
def refinement_loop(initial_solidity: str, econtract_text: str, G_e: nx.DiGraph) -> Tuple[str, list, int]:
    """
    Additive patch loop — minimum 1 iteration always runs for validation.
    Best-score checkpoint: if an iteration scores lower, discard and keep best.
    Returns: (best_code, history, iterations_used)
    """
    from core.smartcontract_kg import build_smartcontract_knowledge_graph

    best_code = initial_solidity; best_accuracy = 0.0
    history: list = []; resolved_components: list = []
    no_patch_streak = 0

    G_s0 = build_smartcontract_knowledge_graph(best_code)
    best_accuracy = compare_knowledge_graphs(G_e, G_s0, best_code)["accuracy"]

    for iteration in range(1, MAX_ITERATIONS + 1):
        G_s_cur  = build_smartcontract_knowledge_graph(best_code)
        cmp_cur  = compare_knowledge_graphs(G_e, G_s_cur, best_code)

        for c in cmp_cur.get("type_coverage",{}).get("covered_semantic",[]):
            if c not in resolved_components: resolved_components.append(c)

        temperature = 0.1 if iteration <= 2 else (0.3 if iteration <= 4 else 0.5)
        patch = _ollama_patch(
            _build_patch_prompt(best_code, cmp_cur, econtract_text, iteration,
                                best_accuracy, resolved_components, history, G_e),
            temperature=temperature)

        if not patch:
            no_patch_streak += 1
            missing = cmp_cur.get("type_coverage",{}).get("missing_semantic",[])
            if no_patch_streak >= 3 and iteration >= 1 and (best_accuracy >= 80.0 or not missing):
                break
        else:
            no_patch_streak = 0

        candidate = _merge_patch(best_code, patch) if patch else best_code
        G_s_new   = build_smartcontract_knowledge_graph(candidate)
        cmp_new   = compare_knowledge_graphs(G_e, G_s_new, candidate)
        new_acc   = cmp_new["accuracy"]

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

        if new_acc >= 100.0 and iteration >= 1:
            best_code = candidate; best_accuracy = new_acc; break
        if new_acc > best_accuracy:
            best_code = candidate; best_accuracy = new_acc
        if iteration >= 1 and len(history) >= 2:
            if history[-1]["accuracy"] <= history[-2]["accuracy"] and not patch:
                break

    return best_code, history, len(history)