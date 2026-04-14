interface Props {
  total: number;
  onboarded: number;
  pending: number;
}

export default function OnboardingStats({ total, onboarded, pending }: Props) {
  return (
    <div style={{ display: "flex", gap: "2rem" }}>
      <div>
        <strong>Total:</strong> {total}
      </div>
      <div>
        <strong>Completados:</strong> {onboarded}
      </div>
      <div>
        <strong>Pendientes:</strong> {pending}
      </div>
    </div>
  );
}
