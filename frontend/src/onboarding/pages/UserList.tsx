import { useEffect, useMemo, useState } from "react";
import apiClient from "../../shared/api/client";
import type { User } from "../../shared/types/user";
import UserCard from "../components/UserCard";

type Filter = "all" | "onboarded" | "pending";

export default function UserList() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    apiClient
      .get("/api/v1/onboarding/users")
      .then((res) => setUsers(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let result = users;

    if (filter === "onboarded") result = result.filter((u) => u.is_onboarded);
    if (filter === "pending") result = result.filter((u) => !u.is_onboarded);

    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (u) =>
          u.phone.toLowerCase().includes(q) ||
          (u.name && u.name.toLowerCase().includes(q))
      );
    }

    return result;
  }, [users, filter, search]);

  if (loading) return <div>Cargando...</div>;

  const filterButtons: { label: string; value: Filter }[] = [
    { label: "Todos", value: "all" },
    { label: "Onboarded", value: "onboarded" },
    { label: "Pendientes", value: "pending" },
  ];

  return (
    <div>
      <h1 style={{ marginBottom: "1rem" }}>Usuarios</h1>

      {/* Search + filter bar */}
      <div
        style={{
          display: "flex",
          gap: ".75rem",
          marginBottom: "1.25rem",
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <input
          type="text"
          placeholder="Buscar por nombre o telefono..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: ".5rem .75rem",
            borderRadius: "8px",
            border: "1px solid #e2e8f0",
            fontSize: ".9rem",
            flex: "1 1 200px",
            minWidth: 0,
          }}
        />
        <div style={{ display: "flex", gap: ".25rem" }}>
          {filterButtons.map((btn) => (
            <button
              key={btn.value}
              onClick={() => setFilter(btn.value)}
              style={{
                padding: ".5rem 1rem",
                borderRadius: "8px",
                border: "none",
                fontSize: ".85rem",
                fontWeight: 600,
                cursor: "pointer",
                background: filter === btn.value ? "#334155" : "#f1f5f9",
                color: filter === btn.value ? "#fff" : "#64748b",
              }}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>

      {/* User list */}
      <div style={{ display: "grid", gap: ".75rem" }}>
        {filtered.map((user) => (
          <UserCard key={user.id} user={user} />
        ))}
        {filtered.length === 0 && (
          <p style={{ color: "#94a3b8" }}>No se encontraron usuarios.</p>
        )}
      </div>
    </div>
  );
}
