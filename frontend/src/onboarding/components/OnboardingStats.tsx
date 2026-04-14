interface Props {
  total: number;
  onboarded: number;
  pending: number;
  mlConnected: number;
}

export default function OnboardingStats({
  total,
  onboarded,
  pending,
  mlConnected,
}: Props) {
  const cards = [
    { label: "Total usuarios", value: total, bg: "#f1f5f9", color: "#334155" },
    { label: "Onboarded", value: onboarded, bg: "#dcfce7", color: "#166534" },
    { label: "Pendientes", value: pending, bg: "#fef9c3", color: "#854d0e" },
    { label: "ML Conectados", value: mlConnected, bg: "#dbeafe", color: "#1e40af" },
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "1rem" }}>
      {cards.map((c) => (
        <div
          key={c.label}
          style={{
            padding: "1.25rem",
            borderRadius: "12px",
            background: c.bg,
          }}
        >
          <p style={{ margin: 0, fontSize: ".85rem", color: "#64748b" }}>
            {c.label}
          </p>
          <p
            style={{
              margin: ".25rem 0 0",
              fontSize: "2rem",
              fontWeight: 700,
              color: c.color,
            }}
          >
            {c.value}
          </p>
        </div>
      ))}
    </div>
  );
}
