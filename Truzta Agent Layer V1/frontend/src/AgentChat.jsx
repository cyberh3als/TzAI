const descriptions = {
  gap: "Gap assessment chat will appear here after its input and output contract is approved.",
  risk: "Risk assessment chat will appear here after its input and output contract is approved.",
  policy: "Policy review chat will appear here after its input and output contract is approved.",
};

export function AgentChat({ agent, onBack }) {
  return <section className="hero">
    <p className="eyebrow">{agent} agent</p>
    <h1>Coming next.</h1>
    <p className="lede">{descriptions[agent]}</p>
    <button onClick={onBack}>Back to workspace</button>
  </section>;
}
