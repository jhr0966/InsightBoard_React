import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Board from "./pages/Board";
import Insights from "./pages/Insights";
import Proposals from "./pages/Proposals";
import Collect from "./pages/Collect";
import TaskDefs from "./pages/TaskDefs";

// 5 라우트 (REACT_MIGRATION_PLAN §4): 보드/인사이트/자동화제안/수집/작업정의.
export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Board />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/proposals" element={<Proposals />} />
        <Route path="/collect" element={<Collect />} />
        <Route path="/taskdefs" element={<TaskDefs />} />
      </Route>
    </Routes>
  );
}
