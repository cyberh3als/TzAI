import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";

/** Chat-style gap interview. The server owns the state machine — including the
 *  2-follow-up cap — so this component only renders whatever step it is handed
 *  and posts answers back. It never decides what to ask next. */
export function GapInterview({ client, onComplete }) {
  const [step, setStep] = useState(null);
  const [turns, setTurns] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const tail = useRef(null);

  useEffect(() => {
    let live = true;
    // gapQuestions is the single producer of the questionnaire — it generates on
    // first call and serves the cache forever after. Awaiting it here means the
    // interview always runs against that one set instead of minting its own.
    api.gapQuestions(client.client_id)
      .then(() => api.gapInterview(client.client_id))
      .then((first) => {
        if (!live) return;
        setStep(first);
        if (first.prompt) setTurns([{ role: "agent", text: first.prompt, kind: first.kind }]);
      })
      .catch((err) => live && setError(err.message));
    return () => { live = false; };
  }, [client.client_id]);

  useEffect(() => { tail.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns, busy]);

  async function send(action) {
    if (busy || !step || step.kind === "complete") return;
    const text = draft.trim();
    if (action === "answer" && !text) return;

    setBusy(true);
    setError("");
    setTurns((prior) => [...prior, { role: "client", text: action === "skip" ? "Skipped" : text }]);
    setDraft("");
    try {
      const next = action === "skip"
        ? await api.gapSkip(client.client_id)
        : await api.gapAnswer(client.client_id, text);
      setStep(next);
      if (next.prompt) setTurns((prior) => [...prior, { role: "agent", text: next.prompt, kind: next.kind }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    setBusy(true);
    setError("");
    try {
      await api.gapEvaluate(client.client_id);
      onComplete();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  if (error && !step) return <p className="error">{error}</p>;
  if (!step) return <div className="workspace preparing">
    <div className="spinner" aria-hidden="true"/>
    <strong>Preparing your interview…</strong>
    <p className="hint">If this is a new client we're writing the questions first. That happens once — after this it opens instantly.</p>
  </div>;

  const done = step.kind === "complete";
  const progress = step.total ? Math.round((step.answered / step.total) * 100) : 0;

  return <div className="workspace">
    <div className="progress"><div style={{ width: `${progress}%` }}/></div>
    <p className="hint">{step.answered} of {step.total} answered{step.domain && !done ? ` · ${step.domain}` : ""}</p>

    <div className="chat">
      {turns.map((turn, index) => (
        <div className={`bubble bubble-${turn.role}`} key={index}>
          {turn.kind === "followup" && <span className="tag tag-followup">Follow-up</span>}
          <p>{turn.text}</p>
        </div>
      ))}
      {busy && !done && <div className="bubble bubble-agent"><p className="thinking">Thinking…</p></div>}
      <div ref={tail}/>
    </div>

    {error && <p className="error">{error}</p>}

    {done ? (
      <div className="chat-done">
        <strong>All questions answered.</strong>
        <p className="hint">We'll now review each answer against the controls it covers. This takes a minute or two.</p>
        <button disabled={busy} onClick={finish}>{busy ? "Assessing…" : "Run the assessment →"}</button>
      </div>
    ) : (
      <div className="chat-input">
        <textarea
          value={draft}
          disabled={busy}
          placeholder={step.kind === "followup" ? "Add the detail, or skip…" : "Type your answer…"}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send("answer"); } }}
        />
        <div className="actions">
          <button className="secondary" disabled={busy} onClick={() => send("skip")}>
            {/* Skipping a pending follow-up abandons only the follow-up — whatever
                was already answered for this question is kept and still assessed. */}
            {step.kind === "followup" ? "Skip the follow-ups →" : "Skip this question →"}
          </button>
          <button disabled={busy || !draft.trim()} onClick={() => send("answer")}>Send</button>
        </div>
        {step.answered > 0 && (
          // The evaluator only scores questions that were actually reached, so
          // stopping early yields a valid partial assessment rather than a broken one.
          <button className="link-button" disabled={busy} onClick={finish}>
            {busy ? "Assessing…" : "Finish now — remaining questions count as gaps"}
          </button>
        )}
      </div>
    )}
  </div>;
}
