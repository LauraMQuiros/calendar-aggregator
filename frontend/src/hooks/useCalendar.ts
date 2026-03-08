import { useState, useCallback } from "react";

export function useCalendar() {
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1); // 1-12
  const [year, setYear] = useState(now.getFullYear());

  const prev = useCallback(() => {
    setMonth((m) => {
      if (m === 1) { setYear((y) => y - 1); return 12; }
      return m - 1;
    });
  }, []);

  const next = useCallback(() => {
    setMonth((m) => {
      if (m === 12) { setYear((y) => y + 1); return 1; }
      return m + 1;
    });
  }, []);

  const today = useCallback(() => {
    const n = new Date();
    setMonth(n.getMonth() + 1);
    setYear(n.getFullYear());
  }, []);

  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDayOfWeek = new Date(year, month - 1, 1).getDay(); // 0=Sun

  const monthName = new Date(year, month - 1).toLocaleString("default", { month: "long" });

  return { month, year, prev, next, today, daysInMonth, firstDayOfWeek, monthName };
}
