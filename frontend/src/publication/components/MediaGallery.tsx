interface MediaItem {
  id: string;
  url: string;
  media_type: string;
}

interface Props {
  media: MediaItem[];
}

export default function MediaGallery({ media }: Props) {
  if (media.length === 0) return null;

  return (
    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
      {media.map((item) => (
        <img
          key={item.id}
          src={item.url}
          alt=""
          style={{ maxWidth: "200px", borderRadius: "8px", objectFit: "cover" }}
        />
      ))}
    </div>
  );
}
