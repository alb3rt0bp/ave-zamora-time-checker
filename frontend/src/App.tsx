import { useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { TrenTrackingSection } from "./components/TrenTrackingSection";
import { PorTrenesPage } from "./components/PorTrenesPage";
import { PorTiemposPage } from "./components/PorTiemposPage";
import { GlobalStatsPage } from "./components/GlobalStatsPage";
import type { AppSection } from "./types";

export default function App() {
  const [activeSection, setActiveSection] = useState<AppSection>("seguimiento");

  return (
    <div className="app-shell">
      <Sidebar activeSection={activeSection} onSelectSection={setActiveSection} />
      {activeSection === "seguimiento" && <TrenTrackingSection />}
      {activeSection === "estadisticas-trenes" && <PorTrenesPage />}
      {activeSection === "estadisticas-tiempos" && <PorTiemposPage />}
      {activeSection === "estadisticas-global" && <GlobalStatsPage />}
    </div>
  );
}
