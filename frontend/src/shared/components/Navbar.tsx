import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <nav style={{ padding: "1rem", borderBottom: "1px solid #ddd", display: "flex", gap: "1rem" }}>
      <Link to="/">Feed</Link>
      <Link to="/moderation">Moderacion</Link>
      <Link to="/admin">Admin</Link>
      <Link to="/admin/users">Usuarios</Link>
    </nav>
  );
}
