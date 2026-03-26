pragma solidity >=0.4.24;
// SPDX-License-Identifier: MIT
/// @title  contract0
/// @notice Auto-generated from E-Contract KG | Type: RENTAL
/// @dev    Jurisdiction: California | Governing Law: Delaware Law
///         Arbitration:  Arbitration (Mutual Consent)
contract contract0 {
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
    string  public constant JURISDICTION   = "California";
    string  public constant GOVERNING_LAW  = "Delaware Law";
    string  public constant ARBITRATION    = "Arbitration (Mutual Consent)";
    // ── Parties ─────────────────────────────────────────────────────
    address public Employee; // Employee
    address public Director; // Director
    address public Agent; // Agent
    address public Customer; // Customer
    address public West; // West
    address public Dorr; // Dorr
    address public Agreement; // Agreement
    address public Parent; // Parent
    address public Company; // Company
    // ── Financial ───────────────────────────────────────────────────
    uint256 public totalContractValue;
    uint256 public paidAmount;
    uint256 public penaltyRateBps;    // basis points (1 bps = 0.01%)
    uint256 public penaltyPeriod;     // seconds per penalty period
    uint256 public liabilityCap;      // max total penalty (0 = uncapped)
    uint256 public accruedPenalties;
    // ── E-Contract Values ──────────────────────────────────────────
    uint256 public constant AMOUNT_31 = 31; // rs 31
    uint256 public constant AMOUNT_35 = 35; // rs 35
    uint256 public constant AMOUNT_40 = 40; // rs 40
    uint256 public constant AMOUNT_47 = 47; // rs 47
    uint256 public constant AMOUNT_63 = 63; // rs 63
    uint256 public constant AMOUNT_65 = 65; // rs 65
    uint256 public constant AMOUNT_67 = 67; // rs 67
    uint256 public constant AMOUNT_115 = 115; // raw=115.00 $115.00
    uint256 public constant AMOUNT_500000 = 500000; // $500,000
    uint256 public constant AMOUNT_1000000 = 1000000; // $1,000,000,
    uint256 public constant AMOUNT_100000 = 100000; // $100,000
    uint256 public constant AMOUNT_200000 = 200000; // $200,000,
    uint256 public constant AMOUNT_10000 = 10000; // $10,000
    uint256 public constant AMOUNT_150000 = 150000; // $150,000,
    uint256 public constant AMOUNT_2500000 = 2500000; // $2,500,000
    uint256 public constant AMOUNT_1500000 = 1500000; // 1,500,000 per annum
    uint256 public constant AMOUNT_300000 = 300000; // 300,000 per annum
    uint256 public constant AMOUNT_3000000 = 3000000; // $3,000,000
    uint256 public constant AMOUNT_22000000 = 22000000; // $22,000,000
    uint256 public constant AMOUNT_7000000 = 7000000; // $7,000,000
    uint256 public constant AMOUNT_197000000 = 197000000; // $197,000,000
    uint256 public constant AMOUNT_5 = 5; // raw=5.18 5.18
    uint256 public constant AMOUNT_1 = 1; // raw=1.7 1.7
    uint256 public constant DATE_June_30__2014 = 1404066600; // June 30, 2014
    uint256 public constant DATE_January_1__2015 = 1420050600; // January 1, 2015
    uint256 public constant DATE_27_April_2016 = 1461695400; // 27 April 2016
    uint256 public constant DATE_May_13__2016 = 1463077800; // May 13, 2016
    uint256 public constant DATE_January_1__2017 = 1483209000; // January 1, 2017
    uint256 public constant DATE_January_1__2018 = 1514745000; // January 1, 2018
    uint256 public constant DATE_January_1__2019 = 1546281000; // January 1, 2019
    uint256 public constant DATE_March_17__2019 = 1552761000; // March 17, 2019
    uint256 public constant DATE_March_31__2019 = 1553970600; // March 31, 2019
    uint256 public constant DATE_July_8__2019 = 1562524200; // July 8, 2019
    uint256 public constant DATE_December_31__2019 = 1577730600; // December 31, 2019
    uint256 public constant DATE_January_1__2021 = 1609439400; // January 1, 2021
    uint256 public constant DATE_JANUARY_14__2021 = 1610562600; // JANUARY 14, 2021
    uint256 public constant DATE_January_14__2021 = 1610562600; // January 14, 2021
    uint256 public constant DATE_June_14__2021 = 1623609000; // June 14, 2021
    // ── Payment Schedules ────────────────────────────────────────────
    struct PaymentSchedule {
        uint256 amount;
        uint256 dueDate;    // Unix timestamp (0 = on-demand)
        bool    released;
        string  description;
    }
    PaymentSchedule[] public paymentSchedules;
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
    uint256 public reportingDeadline = 1404066600; // Unix timestamp
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
	assert(!(msg.sender == Employee ));
	assert(!(!(msg.sender == Employee )));
	assert(!( msg.sender == Director ));
	assert(!(!( msg.sender == Director )));
	assert(!( msg.sender == Agent ));
	assert(!(!( msg.sender == Agent )));
	assert(!( msg.sender == Customer ));
	assert(!(!( msg.sender == Customer )));
	assert(!( msg.sender == West ));
	assert(!(!( msg.sender == West )));
	assert(!( msg.sender == Dorr ));
	assert(!(!( msg.sender == Dorr )));
	assert(!( msg.sender == Agreement ));
	assert(!(!( msg.sender == Agreement )));
	assert(!( msg.sender == Parent ));
	assert(!(!( msg.sender == Parent )));
	assert(!( msg.sender == Company ));
	assert(!(!( msg.sender == Company )));
	assert(!( msg.sender == owner));
	assert(!(!( msg.sender == owner)));
        require(msg.sender == Employee || msg.sender == Director || msg.sender == Agent || msg.sender == Customer || msg.sender == West || msg.sender == Dorr || msg.sender == Agreement || msg.sender == Parent || msg.sender == Company || msg.sender == owner, "Not a party");
        _;
    }
    // ── Constructor ─────────────────────────────────────────────────
    constructor(
        uint256 _totalValue,
        uint256 _penaltyBps,
        uint256 _penaltyPeriod,
        uint256 _liabilityCap,
        address _Employee,
        address _Director,
        address _Agent,
        address _Customer,
        address _West,
        address _Dorr,
        address _Agreement,
        address _Parent,
        address _Company,
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
        Employee = _Employee;
        Director = _Director;
        Agent = _Agent;
        Customer = _Customer;
        West = _West;
        Dorr = _Dorr;
        Agreement = _Agreement;
        Parent = _Parent;
        Company = _Company;
        // Payment schedules from e-contract:
        paymentSchedules.push(PaymentSchedule(31, 0, false, "rs 31"));
        paymentSchedules.push(PaymentSchedule(35, 0, false, "rs 35"));
        paymentSchedules.push(PaymentSchedule(40, 0, false, "rs 40"));
        paymentSchedules.push(PaymentSchedule(47, 0, false, "rs 47"));
        paymentSchedules.push(PaymentSchedule(63, 0, false, "rs 63"));
        paymentSchedules.push(PaymentSchedule(65, 0, false, "rs 65"));
        paymentSchedules.push(PaymentSchedule(67, 0, false, "rs 67"));
        paymentSchedules.push(PaymentSchedule(115000000000000000000, 0, false, "$115.00"));
        // Obligations from e-contract clauses:
        obligationRecords[0] = ObligationRecord("Reasonable Best Efforts 63 5.8.", ObligationStatus.PENDING, address(0), 0, true);
        obligationCount++;
        obligationRecords[1] = ObligationRecord("(a) As used in this Agreement, the following terms shall have the meanings indic", ObligationStatus.PENDING, address(0), 0, false);
        obligationCount++;
        obligationRecords[2] = ObligationRecord("'Cash-Out Amount' means: (i) with respect to (A) a Vested Company Option or (B) ", ObligationStatus.PENDING, address(0), 0, false);
        obligationCount++;
        obligationRecords[3] = ObligationRecord("'Dissenting Shares' means any shares of Company Capital Stock that are issued an", ObligationStatus.PENDING, address(0), 0, false);
        obligationCount++;
        obligationRecords[4] = ObligationRecord("'made available' means, with respect to any statement in this Agreement or the C", ObligationStatus.PENDING, address(0), 0, false);
        obligationCount++;
        obligationRecords[5] = ObligationRecord("'Material Adverse Effect' means with respect to the Company and the Subsidiaries", ObligationStatus.PENDING, address(0), 0, false);
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
    uint256 public constant PENALTY_AMOUNT_0 = 65;
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
