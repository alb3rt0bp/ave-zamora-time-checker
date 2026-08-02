import { useState } from "react";
import { Clock } from "./components/Clock";
import { DatePicker } from "./components/DatePicker";
import { DayView } from "./components/DayView";
import { TodayView } from "./components/TodayView";
import { addDaysIso, yesterdayMadrid } from "./utils/dateLimits";

export default function App() {
  const [selectedDate, setSelectedDate] = useState("");
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
    <main>
      <Clock />
      <h1>Puntualidad de trenes en Zamora</h1>
      <button type="button" onClick={goToPreviousDay}>
        Día ant.
      </button>
      <DatePicker value={selectedDate} maxDate={maxDate} onChange={setSelectedDate} />
      <button type="button" onClick={goToNextDay} disabled={selectedDate === ""}>
        Día sig.
      </button>
      <button type="button" onClick={() => setSelectedDate("")}>
        Hoy
      </button>
      {selectedDate ? <DayView date={selectedDate} /> : <TodayView />}
    </main>
  );
}
