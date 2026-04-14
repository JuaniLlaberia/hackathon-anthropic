import type { User } from "../../shared/types/user";

interface Props {
  user: User;
}

export default function UserCard({ user }: Props) {
  return (
    <div
      style={{
        padding: "1.25rem",
        border: "1px solid #e2e8f0",
        borderRadius: "12px",
        background: "#fff",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: "1rem",
      }}
    >
      <div style={{ flex: 1 }}>
        <h3 style={{ margin: "0 0 .25rem", fontSize: "1.1rem" }}>
          {user.name || "Sin nombre"}
        </h3>
        <p style={{ margin: 0, color: "#64748b", fontSize: ".9rem" }}>
          {user.phone} {user.email ? `· ${user.email}` : ""}
        </p>
      </div>
      <div style={{ display: "flex", gap: ".5rem", flexShrink: 0 }}>
        <span
          style={{
            padding: ".25rem .75rem",
            borderRadius: "9999px",
            fontSize: ".8rem",
            fontWeight: 600,
            background: user.is_onboarded ? "#dcfce7" : "#fef9c3",
            color: user.is_onboarded ? "#166534" : "#854d0e",
          }}
        >
          {user.is_onboarded ? "Onboarded" : "Pendiente"}
        </span>
        <span
          style={{
            padding: ".25rem .75rem",
            borderRadius: "9999px",
            fontSize: ".8rem",
            fontWeight: 600,
            background: user.ml_connected ? "#dbeafe" : "#f1f5f9",
            color: user.ml_connected ? "#1e40af" : "#64748b",
          }}
        >
          {user.ml_connected ? "ML Conectado" : "ML Pendiente"}
        </span>
      </div>
    </div>
  );
}
