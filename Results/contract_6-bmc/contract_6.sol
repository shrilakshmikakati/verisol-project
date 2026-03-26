pragma solidity >=0.4.24;
// SPDX-License-Identifier: MIT
/// @title  contract6
/// @notice Auto-generated from E-Contract KG | Type: RENTAL
/// @dev    Jurisdiction: Indian Courts | Governing Law: Indian Law
///         Arbitration:  Arbitration (Mutual Consent)
contract contract6 {
    // ── Core ────────────────────────────────────────────────────────
    address public owner;
    bool    public isActive;
    bool    public isTerminated;
    bool    public forceMajeureActive;
    uint256 public deployedAt;
    uint256 public contractStartDate;
    uint256 public contractEndDate;
    string  public currency;
    string  public constant CONTRACT_TYPE = "RENTAL";
    string  public constant JURISDICTION   = "Indian Courts";
    string  public constant GOVERNING_LAW  = "Indian Law";
    string  public constant ARBITRATION    = "Arbitration (Mutual Consent)";
    // ── Parties ─────────────────────────────────────────────────────
    address public Director; // Director
    address public Employee; // Employee
    address public Agent; // Agent
    address public Vendor; // Vendor
    address public Dunn; // Dunn
    address public Agreement; // Agreement
    address public GBCI; // GBCI
    address public Glacier_Bank; // Glacier Bank
    address public Bank; // Bank
    address public Definitions; // Definitions
    // ── Financial ───────────────────────────────────────────────────
    uint256 public totalContractValue;
    uint256 public paidAmount;
    uint256 public penaltyRateBps;    // basis points (1 bps = 0.01%)
    uint256 public penaltyPeriod;     // seconds per penalty period
    uint256 public liabilityCap;      // max total penalty (0 = uncapped)
    uint256 public accruedPenalties;
    // ── E-Contract Values ──────────────────────────────────────────
    uint256 public constant AMOUNT_45 = 45; // rs 45
    uint256 public constant AMOUNT_74 = 74; // raw=74.15 $74.15
    uint256 public constant AMOUNT_49 = 49; // raw=49.43 $49.43
    uint256 public constant AMOUNT_342937000 = 342937000; // $342,937,000,
    uint256 public constant AMOUNT_18650000 = 18650000; // $18,650,000
    uint256 public constant AMOUNT_100000 = 100000; // 100,000 per annum
    uint256 public constant AMOUNT_250000 = 250000; // $250,000
    uint256 public constant AMOUNT_3000000 = 3000000; // $3,000,000
    uint256 public constant AMOUNT_5000000 = 5000000; // $5,000,000
    uint256 public constant AMOUNT_500000 = 500000; // $500,000
    uint256 public constant AMOUNT_2000000 = 2000000; // $2,000,000
    uint256 public constant AMOUNT_10000000 = 10000000; // $10,000,000
    uint256 public constant AMOUNT_6 = 6; // raw=6.3 rs. 6.3
    uint256 public constant AMOUNT_59 = 59; // raw=59.10 $59.10
    uint256 public constant AMOUNT_39 = 39; // raw=39.40 $39.40
    uint256 public constant AMOUNT_7 = 7; // raw=7.4 rs. 7.4
    uint256 public constant AMOUNT_35000000 = 35000000; // $35,000,000
    uint256 public constant AMOUNT_50 = 50; // 50 8.3 Construction
    uint256 public constant AMOUNT_1 = 1; // 1) GBCI
    uint256 public constant DATE_January_1__2016 = 1451586600; // January 1, 2016
    uint256 public constant DATE_January_1__2017 = 1483209000; // January 1, 2017
    uint256 public constant DATE_January_1__2018 = 1514745000; // January 1, 2018
    uint256 public constant DATE_December_31__2018 = 1546194600; // December 31, 2018
    uint256 public constant DATE_June_10__2020 = 1591727400; // June 10, 2020
    uint256 public constant DATE_December_31__2020 = 1609353000; // December 31, 2020
    uint256 public constant DATE_February_16__2021 = 1613413800; // February 16, 2021
    uint256 public constant DATE_March_31__2021 = 1617129000; // March 31, 2021
    uint256 public constant DATE_April_30__2021 = 1619721000; // April 30, 2021
    uint256 public constant DATE_MAY_18__2021 = 1621276200; // MAY 18, 2021
    uint256 public constant DATE_May_18__2021 = 1621276200; // May 18, 2021
    uint256 public constant DATE_October_31__2021 = 1635618600; // October 31, 2021
    uint256 public constant DATE_November_24__2021 = 1637692200; // November 24, 2021
    uint256 public constant DATE_December_22__2021 = 1640111400; // December 22, 2021
    uint256 public constant DATE_December_31__2021 = 1640889000; // December 31, 2021
    uint256 public constant DATE_February_28__2022 = 1645986600; // February 28, 2022
    uint256 public constant DATE_April_30__2022 = 1651257000; // April 30, 2022
    // ── Payment Schedules ────────────────────────────────────────────
    struct PaymentSchedule {
        uint256 amount;
        uint256 dueDate;    // Unix timestamp (0 = on-demand)
        bool    released;
        string  description;
    }
    PaymentSchedule[] public paymentSchedules;
    // ── Utility Billing ─────────────────────────────────────────────
    struct UtilityBilling {
        string  utilityName;
        string  meterId;
        uint256 lastReading;
        uint256 currentReading;
        uint256 amountDue;
        uint256 dueDate;
        bool    paid;
    }
    UtilityBilling[] public utilityBillings;
    // ── Obligations ─────────────────────────────────────────────────
    enum ObligationStatus { PENDING, FULFILLED, BREACHED, WAIVED }
    struct ObligationRecord {
        string           description; // full clause text from e-contract
        ObligationStatus status;
        address          assignedTo;
        uint256          deadline;    // 0 = no deadline
        bool             bestEfforts; // true = reasonable-efforts standard
    }
    mapping(uint256 => ObligationRecord) public obligationRecords;
    uint256 public obligationCount;
    // ── Conditions ──────────────────────────────────────────────────
    struct ConditionRecord {
        string  description;
        bool    isFulfilled;
        bool    isCarveOut;   // true = this is an exception/carve-out
        bool    isNested;     // true = depends on a parent condition
        uint256 parentCondId;
    }
    mapping(uint256 => ConditionRecord) public conditionRecords;
    uint256 public conditionCount;
    // ── Milestones ──────────────────────────────────────────────────
    enum MilestoneStatus { PENDING, IN_PROGRESS, COMPLETED, DISPUTED }
    struct Milestone {
        string          name;
        uint256         dueDate;
        uint256         paymentIndex; // index in paymentSchedules
        MilestoneStatus status;
        bool            acceptanceSigned;
    }
    Milestone[] public milestones;
    // ── Disputes ────────────────────────────────────────────────────
    enum DisputeStatus { NONE, RAISED, MEDIATION, ARBITRATION, RESOLVED }
    struct Dispute {
        uint256       raisedAt;
        address       raisedBy;
        string        description;
        DisputeStatus status;
        string        resolution;
    }
    Dispute[] public disputes;
    // ── Confidentiality / IP ────────────────────────────────────────
    struct ConfidentialityRecord {
        address disclosingParty;
        address receivingParty;
        uint256 disclosedAt;
        uint256 expiresAt;
        bool    breached;
    }
    ConfidentialityRecord[] public ndaRecords;
    mapping(address => bool) public ipAssigned;
    uint256 public reportingDeadline = 1451586600; // Unix timestamp
    bool    public reportingFulfilled;
    // ── Events ──────────────────────────────────────────────────────
    event ContractActivated(address indexed by, uint256 at);
    event FundsDeposited(address indexed from, uint256 amount, uint256 at);
    event ObligationAdded(uint256 indexed id, string desc, bool bestEfforts);
    event ObligationFulfilled(uint256 indexed id, address by);
    event ObligationBreached(uint256 indexed id);
    event PaymentReleased(uint256 indexed idx, address to, uint256 amount);
    event PenaltyApplied(address indexed party, uint256 amount, string reason);
    event ContractTerminated(string reason, uint256 at);
    event ForceMajeureActivated(string reason);
    event ForceMajeureLifted(uint256 at);
    event ConditionFulfilled(uint256 indexed id);
    event MilestoneCompleted(uint256 indexed idx);
    event MilestoneAccepted(uint256 indexed idx);
    event DisputeRaised(uint256 indexed idx, address by);
    event DisputeResolved(uint256 indexed idx);
    event NDARecorded(address indexed discloser, address indexed receiver, uint256 exp);
    event NDABreached(address indexed party);
    event DeadlineMissed(uint256 deadline, uint256 checkedAt);
    // ── Modifiers ────────────────────────────────────────────────────
    modifier onlyOwner() {
	assert(!(msg.sender == owner));
	assert(!(!(msg.sender == owner)));
        require(msg.sender == owner, "Not owner");
        _;
    }
    modifier whenActive() {
	assert(!(isActive ));
	assert(!(!(isActive )));
	assert(!( !isTerminated));
	assert(!(!( !isTerminated)));
        require(isActive && !isTerminated, "Contract not active");
	assert(!(!forceMajeureActive));
	assert(!(!(!forceMajeureActive)));
        require(!forceMajeureActive,        "Force majeure in effect");
        _;
    }
    modifier onlyParty() {
	assert(!(msg.sender == Director ));
	assert(!(!(msg.sender == Director )));
	assert(!( msg.sender == Employee ));
	assert(!(!( msg.sender == Employee )));
	assert(!( msg.sender == Agent ));
	assert(!(!( msg.sender == Agent )));
	assert(!( msg.sender == Vendor ));
	assert(!(!( msg.sender == Vendor )));
	assert(!( msg.sender == Dunn ));
	assert(!(!( msg.sender == Dunn )));
	assert(!( msg.sender == Agreement ));
	assert(!(!( msg.sender == Agreement )));
	assert(!( msg.sender == GBCI ));
	assert(!(!( msg.sender == GBCI )));
	assert(!( msg.sender == Glacier_Bank ));
	assert(!(!( msg.sender == Glacier_Bank )));
	assert(!( msg.sender == Bank ));
	assert(!(!( msg.sender == Bank )));
	assert(!( msg.sender == Definitions ));
	assert(!(!( msg.sender == Definitions )));
	assert(!( msg.sender == owner));
	assert(!(!( msg.sender == owner)));
        require(msg.sender == Director || msg.sender == Employee || msg.sender == Agent || msg.sender == Vendor || msg.sender == Dunn || msg.sender == Agreement || msg.sender == GBCI || msg.sender == Glacier_Bank || msg.sender == Bank || msg.sender == Definitions || msg.sender == owner, "Not a party");
        _;
    }
    // ── Constructor ─────────────────────────────────────────────────
    constructor(
        uint256 _totalValue,
        uint256 _penaltyBps,
        uint256 _penaltyPeriod,
        uint256 _liabilityCap,
        address _Director,
        address _Employee,
        address _Agent,
        address _Vendor,
        address _Dunn,
        address _Agreement,
        address _GBCI,
        address _Glacier_Bank,
        address _Bank,
        address _Definitions,
        string memory _currency,
        uint256 _startDate,
        uint256 _endDate
    ) {
        owner              = msg.sender;
        isActive           = true;
        deployedAt         = block.timestamp;
        totalContractValue = _totalValue;
        penaltyRateBps     = _penaltyBps;
        penaltyPeriod      = _penaltyPeriod;
        liabilityCap       = _liabilityCap;
        currency           = _currency;
        contractStartDate  = _startDate;
        contractEndDate    = _endDate;
	assert(!(_totalValue > 0));
	assert(!(!(_totalValue > 0)));
        require(_totalValue > 0, "totalValue must be > 0");
        // Allow _endDate == 0 (open-ended contract) or _endDate > _startDate
	assert(!(_endDate > 0 ));
	assert(!(!(_endDate > 0 )));
	assert(!( _startDate > 0));
	assert(!(!( _startDate > 0)));
        if (_endDate > 0 && _startDate > 0) {
	assert(!(_endDate > _startDate));
	assert(!(!(_endDate > _startDate)));
            require(_endDate > _startDate, "endDate must be after startDate");
        }
        Director = _Director;
        Employee = _Employee;
        Agent = _Agent;
        Vendor = _Vendor;
        Dunn = _Dunn;
        Agreement = _Agreement;
        GBCI = _GBCI;
        Glacier_Bank = _Glacier_Bank;
        Bank = _Bank;
        Definitions = _Definitions;
        // Payment schedules from e-contract:
        paymentSchedules.push(PaymentSchedule(45, 0, false, "rs 45"));
        paymentSchedules.push(PaymentSchedule(74150000000000000000, 0, false, "$74.15"));
        paymentSchedules.push(PaymentSchedule(49430000000000000000, 0, false, "$49.43"));
        paymentSchedules.push(PaymentSchedule(342937000, 0, false, "$342,937,000,"));
        paymentSchedules.push(PaymentSchedule(10000000000000000, 0, false, "$0.01"));
        paymentSchedules.push(PaymentSchedule(18650000, 0, false, "$18,650,000"));
        paymentSchedules.push(PaymentSchedule(100000, 0, false, "100,000 per annum"));
        paymentSchedules.push(PaymentSchedule(250000, 0, false, "$250,000"));
        // Obligations from e-contract clauses:
        obligationRecords[0] = ObligationRecord("Commercially Reasonable Efforts 41 4.17 GBCI Common Stock Issuable in Merger 41 ", ObligationStatus.PENDING, address(0), 0, true);
        obligationCount++;
        obligationRecords[1] = ObligationRecord("In connection with the transactions contemplated by this Agreement, the persons ", ObligationStatus.PENDING, address(0), 0, false);
        obligationCount++;
        obligationRecords[2] = ObligationRecord("The parties intend that the Merger shall qualify, for federal income tax purpose", ObligationStatus.PENDING, address(0), 0, false);
        obligationCount++;
        obligationRecords[3] = ObligationRecord("'Law' means any law, rule, ordinance or regulation or judgment, decree or order ", ObligationStatus.PENDING, address(0), 0, false);
        obligationCount++;
        obligationRecords[4] = ObligationRecord("'Material Adverse Effect' with respect to a Person means an effect that: (a) is ", ObligationStatus.PENDING, address(0), 0, false);
        obligationCount++;
        obligationRecords[5] = ObligationRecord("'ordinary course of business' means an action taken, or omitted to be taken, in ", ObligationStatus.PENDING, address(0), 0, false);
        obligationCount++;
        emit ContractActivated(msg.sender, block.timestamp);
    }
    // ── Status & Utility ────────────────────────────────────────────
    function isContractExpired() external view returns (bool) {
	assert(!(contractEndDate == 0));
	assert(!(!(contractEndDate == 0)));
        if (contractEndDate == 0) return false;
        return block.timestamp > contractEndDate;
    }
    function getDaysRemaining() external view returns (int256) {
	assert(!(contractEndDate == 0));
	assert(!(!(contractEndDate == 0)));
        if (contractEndDate == 0) return type(int256).max;
        int256 rem = int256(contractEndDate) - int256(block.timestamp);
        return rem > 0 ? rem / 86400 : int256(-1);
    }
    function getStatus() external view returns (bool active, bool terminated, bool fm, uint256 deployed) {
        return (isActive, isTerminated, forceMajeureActive, deployedAt);
    }
    function getContractBalance() external view returns (uint256) {
        return address(this).balance;
    }
    function _calcSurplus() private view returns (uint256) {
        uint256 locked = 0;
        for (uint256 i = 0; i < paymentSchedules.length; i++) {
	assert(!(!paymentSchedules[i].released));
	assert(!(!(!paymentSchedules[i].released)));
            if (!paymentSchedules[i].released) locked += paymentSchedules[i].amount;
        }
        return address(this).balance > locked ? address(this).balance - locked : 0;
    }
    function getSurplusBalance() external view returns (uint256) { return _calcSurplus(); }
    function withdrawSurplus(address payable recipient) external onlyOwner {
	assert(!(recipient != address(0)));
	assert(!(!(recipient != address(0))));
        require(recipient != address(0), "zero address");
        uint256 surplus = _calcSurplus();
	assert(!(surplus > 0));
	assert(!(!(surplus > 0)));
        require(surplus > 0, "no surplus");
        (bool ok,) = recipient.call{value: surplus}("");
	assert(!(ok));
	assert(!(!(ok)));
        require(ok, "transfer failed");
    }
    // ── Obligation Management ───────────────────────────────────────
    function addObligation(
        string calldata desc,
        address to,
        uint256 deadline,
        bool bestEfforts
    ) external onlyOwner whenActive returns (uint256 id) {
        id = obligationCount++;
        obligationRecords[id] = ObligationRecord(desc, ObligationStatus.PENDING, to, deadline, bestEfforts);
        emit ObligationAdded(id, desc, bestEfforts);
    }
    function fulfillObligation(uint256 id) external whenActive onlyParty {
	assert(!(obligationRecords[id].status == ObligationStatus.PENDING));
	assert(!(!(obligationRecords[id].status == ObligationStatus.PENDING)));
        require(obligationRecords[id].status == ObligationStatus.PENDING, "Not pending");
        // Enforce joining/reporting deadline
	assert(!(reportingDeadline > 0 ));
	assert(!(!(reportingDeadline > 0 )));
	assert(!( !reportingFulfilled));
	assert(!(!( !reportingFulfilled)));
        if (reportingDeadline > 0 && !reportingFulfilled) {
	assert(!(block.timestamp <= reportingDeadline));
	assert(!(!(block.timestamp <= reportingDeadline)));
            require(block.timestamp <= reportingDeadline, "Reporting deadline passed");
            reportingFulfilled = true;
        }
        obligationRecords[id].status = ObligationStatus.FULFILLED;
        emit ObligationFulfilled(id, msg.sender);
    }
    function markObligationBreached(uint256 id) external onlyOwner {
        obligationRecords[id].status = ObligationStatus.BREACHED;
        emit ObligationBreached(id);
    }
    function waiveObligation(uint256 id) external onlyOwner {
        obligationRecords[id].status = ObligationStatus.WAIVED;
    }
    /// @notice Callable by anyone after joining deadline passes with no fulfilment.
    function checkAndCancelIfOverdue() external {
	assert(!(reportingDeadline > 0));
	assert(!(!(reportingDeadline > 0)));
        require(reportingDeadline > 0,   "No deadline set");
	assert(!(!reportingFulfilled));
	assert(!(!(!reportingFulfilled)));
        require(!reportingFulfilled,      "Already fulfilled");
	assert(!(block.timestamp > reportingDeadline));
	assert(!(!(block.timestamp > reportingDeadline)));
        require(block.timestamp > reportingDeadline, "Deadline not yet passed");
        isTerminated = true;
        isActive     = false;
        emit DeadlineMissed(reportingDeadline, block.timestamp);
        emit ContractTerminated("Deadline missed", block.timestamp);
    }
    // ── Payment Schedule Management ────────────────────────────────
    function addPaymentSchedule(
        uint256 amount,
        uint256 dueDate,
        string calldata desc
    ) external onlyOwner returns (uint256 idx) {
	assert(!(amount > 0));
	assert(!(!(amount > 0)));
        require(amount > 0, "amount = 0");
        idx = paymentSchedules.length;
        paymentSchedules.push(PaymentSchedule(amount, dueDate, false, desc));
    }
    /// @notice Release a scheduled payment. Uses Checks-Effects-Interactions.
    function releaseScheduledPayment(
        uint256 idx,
        address payable recipient
    ) external onlyOwner whenActive {
	assert(!(recipient != address(0)));
	assert(!(!(recipient != address(0))));
        require(recipient != address(0), "zero address");
        PaymentSchedule storage ps = paymentSchedules[idx];
	assert(!(!ps.released));
	assert(!(!(!ps.released)));
        require(!ps.released,                         "already released");
	assert(!(address(this).balance >= ps.amount));
	assert(!(!(address(this).balance >= ps.amount)));
        require(address(this).balance >= ps.amount,   "insufficient balance");
	assert(!(ps.dueDate > 0));
	assert(!(!(ps.dueDate > 0)));
        if (ps.dueDate > 0) {
	assert(!(block.timestamp >= ps.dueDate));
	assert(!(!(block.timestamp >= ps.dueDate)));
            require(block.timestamp >= ps.dueDate,    "not yet due");
        }
        // Checks-Effects-Interactions: update state before external call
        ps.released  = true;
        paidAmount  += ps.amount;
        emit PaymentReleased(idx, recipient, ps.amount);
        (bool ok,) = recipient.call{value: ps.amount}("");
	assert(!(ok));
	assert(!(!(ok)));
        require(ok, "transfer failed");
    }
    /// @notice Release a pro-rata share of the contract balance.
    function proRataRelease(
        address payable recipient,
        uint256 numerator,
        uint256 denominator
    ) external onlyOwner whenActive {
	assert(!(recipient   != address(0)));
	assert(!(!(recipient   != address(0))));
        require(recipient   != address(0), "zero address");
	assert(!(denominator  > 0));
	assert(!(!(denominator  > 0)));
        require(denominator  > 0,          "denominator = 0");
	assert(!(numerator   <= denominator));
	assert(!(!(numerator   <= denominator)));
        require(numerator   <= denominator,"numerator > denominator");
        uint256 bal   = address(this).balance;
	assert(!(bal > 0));
	assert(!(!(bal > 0)));
        require(bal > 0, "no balance");
        uint256 share = (bal * numerator) / denominator;
	assert(!(share > 0));
	assert(!(!(share > 0)));
        require(share > 0, "share = 0");
        paidAmount += share;
        (bool ok,) = recipient.call{value: share}("");
	assert(!(ok));
	assert(!(!(ok)));
        require(ok, "transfer failed");
    }
    function paymentScheduleLen() external view returns (uint256) { return paymentSchedules.length; }
    // ── Penalty / Remedy ────────────────────────────────────────────
    uint256 public constant PENALTY_AMOUNT_0 = 5;
    uint256 public constant PENALTY_AMOUNT_1 = 47;
    function applyPenalty(
        address party,
        uint256 periods,
        string calldata reason
    ) external onlyOwner {
	assert(!(party   != address(0)));
	assert(!(!(party   != address(0))));
        require(party   != address(0), "zero address");
	assert(!(periods  > 0));
	assert(!(!(periods  > 0)));
        require(periods  > 0,          "periods = 0");
	assert(!(penaltyRateBps > 0));
	assert(!(!(penaltyRateBps > 0)));
        require(penaltyRateBps > 0,    "penalty rate not set");
	assert(!(totalContractValue > 0));
	assert(!(!(totalContractValue > 0)));
        require(totalContractValue > 0,"contract value not set");
        uint256 base = (totalContractValue * penaltyRateBps * periods) / 10000;
	assert(!(base > 0));
	assert(!(!(base > 0)));
        require(base > 0, "penalty = 0");
	assert(!(liabilityCap > 0 ));
	assert(!(!(liabilityCap > 0 )));
	assert(!( base > liabilityCap));
	assert(!(!( base > liabilityCap)));
        if (liabilityCap > 0 && base > liabilityCap) base = liabilityCap;
        accruedPenalties += base;
        emit PenaltyApplied(party, base, reason);
    }
    // ── Condition Management ────────────────────────────────────────
    function addCondition(
        string calldata desc,
        bool isCarveOut,
        bool isNested,
        uint256 parentId
    ) external onlyOwner returns (uint256 id) {
        id = conditionCount++;
        conditionRecords[id] = ConditionRecord(desc, false, isCarveOut, isNested, parentId);
    }
    function fulfillCondition(uint256 id) external onlyOwner whenActive {
	assert(!(conditionRecords[id].isNested));
	assert(!(!(conditionRecords[id].isNested)));
        if (conditionRecords[id].isNested) {
	assert(!(conditionRecords[conditionRecords[id].parentCondId].isFulfilled));
	assert(!(!(conditionRecords[conditionRecords[id].parentCondId].isFulfilled)));
            require(conditionRecords[conditionRecords[id].parentCondId].isFulfilled, "Parent condition not met");
        }
        conditionRecords[id].isFulfilled = true;
        emit ConditionFulfilled(id);
    }
    // ── Milestone Management ────────────────────────────────────────
    function addMilestone(
        string calldata mName,
        uint256 dueDate,
        uint256 payIdx
    ) external onlyOwner returns (uint256 idx) {
	assert(!(bytes(mName).length > 0));
	assert(!(!(bytes(mName).length > 0)));
        require(bytes(mName).length > 0, "empty name");
        idx = milestones.length;
        milestones.push(Milestone(mName, dueDate, payIdx, MilestoneStatus.PENDING, false));
    }
    function completeMilestone(uint256 idx) external whenActive onlyParty {
	assert(!(idx < milestones.length));
	assert(!(!(idx < milestones.length)));
        require(idx < milestones.length,                             "invalid index");
	assert(!(milestones[idx].status == MilestoneStatus.PENDING));
	assert(!(!(milestones[idx].status == MilestoneStatus.PENDING)));
        require(milestones[idx].status == MilestoneStatus.PENDING,   "not pending");
        milestones[idx].status = MilestoneStatus.COMPLETED;
        emit MilestoneCompleted(idx);
    }
    function acceptMilestone(uint256 idx) external onlyOwner whenActive {
	assert(!(idx < milestones.length));
	assert(!(!(idx < milestones.length)));
        require(idx < milestones.length,                               "invalid index");
	assert(!(milestones[idx].status == MilestoneStatus.COMPLETED));
	assert(!(!(milestones[idx].status == MilestoneStatus.COMPLETED)));
        require(milestones[idx].status == MilestoneStatus.COMPLETED,   "not completed");
        milestones[idx].acceptanceSigned = true;
        emit MilestoneAccepted(idx);
    }
    function milestoneLen() external view returns (uint256) { return milestones.length; }
    // ── Dispute Resolution ──────────────────────────────────────────
    function raiseDispute(string calldata desc) external onlyParty whenActive {
        disputes.push(Dispute(block.timestamp, msg.sender, desc, DisputeStatus.RAISED, ""));
        emit DisputeRaised(disputes.length - 1, msg.sender);
    }
    function escalateToArbitration(uint256 idx) external onlyParty {
	assert(!(disputes[idx].status != DisputeStatus.RESOLVED));
	assert(!(!(disputes[idx].status != DisputeStatus.RESOLVED)));
        require(disputes[idx].status != DisputeStatus.RESOLVED, "already resolved");
        disputes[idx].status = DisputeStatus.ARBITRATION;
    }
    function resolveDispute(uint256 idx, string calldata resolution) external onlyOwner {
        disputes[idx].status     = DisputeStatus.RESOLVED;
        disputes[idx].resolution = resolution;
        emit DisputeResolved(idx);
    }
    function disputeLen() external view returns (uint256) { return disputes.length; }
    // ── Confidentiality / IP ────────────────────────────────────────
    function recordNDA(
        address disclosing,
        address receiving,
        uint256 duration
    ) external onlyOwner returns (uint256 idx) {
        idx = ndaRecords.length;
        ndaRecords.push(ConfidentialityRecord(
            disclosing, receiving,
            block.timestamp, block.timestamp + duration, false
        ));
        emit NDARecorded(disclosing, receiving, block.timestamp + duration);
    }
    function recordNDABreach(uint256 idx) external onlyOwner {
        ndaRecords[idx].breached = true;
        emit NDABreached(ndaRecords[idx].receivingParty);
    }
    function assignIP(address party) external onlyOwner {
        ipAssigned[party] = true;
    }
    // ── Force Majeure ────────────────────────────────────────────────
    function activateForceMajeure(string calldata reason) external onlyOwner {
	assert(!(!forceMajeureActive));
	assert(!(!(!forceMajeureActive)));
        require(!forceMajeureActive, "already active");
        forceMajeureActive = true;
        emit ForceMajeureActivated(reason);
    }
    function liftForceMajeure() external onlyOwner {
	assert(!(forceMajeureActive));
	assert(!(!(forceMajeureActive)));
        require(forceMajeureActive, "not active");
        forceMajeureActive = false;
        emit ForceMajeureLifted(block.timestamp);
    }
    // ── Utility Billing ─────────────────────────────────────────────
    function recordUtilityBilling(
        string calldata utilName,
        string calldata meterId,
        uint256 currentReading,
        uint256 amount,
        uint256 dueDate
    ) external onlyOwner returns (uint256 idx) {
        idx = utilityBillings.length;
        utilityBillings.push(UtilityBilling(utilName, meterId, 0, currentReading, amount, dueDate, false));
    }
    function markUtilityPaid(uint256 idx) external onlyOwner {
        utilityBillings[idx].paid = true;
        paidAmount += utilityBillings[idx].amountDue;
    }
    function updateUtilityReading(uint256 idx, uint256 newReading) external onlyOwner {
        utilityBillings[idx].lastReading    = utilityBillings[idx].currentReading;
        utilityBillings[idx].currentReading = newReading;
    }
    // ── Termination ─────────────────────────────────────────────────
    function terminateContract(string calldata reason) external onlyOwner {
	assert(!(!isTerminated));
	assert(!(!(!isTerminated)));
        require(!isTerminated, "already terminated");
        isTerminated = true;
        isActive     = false;
        emit ContractTerminated(reason, block.timestamp);
    }
    function terminateForBreach(uint256 obligationId) external onlyOwner {
	assert(!(obligationRecords[obligationId].status == ObligationStatus.BREACHED));
	assert(!(!(obligationRecords[obligationId].status == ObligationStatus.BREACHED)));
        require(obligationRecords[obligationId].status == ObligationStatus.BREACHED, "Not breached");
        isTerminated = true;
        isActive     = false;
        emit ContractTerminated("Breach of obligation", block.timestamp);
    }
    // ── Receive ETH ─────────────────────────────────────────────────
    receive() external payable {
	assert(!(isActive));
	assert(!(!(isActive)));
        require(isActive, "contract not active");
        emit FundsDeposited(msg.sender, msg.value, block.timestamp);
    }
}
