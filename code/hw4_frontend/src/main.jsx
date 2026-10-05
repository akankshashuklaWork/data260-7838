import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Provider, useDispatch, useSelector } from "react-redux";
import { api } from "./api/axios";
import { createListing, deleteListing, fetchListings, updateListing } from "./features/listings/listingsSlice";
import { store } from "./store/store";
import "./styles.css";

const blank = { listing_code: "", property_title: "", property_location: "", submitter_email: "", property_description: "", property_category: "Apartment", terms_accepted: true, available_units: 1, owner_id: "" };

function Login({ onLogin }) {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState("");
  const submit = async (event) => { event.preventDefault(); setError(""); try { const result = await api.post("/auth/login", { email, password }); onLogin(result.data); } catch (e) { setError(e.response?.data?.detail || "Login failed"); } };
  return <form className="login" onSubmit={submit}><strong>Login to HW5 rental listings</strong><input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required /><input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required /><button>Login</button>{error && <span className="error">{error}</span>}</form>;
}

function ListingForm({ owners, initial = blank, onSubmit, buttonText }) {
  const [form, setForm] = useState({ ...blank, ...initial });
  const change = (event) => { const { name, value } = event.target; setForm((old) => ({ ...old, [name]: ["available_units", "owner_id"].includes(name) ? Number(value) : value })); };
  return <form className="form" onSubmit={(e) => { e.preventDefault(); onSubmit(form); }}>
    {[['listing_code','Listing code'],['property_title','Title'],['property_location','Location'],['submitter_email','Submitter email']].map(([name,label]) => <label key={name}>{label}<input name={name} value={form[name] || ""} onChange={change} required /></label>)}
    <label>Category<select name="property_category" value={form.property_category} onChange={change}>{['Apartment','House','Condo','Townhouse'].map((v) => <option key={v}>{v}</option>)}</select></label>
    <label>Available units<input type="number" min="0" name="available_units" value={form.available_units} onChange={change} required /></label>
    <label>Owner<select name="owner_id" value={form.owner_id} onChange={change} required><option value="">Select owner</option>{owners.map((o) => <option key={o.id} value={o.id}>{o.id} — {o.first_name} {o.last_name}</option>)}</select></label>
    <label>Description<textarea name="property_description" minLength="26" value={form.property_description || ""} onChange={change} required /></label>
    <button>{buttonText}</button>
  </form>;
}

function Home({ owners }) {
  const dispatch = useDispatch(); const { items, loading, error } = useSelector((state) => state.listings);
  // Load the initial Home list once.  Later Create, Update, and Delete actions
  // already update Redux state, so returning Home does not replace that state.
  useEffect(() => { if (!items.length) dispatch(fetchListings()); }, [dispatch, items.length]);
  return <section className="panel"><div className="panel-heading"><div><h2>Home</h2><p>All rental listings from Redux state. Current records loaded: {items.length}.</p></div><button onClick={() => dispatch(fetchListings())}>Refresh</button></div>{loading && <p>Loading…</p>}{error && <p className="error">{error}</p>}<table><thead><tr><th>ID</th><th>Code</th><th>Title</th><th>Location</th><th>Owner</th><th>Units</th><th>Delete</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td>{item.id}</td><td>{item.listing_code}</td><td>{item.property_title}</td><td>{item.property_location}</td><td>{owners.find((o) => o.id === item.owner_id)?.email || item.owner_id}</td><td>{item.available_units}</td><td><button className="danger" onClick={() => dispatch(deleteListing(item.id))}>Delete</button></td></tr>)}{!items.length && !loading && <tr><td colSpan="7">No listings found.</td></tr>}</tbody></table></section>;
}

function App() {
  const [auth, setAuth] = useState(null); const [tab, setTab] = useState("home"); const [owners, setOwners] = useState([]); const [editId, setEditId] = useState(""); const [message, setMessage] = useState(""); const dispatch = useDispatch(); const items = useSelector((state) => state.listings.items);
  useEffect(() => { api.get("/auth/me").then((r) => setAuth(r.data)).catch(() => setAuth(null)); }, []);
  useEffect(() => { if (auth) api.get("/owners?skip=0&limit=200").then((r) => setOwners(r.data)); }, [auth]);
  const save = async (payload) => { setMessage(""); try { await dispatch(createListing(payload)).unwrap(); setMessage("Listing created."); setTab("home"); } catch (e) { setMessage(String(e)); } };
  const update = async (payload) => { try { await dispatch(updateListing({ id: Number(editId), payload })).unwrap(); setMessage("Listing updated."); setTab("home"); } catch (e) { setMessage(String(e)); } };
  if (!auth) return <main><h1>Rental Housing Listings HW5</h1><Login onLogin={setAuth} /></main>;
  const selected = items.find((item) => item.id === Number(editId)) || blank;
  return <main><header><h1>Rental Housing Listings</h1><span>{auth.email}</span><button onClick={async () => { await api.post("/auth/logout"); setAuth(null); }}>Logout</button></header><nav><button onClick={() => setTab("home")}>Home</button><button onClick={() => setTab("create")}>Create</button><button onClick={() => setTab("update")}>Update</button></nav>{message && <p className="notice">{message}</p>}{tab === "home" && <Home owners={owners} />}{tab === "create" && <ListingForm owners={owners} onSubmit={save} buttonText="Create listing" />}{tab === "update" && <section><label>Listing ID<input type="number" value={editId} onChange={(e) => setEditId(e.target.value)} /></label><ListingForm key={editId} owners={owners} initial={selected} onSubmit={update} buttonText="Update listing" /></section>}</main>;
}

createRoot(document.getElementById("root")).render(<Provider store={store}><App /></Provider>);
