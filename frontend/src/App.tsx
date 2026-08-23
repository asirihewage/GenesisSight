import { Route, Routes } from "react-router-dom";
import { Dashboard } from "@/pages/Dashboard";
import { Upload } from "@/pages/Upload";
import { VideoAnalysis } from "@/pages/VideoAnalysis";
import { Search } from "@/pages/Search";
import { Settings } from "@/pages/Settings";
import { People } from "@/pages/People";
import { About } from "@/pages/About";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/upload" element={<Upload />} />
      <Route path="/videos/:id" element={<VideoAnalysis />} />
      <Route path="/people" element={<People />} />
      <Route path="/search" element={<Search />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="/about" element={<About />} />
      <Route path="*" element={<Dashboard />} />
    </Routes>
  );
}
