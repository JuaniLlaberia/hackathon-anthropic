import { Link } from "react-router-dom";

interface Props {
  publication: {
    id: string;
    title: string;
    body: string;
    status: string;
    created_at: string;
  };
}

export default function PublicationCard({ publication }: Props) {
  return (
    <div style={{ padding: "1rem", border: "1px solid #eee", borderRadius: "8px" }}>
      <Link to={`/publication/${publication.id}`}>
        <h3>{publication.title}</h3>
      </Link>
      <p>{publication.body.substring(0, 150)}...</p>
      <small style={{ color: "#888" }}>
        {publication.status} | {new Date(publication.created_at).toLocaleDateString()}
      </small>
    </div>
  );
}
