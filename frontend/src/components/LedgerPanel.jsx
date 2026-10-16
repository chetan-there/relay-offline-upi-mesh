function shortHash(hash) {
  return hash ? `${hash.slice(0, 10)}…${hash.slice(-6)}` : "—";
}

const BADGE_CLASS = {
  SETTLED: "badge--settled",
  DUPLICATE_DROPPED: "badge--duplicate",
  INVALID: "badge--invalid",
  REJECTED: "badge--rejected",
};

export default function LedgerPanel({ accounts, transactions, flushResults }) {
  return (
    <section className="panel panel--ledger" aria-labelledby="ledger-heading">
      <h2 id="ledger-heading" className="panel-title">Settled state</h2>

      <h3 className="panel-subtitle">Balances</h3>
      <table className="table">
        <thead><tr><th>Account</th><th>Balance</th></tr></thead>
        <tbody>
          {accounts.map((a) => (
            <tr key={a.id}>
              <td>{a.label}</td>
              <td className="amount-cell">₹{a.balance.toLocaleString("en-IN")}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="panel-subtitle">Transaction ledger</h3>
      <div className="table-scroll">
        <table className="table">
          <thead><tr><th>#</th><th>From → To</th><th>Amount</th><th>Packet hash</th></tr></thead>
          <tbody>
            {transactions.map((t) => (
              <tr key={t.id}>
                <td>{t.id}</td>
                <td>{t.sender} → {t.receiver}</td>
                <td className="amount-cell">₹{t.amount.toLocaleString("en-IN")}</td>
                <td className="hash-cell" title={t.packetHash}>{shortHash(t.packetHash)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {transactions.length === 0 && (
          <p className="empty-state">No settlements yet — inject a payment and flush the bridge to see one land here.</p>
        )}
      </div>

      <h3 className="panel-subtitle">Last flush results</h3>
      <ul className="result-list">
        {(!flushResults || flushResults.length === 0) && (
          <li className="result-item result-item--muted">Nothing flushed yet.</li>
        )}
        {flushResults?.map((r, i) => (
          <li className="result-item" key={i}>
            <span>{r.bridgeId} · {shortHash(r.packetHash)}</span>
            <span className={`badge ${BADGE_CLASS[r.outcome] ?? ""}`}>{r.outcome?.replace("_", " ")}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
