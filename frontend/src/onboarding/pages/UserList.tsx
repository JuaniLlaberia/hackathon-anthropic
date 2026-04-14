import { useEffect, useState } from "react";
import apiClient from "../../shared/api/client";
import type { User } from "../../shared/types/user";
import UserCard from "../components/UserCard";

export default function UserList() {
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

  return (
    <div>
      <h1>Usuarios</h1>
      <div style={{ display: "grid", gap: "1rem" }}>
        {users.map((user) => (
          <UserCard key={user.id} user={user} />
        ))}
        {users.length === 0 && <p>No hay usuarios registrados.</p>}
      </div>
    </div>
  );
}
