export default function Topbar({ connected }) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true"></span>
        <div>
          <div className="brand-name">Relay</div>
          <div className="brand-sub">offline UPI, settled through strangers' phones</div>
        </div>
      </div>
      <div className="topbar-status">
        <span className={`dot ${connected ? "dot--live" : "dot--down"}`} aria-hidden="true"></span>
        {connected ? "connected to backend" : "backend unreachable"}
      </div>
    </header>
  );
}
