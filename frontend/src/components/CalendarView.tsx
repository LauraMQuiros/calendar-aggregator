import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type CalendarEvent } from "@/lib/api";
import { useCalendar } from "@/hooks/useCalendar";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { EventDetailModal } from "@/components/EventDetailModal";

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function CalendarView() {
  const cal = useCalendar();
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["calendar", cal.month, cal.year],
    queryFn: () => api.getEvents({ month: cal.month, year: cal.year }),
  });

  const events = data ?? [];

  // Group events by day
  const eventsByDay: Record<number, CalendarEvent[]> = {};
  for (const ev of events) {
    if (!ev.date) continue;
    const parts = ev.date.split("-");
    if (parts.length >= 3) {
      const day = parseInt(parts[2], 10);
      if (!eventsByDay[day]) eventsByDay[day] = [];
      eventsByDay[day].push(ev);
    }
  }

  const todayDate = new Date();
  const isCurrentMonth = todayDate.getMonth() + 1 === cal.month && todayDate.getFullYear() === cal.year;

  // Build grid cells
  const cells: (number | null)[] = [];
  for (let i = 0; i < cal.firstDayOfWeek; i++) cells.push(null);
  for (let d = 1; d <= cal.daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  return (
    <div className="flex-1 p-6 overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-primary">
          {cal.monthName} {cal.year}
        </h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={cal.today}>
            Today
          </Button>
          <Button variant="ghost" size="icon" onClick={cal.prev}>
            <ChevronLeft className="h-5 w-5" />
          </Button>
          <Button variant="ghost" size="icon" onClick={cal.next}>
            <ChevronRight className="h-5 w-5" />
          </Button>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin mr-2" /> Loading events…
        </div>
      )}

      {isError && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive mb-6">
          Failed to load calendar: {error instanceof Error ? error.message : "Unknown error"}
        </div>
      )}

      {/* Calendar Grid */}
      {!isLoading && (
        <div className="rounded-xl border border-border overflow-hidden shadow-[var(--shadow-card)]">
          {/* Day headers */}
          <div className="grid grid-cols-7 bg-muted">
            {DAY_NAMES.map((d) => (
              <div key={d} className="text-center text-xs font-semibold text-muted-foreground py-2.5 uppercase tracking-wider">
                {d}
              </div>
            ))}
          </div>

          {/* Day cells */}
          <div className="grid grid-cols-7">
            {cells.map((day, i) => {
              const isToday = isCurrentMonth && day === todayDate.getDate();
              const dayEvents = day ? eventsByDay[day] || [] : [];

              return (
                <div
                  key={i}
                  className={`min-h-[120px] border-t border-r border-border p-2 bg-card ${
                    day ? "hover:bg-accent/20 transition-colors" : "bg-muted/30"
                  } ${i % 7 === 0 ? "" : ""}`}
                >
                  {day && (
                    <>
                      <span
                        className={`text-sm inline-flex items-center justify-center w-7 h-7 rounded-full ${
                          isToday ? "bg-primary text-primary-foreground font-bold" : "text-foreground"
                        }`}
                      >
                        {day}
                      </span>
                      <div className="mt-1 space-y-0.5">
                        {dayEvents.slice(0, 3).map((ev) => (
                          <button
                            key={ev.id}
                            onClick={() => setSelectedEvent(ev)}
                            className="w-full text-left bg-primary text-primary-foreground px-1.5 py-0.5 rounded text-[10px] font-medium truncate hover:opacity-90 transition-opacity"
                          >
                            {ev.start_time && <span className="opacity-75">{ev.start_time} </span>}
                            {ev.title}
                          </button>
                        ))}
                        {dayEvents.length > 3 && (
                          <p className="text-[10px] text-muted-foreground pl-1">+{dayEvents.length - 3} more</p>
                        )}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Event count summary */}
      {!isLoading && (
        <p className="text-xs text-muted-foreground mt-4 text-right">
          {events.length} event{events.length !== 1 ? "s" : ""} this month
        </p>
      )}

      <EventDetailModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
