// CRA Bounded Execution & Governance Check
if (n >= 400) {
  noLoop(); // Hard Operational Halt: Stop frame rendering
  
  emitCRABreachEvent({
    eventCode: "CRA-BREACH-RCI-IV",
    vector: "Resource Envelope Inversion",
    payload: {
      finalT: t,
      finalN: n,
      perimeterState: 400 - n
    }
  });
  
  setGovernanceState("HALTED_AWAITING_CLEARANCE");
}
