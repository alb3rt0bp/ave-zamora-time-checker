interface DatePickerProps {
  value: string;
  maxDate: string;
  onChange: (dateIso: string) => void;
}

export function DatePicker({ value, maxDate, onChange }: DatePickerProps) {
  return (
    <label className="date-field">
      {/* Etiqueta accesible pero visualmente oculta: el contexto (flechas de
          día anterior/siguiente a los lados) ya deja claro qué es este campo,
          igual que el botón de refrescar de TodayView usa solo aria-label. */}
      <span className="sr-only">Fecha</span>
      <input
        type="date"
        className="date-input"
        value={value}
        max={maxDate}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
