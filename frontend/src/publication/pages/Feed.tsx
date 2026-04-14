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

export default function Feed() {
  const [publications, setPublications] = useState<Publication[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get("/api/v1/publications", { params: { status: "approved" } })
      .then((res) => setPublications(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Cargando...</div>;

  return (
    <div>
      <h1>Feed</h1>
      <div style={{ display: "grid", gap: "1rem" }}>
        {publications.map((pub) => (
          <PublicationCard key={pub.id} publication={pub} />
        ))}
        {publications.length === 0 && <p>No hay publicaciones aprobadas.</p>}
      </div>
    </div>
  );
}
