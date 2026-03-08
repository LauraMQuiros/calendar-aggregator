import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/sonner";
import { Sidebar } from "@/components/Sidebar";
import { CalendarView } from "@/components/CalendarView";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex h-screen bg-background">
        <Sidebar />
        <main className="flex-1 flex flex-col min-w-0">
          <CalendarView />
        </main>
      </div>
      <Toaster />
    </QueryClientProvider>
  );
}
