interface Category {
  id: string;
  name: string;
  slug: string;
}

interface Props {
  categories: Category[];
  selected: string | null;
  onSelect: (slug: string | null) => void;
}

export default function CategoryFilter({ categories, selected, onSelect }: Props) {
  return (
    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
      <button
        onClick={() => onSelect(null)}
        style={{
          padding: "0.5rem 1rem",
          border: "1px solid #ccc",
          borderRadius: "20px",
          background: selected === null ? "#333" : "white",
          color: selected === null ? "white" : "#333",
          cursor: "pointer",
        }}
      >
        Todas
      </button>
      {categories.map((cat) => (
        <button
          key={cat.id}
          onClick={() => onSelect(cat.slug)}
          style={{
            padding: "0.5rem 1rem",
            border: "1px solid #ccc",
            borderRadius: "20px",
            background: selected === cat.slug ? "#333" : "white",
            color: selected === cat.slug ? "white" : "#333",
            cursor: "pointer",
          }}
        >
          {cat.name}
        </button>
      ))}
    </div>
  );
}
