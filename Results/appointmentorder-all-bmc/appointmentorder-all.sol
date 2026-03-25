pragma solidity >=0.4.24;
// SPDX-License-Identifier: MIT
/// @title appointmentorderall — Auto-generated from E-Contract KG
/// @notice Jurisdiction: Indian Courts | Governing Law: Indian Law
contract appointmentorderall {
    address public owner; bool public isActive; bool public isTerminated;
    bool public forceMajeureActive; uint256 public deployedAt;
    uint256 public contractStartDate; uint256 public contractEndDate;
    string public currency; string public jurisdiction;
    address public Professor;
    address public Candidate;
    address public Intern;
    address public Sangharatna_GodboleyDt;
    address public ETI_DHANUSH;
    address public Sangharatna_Godboley;
    address public SHRILAKSHMI_KAKATI_shrilakshmika;
    address public India;
    address public Telangana;
    address public Sangharatna_GodboleyDt_08_07_202;
    uint256 public totalContractValue; uint256 public paidAmount;
    uint256 public penaltyRateBps; uint256 public penaltyPeriod; uint256 public liabilityCap; uint256 public accruedPenalties;
    struct PaymentSchedule { uint256 amount; uint256 dueDate; bool released; string description; }
    PaymentSchedule[] public paymentSchedules;
    enum ObligationStatus { PENDING, FULFILLED, BREACHED, WAIVED }
    struct ObligationRecord { string description; ObligationStatus status; address assignedTo; uint256 deadline; bool bestEfforts; }
    mapping(uint256 => ObligationRecord) public obligationRecords; uint256 public obligationCount;
    struct ConditionRecord { string description; bool isFulfilled; bool isCarveOut; bool isNested; uint256 parentCondId; }
    mapping(uint256 => ConditionRecord) public conditionRecords; uint256 public conditionCount;
    event ContractActivated(address indexed by, uint256 at);
    event FundsDeposited(address indexed from, uint256 amount, uint256 at);
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
    modifier onlyParty() { require(msg.sender==Professor || msg.sender==Candidate || msg.sender==Intern || msg.sender==Sangharatna_GodboleyDt || msg.sender==ETI_DHANUSH || msg.sender==Sangharatna_Godboley || msg.sender==SHRILAKSHMI_KAKATI_shrilakshmika || msg.sender==India || msg.sender==Telangana || msg.sender==Sangharatna_GodboleyDt_08_07_202||msg.sender==owner,'Not a party'); _; }
    // ── Values extracted from e-contract ────────────────────────────
    uint256 public constant VALUE_10000 = 10000;
    uint256 public constant DATE_08072025 = 1751913000; // Unix timestamp
    uint256 public constant DATE_08082025 = 1754591400; // Unix timestamp
    constructor(
        uint256 _totalValue,
        uint256 _penaltyBps,
        uint256 _penaltyPeriod,
        uint256 _liabilityCap, address _Professor, address _Candidate, address _Intern, address _Sangharatna_GodboleyDt, address _ETI_DHANUSH, address _Sangharatna_Godboley, address _SHRILAKSHMI_KAKATI_shrilakshmika, address _India, address _Telangana, address _Sangharatna_GodboleyDt_08_07_202,
        string memory _currency,
        uint256 _startDate,
        uint256 _endDate
    ) {
        owner=msg.sender; isActive=true; deployedAt=block.timestamp;
        totalContractValue=_totalValue; penaltyRateBps=_penaltyBps;
        penaltyPeriod=_penaltyPeriod; liabilityCap=_liabilityCap;
	assert(!(_totalValue>0));
	assert(!(!(_totalValue>0)));
        require(_totalValue>0,'totalValue=0');
        // penaltyBps=0 is valid for non-penalty contracts (internship, NDA, etc.)
        currency=_currency; contractStartDate=_startDate; contractEndDate=_endDate;
	assert(!(_endDate>_startDate));
	assert(!(!(_endDate>_startDate)));
        require(_endDate>_startDate,'end<=start');
        jurisdiction="Indian Courts";
        Professor=_Professor;
        Candidate=_Candidate;
        Intern=_Intern;
        Sangharatna_GodboleyDt=_Sangharatna_GodboleyDt;
        ETI_DHANUSH=_ETI_DHANUSH;
        Sangharatna_Godboley=_Sangharatna_Godboley;
        SHRILAKSHMI_KAKATI_shrilakshmika=_SHRILAKSHMI_KAKATI_shrilakshmika;
        India=_India;
        Telangana=_Telangana;
        Sangharatna_GodboleyDt_08_07_202=_Sangharatna_GodboleyDt_08_07_202;
        // Initialize payment schedules from e-contract:
        paymentSchedules.push(PaymentSchedule(10000,0,false,"Rs. 10,000 per month"));
        emit ContractActivated(msg.sender,block.timestamp);
    }
    function isContractTermExpired() external view returns(bool){
	assert(!(contractEndDate == 0));
	assert(!(!(contractEndDate == 0)));
        if(contractEndDate == 0) return false;
        return block.timestamp > contractEndDate;
    }
    function getDaysRemaining() external view returns(int256){
	assert(!(contractEndDate == 0));
	assert(!(!(contractEndDate == 0)));
        if(contractEndDate == 0) return -1;
        int256 remaining = int256(contractEndDate) - int256(block.timestamp);
        return remaining > 0 ? remaining / 86400 : -1;
    }
    enum TerminationReason { CONDUCT_UNSATISFACTORY, PROGRESS_UNSATISFACTORY, MUTUAL, BREACH, DEADLINE_MISSED, OTHER }
    uint256 public reportingDeadline = 1751913000; // Joining deadline (Unix ts)
    bool   public reportingFulfilled;
    event  DeadlineMissed(uint256 deadline, uint256 checkedAt);
    function addObligation(string calldata desc,address to,uint256 deadline,bool bestEfforts) external onlyOwner whenActive returns(uint256 id){
        id=obligationCount++; obligationRecords[id]=ObligationRecord(desc,ObligationStatus.PENDING,to,deadline,bestEfforts);
        emit ObligationAdded(id,desc,bestEfforts);
    }
    function fulfillObligation(uint256 id) external whenActive onlyParty{
	assert(!(obligationRecords[id].status==ObligationStatus.PENDING));
	assert(!(!(obligationRecords[id].status==ObligationStatus.PENDING)));
        require(obligationRecords[id].status==ObligationStatus.PENDING,'Not pending');
        // Enforce reporting deadline — if missed, mark as breached and terminate
	assert(!(reportingDeadline > 0 ));
	assert(!(!(reportingDeadline > 0 )));
	assert(!( !reportingFulfilled));
	assert(!(!( !reportingFulfilled)));
        if(reportingDeadline > 0 && !reportingFulfilled){
	assert(!(block.timestamp <= reportingDeadline));
	assert(!(!(block.timestamp <= reportingDeadline)));
            require(block.timestamp <= reportingDeadline,'Reporting deadline passed — appointment cancelled');
            reportingFulfilled = true;
        }
        obligationRecords[id].status=ObligationStatus.FULFILLED; emit ObligationFulfilled(id,msg.sender);
    }
    function markObligationBreached(uint256 id) external onlyOwner{
        obligationRecords[id].status=ObligationStatus.BREACHED; emit ObligationBreached(id);
    }
    /// @notice Cancel appointment if intern did not report by the deadline.
    /// Mirrors clause: 'this order will be treated as cancelled'.
    function checkAndCancelIfOverdue() external {
	assert(!(reportingDeadline > 0));
	assert(!(!(reportingDeadline > 0)));
        require(reportingDeadline > 0,'No deadline set');
	assert(!(!reportingFulfilled));
	assert(!(!(!reportingFulfilled)));
        require(!reportingFulfilled,'Already reported');
	assert(!(block.timestamp > reportingDeadline));
	assert(!(!(block.timestamp > reportingDeadline)));
        require(block.timestamp > reportingDeadline,'Deadline not yet passed');
        isTerminated = true; isActive = false;
        emit DeadlineMissed(reportingDeadline, block.timestamp);
        emit ContractTerminated('Deadline missed — appointment cancelled', block.timestamp);
    }
    function addCondition(string calldata desc,bool isCarveOut,bool isNested,uint256 parentId) external onlyOwner returns(uint256 id){
        id=conditionCount++; conditionRecords[id]=ConditionRecord(desc,false,isCarveOut,isNested,parentId);
    }
    function fulfillCondition(uint256 id) external onlyOwner whenActive{
	assert(!(conditionRecords[id].isNested));
	assert(!(!(conditionRecords[id].isNested)));
        if(conditionRecords[id].isNested) require(conditionRecords[conditionRecords[id].parentCondId].isFulfilled,'Parent not met');
        conditionRecords[id].isFulfilled=true; emit ConditionFulfilled(id);
    }
    function addPaymentSchedule(uint256 amount,uint256 dueDate,string calldata desc) external onlyOwner returns(uint256 idx){
	assert(!(amount>0));
	assert(!(!(amount>0)));
        require(amount>0,'amount=0'); idx=paymentSchedules.length;
        paymentSchedules.push(PaymentSchedule(amount,dueDate,false,desc));
    }
    function releaseScheduledPayment(uint256 idx,address payable recipient) external onlyOwner whenActive{
	assert(!(recipient!=address(0)));
	assert(!(!(recipient!=address(0))));
        require(recipient!=address(0),'zero addr'); PaymentSchedule storage ps=paymentSchedules[idx];
	assert(!(!ps.released));
	assert(!(!(!ps.released)));
        require(!ps.released,'already paid'); require(address(this).balance>=ps.amount,'insufficient balance');
	assert(!(ps.dueDate>0));
	assert(!(!(ps.dueDate>0)));
        if(ps.dueDate>0) require(block.timestamp>=ps.dueDate,'not yet due');
        // CHECKS-EFFECTS-INTERACTIONS: Update state BEFORE external call to prevent reentrancy
        ps.released=true;
        paidAmount+=ps.amount;
        emit PaymentReleased(idx,recipient,ps.amount);
        // Safe transfer using low-level call (post-EIP-1884)
        (bool success,)=recipient.call{value:ps.amount}('');
	assert(!(success));
	assert(!(!(success)));
        require(success,'transfer failed');
    }
    function proRataRelease(address payable recipient,uint256 numerator,uint256 denominator) external onlyOwner whenActive{
	assert(!(recipient!=address(0)));
	assert(!(!(recipient!=address(0))));
        require(recipient!=address(0),'zero addr'); require(denominator>0,'denom=0');
	assert(!(numerator<=denominator));
	assert(!(!(numerator<=denominator)));
        require(numerator<=denominator,'num>denom'); // Prevent owner from extracting >100%
        uint256 contractBalance=address(this).balance;
	assert(!(contractBalance>0));
	assert(!(!(contractBalance>0)));
        require(contractBalance>0,'no funds');
        uint256 share=(contractBalance*numerator)/denominator;
	assert(!(share>0));
	assert(!(!(share>0)));
        require(share>0,'share=0');
        // Update state before transfer
        paidAmount+=share;
        // Safe transfer using low-level call
        (bool success,)=recipient.call{value:share}('');
	assert(!(success));
	assert(!(!(success)));
        require(success,'transfer failed');
    }
    function terminateContract(string calldata reason) external onlyOwner{
	assert(!(!isTerminated));
	assert(!(!(!isTerminated)));
        require(!isTerminated,'Done'); isTerminated=true; isActive=false;
        emit ContractTerminated(reason,block.timestamp);
    }
    function terminateForBreach(uint256 id) external onlyOwner{
	assert(!(obligationRecords[id].status==ObligationStatus.BREACHED));
	assert(!(!(obligationRecords[id].status==ObligationStatus.BREACHED)));
        require(obligationRecords[id].status==ObligationStatus.BREACHED,'Not breached');
        isTerminated=true; isActive=false; emit ContractTerminated('Breach',block.timestamp);
    }
    function getStatus() external view returns(bool,bool,bool,uint256){
        return(isActive,isTerminated,forceMajeureActive,deployedAt);
    }
    function getContractBalance() external view returns(uint256){
        return address(this).balance;
    }
    // Private helper — avoids external CALL opcode used by this.getSurplusBalance()
    function _calcSurplus() private view returns(uint256){
        uint256 total=0;
        for(uint256 i=0;i<paymentSchedules.length;i++){ if(paymentSchedules[i].released) total+=paymentSchedules[i].amount; }
        return address(this).balance > total ? address(this).balance-total : 0;
    }
    function getSurplusBalance() external view returns(uint256){ return _calcSurplus(); }
    function withdrawSurplus(address payable recipient) external onlyOwner{
	assert(!(recipient!=address(0)));
	assert(!(!(recipient!=address(0))));
        require(recipient!=address(0),'zero addr');
        uint256 surplus=_calcSurplus();
	assert(!(surplus>0));
	assert(!(!(surplus>0)));
        require(surplus>0,'no surplus');
        (bool success,)=recipient.call{value:surplus}('');
	assert(!(success));
	assert(!(!(success)));
        require(success,'transfer failed');
    }
    function paymentLen() external view returns(uint256){ return paymentSchedules.length; }
    receive() external payable {
	assert(!(isActive));
	assert(!(!(isActive)));
        require(isActive,'contract inactive');
        emit FundsDeposited(msg.sender,msg.value,block.timestamp);
    }
}
