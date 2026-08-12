import { useState } from "react";
import { ChevronLeftIcon, ChevronRightIcon } from "./icons";
import { Clock } from "./Clock";
import { DatePicker } from "./DatePicker";
import { DayView } from "./DayView";
import { TodayView } from "./TodayView";
import { useRenfeFlota } from "../hooks/useRenfeFlota";
import { addDaysIso, yesterdayMadrid } from "../utils/dateLimits";

// Contenido íntegro de la antigua vista principal de App.tsx (hoy/día +
// mapa en vivo), movido tal cual a su propia sección del menú lateral, sin
// cambios de comportamiento.
export function TrenTrackingSection() {
  const [selectedDate, setSelectedDate] = useState("");
  const flota = useRenfeFlota();
  const maxDate = yesterdayMadrid();
  // selectedDate === "" significa "hoy" (vista en vivo, sin fecha volcada
  // todavía); para calcular el día anterior necesitamos su equivalente ISO.
  const loadedDate = selectedDate || addDaysIso(maxDate, 1);

  function goToPreviousDay() {
    setSelectedDate(addDaysIso(loadedDate, -1));
  }

  function goToNextDay() {
    if (selectedDate === "") return; // ya estamos en el día más reciente posible
    // Desde el último día volcado (maxDate), el "siguiente" es hoy: vuelve a
    // la vista en vivo en vez de pedir /trains/{hoy}, que todavía no existe.
    setSelectedDate(selectedDate === maxDate ? "" : addDaysIso(selectedDate, 1));
  }

  return (
    <>
      <header className="app-header glass">
        <h1 className="app-title">Puntualidad de trenes en Zamora</h1>
        <Clock />
        <div className="date-toolbar">
          <div className="date-toolbar__nav glass">
            <button type="button" className="date-toolbar__step" onClick={goToPreviousDay}>
              <ChevronLeftIcon />
              <span className="date-toolbar__label">Día ant.</span>
            </button>
            <DatePicker value={selectedDate} maxDate={maxDate} onChange={setSelectedDate} />
            <button
              type="button"
              className="date-toolbar__step"
              onClick={goToNextDay}
              disabled={selectedDate === ""}
            >
              <span className="date-toolbar__label">Día sig.</span>
              <ChevronRightIcon />
            </button>
          </div>
          <button type="button" className="pill-button pill-button--accent" onClick={() => setSelectedDate("")}>
            Hoy
          </button>
        </div>
      </header>
      <main className="app-main">
        {selectedDate ? <DayView date={selectedDate} flota={flota} /> : <TodayView flota={flota} />}
      </main>
    </>
  );
}
