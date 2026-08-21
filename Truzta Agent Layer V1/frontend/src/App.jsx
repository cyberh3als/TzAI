import { useEffect, useState } from "react";
import { AgentChat } from "./AgentChat.jsx";
import { GapQuestions } from "./GapQuestions.jsx";
import { Onboarding } from "./Onboarding.jsx";
import { api } from "./api.js";

export default function App() {
  const [screen, setScreen] = useState("home");
  const [frameworks, setFrameworks] = useState([]);
  const [clients, setClients] = useState([]);
  const [client, setClient] = useState(null);
  const [controls, setControls] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.frameworks(), api.clients()])
      .then(([availableFrameworks, availableClients]) => { setFrameworks(availableFrameworks); setClients(availableClients); })
      .catch((err) => setError(err.message));
  }, []);

  async function chooseClient(clientId) {
    try {
      const [chosenClient, applicableControls] = await Promise.all([api.client(clientId), api.controls(clientId)]);
      setClient(chosenClient);
      setControls(applicableControls);
      setScreen("workspace");
    } catch (err) { setError(err.message); }
  }

  function createdClient(result) {
    const created = result.client;
    setClient(created);
    setControls(result.applicable_controls);
    setClients([{ client_id: created.client_id, organization_name: created.organization.name, frameworks: created.compliance.target_frameworks, updated_at: created.updated_at }, ...clients]);
    setScreen("workspace");
  }

  return <>
    <header><button className="brand-button" onClick={() => setScreen(client ? "workspace" : "home")}>truzta</button><span className="badge">Developer preview</span></header>
    <main>
      {screen === "home" && <Home hasClients={clients.length > 0} ready={frameworks.length > 0} create={() => setScreen("onboarding")} choose={() => setScreen("clients")}/>} 
      {screen === "clients" && <ClientChooser clients={clients} choose={chooseClient} back={() => setScreen("home")}/>} 
      {screen === "onboarding" && <Onboarding frameworks={frameworks} createClient={api.createClient} onBack={() => setScreen("home")} onComplete={createdClient}/>} 
      {screen === "workspace" && client && <Workspace client={client} controls={controls} open={setScreen} changeClient={() => setScreen("clients")}/>}
      {screen === "gap" && client && <GapQuestions client={client} onBack={() => setScreen("workspace")}/>}
      {["risk", "policy"].includes(screen) && <AgentChat agent={screen} onBack={() => setScreen("workspace")}/>}
      {error && <p className="error">{error}</p>}
    </main>
    <footer>Local developer prototype · YAML memory is editable</footer>
  </>;
}

function Home({ hasClients, ready, create, choose }) {
  return <section className="hero"><p className="eyebrow">Compliance, made manageable.</p><h1>Choose or create<br/>a client.</h1><p className="lede">Client workspaces keep organisation context separate for every assessment.</p><div className="agent-buttons"><button disabled={!ready} onClick={create}>Create new client →</button><button className="outline" disabled={!hasClients} onClick={choose}>Choose existing client</button></div></section>;
}

function ClientChooser({ clients, choose, back }) {
  return <section className="flow"><p className="eyebrow">Existing clients</p><h2>Choose a workspace.</h2><div className="client-list">{clients.map((item) => <button className="client-card" key={item.client_id} onClick={() => choose(item.client_id)}><strong>{item.organization_name}</strong><span>{item.frameworks.join(", ")}</span></button>)}</div><button className="secondary" onClick={back}>Back</button></section>;
}

function Workspace({ client, controls, open, changeClient }) {
  return <section className="hero">
    <p className="eyebrow">Client workspace</p>
    <h1>{client.organization.name}</h1>
    <p className="lede">Choose the focused workflow you want to run for this client.</p>
    <div className="agent-buttons"><button onClick={() => open("gap")}>Gap chat</button><button onClick={() => open("risk")}>Risk chat</button><button onClick={() => open("policy")}>Policy review chat</button></div>
    <button className="secondary" onClick={changeClient}>Change client</button>
    <ControlsSummary client={client} controls={controls}/>
  </section>;
}

function ControlsSummary({ client, controls }) {
  return <div className="workspace">
    <p className="eyebrow">Applicable controls</p>
    <p className="hint">{controls.length} SCF controls apply across {client.compliance.target_frameworks.join(", ")}, based on {client.organization.name}'s profile.</p>
    <div className="client-list">
      {controls.slice(0, 20).map((control) => (
        <div className="client-card" key={control.scf_id}>
          <strong>{control.scf_id} — {control.scf_control_name}</strong>
          <span>{control.matched_frameworks.join(", ")}</span>
        </div>
      ))}
    </div>
    {controls.length > 20 && <p className="hint">...and {controls.length - 20} more.</p>}
  </div>;
}
