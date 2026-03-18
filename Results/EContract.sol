// SPDX-License-Identifier: MIT
pragma solidity ^0.8.16;

/// @title EContract — Auto-generated from E-Contract KG
contract EContract {

    address public owner; bool public isActive; bool public isTerminated;
    bool public forceMajeureActive; uint256 public deployedAt;

    address public Lessor;
    address public Tenant;
    address public Lessee;
    address public Ramesh;
    address public Gajendra;
    address public Suresh;

    struct PaymentSchedule { uint256 amount; uint256 dueDate; bool released; string description; }
    PaymentSchedule[] public paymentSchedules;
    uint256 public totalContractValue; uint256 public paidAmount;

    enum ObligationStatus { PENDING, FULFILLED, BREACHED, WAIVED }
    struct ObligationRecord { string description; ObligationStatus status; address assignedTo; uint256 deadline; bool bestEfforts; }
    mapping(uint256 => ObligationRecord) public obligationRecords; uint256 public obligationCount;

    struct ConditionRecord { string description; bool isFulfilled; bool isCarveOut; bool isNested; uint256 parentCondId; }
    mapping(uint256 => ConditionRecord) public conditionRecords; uint256 public conditionCount;

    uint256 public penaltyRateBps; uint256 public penaltyPeriod; uint256 public liabilityCap; uint256 public accruedPenalties;

    string public constant GOVERNING_LAW = "English Law";
    string public constant ARBITRATION_BODY = "ICC";
    enum DisputeStatus { NONE, RAISED, MEDIATION, ARBITRATION, RESOLVED }
    struct Dispute { uint256 raisedAt; address raisedBy; string description; DisputeStatus status; string resolution; }
    Dispute[] public disputes;

    struct ConfidentialityRecord { address disclosingParty; address receivingParty; uint256 disclosedAt; uint256 expiresAt; bool breached; }
    ConfidentialityRecord[] public ndaRecords; mapping(address => bool) public ipAssigned;

    event ContractActivated(address indexed by, uint256 at);
    event ObligationAdded(uint256 indexed id, string desc, bool bestEfforts);
    event ObligationFulfilled(uint256 indexed id, address by);
    event ObligationBreached(uint256 indexed id);
    event ConditionFulfilled(uint256 indexed id);
    event PaymentReleased(uint256 indexed idx, address to, uint256 amount);
    event MilestoneCompleted(uint256 indexed idx); event MilestoneAccepted(uint256 indexed idx);
    event PenaltyApplied(address indexed party, uint256 amount, string reason);
    event DisputeRaised(uint256 indexed idx, address by); event DisputeResolved(uint256 indexed idx);
    event ForceMajeureActivated(string reason); event ForceMajeureLifted(uint256 at);
    event NDAdded(address indexed d, address indexed r, uint256 exp); event NDBreached(address indexed p);
    event ContractTerminated(string reason, uint256 at);

    modifier onlyOwner() { require(msg.sender==owner,'Not owner'); _; }
    modifier whenActive() { require(isActive&&!isTerminated,'Not active'); require(!forceMajeureActive,'Force majeure'); _; }
    modifier onlyParty() { require(msg.sender==Lessor || msg.sender==Tenant || msg.sender==Lessee || msg.sender==Ramesh || msg.sender==Gajendra || msg.sender==Suresh||msg.sender==owner,'Not a party'); _; }

    constructor(uint256 _totalValue,uint256 _penaltyBps,uint256 _penaltyPeriod,uint256 _liabilityCap) {
        owner=msg.sender; isActive=true; deployedAt=block.timestamp;
        totalContractValue=_totalValue; penaltyRateBps=_penaltyBps;
        penaltyPeriod=_penaltyPeriod; liabilityCap=_liabilityCap;
        // Initialize payment schedules from e-contract:
        paymentSchedules.push(PaymentSchedule(18000,0,false,"Rs. 18,000"));
        paymentSchedules.push(PaymentSchedule(60000,0,false,"Rs. 60,000"));
        paymentSchedules.push(PaymentSchedule(1500,0,false,"Rs. 1,500"));
        emit ContractActivated(msg.sender,block.timestamp);
    }

    // ── Values extracted from e-contract ────────────────────────────
    uint256 public constant VALUE_1500 = 1500;
    uint256 public constant VALUE_18000 = 18000;
    uint256 public constant VALUE_2026 = 2026;
    uint256 public constant VALUE_60000 = 60000;

    function addObligation(string calldata desc,address to,uint256 deadline,bool bestEfforts) external onlyOwner whenActive returns(uint256 id){
        id=obligationCount++; obligationRecords[id]=ObligationRecord(desc,ObligationStatus.PENDING,to,deadline,bestEfforts);
        emit ObligationAdded(id,desc,bestEfforts);
    }
    function fulfillObligation(uint256 id) external whenActive onlyParty{
        require(obligationRecords[id].status==ObligationStatus.PENDING,'Not pending');
        obligationRecords[id].status=ObligationStatus.FULFILLED; emit ObligationFulfilled(id,msg.sender);
    }
    function markObligationBreached(uint256 id) external onlyOwner{
        obligationRecords[id].status=ObligationStatus.BREACHED; emit ObligationBreached(id);
    }

    function addCondition(string calldata desc,bool isCarveOut,bool isNested,uint256 parentId) external onlyOwner returns(uint256 id){
        id=conditionCount++; conditionRecords[id]=ConditionRecord(desc,false,isCarveOut,isNested,parentId);
    }
    function fulfillCondition(uint256 id) external onlyOwner whenActive{
        if(conditionRecords[id].isNested) require(conditionRecords[conditionRecords[id].parentCondId].isFulfilled,'Parent not met');
        conditionRecords[id].isFulfilled=true; emit ConditionFulfilled(id);
    }

    function addPaymentSchedule(uint256 amount,uint256 dueDate,string calldata desc) external onlyOwner returns(uint256 idx){
        idx=paymentSchedules.length; paymentSchedules.push(PaymentSchedule(amount,dueDate,false,desc));
    }
    function releaseScheduledPayment(uint256 idx,address payable recipient) external payable onlyOwner whenActive{
        PaymentSchedule storage ps=paymentSchedules[idx];
        require(!ps.released,'Done'); require(msg.value>=ps.amount,'Low');
        if(ps.dueDate>0) require(block.timestamp>=ps.dueDate,'Not due');
        ps.released=true; paidAmount+=ps.amount; recipient.transfer(ps.amount);
        emit PaymentReleased(idx,recipient,ps.amount);
    }
    function proRataRelease(address payable recipient,uint256 numerator,uint256 denominator) external payable onlyOwner whenActive{
        require(denominator>0,'Zero denom'); uint256 share=(msg.value*numerator)/denominator;
        require(share>0,'Zero share'); recipient.transfer(share);
    }

    function applyPenalty(address party,uint256 periods,string calldata reason) external onlyOwner{
        uint256 base=(totalContractValue*penaltyRateBps*periods)/10000;
        if(liabilityCap>0&&base>liabilityCap) base=liabilityCap;
        accruedPenalties+=base; emit PenaltyApplied(party,base,reason);
    }

    function raiseDispute(string calldata desc) external onlyParty whenActive{
        disputes.push(Dispute(block.timestamp,msg.sender,desc,DisputeStatus.RAISED,''));
        emit DisputeRaised(disputes.length-1,msg.sender);
    }
    function escalateToArbitration(uint256 idx) external onlyParty{
        require(disputes[idx].status!=DisputeStatus.RESOLVED,'Done');
        disputes[idx].status=DisputeStatus.ARBITRATION;
    }
    function resolveDispute(uint256 idx,string calldata resolution) external onlyOwner{
        disputes[idx].status=DisputeStatus.RESOLVED; disputes[idx].resolution=resolution;
        emit DisputeResolved(idx);
    }

    function recordNDA(address disclosing,address receiving,uint256 dur) external onlyOwner returns(uint256 idx){
        idx=ndaRecords.length; ndaRecords.push(ConfidentialityRecord(disclosing,receiving,block.timestamp,block.timestamp+dur,false));
        emit NDAdded(disclosing,receiving,block.timestamp+dur);
    }
    function recordNDABreach(uint256 idx) external onlyOwner{ ndaRecords[idx].breached=true; emit NDBreached(ndaRecords[idx].receivingParty); }
    function assignIP(address party) external onlyOwner{ ipAssigned[party]=true; }

    function terminateContract(string calldata reason) external onlyOwner{
        require(!isTerminated,'Done'); isTerminated=true; isActive=false;
        emit ContractTerminated(reason,block.timestamp);
    }
    function terminateForBreach(uint256 id) external onlyOwner{
        require(obligationRecords[id].status==ObligationStatus.BREACHED,'Not breached');
        isTerminated=true; isActive=false; emit ContractTerminated('Breach',block.timestamp);
    }

    function getStatus() external view returns(bool,bool,bool,uint256){
        return(isActive,isTerminated,forceMajeureActive,deployedAt);
    }
    function paymentLen() external view returns(uint256){ return paymentSchedules.length; }
    function disputeLen()   external view returns(uint256){ return disputes.length; }
    receive() external payable {}
}