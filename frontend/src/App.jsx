import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import Topbar from "./components/Topbar.jsx";
import ControlsPanel from "./components/ControlsPanel.jsx";
import MeshPanel from "./components/MeshPanel.jsx";
import LedgerPanel from "./components/LedgerPanel.jsx";
import Explainer from "./components/Explainer.jsx";

export default function App() {
  const [accounts, setAccounts] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [meshState, setMeshState] = useState({ devices: [], log: [] });
  const [flushResults, setFlushResults] = useState([]);
  const [connected, setConnected] = useState(true);

  const refreshAll = useCallback(async () => {
    try {
      const [acc, tx, mesh] = await Promise.all([
        api.getAccounts(),
        api.getTransactions(),
        api.getMeshState(),
      ]);
      setAccounts(acc);
      setTransactions(tx);
      setMeshState(mesh);
      setConnected(true);
    } catch (err) {
      console.error(err);
      setConnected(false);
    }
  }, []);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  async function handleSend(body) {
    const { meshState: newMesh } = await api.sendPayment(body);
    setMeshState(newMesh);
    setConnected(true);
  }

  async function handleGossip() {
    const { meshState: newMesh } = await api.runGossip();
    setMeshState(newMesh);
    setConnected(true);
  }

  async function handleFlush() {
    const { results, meshState: newMesh, accounts: newAccounts, transactions: newTx } = await api.flushBridges();
    setMeshState(newMesh);
    setAccounts(newAccounts);
    setTransactions(newTx);
    setFlushResults(results);
    setConnected(true);
  }

  async function handleReset() {
    const { meshState: newMesh, accounts: newAccounts, transactions: newTx } = await api.reset();
    setMeshState(newMesh);
    setAccounts(newAccounts);
    setTransactions(newTx);
    setFlushResults([]);
    setConnected(true);
  }

  return (
    <>
      <div className="noise"></div>
      <Topbar connected={connected} />
      <main className="layout">
        <ControlsPanel
          accounts={accounts}
          onSend={handleSend}
          onGossip={handleGossip}
          onFlush={handleFlush}
          onReset={handleReset}
        />
        <MeshPanel meshState={meshState} />
        <LedgerPanel accounts={accounts} transactions={transactions} flushResults={flushResults} />
      </main>
      <Explainer />
    </>
  );
}
