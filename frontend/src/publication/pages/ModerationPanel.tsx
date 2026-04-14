import { useEffect, useState } from "react";
import apiClient from "../../shared/api/client";
import PublicationCard from "../components/PublicationCard";

interface Publication {
  id: string;
  title: string;
  body: string;
  status: string;
  created_at: string;
  media: { id: string; url: string; media_type: string }[];
}

export default function ModerationPanel() {
  const [publications, setPublications] = useState<Publication[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchPending = () => {
    setLoading(true);
    apiClient
      .get("/api/v1/publications", { params: { status: "pending" } })
      .then((res) => setPublications(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchPending();
  }, []);

  const handleModerate = async (pubId: string, action: string) => {
    await apiClient.patch(`/api/v1/publications/${pubId}/status`, {
      action,
      reason: action === "reject" ? "Rechazado por moderador" : null,
    });
    fetchPending();
  };

  if (loading) return <div>Cargando...</div>;

  return (
    <div>
      <h1>Panel de Moderacion</h1>
      <div style={{ display: "grid", gap: "1rem" }}>
        {publications.map((pub) => (
          <div key={pub.id} style={{ border: "1px solid #ddd", borderRadius: "8px", padding: "1rem" }}>
            <PublicationCard publication={pub} />
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
              <button onClick={() => handleModerate(pub.id, "approve")} style={{ padding: "0.5rem 1rem", background: "#4caf50", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}>
                Aprobar
              </button>
              <button onClick={() => handleModerate(pub.id, "reject")} style={{ padding: "0.5rem 1rem", background: "#f44336", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}>
                Rechazar
              </button>
            </div>
          </div>
        ))}
        {publications.length === 0 && <p>No hay publicaciones pendientes.</p>}
      </div>
    </div>
  );
}
