interface DatePickerProps {
  value: string;
  maxDate: string;
  onChange: (dateIso: string) => void;
}

export function DatePicker({ value, maxDate, onChange }: DatePickerProps) {
  return (
    <label>
      Fecha
      <input
        type="date"
        value={value}
        max={maxDate}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
