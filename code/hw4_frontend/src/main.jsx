import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Link,
  Route,
  Routes,
  useNavigate,
  useParams,
} from "react-router-dom";
import axios from "axios";
import "./styles.css";

const api = axios.create({
  baseURL: "http://127.0.0.1:8638",
  withCredentials: true,
});

const emptyListing = {
  property_title: "",
  property_location: "",
  submitter_email: "",
  property_description: "",
  property_category: "Apartment",
  terms_accepted: true,
};

const textFields = [
  ["property_title", "Property title"],
  ["property_location", "Property location"],
  ["submitter_email", "Submitter email"],
];

const categories = ["Apartment", "House", "Condo", "Townhouse"];

function Login({ setAuth }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [registering, setRegistering] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    try {
      const credentials = { email, password };

      if (registering) {
        await api.post("/auth/register", {
          name: email.split("@")[0],
          ...credentials,
        });
      }

      const response = await api.post("/auth/login", credentials);
      setAuth(response.data);
      setEmail("");
      setPassword("");
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Request failed");
    }
  }

  return (
    <form className="login" onSubmit={handleSubmit}>
      <strong>{registering ? "Create account" : "Login"}</strong>
      <input
        placeholder="email"
        type="email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        required
      />
      <input
        placeholder="password"
        type="password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        required
      />
      <button>{registering ? "Register" : "Login"}</button>
      <button
        type="button"
        onClick={() => setRegistering((current) => !current)}
      >
        {registering ? "Use login" : "Register"}
      </button>
      {error && <span>{error}</span>}
    </form>
  );
}

function ListingForm({ initial = emptyListing, onSubmit, label }) {
  const [form, setForm] = useState(initial);

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    onSubmit(form);
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      {textFields.map(([field, labelText]) => (
        <label key={field}>
          {labelText}
          <input
            required
            value={form[field]}
            onChange={(event) => updateField(field, event.target.value)}
          />
        </label>
      ))}

      <label>
        Category
        <select
          value={form.property_category}
          onChange={(event) =>
            updateField("property_category", event.target.value)
          }
        >
          {categories.map((category) => (
            <option key={category}>{category}</option>
          ))}
        </select>
      </label>

      <label>
        Description
        <textarea
          required
          minLength="26"
          value={form.property_description}
          onChange={(event) =>
            updateField("property_description", event.target.value)
          }
        />
      </label>

      <button>{label}</button>
    </form>
  );
}

function ListingTable({ rows }) {
  return (
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Title</th>
          <th>Location</th>
          <th>Category</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((listing) => (
          <tr key={listing.id}>
            <td>{listing.id}</td>
            <td>{listing.property_title}</td>
            <td>{listing.property_location}</td>
            <td>{listing.property_category}</td>
            <td>
              <Link to={`/update/${listing.id}`}>Update</Link>{" "}
              <Link to={`/delete/${listing.id}`}>Delete</Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function App() {
  const [auth, setAuth] = useState(null);
  const [rows, setRows] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .get("/auth/me")
      .then((response) => setAuth(response.data))
      .catch(() => setAuth(null));
  }, []);

  useEffect(() => {
    if (auth) {
      api.get("/listings").then((response) => setRows(response.data));
    }
  }, [auth]);

  async function logout() {
    await api.post("/auth/logout");
    setAuth(null);
    setRows([]);
    navigate("/");
  }

  async function createListing(data) {
    const response = await api.post("/listings", data);
    setRows((current) => [...current, response.data]);
    navigate("/");
  }

  async function updateListing(id, data) {
    const response = await api.put(`/listings/${id}`, data);
    setRows((current) =>
      current.map((listing) => (listing.id === id ? response.data : listing)),
    );
    navigate("/");
  }

  async function deleteListing(id) {
    await api.delete(`/listings/${id}`);
    setRows((current) => current.filter((listing) => listing.id !== id));
    navigate("/");
  }

  return (
    <main>
      <header>
        <Link to="/">Rental Housing Listings</Link>
        {auth ? (
          <>
            <Link to="/create">Add record</Link>
            <button onClick={logout}>Logout</button>
          </>
        ) : (
          <span>Login required for records</span>
        )}
      </header>

      <Login setAuth={setAuth} />

      <Routes>
        <Route
          path="/"
          element={auth ? <ListingTable rows={rows} /> : <h2>Login required</h2>}
        />
        <Route
          path="/create"
          element={
            auth ? (
              <ListingForm label="Add listing" onSubmit={createListing} />
            ) : (
              <h2>Login required</h2>
            )
          }
        />
        <Route
          path="/update/:id"
          element={
            auth ? (
              <Edit rows={rows} onSubmit={updateListing} />
            ) : (
              <h2>Login required</h2>
            )
          }
        />
        <Route
          path="/delete/:id"
          element={
            auth ? (
              <Delete rows={rows} onDelete={deleteListing} />
            ) : (
              <h2>Login required</h2>
            )
          }
        />
      </Routes>
    </main>
  );
}

function Edit({ rows, onSubmit }) {
  const { id } = useParams();
  const listing = rows.find((row) => row.id === Number(id));

  if (!listing) {
    return <h2>Loading record...</h2>;
  }

  return (
    <ListingForm
      initial={listing}
      label="Update listing"
      onSubmit={(data) => onSubmit(Number(id), data)}
    />
  );
}

function Delete({ rows, onDelete }) {
  const { id } = useParams();
  const listing = rows.find((row) => row.id === Number(id));

  if (!listing) {
    return <h2>Loading record...</h2>;
  }

  return (
    <section>
      <h2>Delete {listing.property_title}?</h2>
      <button onClick={() => onDelete(Number(id))}>Delete listing</button>
    </section>
  );
}

createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>,
);
