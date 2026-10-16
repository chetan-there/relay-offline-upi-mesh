export default function Explainer() {
  return (
    <footer className="explainer" aria-labelledby="explainer-heading">
      <h2 id="explainer-heading">Why a packet delivered by three strangers still settles once</h2>
      <div className="explainer-grid">
        <div className="explainer-card">
          <h3>Untrusted carriers</h3>
          <p>
            The payload is encrypted with the backend's public key before it ever leaves the sender's phone
            (RSA-OAEP wraps a one-time AES-256 key; AES-256-GCM encrypts the payload). Every phone in between
            only ever holds opaque bytes.
          </p>
        </div>
        <div className="explainer-card">
          <h3>The duplicate storm</h3>
          <p>
            The instant a packet arrives, the backend hashes the ciphertext and atomically claims that hash.
            The first claimer proceeds to settle; every later delivery of the same packet — even microseconds
            later — is dropped before it touches a balance.
          </p>
        </div>
        <div className="explainer-card">
          <h3>Replay defense</h3>
          <p>
            Each payload carries a nonce and a signed timestamp, both inside the encryption. Packets older
            than 24 hours are rejected, and a captured-and-replayed packet is caught by the same hash claim
            used for duplicates.
          </p>
        </div>
      </div>
    </footer>
  );
}
