// Plain words for the AI's codes. The codes stay what's stored and scored; people see these.
export const INTENTS = {
  portal_access: "Can't get into the portal",
  status_payment: "Asking about a payment",
  status_document: "Did you get my documents?",
  form_question: "Question about a form",
  address_change: "Change of address",
  direct_deposit_change: "Change of bank details",
  records_request: "Wants a copy of their records",
  congressional: "A member of Congress is asking",
  complaint: "Complaint",
  overpayment: "Told they were overpaid",
  welfare: "Someone may be at risk",
  urgent_hardship: "Urgent hardship",
  other: "Something else",
};
export const TEAMS = {
  portal_support: "Portal support",
  accounts: "Accounts",
  payments: "Payments",
  correspondence: "Letters & inquiries",
  documents: "Documents",
  general: "General",
  escalations: "Escalations",
};
export const URGENCY = { 1: "1 · can wait", 2: "2 · normal", 3: "3 · soon", 4: "4 · today if possible", 5: "5 · act now" };
export const MOODS = { calm: "Calm", "mildly frustrated": "A bit frustrated", frustrated: "Frustrated", worried: "Worried", anxious: "Anxious" };
export const NEXT_STEP = { standard: "Usual queue", "follow-up": "Follow up personally" };
// deadline-bound requests: what each is, and how long there is (flags.POLICY, in business days)
export const DEADLINES = {
  congressional: ["Congressional inquiry", "a congressional office wants a written answer within 5 business days"],
  records: ["Records request", "a request for records, answered within 20 business days"],
  legal: ["Legal deadline", "the caller named a legal date; 2 business days to act"],
  welfare: ["Welfare", "someone's safety or basic needs may be at risk; reach them within 1 business day, today if at all possible"],
  discrimination: ["Discrimination complaint", "a discrimination complaint, answered within 10 business days"],
};
export const FIELDS = {
  caller: "Caller's name",
  callbackNumber: "Call back on",
  caseId: "Case number",
  program: "Benefit program",
  requestedAction: "What they want done",
};
// "status_payment" -> "Status payment", for anything without a word of its own
export const plain = (code) => (code == null ? "" : String(code).replace(/[_-]+/g, " ").replace(/^./, (c) => c.toUpperCase()));
export const word = (map, code) => map[code] ?? plain(code);
