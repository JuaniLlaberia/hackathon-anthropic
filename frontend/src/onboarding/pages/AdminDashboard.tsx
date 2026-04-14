import { useEffect, useState } from "react";
import apiClient from "../../shared/api/client";
import type { User } from "../../shared/types/user";

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

  return (
    <div>
      <h1>Admin Dashboard</h1>
      <div style={{ display: "flex", gap: "2rem", marginBottom: "2rem" }}>
        <div style={{ padding: "1rem", border: "1px solid #ccc", borderRadius: "8px" }}>
          <h3>Total usuarios</h3>
          <p style={{ fontSize: "2rem" }}>{users.length}</p>
        </div>
        <div style={{ padding: "1rem", border: "1px solid #ccc", borderRadius: "8px" }}>
          <h3>Onboarded</h3>
          <p style={{ fontSize: "2rem" }}>{onboarded}</p>
        </div>
        <div style={{ padding: "1rem", border: "1px solid #ccc", borderRadius: "8px" }}>
          <h3>Pendientes</h3>
          <p style={{ fontSize: "2rem" }}>{pending}</p>
        </div>
      </div>
    </div>
  );
}
