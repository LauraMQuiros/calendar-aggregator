import { type CalendarEvent } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { MapPin, Clock, Globe, FileText } from "lucide-react";

interface Props {
  event: CalendarEvent | null;
  onClose: () => void;
}

export function EventDetailModal({ event, onClose }: Props) {
  if (!event) return null;

  return (
    <Dialog open={!!event} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-xl">{event.title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          {event.date && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Clock className="h-4 w-4 shrink-0" />
              <span>
                {event.date}
                {event.start_time && ` · ${event.start_time}`}
                {event.end_time && ` – ${event.end_time}`}
              </span>
            </div>
          )}
          {event.location && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <MapPin className="h-4 w-4 shrink-0" />
              <span>{event.location}</span>
            </div>
          )}
          {event.description && (
            <div className="flex items-start gap-2 text-muted-foreground">
              <FileText className="h-4 w-4 shrink-0 mt-0.5" />
              <p className="whitespace-pre-wrap">{event.description}</p>
            </div>
          )}
          {event.source_url && (
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4 shrink-0 text-muted-foreground" />
              <a
                href={event.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline truncate"
              >
                {event.source_url}
              </a>
            </div>
          )}
          {event.original_language && (
            <p className="text-xs text-muted-foreground">
              Original language: {event.original_language}
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
