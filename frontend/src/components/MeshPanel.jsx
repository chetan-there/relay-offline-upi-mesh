const DEVICE_ROLE = {
  "phone-alice": "Origin — sender's phone",
  "phone-stranger1": "Passing stranger",
  "phone-stranger2": "Passing stranger",
  "phone-bridge": "Has a signal",
  "phone-bob": "Receiver's phone",
};

export default function MeshPanel({ meshState }) {
  const devices = meshState?.devices ?? [];
  const log = meshState?.log ?? [];

  return (
    <section className="panel panel--mesh" aria-labelledby="mesh-heading">
      <h2 id="mesh-heading" className="panel-title">Mesh state</h2>
      <div className="mesh-grid">
        {devices.map((d) => {
          const active = d.packetCount > 0;
          return (
            <div key={d.id} className={`mesh-device ${active ? "has-packets" : ""}`}>
              <div className="mesh-device-top">
                <span className="mesh-device-name">{d.label}</span>
                <span
                  className={`mesh-signal ${d.hasInternet ? "online" : ""}`}
                  title={d.hasInternet ? "has internet" : "offline"}
                ></span>
              </div>
              <div className="mesh-device-role">{DEVICE_ROLE[d.id] ?? ""}</div>
              <div className={`mesh-packet-count ${active ? "active" : ""}`}>{d.packetCount}</div>
              <div className="mesh-packet-label">packet{d.packetCount === 1 ? "" : "s"} held</div>
            </div>
          );
        })}
      </div>

      <h3 className="panel-subtitle">Pipeline log</h3>
      <ul className="log-list">
        {log.length === 0 && <li className="log-empty">No activity yet.</li>}
        {log.map((entry, i) => (
          <li key={i}>{entry.message}</li>
        ))}
      </ul>
    </section>
  );
}
