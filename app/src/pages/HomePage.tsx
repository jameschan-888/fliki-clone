import { useState } from "react";
import { EnvCheckBadge } from "../components/layout/EnvCheckBadge";
import { ProviderKeyManager } from "../components/editor/ProviderKeyManager";
import App from "../App";

export function HomePage() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  return (
    <>
      <nav>
        <a href="#" onClick={(e) => { e.preventDefault(); location.reload(); }}>Fliki 还原</a>
        <div className="navRight">
          <EnvCheckBadge />
          <button type="button" className="textButton" onClick={() => setSettingsOpen(true)}>设置</button>
        </div>
      </nav>
      <App />
      <ProviderKeyManager open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}