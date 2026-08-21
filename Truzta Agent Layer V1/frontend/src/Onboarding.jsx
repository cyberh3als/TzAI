import { useMemo, useState } from "react";

const questionGroups = [
  {
    title: "Compliance target",
    questions: [
      { id: "frameworks", label: "Which compliance frameworks are you working towards?", hint: "Select every framework you need to comply with — you can pick more than one.", type: "multi", required: true },
    ],
  },
  {
    title: "Organization",
    questions: [
      { id: "organization_name", label: "What is your organisation called?", hint: "Used to identify your workspace.", type: "text", required: true },
      { id: "employee_range", label: "How many people work at the organisation?", hint: "Include full-time, part-time, and contracted staff.", type: "single", required: true, options: ["1-9", "10-49", "50-249", "250-999", "1000+"] },
      { id: "industry", label: "What industry best describes your business?", hint: "e.g. Fintech, Healthcare, E-commerce, Professional services", type: "text", required: false },
      { id: "countries", label: "Which countries do you operate in, and/or serve customers in?", hint: "This can affect which country-specific privacy laws (e.g. GDPR, PDPA) apply to you.", type: "list", required: true },
      { id: "departments", label: "What are the departments in your organisation?", hint: "e.g. Engineering, Customer Support, Finance", type: "list", required: false },
    ],
  },
  {
    title: "Applicability",
    questions: [
      { id: "sensitive_data", label: "What sensitive data do you handle?", hint: "Select everything that applies — this determines which data-specific controls are relevant to you.", type: "multi", required: true, options: ["Personal data", "Health data", "Payment card data", "Employee data", "Financial data", "None / unsure"] },
      { id: "does_development", label: "Does your organisation build or maintain software?", hint: "Includes any in-house development — your core product or internal tools.", type: "boolean", required: true },
      { id: "work_model", label: "How does your team work?", hint: "Determines whether physical security controls (badges, visitor logs, office access) apply to you.", type: "single", required: true, options: ["Fully on-site", "Fully remote", "Hybrid"] },
    ],
  },
  {
    title: "Technology & infrastructure",
    questions: [
      { id: "identity_provider", label: "What manages employee identities and access?", hint: "e.g. Microsoft Entra ID, Okta, Google Cloud Identity — include SSO, MFA, admin access if relevant.", type: "text", required: false },
      { id: "device_management", label: "Are company laptops and phones centrally managed?", hint: 'e.g. Microsoft Intune, Endpoint Central, Zoho UEM — or "None".', type: "text", required: false },
      { id: "endpoint_protection", label: "What protects employee laptops and servers?", hint: "e.g. Microsoft Defender, SentinelOne, Sophos", type: "text", required: false },
      { id: "password_manager", label: "Do employees use a password manager?", hint: 'e.g. 1Password, Bitwarden, or an enterprise password manager — or "None".', type: "text", required: false },
      { id: "cloud_infrastructure", label: "What cloud infrastructure do you run, and how are production and development environments separated?", hint: "e.g. AWS, GCP, Azure — describe prod/dev separation if any.", type: "textarea", required: false },
      { id: "network_security", label: "How is your corporate and production network protected?", hint: "e.g. firewalls, VPNs, Palo Alto, Fortinet, Cisco, Cloudflare Access", type: "text", required: false },
      { id: "vulnerability_management", label: "What tools do you use for vulnerability scanning and remediation?", hint: 'e.g. Tenable, Nessus, Qualys, Microsoft Defender Vulnerability Management — or "None".', type: "text", required: false },
      { id: "patch_management", label: "How are operating systems and applications patched?", hint: "e.g. Intune, ManageEngine, NinjaOne — include frequency if known.", type: "text", required: false },
      { id: "backup_recovery", label: "What systems and data are backed up, and how often?", hint: "Include backup frequency and recovery time objective if known.", type: "textarea", required: false },
      { id: "email_collaboration", label: "What platform handles company email and document collaboration?", hint: "e.g. Microsoft 365, Google Workspace — note MFA / email security if known.", type: "text", required: false },
      { id: "logging_siem", label: "Where do your security logs go?", hint: 'e.g. Microsoft Sentinel, Splunk Enterprise Security, Google SecOps — or "None".', type: "text", required: false },
    ],
  },
];

function splitList(text) {
  return text.split(",").map((item) => item.trim()).filter(Boolean);
}

function isAnswered(question, value) {
  if (question.type === "boolean") return value !== undefined;
  if (Array.isArray(value)) return value.length > 0;
  return Boolean(value);
}

function ListInput({ value, onChange }) {
  const [text, setText] = useState(() => (value || []).join(", "));
  return <textarea autoFocus value={text} onChange={(event) => {
    setText(event.target.value);
    onChange(splitList(event.target.value));
  }} placeholder="Type your answer here, separated by commas"/>;
}

function Question({ question, value, onChange }) {
  if (["single", "multi"].includes(question.type)) {
    const values = question.type === "multi" ? (Array.isArray(value) ? value : []) : (value === undefined ? [] : [value]);
    const selected = new Set(values);
    return <div className="choices">{question.options.map((option) => (
      <label className="choice" key={option}>
        <input type={question.type === "multi" ? "checkbox" : "radio"} checked={selected.has(option)} onChange={(event) => {
          if (question.type === "single") return onChange(option);
          onChange(event.target.checked ? [...selected, option] : [...selected].filter((item) => item !== option));
        }}/><span>{option}</span>
      </label>
    ))}</div>;
  }
  if (question.type === "boolean") {
    return <div className="choices">{["Yes", "No"].map((label) => {
      const boolValue = label === "Yes";
      return <label className="choice" key={label}>
        <input type="radio" checked={value === boolValue} onChange={() => onChange(boolValue)}/><span>{label}</span>
      </label>;
    })}</div>;
  }
  if (question.type === "list") return <ListInput value={value} onChange={onChange}/>;
  if (question.type === "textarea") return <textarea autoFocus value={value || ""} onChange={(event) => onChange(event.target.value)} placeholder="Type your answer here"/>;
  return <input autoFocus value={value || ""} onChange={(event) => onChange(event.target.value)} placeholder="Type your answer here"/>;
}

export function Onboarding({ frameworks, createClient, onComplete, onBack }) {
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const questions = useMemo(() => questionGroups.flatMap((group) => group.questions.map((question) => (
    question.id === "frameworks" ? { ...question, group: group.title, options: frameworks.map((item) => item.name) } : { ...question, group: group.title }
  ))), [frameworks]);
  const question = questions[index];

  async function next(event) {
    event.preventDefault();
    setError("");
    const value = answers[question.id];
    if (question.required && !isAnswered(question, value)) return setError("Please answer this question.");
    if (index < questions.length - 1) return setIndex(index + 1);
    try {
      setSaving(true);
      onComplete(await createClient(answers));
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return <section className="flow">
    <div className="progress"><div style={{ width: `${((index + 1) / questions.length) * 100}%` }}/></div>
    <p className="eyebrow">{question.group} · Question {index + 1} of {questions.length}</p>
    <form onSubmit={next}>
      <h2>{question.label}</h2>
      <p className="hint">{question.hint}</p>
      <Question key={question.id} question={question} value={answers[question.id]} onChange={(value) => setAnswers({ ...answers, [question.id]: value })}/>
      {error && <p className="error">{error}</p>}
      <div className="actions"><button type="button" className="secondary" onClick={() => index ? setIndex(index - 1) : onBack()}>Back</button><button disabled={saving}>{saving ? "Creating client..." : "Continue →"}</button></div>
    </form>
  </section>;
}
