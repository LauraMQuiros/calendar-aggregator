import { Sidebar } from "@/components/Sidebar";
import { CalendarView } from "@/components/CalendarView";

const Index = () => {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <CalendarView />
    </div>
  );
};

export default Index;
