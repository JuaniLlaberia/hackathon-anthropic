import type { User } from "../../shared/types/user";

interface Props {
  user: User;
}

export default function UserCard({ user }: Props) {
  return (
    <div style={{ padding: "1rem", border: "1px solid #ddd", borderRadius: "8px" }}>
      <h3>{user.name || "Sin nombre"}</h3>
      <p>Tel: {user.phone}</p>
      <p>Email: {user.email || "-"}</p>
      <p>Estado: {user.is_onboarded ? "Onboarded" : "Pendiente"}</p>
      <p>Rol: {user.role}</p>
    </div>
  );
}
