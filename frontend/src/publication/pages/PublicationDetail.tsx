import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import apiClient from "../../shared/api/client";

interface Publication {
  id: string;
  title: string;
  body: string;
  status: string;
  created_at: string;
  media: { id: string; url: string; media_type: string }[];
}

export default function PublicationDetail() {
  const { id } = useParams<{ id: string }>();
  const [publication, setPublication] = useState<Publication | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get(`/api/v1/publications/${id}`)
      .then((res) => setPublication(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div>Cargando...</div>;
  if (!publication) return <div>Publicacion no encontrada.</div>;

  return (
    <div>
      <h1>{publication.title}</h1>
      <p style={{ color: "#666" }}>Estado: {publication.status}</p>
      <p>{publication.body}</p>
      {publication.media.length > 0 && (
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {publication.media.map((m) => (
            <img key={m.id} src={m.url} alt="" style={{ maxWidth: "300px", borderRadius: "8px" }} />
          ))}
        </div>
      )}
    </div>
  );
}
