// One field definition for new registration and historical FIR snapshots.
export const FIR_SOURCES = [
  ["TELEVISION", "Television"], ["NEWSPAPER", "Newspaper"], ["MEDICAL_CAMPS", "Medical Camps"],
  ["SIGN_BOARDS", "Sign Boards"], ["BANNERS", "Banners"], ["NEARBY_RESIDENCE", "Nearby Residence"],
  ["SOCIAL_MEDIA", "Social Media"], ["YOUTUBE", "YouTube"], ["FACEBOOK", "Facebook"], ["INSTAGRAM", "Instagram"],
  ["ONLINE_SEARCH", "Online Search"], ["REFERRAL", "Referral"], ["OTHERS", "Others"],
];
export const EMPTY_FIR = {
  first_name: "", last_name: "", gender: "MALE", age: "", marital_status: "SINGLE", phone: "", address: "",
  height_cm: "", weight_kg: "", consulting_doctor_id: "", sources: [], referral_name: "", chief_complaint: "",
  visit_type: "WALK_IN", preferred_language: "EN",
};
export const FIRField = ({ label, required, hint, children }) => <div>
  <label className="text-xs uppercase tracking-wider font-semibold text-gray-500 block mb-1.5">{label}{required && <span className="text-red-500 ml-0.5">*</span>}</label>
  {children}{hint && <div className="text-[11px] text-gray-400 mt-1">{hint}</div>}
</div>;
const Section = ({ title, subtitle, children }) => <div className="bg-white border border-gray-200 rounded-md p-6 space-y-4"><div><div className="font-display font-semibold text-base text-gray-900">{title}</div>{subtitle && <div className="text-xs text-gray-500 mt-0.5">{subtitle}</div>}</div>{children}</div>;

export const FIRFields = ({ form, onChange, doctors, photoSlot }) => {
  const edit = (key, value) => onChange({ ...form, [key]: value });
  const h = parseFloat(form.height_cm), w = parseFloat(form.weight_kg);
  const bmi = h > 0 && w > 0 ? (w / ((h / 100) ** 2)).toFixed(1) : "";
  const text = (key, testId, props = {}) => <input className="input" value={form[key] ?? ""} onChange={e => edit(key, e.target.value)} data-testid={testId} {...props} />;
  const select = (key, testId, options) => <select className="input" value={form[key]} onChange={e => edit(key, e.target.value)} data-testid={testId}>{options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>;
  return <>
    <Section title="Patient Information">
      {photoSlot}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <FIRField label="First name" required>{text("first_name", "first-name-input", { required: true })}</FIRField>
        <FIRField label="Last name">{text("last_name", "last-name-input")}</FIRField>
        <FIRField label="Age" required>{text("age", "age-input", { type: "number", min: 0, max: 150, required: true, className: "input tabular-nums" })}</FIRField>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <FIRField label="Gender" required>{select("gender", "gender-select", [["MALE", "Male"], ["FEMALE", "Female"], ["OTHER", "Other"]])}</FIRField>
        <FIRField label="Marital status">{select("marital_status", "marital-select", [["SINGLE", "Single"], ["MARRIED", "Married"], ["DIVORCED", "Divorced"], ["WIDOWED", "Widowed"], ["OTHER", "Other"]])}</FIRField>
        <FIRField label="Language">{select("preferred_language", "language-select", [["EN", "English"], ["TE", "Telugu"]])}</FIRField>
      </div>
      <FIRField label="Phone number" required>{text("phone", "phone-input", { required: true, className: "input tabular-nums" })}</FIRField>
      <FIRField label="Address"><textarea rows={2} className="input" value={form.address} onChange={e => edit("address", e.target.value)} data-testid="address-input" /></FIRField>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <FIRField label="Height (cm)" hint="in centimeters, e.g. 170">{text("height_cm", "height-input", { type: "number", step: "1", min: "20", max: "300", placeholder: "170", className: "input tabular-nums" })}</FIRField>
        <FIRField label="Weight (kg)" hint="in kilograms, e.g. 65">{text("weight_kg", "weight-input", { type: "number", step: "0.1", min: "1", max: "500", placeholder: "65", className: "input tabular-nums" })}</FIRField>
        <FIRField label="BMI (auto)"><input className="input bg-gray-50 tabular-nums" value={bmi} readOnly placeholder="—" data-testid="bmi-display" /></FIRField>
      </div>
      <FIRField label="Consulting doctor" required><select className="input" value={form.consulting_doctor_id} onChange={e => edit("consulting_doctor_id", e.target.value)} required data-testid="consulting-doctor-select"><option value="">— Select —</option>{doctors.map(d => <option key={d.id} value={d.id}>{d.display_name}</option>)}</select></FIRField>
    </Section>
    <Section title="How did you know about us?" subtitle="Select all that apply">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2" data-testid="sources-grid">{FIR_SOURCES.map(([value, label]) => <label key={value} className={`flex items-center gap-2 px-3 py-2 border rounded-md text-sm cursor-pointer transition ${form.sources.includes(value) ? "bg-teal-50 border-teal-300 text-teal-900" : "border-gray-200 hover:bg-gray-50"}`}><input type="checkbox" checked={form.sources.includes(value)} onChange={() => edit("sources", form.sources.includes(value) ? form.sources.filter(s => s !== value) : [...form.sources, value])} className="accent-teal-700" data-testid={`source-${value}`} />{label}</label>)}</div>
      {(form.sources.includes("REFERRAL") || form.sources.includes("OTHERS")) && <FIRField label="Referral person name">{text("referral_name", "referral-name-input")}</FIRField>}
    </Section>
    <Section title="Medical Information">
      <FIRField label="Nature of health problem / chief complaint" required><textarea rows={3} className="input" value={form.chief_complaint} onChange={e => edit("chief_complaint", e.target.value)} required data-testid="chief-complaint-input" /></FIRField>
      <FIRField label="Visit type" required><div className="flex gap-3">{["WALK_IN", "APPOINTMENT"].map(v => <label key={v} className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 border rounded-md text-sm cursor-pointer ${form.visit_type === v ? "bg-teal-50 border-teal-300 text-teal-900 font-medium" : "border-gray-200 hover:bg-gray-50"}`}><input type="radio" name="visit_type" value={v} checked={form.visit_type === v} onChange={() => edit("visit_type", v)} className="accent-teal-700" data-testid={`visit-type-${v}`} />{v === "WALK_IN" ? "Walk-in" : "Appointment"}</label>)}</div></FIRField>
    </Section>
  </>;
};