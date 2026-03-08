import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Website, type Folder } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, RefreshCw, FolderIcon, Globe, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

export function Sidebar() {
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [expandedFolders, setExpandedFolders] = useState<Set<number>>(new Set());

  const { data: websites = [], isLoading: sitesLoading } = useQuery({
    queryKey: ["websites"],
    queryFn: () => api.getWebsites(),
  });

  const { data: folders = [] } = useQuery({
    queryKey: ["folders"],
    queryFn: () => api.getFolders(),
  });

  const addSite = useMutation({
    mutationFn: api.createWebsite,
    onSuccess: () => {
      toast.success("Website added");
      qc.invalidateQueries({ queryKey: ["websites"] });
      setAddOpen(false);
      setUrl("");
      setName("");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteSite = useMutation({
    mutationFn: api.deleteWebsite,
    onSuccess: () => {
      toast.success("Website removed");
      qc.invalidateQueries({ queryKey: ["websites"] });
      qc.invalidateQueries({ queryKey: ["calendar"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const extract = useMutation({
    mutationFn: api.triggerExtraction,
    onSuccess: (data) => {
      toast.success(`Extracted ${data.events_extracted} events`);
      qc.invalidateQueries({ queryKey: ["calendar"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const toggleFolder = (id: number) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const statusColor = (s: string) => {
    switch (s) {
      case "active": return "text-green-500";
      case "inactive": return "text-muted-foreground";
      case "unreachable": return "text-orange-500";
      case "error": return "text-destructive";
      default: return "text-muted-foreground";
    }
  };

  const ungrouped = websites.filter((w) => !w.folder_id);
  const grouped = folders.map((f) => ({
    ...f,
    sites: websites.filter((w) => w.folder_id === f.id),
  }));

  return (
    <aside className="w-[380px] shrink-0 bg-card border-r border-border flex flex-col h-screen overflow-hidden">
      <div className="p-5 border-b border-border">
        <h2 className="text-lg font-bold text-primary flex items-center gap-2">
          <Globe className="h-5 w-5" /> Monitored Websites
        </h2>
      </div>

      {/* Toolbar */}
      <div className="p-3 flex gap-2 bg-accent/50 border-b border-border">
        <Dialog open={addOpen} onOpenChange={setAddOpen}>
          <DialogTrigger asChild>
            <Button size="sm" className="gap-1">
              <Plus className="h-4 w-4" /> Add Website
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Website to Monitor</DialogTitle>
            </DialogHeader>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!url.trim()) return;
                addSite.mutate({ url: url.trim(), name: name.trim() || undefined });
              }}
              className="space-y-4"
            >
              <div>
                <Label>URL</Label>
                <Input placeholder="https://example.com/events" value={url} onChange={(e) => setUrl(e.target.value)} />
              </div>
              <div>
                <Label>Name (optional)</Label>
                <Input placeholder="My Events Page" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <Button type="submit" disabled={addSite.isPending} className="w-full">
                {addSite.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Add Website
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Website list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {sitesLoading && (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin mr-2" /> Loading…
          </div>
        )}

        {grouped.map((folder) => (
          <div key={folder.id} className="rounded-lg border border-border overflow-hidden">
            <button
              onClick={() => toggleFolder(folder.id)}
              className="w-full flex items-center gap-2 px-3 py-2.5 bg-muted/50 hover:bg-muted transition-colors text-sm font-medium"
            >
              {expandedFolders.has(folder.id) ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              <FolderIcon className="h-4 w-4 text-primary" />
              {folder.name}
              <span className="ml-auto text-xs text-muted-foreground">{folder.sites.length}</span>
            </button>
            {expandedFolders.has(folder.id) && (
              <div>
                {folder.sites.map((w) => (
                  <WebsiteItem key={w.id} website={w} statusColor={statusColor} onDelete={deleteSite.mutate} onExtract={extract.mutate} />
                ))}
              </div>
            )}
          </div>
        ))}

        {ungrouped.map((w) => (
          <WebsiteItem key={w.id} website={w} statusColor={statusColor} onDelete={deleteSite.mutate} onExtract={extract.mutate} />
        ))}

        {!sitesLoading && websites.length === 0 && (
          <p className="text-center text-muted-foreground text-sm py-8">No websites yet. Add one to get started!</p>
        )}
      </div>
    </aside>
  );
}

function WebsiteItem({
  website,
  statusColor,
  onDelete,
  onExtract,
}: {
  website: Website;
  statusColor: (s: string) => string;
  onDelete: (id: number) => void;
  onExtract: (id: number) => void;
}) {
  return (
    <div className="flex items-center gap-2 px-3 py-2.5 border-b border-border last:border-0 hover:bg-accent/30 transition-colors group">
      <span className={`text-lg ${statusColor(website.status)}`}>●</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{website.name || website.url}</p>
        {website.name && <p className="text-xs text-muted-foreground truncate">{website.url}</p>}
      </div>
      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onExtract(website.id)} title="Extract events">
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => onDelete(website.id)} title="Remove">
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
