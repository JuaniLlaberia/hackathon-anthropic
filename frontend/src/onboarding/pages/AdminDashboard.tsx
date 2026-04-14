import { useEffect, useState } from "react";
import apiClient from "../../shared/api/client";
import type { User } from "../../shared/types/user";
import OnboardingStats from "../components/OnboardingStats";

export default function AdminDashboard() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get("/api/v1/onboarding/users")
      .then((res) => setUsers(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Cargando...</div>;

  const onboarded = users.filter((u) => u.is_onboarded).length;
  const pending = users.filter((u) => !u.is_onboarded).length;
  const mlConnected = users.filter((u) => u.ml_connected).length;

  return (
    <div>
      <h1 style={{ marginBottom: "1.5rem" }}>Admin Dashboard</h1>
      <OnboardingStats
        total={users.length}
        onboarded={onboarded}
        pending={pending}
        mlConnected={mlConnected}
      />
    </div>
  );
}
