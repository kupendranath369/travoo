// Draft legal content (English). Requires professional legal review before launch in any region.
export const LEGAL_DOCS: Record<string, [string, string][]> = {
  terms: [
    ["1. About Travoo", "Travoo is a technology platform that connects drivers travelling between destinations with passengers who wish to share the journey and its costs. Travoo is not a transport operator and does not own, operate or control vehicles."],
    ["2. Accounts", "You must provide accurate information, keep your password secure and be at least 18 years old. One account may act as both passenger and driver."],
    ["3. Payments", "Passengers pay drivers directly by Cash or UPI. Travoo does not collect, hold, process, verify or refund any payment and charges no commission at present."],
    ["4. Conduct", "Users must behave respectfully, follow traffic laws and must not use Travoo for commercial taxi services where prohibited by law."],
    ["5. Liability", "Travoo is not a party to the agreement between driver and passenger. To the extent permitted by law, Travoo is not liable for the conduct of users."],
    ["6. Suspension", "Travoo may suspend accounts that violate these terms or receive credible safety reports."],
  ],
  privacy: [
    ["Data we collect", "Name, email, mobile number, language, trip and booking records, messages, ratings and, for drivers, licence and vehicle registration details."],
    ["Why we use it", "To run bookings, verify drivers, keep the platform safe, provide support and meet legal obligations (Digital Personal Data Protection Act, 2023)."],
    ["Sharing", "Phone numbers are shared between driver and passenger only after a booking is confirmed. Document numbers are masked and visible only to admins."],
    ["Your rights", "You may access, correct or request erasure of your data and withdraw consent by contacting grievance@travoo.in."],
  ],
  driver: [
    ["Eligibility", "Valid driving licence, valid registration certificate, valid insurance and roadworthy vehicle are required."],
    ["Cost sharing", "Prices should reflect a fair share of trip costs. Operating as a commercial transport service may require permits under the Motor Vehicles Act, 1988 and state rules."],
    ["Responsibilities", "Drive safely, honour confirmed bookings, mark fares received truthfully and cancel only when unavoidable."],
  ],
  passenger: [
    ["Bookings", "Arrive at the pickup point on time, carry ID and respect the driver's vehicle rules."],
    ["Payment", "Pay the agreed fare directly to the driver by Cash or UPI."],
    ["Cancellations", "Cancel as early as possible through the app so the seat can be offered to others."],
  ],
  cancellation: [
    ["Passengers", "Passengers may cancel free of charge up to the deadline configured by Travoo (default 6 hours before departure). Late cancellations may affect your rating."],
    ["Drivers", "Drivers should cancel at least 12 hours before departure. All passengers are notified automatically."],
    ["Refunds", "Because payments are made directly to drivers, Travoo does not process refunds. Any refund agreed between driver and passenger is recorded for reference only."],
  ],
  compliance: [
    ["Vehicle permits", "Private (white-plate) vehicles carrying paying passengers may be considered as operating a transport service without a permit in some states. Obtain legal opinion per state."],
    ["Aggregator rules", "Motor Vehicle Aggregator Guidelines, 2020 and state aggregator policies may apply. Licensing requirements must be reviewed before launch."],
    ["Insurance", "Confirm that drivers' motor insurance covers passengers in cost-sharing arrangements."],
    ["Taxation", "Review GST and income-tax implications for drivers and for any future platform fees."],
    ["Data protection", "DPDP Act, 2023: consent records, grievance officer, data retention and breach-reporting processes."],
    ["IT Rules", "Information Technology (Intermediary Guidelines) Rules, 2021: grievance redressal timelines and user notices."],
    ["State restrictions", "Paid intercity carpooling is not automatically permitted in all states. Legal review is required before launching in each region."],
  ],
};
