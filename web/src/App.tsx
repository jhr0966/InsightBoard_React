import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Board from "./pages/Board";
import Insights from "./pages/Insights";
import Proposals from "./pages/Proposals";
import Collect from "./pages/Collect";
import Feed from "./pages/Feed";
import TaskDefs from "./pages/TaskDefs";
import PersonaPage from "./pages/Persona";

// Step 11 IA: 오늘(보드)/뉴스 탐색(feed)/자동화 과제/분석실 + 관리(수집·작업정의).
export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Board />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/proposals" element={<Proposals />} />
        <Route path="/feed" element={<Feed />} />
        <Route path="/collect" element={<Collect />} />
        <Route path="/taskdefs" element={<TaskDefs />} />
        <Route path="/persona" element={<PersonaPage />} />
      </Route>
    </Routes>
  );
}
