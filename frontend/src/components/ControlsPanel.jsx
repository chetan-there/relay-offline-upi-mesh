import { useState } from "react";

export default function ControlsPanel({ accounts, onSend, onGossip, onFlush, onReset }) {
  const [sender, setSender] = useState("alice");
  const [receiver, setReceiver] = useState("bob");
  const [amount, setAmount] = useState(500);
  const [pin, setPin] = useState("1234");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null); // "send" | "gossip" | "flush" | "reset" | null

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    if (sender === receiver) {
      setError("Sender and receiver must be different accounts.");
      return;
    }
    setBusy("send");
    try {
      await onSend({ sender, receiver, amount: Number(amount), pin });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  async function handleGossip() {
    setBusy("gossip");
    try {
      await onGossip();
    } finally {
      setBusy(null);
    }
  }

  async function handleFlush() {
    setBusy("flush");
    try {
      await onFlush();
    } finally {
      setBusy(null);
    }
  }

  async function handleReset() {
    setBusy("reset");
    try {
      await onReset();
      setError(null);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="panel panel--controls" aria-labelledby="pipeline-heading">
      <h2 id="pipeline-heading" className="panel-title">Run the pipeline</h2>
      <p className="panel-hint">Four steps, same order every real delivery follows.</p>

      <form className="stepblock" onSubmit={handleSubmit}>
        <div className="step-head">
          <span className="step-num">01</span>
          <h3>Compose a payment</h3>
        </div>
        <p className="step-desc">
          Encrypted on Alice's phone with the backend's public key. Nobody carrying it can read the amount.
        </p>

        <label className="field">
          <span>From</span>
          <select value={sender} onChange={(e) => setSender(e.target.value)} required>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>{a.label}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>To</span>
          <select value={receiver} onChange={(e) => setReceiver(e.target.value)} required>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>{a.label}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Amount (₹)</span>
          <input type="number" min="1" step="1" value={amount} onChange={(e) => setAmount(e.target.value)} required />
        </label>
        <label className="field">
          <span>PIN</span>
          <input type="password" minLength={4} maxLength={6} value={pin} onChange={(e) => setPin(e.target.value)} required />
        </label>

        <button type="submit" className="btn btn--primary" disabled={busy === "send"}>
          {busy === "send" ? "Encrypting…" : "Inject into mesh"}
        </button>
        {error && <p className="field-error" role="alert">{error}</p>}
      </form>

      <div className="stepblock">
        <div className="step-head">
          <span className="step-num">02</span>
          <h3>Run a gossip round</h3>
        </div>
        <p className="step-desc">
          Every phone holding the packet broadcasts it to every phone nearby. Run it twice to reach the whole mesh.
        </p>
        <button type="button" className="btn" onClick={handleGossip} disabled={busy === "gossip"}>
          {busy === "gossip" ? "Broadcasting…" : "Run gossip round"}
        </button>
      </div>

      <div className="stepblock">
        <div className="step-head">
          <span className="step-num">03</span>
          <h3>Bridge walks outside</h3>
        </div>
        <p className="step-desc">Any phone with a signal uploads everything it's carrying to the backend for settlement.</p>
        <button type="button" className="btn" onClick={handleFlush} disabled={busy === "flush"}>
          {busy === "flush" ? "Uploading…" : "Bridges upload to backend"}
        </button>
      </div>

      <div className="stepblock">
        <button type="button" className="btn btn--ghost" onClick={handleReset} disabled={busy === "reset"}>
          Reset mesh + ledger
        </button>
      </div>
    </section>
  );
}
