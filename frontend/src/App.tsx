import { Routes, Route } from "react-router-dom";
import Layout from "./shared/components/Layout";

// Grupo A - Onboarding
import AdminDashboard from "./onboarding/pages/AdminDashboard";
import UserList from "./onboarding/pages/UserList";

// Grupo B - Publications
import Feed from "./publication/pages/Feed";
import PublicationDetail from "./publication/pages/PublicationDetail";
import ModerationPanel from "./publication/pages/ModerationPanel";

function App() {
  return (
    <Layout>
      <Routes>
        {/* Grupo A */}
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/admin/users" element={<UserList />} />

        {/* Grupo B */}
        <Route path="/" element={<Feed />} />
        <Route path="/publication/:id" element={<PublicationDetail />} />
        <Route path="/moderation" element={<ModerationPanel />} />
      </Routes>
    </Layout>
  );
}

export default App;
