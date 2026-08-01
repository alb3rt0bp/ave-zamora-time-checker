import { useState } from "react";
import { DatePicker } from "./components/DatePicker";
import { DayView } from "./components/DayView";
import { TodayView } from "./components/TodayView";
import { yesterdayMadrid } from "./utils/dateLimits";

export default function App() {
  const [selectedDate, setSelectedDate] = useState("");
  const maxDate = yesterdayMadrid();

  return (
    <main>
      <h1>Puntualidad de trenes en Zamora</h1>
      <DatePicker value={selectedDate} maxDate={maxDate} onChange={setSelectedDate} />
      {selectedDate ? <DayView date={selectedDate} /> : <TodayView />}
    </main>
  );
}
